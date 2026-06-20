"""
Distribuicao de NF-e via NFeDistribuicaoDFe (Ambiente Nacional, mTLS A1).

Suporta os tres modos:
- distNSU: busca incremental por ultimo NSU
- consNSU: consulta por NSU especifico
- consChNFe: consulta por chave de acesso de 44 digitos

Tambem oferece manifestacao do destinatario (eventos 210200/210210/210220/210240).

SEGURANCA:
- Senha do .pfx e chave privada NUNCA aparecem em logs, excecoes ou disco persistente.
- Arquivos PEM temporarios (quando necessarios) sao criados com permissao 0600
  e apagados no bloco finally.
- XML externo sempre parseado via parse_xml() (anti-XXE).
"""

from __future__ import annotations

import base64
import gzip
import os
import re
import ssl
import tempfile
import xml.sax.saxutils
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

import httpx
from lxml import etree
from signxml import XMLSigner  # type: ignore[attr-defined]

from .._core.errors import FiscalHTTPError, FiscalValidationError
from .._core.logging import get_logger
from ..shared.rate_limiter import SlidingWindowRateLimiter
from ..shared.validators import validate_chave_nfe
from ..shared.xml_utils import build_soap_envelope, extract_soap_body, parse_xml
from .xml_parser import parse_nfe_xml

if TYPE_CHECKING:
    from .schemas import NFeResponse

logger = get_logger(__name__)

# Rate limiter conservador para endpoints SEFAZ (~1 req/s).
# Distribui a cota por chave de endpoint para nao misturar
# distribuicao e recepcao de eventos.
_sefaz_nfe_limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=1.0)

# Tipo de ambiente SEFAZ
Ambiente = Literal["producao", "homologacao"]

# Codigos de evento de manifestacao do destinatario
EVENTO_CIENCIA = "210200"
EVENTO_CONFIRMACAO = "210210"
EVENTO_DESCONHECIMENTO = "210220"
EVENTO_OPERACAO_NAO_REALIZADA = "210240"

_EVENTOS_VALIDOS = {
    EVENTO_CIENCIA,
    EVENTO_CONFIRMACAO,
    EVENTO_DESCONHECIMENTO,
    EVENTO_OPERACAO_NAO_REALIZADA,
}

# Endpoints NFeDistribuicaoDFe
_ENDPOINTS_DISTRIBUICAO: dict[Ambiente, str] = {
    "producao": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
    "homologacao": "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
}

# Endpoints NFeRecepcaoEvento (Ambiente Nacional - AN)
_ENDPOINTS_EVENTO: dict[Ambiente, str] = {
    "producao": "https://www.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx",
    "homologacao": "https://hom.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx",
}

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"
_NS_DS = "http://www.w3.org/2000/09/xmldsig#"

# Regex: CNPJ 14 digitos numericos ou CPF 11 digitos numericos
_CNPJ_RE = re.compile(r"^\d{14}$")
_CPF_RE = re.compile(r"^\d{11}$")
_NSU_RE = re.compile(r"^\d{1,15}$")

# Mapeamento simplificado UF sigla -> codigo numerico IBGE
_UF_CODIGOS: dict[str, str] = {
    "AC": "12",
    "AL": "27",
    "AM": "13",
    "AP": "16",
    "BA": "29",
    "CE": "23",
    "DF": "53",
    "ES": "32",
    "GO": "52",
    "MA": "21",
    "MG": "31",
    "MS": "50",
    "MT": "51",
    "PA": "15",
    "PB": "25",
    "PE": "26",
    "PI": "22",
    "PR": "41",
    "RJ": "33",
    "RN": "24",
    "RO": "11",
    "RR": "14",
    "RS": "43",
    "SC": "42",
    "SE": "28",
    "SP": "35",
    "TO": "17",
}


# ---------------------------------------------------------------------------
# Schemas de retorno
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentoDistribuicao:
    """Documento retornado pela consulta de distribuicao NF-e."""

    nsu: str
    """Numero Sequencial Unico do documento."""

    tipo: str
    """Tipo do schema: resNFe (resumo), procNFe ou nfeProc (completo), etc."""

    schema: str
    """Nome do schema (ex: resNFe_v1.01.xsd, procNFe_v4.00.xsd)."""

    chave: str | None
    """Chave de acesso de 44 digitos, se disponivel no documento."""

    resumo: dict[str, str | None] | None
    """Campos principais do resNFe (emitente, valor, situacao), se for resumo.

    O campo 'situacao' corresponde a cSitNFe da SEFAZ e pode ser None quando o
    resNFe nao trouxer esse elemento (nao confundir com digVal, que e o digest).
    """

    dados_completos: NFeResponse | None
    """NFeResponse parseado via parse_nfe_xml, se for procNFe/nfeProc."""


