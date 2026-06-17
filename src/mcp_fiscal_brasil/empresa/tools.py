"""Funções de tool para o módulo Empresa."""

from mcp_fiscal_brasil._core import get_logger

from .client import EmpresaClient
from .schemas import EmpresaInfo

logger = get_logger(__name__)

_client = EmpresaClient()


async def consultar_empresa_completa(cnpj: str) -> EmpresaInfo:
    """
    Consulta dados enriquecidos de uma empresa cruzando CNPJ e Simples Nacional.

    Combina informações da Receita Federal (CNPJ) com dados do Simples Nacional
    em uma única consulta paralela.

    Args:
        cnpj: Número do CNPJ com 14 dígitos, com ou sem formatação.

    Returns:
        EmpresaInfo com razão social, situação, porte, regime tributário, CNAE e endereço.
    """
    logger.info("tool_consultar_empresa_completa_called", cnpj=cnpj)
    return await _client.get_empresa(cnpj)
