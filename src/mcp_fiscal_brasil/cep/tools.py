"""Funções de tool para o módulo CEP."""

from mcp_fiscal_brasil._core import get_logger

from .client import CEPClient
from .schemas import Endereco

logger = get_logger(__name__)

_client = CEPClient()


async def consultar_cep(cep: str) -> Endereco:
    """
    Consulta o endereço completo a partir de um CEP brasileiro.

    Args:
        cep: CEP com 8 dígitos, com ou sem hífen (ex: '01001-000' ou '01001000').

    Returns:
        Endereco com logradouro, bairro, cidade, estado e serviço de origem.
    """
    logger.info("tool_consultar_cep_called", cep=cep)
    return await _client.get_address(cep)