@dataclass(frozen=True)
class DistribuicaoResult:
    """Resultado de uma consulta NFeDistribuicaoDFe."""

    ultimo_nsu: str
    """Ultimo NSU retornado pela SEFAZ nesta consulta."""

    max_nsu: str
    """Maior NSU disponivel para o ator consultante."""

    documentos: list[DocumentoDistribuicao]
    """Lista de documentos retornados."""


@dataclass(frozen=True)
class ManifestacaoResult:
    """Resultado de uma manifestacao do destinatario."""

    sucesso: bool
    """True se o evento foi recebido pela SEFAZ com sucesso."""

    chave: str
    """Chave de acesso da NF-e manifestada."""

    tipo_evento: str
    """Codigo do evento (ex: 210200)."""

    numero_protocolo: str | None
    """Numero do protocolo retornado pela SEFAZ."""

    codigo_retorno: str | None
    """cStat retornado pela SEFAZ (135 = sucesso)."""

    motivo: str | None
    """xMotivo retornado pela SEFAZ."""


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


def _validar_cnpj_cpf(valor: str, campo: str) -> str:
    """Valida e normaliza CNPJ (14 dig) ou CPF (11 dig). Lanca FiscalValidationError."""
    digitos = _somente_digitos(valor)
    if _CNPJ_RE.match(digitos) or _CPF_RE.match(digitos):
        return digitos
    raise FiscalValidationError(
        message=f"O campo '{campo}' deve ser um CNPJ (14 digitos) ou CPF (11 digitos) numerico. Recebido: {valor!r}",
        field=campo,
        value=valor,
    )


def _validar_nsu(nsu: str | int, campo: str = "nsu") -> str:
    """Valida e normaliza NSU (1-15 digitos numericos). Lanca FiscalValidationError."""
    nsu_str = str(nsu).strip()
    if not _NSU_RE.match(nsu_str):
        raise FiscalValidationError(
            message=f"NSU invalido: '{nsu_str}'. Deve conter apenas digitos (max 15).",
            field=campo,
            value=nsu_str,
        )
    return nsu_str.zfill(15)


def _validar_chave(chave: str) -> str:
    """Valida chave de acesso de 44 digitos. Lanca FiscalValidationError."""
    chave_limpa = _somente_digitos(chave)
    if not validate_chave_nfe(chave_limpa):
        raise FiscalValidationError(
            message=f"Chave de acesso invalida (44 digitos, modulo 11). Recebido: {chave!r}",
            field="chave",
            value=chave,
        )
    return chave_limpa


def _carregar_pkcs12(
    caminho_certificado: str,
    senha: str,
) -> tuple[bytes, bytes, list[bytes]]:
    """
    Carrega um arquivo PKCS12 (.pfx/.p12) e retorna (chave_pem, cert_pem, chain_pem).

    SEGURANCA: a senha NAO e logada nem incluida em mensagens de excecao.
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
        # Evitar vazar a senha na mensagem
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
    chain_pem = []
    for c in additional_certs or []:
        chain_pem.append(c.public_bytes(serialization.Encoding.PEM))

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


def _criar_ssl_context_em_memoria(
    chave_pem: bytes,
    cert_pem: bytes,
    chain_pem: list[bytes],
) -> ssl.SSLContext:
    """
    Monta um ssl.SSLContext usando arquivos PEM temporarios com permissao 0600.

    Os arquivos sao criados com os.open (O_CREAT|O_WRONLY|O_EXCL, 0o600)
    para que ja nascam com a permissao restrita, sem janela 0644. Sao
    apagados no bloco finally. A chave privada nunca e logada.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_default_certs()

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


def _descompactar_doc_zip(doc_zip_b64: str) -> bytes:
    """Descompacta um docZip (base64 + gzip) retornado pela SEFAZ."""
    compressed = base64.b64decode(doc_zip_b64.strip())
    return gzip.decompress(compressed)


