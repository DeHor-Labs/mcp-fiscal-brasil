"""Funções de tool para o módulo MEI."""

from mcp_fiscal_brasil._core import get_logger

from .client import MEIClient
from .schemas import MEIStatus

logger = get_logger(__name__)

_client = MEIClient()


async def consultar_status_mei(cnpj: str) -> MEIStatus:
    """
    Consulta o status MEI e Simples Nacional de um CNPJ.

    Args:
        cnpj: Número do CNPJ com 14 dígitos, com ou sem formatação.

    Returns:
        MEIStatus com situação MEI, Simples Nacional e datas de opção/exclusão.
    """
    logger.info("tool_consultar_status_mei_called", cnpj=cnpj)
    return await _client.get_mei_status(cnpj)
