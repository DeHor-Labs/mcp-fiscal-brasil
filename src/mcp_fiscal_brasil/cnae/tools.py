"""Funções de tool para o módulo CNAE."""

from mcp_fiscal_brasil._core import FiscalValidationError, get_logger

from .client import CNAEClient
from .schemas import CNAEActivity

logger = get_logger(__name__)

_client = CNAEClient()

_MAX_TEXTO_BUSCA = 200


async def consultar_cnae(codigo: str) -> CNAEActivity:
    """
    Consulta uma atividade econômica CNAE pelo código de subclasse (7 dígitos).

    Args:
        codigo: Código da subclasse CNAE com 7 dígitos, com ou sem pontuação
                (ex: '6201501' ou '62.01-5/01').

    Returns:
        CNAEActivity com código e descrição da atividade.

    Raises:
        FiscalValidationError: Se o código não tiver 7 dígitos numéricos.
    """
    codigo_limpo = codigo.replace(".", "").replace("-", "").replace("/", "").strip()
    if not codigo_limpo.isdigit() or len(codigo_limpo) != 7:
        raise FiscalValidationError(
            f"Formato de código CNAE inválido: '{codigo}'. "
            "Informe 7 dígitos numéricos (ex: '6201501').",
            field="codigo",
            value=codigo,
        )
    logger.info("tool_consultar_cnae_called", codigo=codigo_limpo)
    return await _client.get_activity(codigo_limpo)


async def buscar_cnae(texto: str) -> list[CNAEActivity]:
    """
    Busca atividades econômicas CNAE por texto na descrição.

    Args:
        texto: Texto para busca na descrição das atividades (ex: 'software', 'restaurante').
               Máximo de 200 caracteres.

    Returns:
        Lista de CNAEActivity correspondentes à busca.

    Raises:
        FiscalValidationError: Se o texto estiver vazio ou exceder o limite de caracteres.
    """
    texto_strip = texto.strip()
    if not texto_strip:
        raise FiscalValidationError(
            "O texto de busca não pode ser vazio.",
            field="texto",
            value=texto,
        )
    if len(texto_strip) > _MAX_TEXTO_BUSCA:
        raise FiscalValidationError(
            f"Texto de busca muito longo ({len(texto_strip)} caracteres). "
            f"Máximo permitido: {_MAX_TEXTO_BUSCA} caracteres.",
            field="texto",
            value=texto_strip[:50] + "...",
        )
    logger.info("tool_buscar_cnae_called", texto=texto_strip)
    return await _client.get_activities(search=texto_strip)