def _extrair_chave_xml(root: etree._Element) -> str | None:
    """Tenta extrair a chave de acesso de 44 digitos do XML."""
    ns = {"nfe": _NS_NFE}
    candidates = [
        ".//nfe:infNFe/@Id",
        ".//nfe:chNFe/text()",
        ".//nfe:chNFe",
    ]
    for xpath in candidates:
        vals = root.xpath(xpath, namespaces=ns)
        if vals:
            raw = str(vals[0]).strip()
            digitos = _somente_digitos(raw)
            if len(digitos) == 44:
                return digitos
    return None


def _extrair_resumo_resnfe(root: etree._Element) -> dict[str, str | None]:
    """Extrai campos principais de um documento resNFe."""
    ns = {"nfe": _NS_NFE}

    def _txt(xpath: str) -> str:
        vals = root.xpath(xpath, namespaces=ns)
        return str(vals[0]).strip() if vals else ""

    def _txt_or_none(xpath: str) -> str | None:
        vals = root.xpath(xpath, namespaces=ns)
        return str(vals[0]).strip() if vals else None

    return {
        "chave": _txt(".//nfe:chNFe/text()"),
        "emitente_cnpj": _txt(".//nfe:CNPJ/text()"),
        "emitente_nome": _txt(".//nfe:xNome/text()"),
        "valor_nf": _txt(".//nfe:vNF/text()"),
        # cSitNFe e o campo correto para situacao da NF-e no resNFe;
        # digVal e o digest do documento e NAO deve ser retornado aqui.
        "situacao": _txt_or_none(".//nfe:cSitNFe/text()"),
        "data_autorizacao": _txt(".//nfe:dhRecbto/text()"),
        "tipo_nf": _txt(".//nfe:tpNF/text()"),
    }


def _parse_documento(nsu: str, doc_xml_bytes: bytes, schema_name: str) -> DocumentoDistribuicao:
    """Parseia um documento retornado pela SEFAZ e monta DocumentoDistribuicao."""
    try:
        root = parse_xml(doc_xml_bytes)
    except Exception:
        return DocumentoDistribuicao(
            nsu=nsu,
            tipo="desconhecido",
            schema=schema_name,
            chave=None,
            resumo=None,
            dados_completos=None,
        )

    chave = _extrair_chave_xml(root)
    schema_lower = schema_name.lower()

    # Tipos de documento completo (contem a NF-e autenticada)
    if any(t in schema_lower for t in ("procnfe", "nfeproc")):
        dados_completos = None
        if chave:
            try:
                dados_completos = parse_nfe_xml(doc_xml_bytes, chave)
            except Exception:
                pass
        return DocumentoDistribuicao(
            nsu=nsu,
            tipo="procNFe",
            schema=schema_name,
            chave=chave,
            resumo=None,
            dados_completos=dados_completos,
        )

    # resNFe: resumo
    if "resnfe" in schema_lower:
        resumo = _extrair_resumo_resnfe(root)
        return DocumentoDistribuicao(
            nsu=nsu,
            tipo="resNFe",
            schema=schema_name,
            chave=chave or resumo.get("chave") or None,
            resumo=resumo,
            dados_completos=None,
        )

    return DocumentoDistribuicao(
        nsu=nsu,
        tipo=schema_name,
        schema=schema_name,
        chave=chave,
        resumo=None,
        dados_completos=None,
    )


def _construir_body_dist_nsu(
    cnpj_cpf: str,
    uf_autor: str,
    ultimo_nsu: str,
) -> str:
    """Monta o corpo SOAP para distNSU (distribuicao incremental por ultimo NSU)."""
    tipo = "CNPJ" if len(cnpj_cpf) == 14 else "CPF"
    uf_autor_esc = xml.sax.saxutils.escape(uf_autor)
    return (
        f'<nfeDistDFeInt xmlns="{_NS_NFE}" versao="1.01">'
        f"<tpAmb>1</tpAmb>"
        f"<cUFAutor>{uf_autor_esc}</cUFAutor>"
        f"<{tipo}>{cnpj_cpf}</{tipo}>"
        f"<distNSU>"
        f"<ultNSU>{ultimo_nsu}</ultNSU>"
        f"</distNSU>"
        f"</nfeDistDFeInt>"
    )


