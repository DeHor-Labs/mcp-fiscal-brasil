"""
Helpers compartilhados para chamadas SOAP com mTLS aos webservices SEFAZ.

Usado por distribuicao.py (NFeDistribuicaoDFe, NFeRecepcaoEvento) e
status_sefaz.py (NfeStatusServico4). Centraliza carregamento de certificado
A1 (.pfx/.p12), montagem do SSLContext e envio do envelope SOAP.

SEGURANCA:
- Senha do .pfx e chave privada NUNCA aparecem em logs, excecoes ou disco
  persistente.
- Arquivos PEM temporarios sao criados com permissao 0600 e apagados no
  bloco finally.
"""

from __future__ import annotations

import os
import re
import ssl
import tempfile

import httpx
from lxml import etree

from .._core.config import settings
from .._core.errors import (
    FiscalConfigurationError,
    FiscalHTTPError,
    FiscalValidationError,
)
from ..shared.rate_limiter import SlidingWindowRateLimiter
from ..shared.xml_utils import build_soap_envelope, extract_soap_body

# Rate limiter conservador para endpoints SEFAZ (~1 req/s por endpoint), para
# nao misturar cotas entre distribuicao, eventos e status.
sefaz_rate_limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=1.0)

_CNPJ_DIGITS_RE = re.compile(r"\D")


def _validar_emitente_cnpj(cert_pem: bytes) -> None:
    """
    Confere que o certificado carregado pertence ao NFE_EMITENTE_CNPJ configurado.

    Nao faz nada se NFE_EMITENTE_CNPJ nao estiver configurado (opt-in: tools que
    recebem caminho_certificado/senha diretamente por parametro continuam
    funcionando sem essa variavel, comportamento legado preservado).

    Raises:
        FiscalConfigurationError: se NFE_EMITENTE_CNPJ estiver configurado e o
            certificado carregado pertencer a outro CNPJ.
    """
    esperado = _CNPJ_DIGITS_RE.sub("", settings.nfe_emitente_cnpj or "")
    if not esperado:
        return

    from cryptography import x509

    from .assinatura import _extrair_cn, _extrair_cnpj_cpf

    cert = x509.load_pem_x509_certificate(cert_pem)
    cnpj_certificado = _extrair_cnpj_cpf(_extrair_cn(cert))

    if cnpj_certificado != esperado:
        raise FiscalConfigurationError(
            message=(
                "O certificado carregado nao corresponde ao NFE_EMITENTE_CNPJ "
                "configurado. Confira se o arquivo montado e o CNPJ esperado "
                "sao do mesmo titular."
            )
        )


def carregar_pkcs12(
    caminho_certificado: str,
    senha: str,
) -> tuple[bytes, bytes, list[bytes]]:
    """
    Carrega um arquivo PKCS12 (.pfx/.p12) e retorna (chave_pem, cert_pem, chain_pem).

    SEGURANCA: a senha NAO e logada nem incluida em mensagens de excecao.

    Raises:
        FiscalValidationError: caminho invalido, senha incorreta ou certificado corrompido.
        FiscalConfigurationError: NFE_EMITENTE_CNPJ configurado e divergente do
            CNPJ do certificado carregado.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        with open(caminho_certificado, "rb") as f:
            pfx_data = f.read()
    except OSError as exc:
        raise FiscalValidationError(
            message=f"Nao foi possivel abrir o certificado: {exc.strerror}. Verifique o caminho.",
            field="caminho_certificado",
            value=caminho_certificado,
        ) from exc

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data, senha.encode("utf-8")
        )
    except Exception as exc:
        exc_str = str(exc)
        if "password" in exc_str.lower() or "senha" in exc_str.lower():
            motivo = "Senha incorreta ou certificado corrompido."
        else:
            motivo = f"Erro ao carregar certificado PKCS12: {exc.__class__.__name__}"
        raise FiscalValidationError(
            message=motivo,
            field="caminho_certificado",
            value=caminho_certificado,
        ) from exc

    if private_key is None or certificate is None:
        raise FiscalValidationError(
            message="Certificado ou chave privada ausente no arquivo PKCS12.",
            field="caminho_certificado",
            value=caminho_certificado,
        )

    chave_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    chain_pem = [c.public_bytes(serialization.Encoding.PEM) for c in additional_certs or []]

    _validar_emitente_cnpj(cert_pem)

    return chave_pem, cert_pem, chain_pem


def _escrever_pem_atomico(suffix: str, conteudo: bytes) -> str:
    """
    Cria um arquivo PEM temporario com permissao 0600 de forma atomica.

    Usa tempfile.mkstemp(), que cria o arquivo atomicamente com permissao 0600
    (sem janela de exposicao em 0644). Retorna o caminho do arquivo criado;
    o chamador e responsavel por apagar o arquivo no bloco finally.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, conteudo)
    finally:
        os.close(fd)
    return path


