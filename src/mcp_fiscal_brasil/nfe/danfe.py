"""Geracao de DANFE em PDF a partir de XML de NF-e.

Suporte a modelo 55 (NF-e) com namespace do portal fiscal (portalfiscal.inf.br/nfe).
Modelo 65 (NFC-e) nao e suportado na versao 1.0.0 da lib brazilfiscalreport.

Seguranca:
- Todo XML externo e parseado via parse_xml() (resolve_entities=False, no_network=True)
  antes de ser entregue a lib brazilfiscalreport. Isso impede XXE e billion-laughs
  mesmo quando o XML vem de fonte nao confiavel (usuario ou LLM).
- A lib brazilfiscalreport usa xml.etree internamente (sem protecao XXE propria);
  a validacao previa via lxml com _SAFE_PARSER e a barreira de seguranca.
"""

from __future__ import annotations

import base64

from lxml import etree
from pydantic import BaseModel

from .._core.errors import FiscalValidationError
from ..shared.xml_utils import NS_NFE, parse_xml, xpath_text
from .xml_parser import extrair_chave_nfe, extrair_modelo_nfe


class DanfeGenerationError(FiscalValidationError):
    """Erro ao gerar o DANFE."""

    def __init__(self, field: str, value: str, reason: str) -> None:
        super().__init__(message=reason, field=field, value=value)


class DanfeResult(BaseModel):
    """Resultado da geracao de DANFE em PDF."""

    pdf_base64: str
    """Conteudo do PDF codificado em base64."""

    modelo: int
    """Modelo do documento fiscal: 55 para NF-e."""

    nome_arquivo: str
    """Nome de arquivo sugerido para o PDF, incluindo a chave de acesso."""

    paginas: int | None = None
    """Numero de paginas do PDF (disponivel quando calculavel)."""

    chave_acesso: str
    """Chave de acesso de 44 digitos do documento."""

    numero: str | None = None
    """Numero da nota fiscal extraido do XML."""

    serie: str | None = None
    """Serie da nota fiscal extraida do XML."""


def _extrair_metadados_xml(xml_content: str | bytes) -> tuple[str, int, str | None, str | None]:
    """
    Extrai chave, modelo, numero e serie do XML da NF-e.

    Delega extracao de chave e modelo aos helpers compartilhados
    extrair_chave_nfe e extrair_modelo_nfe (xml_parser.py), que ja
    aplicam parse_xml (anti-XXE) internamente.

    Args:
        xml_content: Conteudo XML da nota fiscal.

    Returns:
        Tupla (chave, modelo, numero, serie).

    Raises:
        DanfeGenerationError: Se o XML nao contiver infNFe valido ou chave invalida.
        XMLParseError: Se o XML estiver malformado (propagado de parse_xml).
    """
    chave = extrair_chave_nfe(xml_content)
    if chave is None:
        raise DanfeGenerationError(
            field="xml",
            value="<xml>",
            reason=(
                "XML invalido: elemento <infNFe> nao encontrado ou Id nao contem "
                "44 digitos numericos. Verifique se o XML e uma NF-e valida."
            ),
        )

    modelo = extrair_modelo_nfe(xml_content)

    # Extrai numero e serie diretamente do XML parseado (seguro, anti-XXE via parse_xml)
    root = parse_xml(xml_content)
    ns = NS_NFE
    ide = root.find(".//nfe:ide", ns)
    if ide is None:
        ide = root.find(".//ide")

    def _text(el: etree._Element | None, xpath_ns: str, xpath_plain: str) -> str | None:
        if el is None:
            return None
        return xpath_text(el, xpath_ns, ns) or xpath_text(el, xpath_plain, {})

    numero = _text(ide, "nfe:nNF/text()", "nNF/text()")
    serie = _text(ide, "nfe:serie/text()", "serie/text()")

    return chave, modelo, numero, serie


def _verificar_namespace_portalfiscal(xml_content: str | bytes) -> None:
    """
    Verifica se o XML contem o namespace do portal fiscal necessario para a lib.

    A brazilfiscalreport 1.0.0 requer o namespace
    'http://www.portalfiscal.inf.br/nfe' no XML para funcionar corretamente.
    Se o namespace estiver ausente, lanca DanfeGenerationError com instrucao clara.

    Args:
        xml_content: Conteudo XML como string ou bytes.

    Raises:
        DanfeGenerationError: Se o namespace do portal fiscal nao for encontrado.
    """
    ns_portalfiscal = "http://www.portalfiscal.inf.br/nfe"
    conteudo = (
        xml_content
        if isinstance(xml_content, str)
        else xml_content.decode("utf-8", errors="replace")
    )
    if ns_portalfiscal not in conteudo:
        raise DanfeGenerationError(
            field="namespace",
            value="<xml>",
            reason=(
                "O XML nao contem o namespace do portal fiscal "
                f"('{ns_portalfiscal}'). "
                "A geracao de DANFE requer o namespace no elemento raiz. "
                'Exemplo: <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"> '
                'ou <NFe xmlns="http://www.portalfiscal.inf.br/nfe">.'
            ),
        )