def _construir_body_cons_nsu(
    cnpj_cpf: str,
    uf_autor: str,
    nsu: str,
) -> str:
    """Monta o corpo SOAP para consNSU (consulta por NSU especifico)."""
    tipo = "CNPJ" if len(cnpj_cpf) == 14 else "CPF"
    uf_autor_esc = xml.sax.saxutils.escape(uf_autor)
    return (
        f'<nfeDistDFeInt xmlns="{_NS_NFE}" versao="1.01">'
        f"<tpAmb>1</tpAmb>"
        f"<cUFAutor>{uf_autor_esc}</cUFAutor>"
        f"<{tipo}>{cnpj_cpf}</{tipo}>"
        f"<consNSU>"
        f"<NSU>{nsu}</NSU>"
        f"</consNSU>"
        f"</nfeDistDFeInt>"
    )


def _construir_body_cons_ch_nfe(
    cnpj_cpf: str,
    uf_autor: str,
    chave: str,
) -> str:
    """Monta o corpo SOAP para consChNFe (consulta por chave de 44 digitos)."""
    tipo = "CNPJ" if len(cnpj_cpf) == 14 else "CPF"
    uf_autor_esc = xml.sax.saxutils.escape(uf_autor)
    return (
        f'<nfeDistDFeInt xmlns="{_NS_NFE}" versao="1.01">'
        f"<tpAmb>1</tpAmb>"
        f"<cUFAutor>{uf_autor_esc}</cUFAutor>"
        f"<{tipo}>{cnpj_cpf}</{tipo}>"
        f"<consChNFe>"
        f"<chNFe>{chave}</chNFe>"
        f"</consChNFe>"
        f"</nfeDistDFeInt>"
    )


def _parse_retorno_dist(body_el: etree._Element) -> DistribuicaoResult:
    """Parseia o elemento retDistDFeInt e retorna DistribuicaoResult."""
    ns = {"nfe": _NS_NFE}

    def _txt(xpath: str) -> str:
        vals = body_el.xpath(xpath, namespaces=ns)
        return str(vals[0]).strip() if vals else ""

    c_stat = _txt(".//nfe:cStat/text()")
    x_motivo = _txt(".//nfe:xMotivo/text()")
    ultimo_nsu = _txt(".//nfe:ultNSU/text()") or "000000000000000"
    max_nsu = _txt(".//nfe:maxNSU/text()") or ultimo_nsu

    # cStat != 138 (Documento localizado) e != 137 (Nenhum documento) -> erro
    if c_stat not in ("137", "138", ""):
        raise FiscalHTTPError(
            message=f"SEFAZ retornou erro na distribuicao: {c_stat} - {x_motivo}",
            status_code=200,
            url="NFeDistribuicaoDFe",
        )

    documentos: list[DocumentoDistribuicao] = []
    docs_el = body_el.xpath(".//nfe:loteDistDFeInt/nfe:docZip", namespaces=ns)
    for doc_el in docs_el:
        nsu_doc = str(doc_el.get("NSU", "")).strip()
        schema_name = str(doc_el.get("schema", "")).strip()
        doc_zip_b64 = (doc_el.text or "").strip()

        if not doc_zip_b64:
            continue
        try:
            doc_bytes = _descompactar_doc_zip(doc_zip_b64)
            doc = _parse_documento(nsu_doc, doc_bytes, schema_name)
        except Exception as exc:
            logger.warning("nfe.distribuicao.parse_doc_falhou", nsu=nsu_doc, erro=str(exc))
            doc = DocumentoDistribuicao(
                nsu=nsu_doc,
                tipo="erro",
                schema=schema_name,
                chave=None,
                resumo=None,
                dados_completos=None,
            )
        documentos.append(doc)

    return DistribuicaoResult(
        ultimo_nsu=ultimo_nsu,
        max_nsu=max_nsu,
        documentos=documentos,
    )


async def _enviar_soap(
    url: str,
    soap_body_content: str,
    ssl_ctx: ssl.SSLContext,
    timeout: float = 30.0,
) -> etree._Element:
    """Envia requisicao SOAP via mTLS e retorna o elemento Body da resposta.

    Rate limit: maximo 1 req/s por endpoint SEFAZ (conservador para evitar
    bloqueio por flood). O limitador e aplicado por URL de endpoint.
    """
    # Aplica rate-limit por endpoint antes de enviar a requisicao
    await _sefaz_nfe_limiter.acquire(url)

    envelope = build_soap_envelope(soap_body_content, namespace=_NS_NFE)

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


