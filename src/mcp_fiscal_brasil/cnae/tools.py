"""Funções de tool para o módulo CNAE."""

from mcp_fiscal_brasil._core import get_logger

from .client import CNAEClient
from .schemas import CNAEActivity

logger = get_logger(__name__)

_client = CNAEClient()


async def consultar_cnae(codigo: str) -> CNAEActivity:
    """
    Consulta uma atividade econômica CNAE pelo código de subclasse (7 dígitos).

    Args:
        codigo: Código da subclasse CNAE com 7 dígitos, com ou sem pontuação.

    Returns:
        CNAEActivity com código e descrição da atividade.
    """
    logger.info("tool_consultar_cnae_called", codigo=codigo)
    return await _client.get_activity(codigo)


async def buscar_cnae(texto: str) -> list[CNAEActivity]:
    """
    Busca atividades econômicas CNAE por texto na descrição.

    Args:
        texto: Texto para busca na descrição das atividades (ex: 'software', 'restaurante').

    Returns:
        Lista de CNAEActivity correspondentes à busca.
    """
    logger.info("tool_buscar_cnae_called", texto=texto)
    return await _client.get_activities(search=texto)