def criar_ssl_context_em_memoria(
    chave_pem: bytes,
    cert_pem: bytes,
    chain_pem: list[bytes],
) -> ssl.SSLContext:
    """
    Monta um ssl.SSLContext usando arquivos PEM temporarios com permissao 0600.

    Usa ssl.create_default_context() - forma recomendada pela stdlib para
    validacao de certificado (CERT_REQUIRED + check_hostname habilitados e
    CAs do sistema carregadas), em vez de instanciar SSLContext manualmente
    e setar os atributos de seguranca um a um. Sobre esse contexto e
    carregado o certificado de cliente (mTLS) via load_cert_chain().

    Os arquivos sao criados via tempfile.mkstemp() (_escrever_pem_atomico),
    que abre o arquivo atomicamente (O_CREAT|O_EXCL) ja com permissao
    restrita 0600, sem janela de exposicao com permissao mais aberta. Sao
    apagados no bloco finally. A chave privada nunca e logada.
    """
    ctx = ssl.create_default_context()

    tmp_key: str | None = None
    tmp_cert: str | None = None

    try:
        tmp_key = _escrever_pem_atomico("_key.pem", chave_pem)
        tmp_cert = _escrever_pem_atomico("_cert.pem", cert_pem + b"".join(chain_pem))

        ctx.load_cert_chain(certfile=tmp_cert, keyfile=tmp_key)
    finally:
        if tmp_key and os.path.exists(tmp_key):
            os.unlink(tmp_key)
        if tmp_cert and os.path.exists(tmp_cert):
            os.unlink(tmp_cert)

    return ctx


async def enviar_soap(
    url: str,
    soap_body_content: str,
    ssl_ctx: ssl.SSLContext,
    namespace: str,
    timeout: float = 30.0,
) -> etree._Element:
    """Envia requisicao SOAP via mTLS e retorna o elemento Body da resposta.

    Rate limit: maximo 1 req/s por endpoint SEFAZ (conservador para evitar
    bloqueio por flood). O limitador e aplicado por URL de endpoint.
    """
    await sefaz_rate_limiter.acquire(url)

    envelope = build_soap_envelope(soap_body_content, namespace=namespace)

    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": "",
    }

    try:
        async with httpx.AsyncClient(verify=ssl_ctx, timeout=timeout) as client:
            response = await client.post(url, content=envelope.encode("utf-8"), headers=headers)
    except httpx.RequestError as exc:
        raise FiscalHTTPError(
            message=f"Falha de conexao com a SEFAZ: {exc.__class__.__name__}",
            status_code=0,
            url=url,
        ) from exc

    if response.status_code != 200:
        raise FiscalHTTPError(
            message=f"SEFAZ retornou HTTP {response.status_code}",
            status_code=response.status_code,
            url=url,
        )

    return extract_soap_body(response.text)


__all__ = [
    "carregar_pkcs12",
    "criar_ssl_context_em_memoria",
    "enviar_soap",
    "sefaz_rate_limiter",
]