# ---------------------------------------------------------------------------
# Funcoes publicas
# ---------------------------------------------------------------------------


async def baixar_nfe_distribuicao(
    caminho_certificado: str,
    senha: str,
    cnpj_cpf: str,
    uf: str,
    modo: Literal["distNSU", "consNSU", "consChNFe"] = "distNSU",
    ultimo_nsu: str | int = "0",
    nsu: str | int | None = None,
    chave: str | None = None,
    ambiente: Ambiente = "producao",
    timeout: float = 30.0,
) -> DistribuicaoResult:
    """
    Baixa documentos fiscais via NFeDistribuicaoDFe com mTLS usando certificado A1 local.

    A Ciencia da Operacao (evento 210200) e pre-requisito para a SEFAZ liberar o
    XML completo (procNFe) ao destinatario. Sem ela, apenas o resNFe (resumo) e
    disponibilizado. Use manifestar_nfe() apos baixar o resNFe para registrar
    a ciencia e depois consultar novamente para obter o procNFe completo.

    Args:
        caminho_certificado: Caminho absoluto para o arquivo .pfx ou .p12.
        senha: Senha do certificado. NUNCA logada ou incluida em excecoes.
        cnpj_cpf: CNPJ (14 dig) ou CPF (11 dig) do autor da consulta.
        uf: Codigo da UF do autor (ex: "35" para SP ou "SP").
        modo: "distNSU" (incremental), "consNSU" (NSU especifico),
            "consChNFe" (por chave).
        ultimo_nsu: Ultimo NSU recebido (modo distNSU). Default 0 = busca todos.
        nsu: NSU especifico a consultar (modo consNSU).
        chave: Chave de acesso de 44 digitos (modo consChNFe).
        ambiente: "producao" ou "homologacao".
        timeout: Timeout HTTP em segundos.

    Returns:
        DistribuicaoResult com documentos e NSUs.

    Raises:
        FiscalValidationError: Inputs invalidos ou certificado invalido/senha errada.
        FiscalHTTPError: Falha HTTP ou erro retornado pela SEFAZ.
    """
    # Validacao de inputs
    cnpj_cpf_norm = _validar_cnpj_cpf(cnpj_cpf, "cnpj_cpf")

    # UF: aceita sigla (ex: "SP") ou codigo numerico IBGE (ex: "35")
    uf_str = str(uf).strip()
    uf_codigo = _UF_CODIGOS.get(uf_str.upper(), uf_str)

    # Carrega o certificado A1
    chave_pem, cert_pem, chain_pem = _carregar_pkcs12(caminho_certificado, senha)
    ssl_ctx = _criar_ssl_context_em_memoria(chave_pem, cert_pem, chain_pem)

    # Monta o corpo SOAP conforme o modo
    endpoint = _ENDPOINTS_DISTRIBUICAO[ambiente]

    if modo == "distNSU":
        nsu_norm = _validar_nsu(ultimo_nsu, "ultimo_nsu")
        body_content = _construir_body_dist_nsu(cnpj_cpf_norm, uf_codigo, nsu_norm)

    elif modo == "consNSU":
        if nsu is None:
            raise FiscalValidationError(
                message="Parametro 'nsu' e obrigatorio no modo consNSU.",
                field="nsu",
                value=None,
            )
        nsu_norm = _validar_nsu(nsu, "nsu")
        body_content = _construir_body_cons_nsu(cnpj_cpf_norm, uf_codigo, nsu_norm)

    elif modo == "consChNFe":
        if not chave:
            raise FiscalValidationError(
                message="Parametro 'chave' e obrigatorio no modo consChNFe.",
                field="chave",
                value=chave,
            )
        chave_norm = _validar_chave(chave)
        body_content = _construir_body_cons_ch_nfe(cnpj_cpf_norm, uf_codigo, chave_norm)

    else:
        raise FiscalValidationError(
            message=f"Modo desconhecido: {modo!r}. Use 'distNSU', 'consNSU' ou 'consChNFe'.",
            field="modo",
            value=modo,
        )

    body_el = await _enviar_soap(endpoint, body_content, ssl_ctx, timeout)
    return _parse_retorno_dist(body_el)


