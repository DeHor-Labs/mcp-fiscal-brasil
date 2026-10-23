"""Validação de assinatura digital XMLDSig em documentos NF-e (ICP-Brasil)."""

from __future__ import annotations

import base64
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from lxml import etree
from signxml import SignatureConfiguration, XMLVerifier  # type: ignore[attr-defined, unused-ignore]

from .._core.errors import FiscalValidationError
from .._core.logging import get_logger
from ..shared.xml_utils import NS_NFE, parse_xml

logger_assinatura = get_logger(__name__)

# Limite máximo para o ca_bundle a fim de evitar processamento de entrada gigante
_CA_BUNDLE_MAX_BYTES = 1 * 1024 * 1024  # 1 MB

if TYPE_CHECKING:
    from cryptography.x509 import Certificate

# Pattern para extrair CNPJ de 14 dígitos numéricos do CN do certificado
_CNPJ_RE = re.compile(r"\d{14}")


@dataclass(frozen=True)
class AssinaturaResult:
    """Resultado da validação de assinatura digital XMLDSig de uma NF-e."""

    assinatura_valida: bool
    """True se a assinatura criptográfica e a integridade do digest forem válidas."""

    motivo: str | None = None
    """Descrição do erro caso assinatura_valida seja False, None se válida."""

    titular: str | None = None
    """CN (Common Name) do certificado assinante, normalmente razão social + CNPJ."""

    cnpj_cpf: str | None = None
    """CNPJ de 14 dígitos numéricos extraído do CN, se presente; não extrai CPF."""

    validade_inicio: datetime | None = None
    """Início da validade do certificado."""

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
    """Extrai CNPJ de 14 dígitos numéricos do CN do certificado, se presente."""
    if not cn:
        return None
    match = _CNPJ_RE.search(cn)
    return match.group() if match else None


