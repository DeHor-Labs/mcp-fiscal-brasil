"""Funções de tool para o módulo IBGE."""

from mcp_fiscal_brasil._core import get_logger

from .client import IBGEClient
from .schemas import Estado, Municipio

logger = get_logger(__name__)

_client = IBGEClient()


async def consultar_municipios_ibge(uf: str | None = None) -> list[Municipio]:
    """
    Consulta municípios brasileiros, opcionalmente filtrados por UF.

    Args:
        uf: Sigla do estado (ex: 'GO', 'SP'). Se omitida, retorna todos os municípios.

    Returns:
        Lista de Municipio com id, nome, microrregião e estado.
    """
    logger.info("tool_consultar_municipios_ibge_called", uf=uf)
    return await _client.get_municipalities(uf)


async def consultar_estado_ibge(uf: str) -> Estado:
    """
    Consulta os dados de um estado (UF) pelo código ou sigla.

    Args:
        uf: Sigla do estado (ex: 'GO', 'SP', 'RJ').

    Returns:
        Estado com id, sigla, nome e região.
    """
    logger.info("tool_consultar_estado_ibge_called", uf=uf)
    return await _client.get_state(uf)