def _montar_xml_evento(
    chave: str,
    cnpj_cpf: str,
    tipo_evento: str,
    numero_sequencia: int,
    justificativa: str | None,
    ambiente_codigo: str,
) -> etree._Element:
    """Monta o elemento XML do evento de manifestacao (sem assinatura)."""
    data_hora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S-00:00")
    c_orgao = "91"  # AN - Ambiente Nacional para manifestacao

    tipo_tag = "CNPJ" if len(cnpj_cpf) == 14 else "CPF"

    desc_evento = {
        EVENTO_CIENCIA: "Ciencia da Operacao",
        EVENTO_CONFIRMACAO: "Confirmacao da Operacao",
        EVENTO_DESCONHECIMENTO: "Desconhecimento da Operacao",
        EVENTO_OPERACAO_NAO_REALIZADA: "Operacao nao Realizada",
    }.get(tipo_evento, "Evento")

    det_evento_inner = f"<descEvento>{desc_evento}</descEvento>" + (
        f"<xJust>{xml.sax.saxutils.escape(justificativa)}</xJust>" if justificativa else ""
    )

    xml_str = (
        f'<envEvento versao="1.00" xmlns="{_NS_NFE}">'
        f"<idLote>{numero_sequencia}</idLote>"
        f'<evento versao="1.00">'
        f'<infEvento Id="ID{tipo_evento}{chave}{str(numero_sequencia).zfill(2)}">'
        f"<cOrgao>{c_orgao}</cOrgao>"
        f"<tpAmb>{ambiente_codigo}</tpAmb>"
        f"<{tipo_tag}>{cnpj_cpf}</{tipo_tag}>"
        f"<chNFe>{chave}</chNFe>"
        f"<dhEvento>{data_hora}</dhEvento>"
        f"<tpEvento>{tipo_evento}</tpEvento>"
        f"<nSeqEvento>{numero_sequencia}</nSeqEvento>"
        f"<verEvento>1.00</verEvento>"
        f'<detEvento versao="1.00">{det_evento_inner}</detEvento>'
        f"</infEvento>"
        f"</evento>"
        f"</envEvento>"
    )
    return parse_xml(xml_str.encode("utf-8"))


def _get_ref_id(evento_el: etree._Element) -> str:
    """Retorna o atributo Id de infEvento, ou de evento_el como fallback."""
    inf_evento = evento_el.find(f".//{{{_NS_NFE}}}infEvento")
    target = inf_evento if inf_evento is not None else evento_el
    return str(target.get("Id", ""))


def _assinar_evento(
    evento_el: etree._Element,
    chave_pem: bytes,
    cert_pem: bytes,
) -> etree._Element:
    """Assina o elemento infEvento com XMLDSig usando a chave privada do certificado A1."""
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private_key = load_pem_private_key(chave_pem, password=None)
    certificate = x509.load_pem_x509_certificate(cert_pem)

    if not isinstance(private_key, (RSAPrivateKey, EllipticCurvePrivateKey)):
        raise FiscalValidationError(
            message="Tipo de chave nao suportado para assinatura NF-e: apenas RSA e EC sao aceitos.",
            field="caminho_certificado",
            value="",
        )

    signer = XMLSigner()  # metodo padrao: enveloped
    signed = signer.sign(
        evento_el,
        key=private_key,
        cert=[certificate],
        reference_uri="#" + _get_ref_id(evento_el),
    )
    return signed


def _parse_retorno_evento(
    body_el: etree._Element, chave: str, tipo_evento: str
) -> ManifestacaoResult:
    """Parseia o retEnvEvento e retorna ManifestacaoResult."""
    ns = {"nfe": _NS_NFE}

    def _txt(xpath: str) -> str:
        vals = body_el.xpath(xpath, namespaces=ns)
        return str(vals[0]).strip() if vals else ""

    c_stat = _txt(".//nfe:cStat/text()")
    x_motivo = _txt(".//nfe:xMotivo/text()")
    n_prot = _txt(".//nfe:nProt/text()")

    sucesso = c_stat == "135"
    return ManifestacaoResult(
        sucesso=sucesso,
        chave=chave,
        tipo_evento=tipo_evento,
        numero_protocolo=n_prot or None,
        codigo_retorno=c_stat or None,
        motivo=x_motivo or None,
    )