def _extrair_ac_emissora(cert: Certificate) -> str | None:
    """Retorna o DN do emissor do certificado como string legível."""
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

    Verifica a integridade do Reference/DigestValue e a assinatura criptográfica
    do infNFe referenciado pela Signature, filha de NFe. Extrai dados do certificado assinante.

    Args:
        xml_content: Conteúdo XML da NF-e (str ou bytes). Todo XML externo
            é parseado via parse_xml() (anti-XXE).
        ca_bundle: Opcional. PEM com cadeia ICP-Brasil para validar o emissor
            do certificado.
            - ``str``: caminho de arquivo PEM no sistema de arquivos. O arquivo
              deve existir e ser legível; caso contrário, levanta
              ``FiscalValidationError`` com mensagem clara.
            - ``bytes``: conteúdo PEM diretamente em memória.
            - ``None``: valida a assinatura sem exigir cadeia confiável (não
              falha por ausência de bundle, mas não confirma a AC emissora).

    Returns:
        AssinaturaResult com o resultado da validação e dados do certificado.
        NUNCA reporta assinatura inválida como válida.

    Raises:
        FiscalValidationError: Se o arquivo ``ca_bundle`` não existir ou não puder ser lido,
            ou se o conteúdo exceder 1 MB.
        XMLParseError: Se o XML for malformado (propagado de parse_xml).
    """
    bundle_bytes: bytes | None = None
    if isinstance(ca_bundle, str):
        if not os.path.isfile(ca_bundle):
            raise FiscalValidationError(
                message=f"Arquivo ca_bundle não encontrado: '{ca_bundle}'.",
                field="ca_bundle",
                value=ca_bundle,
            )
        try:
            with open(ca_bundle, "rb") as pem:
                bundle_bytes = pem.read(_CA_BUNDLE_MAX_BYTES + 1)
        except OSError as exc:
            raise FiscalValidationError(
                message="Não foi possível ler o arquivo ca_bundle.",
                field="ca_bundle",
                value=ca_bundle,
            ) from exc

    else:
        bundle_bytes = ca_bundle

    if bundle_bytes is not None and len(bundle_bytes) > _CA_BUNDLE_MAX_BYTES:
        raise FiscalValidationError(
            message="O ca_bundle excede o limite de 1 MB. Forneça apenas a cadeia ICP-Brasil necessária.",
            field="ca_bundle",
            value=f"{len(bundle_bytes)} bytes",
        )

    # Parseia via parse_xml (resolve_entities=False, no_network=True) - anti-XXE
    root = parse_xml(xml_content)

    nfe_tag = f"{{{NS_NFE['nfe']}}}NFe"
    if root.tag == nfe_tag:
        nfe_nodes = [root]
        signature_location = "./"
    elif root.tag == f"{{{NS_NFE['nfe']}}}nfeProc":
        nfe_nodes = root.findall(nfe_tag)
        signature_location = f"./{nfe_tag}/"
    else:
        nfe_nodes = []
        signature_location = "./"
    if len(nfe_nodes) != 1:
        return AssinaturaResult(False, "Esperado um único elemento NFe na raiz ou em nfeProc.")
    nfe = nfe_nodes[0]
    inf_nodes = root.xpath(".//nfe:infNFe", namespaces=NS_NFE)
    if len(inf_nodes) != 1 or inf_nodes[0].getparent() is not nfe:
        return AssinaturaResult(False, "Esperado um único infNFe diretamente em NFe.")
    inf_nfe = inf_nodes[0]
    inf_id = inf_nfe.get("Id")
    if not inf_id or len(root.xpath("//*[@*[local-name()='Id']=$id]", id=inf_id)) != 1:
        return AssinaturaResult(False, "Id do infNFe ausente ou duplicado.")
    signature_nodes = root.xpath(".//ds:Signature", namespaces=NS_NFE)
    if len(signature_nodes) != 1 or signature_nodes[0].getparent() is not nfe:
        return AssinaturaResult(False, "Esperada uma única Signature diretamente em NFe.")
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

    if cert_obj is None and bundle_bytes is None:
        # Sem certificado embutido e sem ca_bundle: impossível validar a
        # confiança do assinante. Retorna inválido para evitar falsa validação
        # contra a CA store do sistema (que aceitaria qualquer cert SSL).
        return AssinaturaResult(
            assinatura_valida=False,
            motivo=(
                "XML não contém certificado embutido e nenhum ca_bundle foi fornecido; "
                "impossível validar a confiança do assinante."
            ),
        )

    try:
        verifier = XMLVerifier()
        references = signature_el.xpath("./ds:SignedInfo/ds:Reference", namespaces=NS_NFE)
        if len(references) != 1 or references[0].get("URI") != f"#{inf_id}":
            return AssinaturaResult(False, "Reference URI deve apontar para o Id do infNFe.")
        xml_bytes = etree.tostring(root)
        config = SignatureConfiguration(location=signature_location, expect_references=1)

        if bundle_bytes is not None:
            # SignXML exige caminho; usa exatamente os bytes já lidos e limitados.
            with tempfile.TemporaryDirectory() as directory:
                pem_path = os.path.join(directory, "ca.pem")
                with open(pem_path, "wb") as pem:
                    pem.write(bundle_bytes)
                verified = verifier.verify(
                    data=xml_bytes, ca_pem_file=pem_path, id_attribute="Id", expect_config=config
                )
        else:
            verified = verifier.verify(
                data=xml_bytes, x509_cert=cert_obj, id_attribute="Id", expect_config=config
            )

        if isinstance(verified, list):
            return AssinaturaResult(False, "Esperada uma única referência verificada ao infNFe.")
        signed = verified.signed_xml
        if (
            signed is None
            or signed.tag != inf_nfe.tag
            or signed.get("Id") != inf_id
            or etree.tostring(signed, method="c14n", exclusive=True, with_comments=False)
            != etree.tostring(inf_nfe, method="c14n", exclusive=True, with_comments=False)
        ):
            return AssinaturaResult(
                False, "Conteúdo verificado não corresponde ao infNFe esperado."
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