def _normalizar_xml_para_danfe(xml_content: str | bytes) -> str:
    """
    Converte o XML para string UTF-8 para a lib brazilfiscalreport.

    A lib usa ET.fromstring internamente e aceita string. Como o XML ja foi
    validado (anti-XXE) em _extrair_metadados_xml, aqui apenas convertemos
    o tipo sem novo parse.

    Args:
        xml_content: XML como string ou bytes.

    Returns:
        XML como string UTF-8.
    """
    if isinstance(xml_content, bytes):
        return xml_content.decode("utf-8", errors="replace")
    return xml_content


def gerar_danfe(xml_content: str | bytes) -> DanfeResult:
    """
    Gera o DANFE em PDF a partir do XML de uma NF-e (modelo 55).

    Suporta apenas modelo 55. Modelo 65 (NFC-e) nao e suportado pela
    brazilfiscalreport 1.0.0 - sera suportado em versao futura da lib.

    SEGURANCA: o XML e validado via parse_xml() (anti-XXE) antes de ser
    entregue a lib brazilfiscalreport, que usa xml.etree sem protecao propria.

    O XML pode conter ou nao o involucro de protocolo <nfeProc>. Quando o XML
    nao tiver protocolo de autorizacao, o DANFE e gerado sem o numero de
    protocolo no rodape (comportamento identico ao da lib).

    NAMESPACE OBRIGATORIO: o XML deve conter o namespace do portal fiscal
    (http://www.portalfiscal.inf.br/nfe) para que a lib possa processar o XML.

    Args:
        xml_content: XML completo da NF-e como string ou bytes.
                     Deve conter o namespace do portal fiscal
                     (http://www.portalfiscal.inf.br/nfe).
                     Aceita XML com ou sem involucro <nfeProc>.

    Returns:
        DanfeResult com o PDF em base64, metadados do documento e nome de
        arquivo sugerido.

    Raises:
        DanfeGenerationError: Se o XML for invalido, o modelo nao for suportado
                              (65 = nao suportado, ver nota acima), o namespace
                              estiver ausente, ou a geracao do PDF falhar.
        XMLParseError: Se o XML estiver malformado (propagado de parse_xml).
    """
    # parse_xml (anti-XXE) e chamado dentro de _extrair_metadados_xml
    chave, modelo, numero, serie = _extrair_metadados_xml(xml_content)

    if modelo == 65:
        raise DanfeGenerationError(
            field="ide/mod",
            value="65",
            reason=(
                "DANFE NFC-e (modelo 65) ainda nao e suportado nesta versao. "
                "A lib brazilfiscalreport 1.0.0 nao possui classe dedicada a NFC-e. "
                "Para NFC-e, utilize uma solucao especifica de cupom fiscal. "
                "Esta ferramenta suporta apenas NF-e (modelo 55)."
            ),
        )

    if modelo != 55:
        raise DanfeGenerationError(
            field="ide/mod",
            value=str(modelo),
            reason=(
                f"Modelo de documento '{modelo}' nao suportado para geracao de DANFE. "
                "Modelo suportado: 55 (NF-e)."
            ),
        )

    # Verificacao de namespace antes de entregar a lib (falha clara ao inves de erro obscuro)
    _verificar_namespace_portalfiscal(xml_content)

    xml_str = _normalizar_xml_para_danfe(xml_content)
    pdf_bytes = _gerar_danfe_nfe(xml_str, chave)

    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
    nome_arquivo = f"DANFE_NFE_{chave}.pdf"

    return DanfeResult(
        pdf_base64=pdf_base64,
        modelo=modelo,
        nome_arquivo=nome_arquivo,
        paginas=None,  # fpdf2 nao expoe contagem de paginas apos output()
        chave_acesso=chave,
        numero=numero,
        serie=serie,
    )


def _gerar_danfe_nfe(xml_str: str, chave: str) -> bytes:
    """
    Gera o PDF do DANFE A4 para NF-e (modelo 55).

    O XML ja foi validado (anti-XXE) e verificado com namespace antes desta chamada.

    Args:
        xml_str: XML da NF-e como string com namespace do portal fiscal.
        chave: Chave de acesso de 44 digitos (usada apenas para mensagens de erro).

    Returns:
        Bytes do PDF gerado.

    Raises:
        DanfeGenerationError: Se a geracao do PDF falhar.
    """
    try:
        from brazilfiscalreport.danfe import Danfe

        danfe = Danfe(xml=xml_str)
        result = danfe.output()
        # output() sem argumento retorna bytearray; converte para bytes
        return bytes(result) if result is not None else b""
    except ImportError as exc:
        raise DanfeGenerationError(
            field="dependencia",
            value="brazilfiscalreport",
            reason=(
                "Biblioteca 'brazilfiscalreport' nao encontrada. "
                "Instale com: pip install brazilfiscalreport"
            ),
        ) from exc
    except Exception as exc:
        raise DanfeGenerationError(
            field="xml",
            value=chave,
            reason=f"Erro ao gerar DANFE NF-e: {exc}",
        ) from exc