async def manifestar_nfe(
    chave: str,
    tipo_evento: str,
    caminho_certificado: str,
    senha: str,
    cnpj_cpf: str,
    uf: str = "91",
    numero_sequencia: int = 1,
    justificativa: str | None = None,
    ambiente: Ambiente = "producao",
    timeout: float = 30.0,
) -> ManifestacaoResult:
    """
    Manifesta o destinatario em uma NF-e via NFeRecepcaoEvento.

    IMPORTANTE: A Ciencia da Operacao (210200) e pre-requisito obrigatorio para
    a SEFAZ liberar o XML completo (procNFe) ao destinatario. Sem registrar a
    ciencia primeiro, somente o resNFe (resumo) fica disponivel na distribuicao.

    Eventos disponiveis:
    - 210200: Ciencia da Operacao (sem justificativa)
    - 210210: Confirmacao da Operacao (sem justificativa)
    - 210220: Desconhecimento da Operacao (sem justificativa)
    - 210240: Operacao nao Realizada (justificativa OBRIGATORIA, min. 15 chars)

    Args:
        chave: Chave de acesso de 44 digitos da NF-e.
        tipo_evento: Codigo do evento (ex: "210200").
        caminho_certificado: Caminho absoluto para o arquivo .pfx/.p12.
        senha: Senha do certificado A1. NUNCA logada ou incluida em excecoes.
        cnpj_cpf: CNPJ (14 dig) ou CPF (11 dig) do destinatario.
        uf: UF do autor (default "91" = AN - Ambiente Nacional).
        numero_sequencia: Numero sequencial do evento para esta chave (1 a 20).
        justificativa: Obrigatoria para 210240 (min. 15 chars). Ignorada nos demais.
        ambiente: "producao" ou "homologacao".
        timeout: Timeout HTTP em segundos.

    Returns:
        ManifestacaoResult com protocolo e codigo de retorno da SEFAZ.

    Raises:
        FiscalValidationError: Inputs invalidos, certificado invalido ou justificativa ausente.
        FiscalHTTPError: Falha HTTP ou erro da SEFAZ.
    """
    chave_norm = _validar_chave(chave)
    cnpj_cpf_norm = _validar_cnpj_cpf(cnpj_cpf, "cnpj_cpf")

    if tipo_evento not in _EVENTOS_VALIDOS:
        raise FiscalValidationError(
            message=f"Tipo de evento invalido: {tipo_evento!r}. Valores aceitos: {sorted(_EVENTOS_VALIDOS)}",
            field="tipo_evento",
            value=tipo_evento,
        )

    if tipo_evento == EVENTO_OPERACAO_NAO_REALIZADA:
        if not justificativa or len(justificativa.strip()) < 15:
            raise FiscalValidationError(
                message="Justificativa obrigatoria para o evento 210240 (Operacao nao Realizada) e deve ter ao menos 15 caracteres.",
                field="justificativa",
                value=justificativa,
            )

    ambiente_codigo = "1" if ambiente == "producao" else "2"
    endpoint = _ENDPOINTS_EVENTO[ambiente]

    chave_pem, cert_pem, chain_pem = _carregar_pkcs12(caminho_certificado, senha)
    ssl_ctx = _criar_ssl_context_em_memoria(chave_pem, cert_pem, chain_pem)

    evento_el = _montar_xml_evento(
        chave=chave_norm,
        cnpj_cpf=cnpj_cpf_norm,
        tipo_evento=tipo_evento,
        numero_sequencia=numero_sequencia,
        justificativa=justificativa,
        ambiente_codigo=ambiente_codigo,
    )

    signed_el = _assinar_evento(evento_el, chave_pem, cert_pem)
    body_content = etree.tostring(signed_el, encoding="unicode")

    body_el = await _enviar_soap(endpoint, body_content, ssl_ctx, timeout)
    return _parse_retorno_evento(body_el, chave_norm, tipo_evento)


__all__ = [
    "EVENTO_CIENCIA",
    "EVENTO_CONFIRMACAO",
    "EVENTO_DESCONHECIMENTO",
    "EVENTO_OPERACAO_NAO_REALIZADA",
    "Ambiente",
    "DistribuicaoResult",
    "DocumentoDistribuicao",
    "ManifestacaoResult",
    "baixar_nfe_distribuicao",
    "manifestar_nfe",
]
