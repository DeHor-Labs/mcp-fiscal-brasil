"""Tool de parse de documento NF-e/NFC-e a partir de XML bruto."""

from pydantic import BaseModel

from .._core.errors import FiscalValidationError
from .schemas import NFeResponse
from .xml_parser import extrair_chave_nfe, parse_nfe_xml


class DocumentoParseError(FiscalValidationError):
    """Erro de validacao ao fazer parse de XML de documento fiscal."""

    def __init__(self, field: str, value: str, reason: str) -> None:
        super().__init__(message=reason, field=field, value=value)


class ParseNFeDocumentoResult(BaseModel):
    """Resultado do parse de documento NF-e/NFC-e."""

    nfe: NFeResponse
    chave_extraida: str
    modelo: int


def _extrair_chave_do_xml(xml_content: str | bytes) -> str:
    """
    Extrai a chave de acesso (44 digitos) do atributo Id do infNFe.

    O atributo Id tem o formato "NFe<44 digitos>" ou apenas "<44 digitos>".
    Remove o prefixo "NFe" se presente. Delega a extracao ao helper
    compartilhado extrair_chave_nfe (xml_parser.py).

    Args:
        xml_content: Conteudo XML da NF-e ou NFC-e.

    Returns:
        Chave de acesso com 44 digitos.

    Raises:
        DocumentoParseError: Se o XML nao contiver o elemento infNFe com Id valido.
    """
    chave = extrair_chave_nfe(xml_content)
    if chave is None:
        raise DocumentoParseError(
            field="infNFe/@Id",
            value="<xml>",
            reason=(
                "XML invalido: elemento <infNFe> nao encontrado ou Id nao contem "
                "44 digitos numericos apos remover o prefixo 'NFe'. "
                "Verifique se o XML e uma NF-e ou NFC-e valida."
            ),
        )
    return chave


def parse_nfe_documento(xml_content: str | bytes) -> NFeResponse:
    """
    Parseia o XML completo de uma NF-e ou NFC-e e retorna NFeResponse.

    Aceita XMLs com ou sem o involucro de protocolo <nfeProc>, com ou sem
    namespace do portal fiscal. Extrai a chave de acesso automaticamente do
    atributo Id do elemento <infNFe>.

    Args:
        xml_content: XML completo da NF-e ou NFC-e como string ou bytes.
                     Pode conter o involucro <nfeProc> ou ser a NF-e nua.

    Returns:
        NFeResponse com todos os dados do documento fiscal.

    Raises:
        DocumentoParseError: Se o XML nao for uma NF-e/NFC-e valida ou a chave
                             extraida nao tiver 44 digitos.
        XMLParseError: Se o XML estiver malformado (lxml nao conseguir parsear).
    """
    chave = _extrair_chave_do_xml(xml_content)
    return parse_nfe_xml(xml_content, chave)
