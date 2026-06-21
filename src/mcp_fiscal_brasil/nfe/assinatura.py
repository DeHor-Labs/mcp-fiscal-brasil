"""Validacao de assinatura digital XMLDSig em documentos NF-e (ICP-Brasil)."""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from lxml import etree
from signxml import XMLVerifier

from .._core.errors import FiscalValidationError
from .._core.logging import get_logger
from ..shared.xml_utils import parse_xml

logger_assinatura = get_logger(__name__)

# Limite maximo para o ca_bundle a fim de evitar processamento de entrada gigante
_CA_BUNDLE_MAX_BYTES = 1 * 1024 * 1024  # 1 MB

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

# Pattern para extrair CNPJ de 14 digitos numericos do CN do certificado
_CNPJ_RE = re.compile(r"\d{14}")


@dataclass(frozen=True)
class AssinaturaResult:
    """Resultado da validacao de assinatura digital XMLDSig de uma NF-e."""

    assinatura_valida: bool
    """True se a assinatura criptografica e a integridade do digest forem validas."""

    motivo: str | None = None
    """Descricao do erro caso assinatura_valida seja False, None se valida."""

    titular: str | None = None
    """CN (Common Name) do certificado assinante, normalmente razao social + CNPJ."""

    cnpj_cpf: str | None = None
    """CNPJ ou CPF extraido do CN do certificado, se presente."""

    validade_inicio: datetime | None = None
    """Inicio da validade do certificado."""

    validade_fim: datetime | None = None
    """Fim da validade do certificado."""

    ac_emissora: str | None = None
    """DN do emissor (Autoridade Certificadora) do certificado."""


def _extrair_cert_x509(signature_xml: etree._Element) -> Certificate | None:
    """Extrai o certificado X.509 do elemento Signature do XML, se presente."""
    from cryptography import x509

    ns = {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    x509_nodes = signature_xml.xpath(".//ds:X509Certificate/text()", namespaces=ns)
    if not x509_nodes:
        return None

    try:
        der_bytes = base64.b64decode(str(x509_nodes[0]).strip())
        return x509.load_der_x509_certificate(der_bytes)
    except Exception as exc:
        logger_assinatura.debug("nfe.assinatura.extrair_cert_x509.falhou", erro=str(exc))
        return None


def _extrair_cn(cert: Certificate) -> str | None:
    """Extrai o valor do atributo CN (Common Name) do Subject do certificado."""
    from cryptography.x509.oid import NameOID

    try:
        attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if attrs:
            return str(attrs[0].value)
    except Exception as exc:
        logger_assinatura.debug("nfe.assinatura.extrair_cn.falhou", erro=str(exc))
    return None


def _extrair_cnpj_cpf(cn: str | None) -> str | None:
    """Extrai CNPJ de 14 digitos numericos do CN do certificado, se presente."""
    if not cn:
        return None
    match = _CNPJ_RE.search(cn)
    return match.group() if match else None


def _extrair_ac_emissora(cert: Certificate) -> str | None:
    """Retorna o DN do emissor do certificado como string legivel."""
    try:
        issuer_attrs = []
        for attr in cert.issuer:
            value = (
                attr.value
                if isinstance(attr.value, str)
                else attr.value.decode("utf-8", errors="replace")
            )
            issuer_attrs.append(f"{attr.oid.dotted_string}={value}")
        return ", ".join(issuer_attrs) if issuer_attrs else None
    except Exception as exc:
        logger_assinatura.debug("nfe.assinatura.extrair_ac_emissora.falhou", erro=str(exc))
        return None


def _preencher_dados_cert(
    cert: Certificate,
) -> tuple[str | None, str | None, datetime | None, datetime | None, str | None]:
    """Extrai titular, cnpj_cpf, validade_inicio, validade_fim, ac_emissora do cert."""
    cn = _extrair_cn(cert)
    cnpj_cpf = _extrair_cnpj_cpf(cn)

    try:
        validade_inicio: datetime | None = cert.not_valid_before_utc
    except AttributeError:
        # Python < 3.11 usa not_valid_before (sem fuso)
        try:
            validade_inicio = cert.not_valid_before
        except Exception:
            validade_inicio = None

    try:
        validade_fim: datetime | None = cert.not_valid_after_utc
    except AttributeError:
        try:
            validade_fim = cert.not_valid_after
        except Exception:
            validade_fim = None

    ac_emissora = _extrair_ac_emissora(cert)
    return cn, cnpj_cpf, validade_inicio, validade_fim, ac_emissora


def validar_assinatura_nfe(
    xml_content: str | bytes,
    ca_bundle: str | bytes | None = None,
) -> AssinaturaResult:
    """
    Valida a assinatura digital XMLDSig de uma NF-e.

    Verifica a integridade do Reference/DigestValue e a assinatura criptografica
    do elemento Signature presente em infNFe. Extrai dados do certificado assinante.

    Args:
        xml_content: Conteudo XML da NF-e (str ou bytes). Todo XML externo
            e parseado via parse_xml() (anti-XXE).
        ca_bundle: Opcional. PEM com cadeia ICP-Brasil para validar o emissor
            do certificado.
            - ``str``: caminho de arquivo PEM no sistema de arquivos. O arquivo
              deve existir e ser legivel; caso contrario, levanta
              ``FiscalValidationError`` com mensagem clara.
            - ``bytes``: conteudo PEM diretamente em memoria.
            - ``None``: valida a assinatura sem exigir cadeia confiavel (nao
              falha por ausencia de bundle, mas nao confirma a AC emissora).

    Returns:
        AssinaturaResult com o resultado da validacao e dados do certificado.
        NUNCA reporta assinatura invalida como valida.

    Raises:
        FiscalValidationError: Se ``ca_bundle`` for ``str`` e o caminho nao existir,
            ou se o conteudo exceder 1 MB.
        XMLParseError: Se o XML for malformado (propagado de parse_xml).
    """
    # Valida ca_bundle str (caminho de arquivo) antes de qualquer processamento
    if isinstance(ca_bundle, str):
        if not os.path.isfile(ca_bundle):
            raise FiscalValidationError(
                message=(
                    f"Arquivo ca_bundle nao encontrado: '{ca_bundle}'. "
                    "Informe o caminho absoluto de um arquivo PEM valido da cadeia ICP-Brasil."
                ),
                field="ca_bundle",
                value=ca_bundle,
            )

    # Valida tamanho do ca_bundle antes de qualquer processamento (DoS guard)
    if ca_bundle is not None:
        bundle_bytes = ca_bundle if isinstance(ca_bundle, bytes) else ca_bundle.encode()
        if len(bundle_bytes) > _CA_BUNDLE_MAX_BYTES:
            raise FiscalValidationError(
                message="O ca_bundle excede o limite de 1 MB. Forneca apenas a cadeia ICP-Brasil necessaria.",
                field="ca_bundle",
                value=f"{len(bundle_bytes)} bytes",
            )

    # Parseia via parse_xml (resolve_entities=False, no_network=True) - anti-XXE
    root = parse_xml(xml_content)

    # Localiza o elemento Signature (pode estar dentro de NFe ou diretamente na raiz)
    ns_ds = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
    signature_nodes = root.xpath(".//ds:Signature", namespaces=ns_ds)
    if not signature_nodes:
        return AssinaturaResult(
            assinatura_valida=False,
            motivo="Elemento Signature nao encontrado no XML.",
        )

    # Dados do certificado (extraidos antes da verificacao para retornar mesmo em falha)
    signature_el = signature_nodes[0]
    cert_obj = _extrair_cert_x509(signature_el)
    titular: str | None = None
    cnpj_cpf: str | None = None
    validade_inicio: datetime | None = None
    validade_fim: datetime | None = None
    ac_emissora: str | None = None

    if cert_obj is not None:
        titular, cnpj_cpf, validade_inicio, validade_fim, ac_emissora = _preencher_dados_cert(
            cert_obj
        )

    try:
        verifier = XMLVerifier()
        xml_bytes = etree.tostring(root)

        if ca_bundle is not None:
            # Validacao completa: verifica assinatura + cadeia de confianca ICP-Brasil.
            # ca_bundle pode ser bytes PEM ou str com caminho para arquivo PEM.
            verifier.verify(data=xml_bytes, ca_pem_file=ca_bundle)
        elif cert_obj is not None:
            # Validacao sem cadeia: verifica integridade (DigestValue) e assinatura
            # criptografica usando o certificado embutido no proprio XML.
            # Nao valida se o certificado e confiavel (sem CA bundle).
            verifier.verify(data=xml_bytes, x509_cert=cert_obj)
        else:
            # Sem certificado embutido e sem ca_bundle: impossivel validar a
            # confianca do assinante. Retorna invalido para evitar falsa validacao
            # contra a CA store do sistema (que aceitaria qualquer cert SSL).
            return AssinaturaResult(
                assinatura_valida=False,
                motivo=(
                    "XML nao contem certificado embutido e nenhum ca_bundle foi fornecido; "
                    "impossivel validar a confianca do assinante."
                ),
            )

        return AssinaturaResult(
            assinatura_valida=True,
            motivo=None,
            titular=titular,
            cnpj_cpf=cnpj_cpf,
            validade_inicio=validade_inicio,
            validade_fim=validade_fim,
            ac_emissora=ac_emissora,
        )
    except Exception as exc:
        return AssinaturaResult(
            assinatura_valida=False,
            motivo=str(exc),
            titular=titular,
            cnpj_cpf=cnpj_cpf,
            validade_inicio=validade_inicio,
            validade_fim=validade_fim,
            ac_emissora=ac_emissora,
        )


__all__ = ["AssinaturaResult", "validar_assinatura_nfe"]
