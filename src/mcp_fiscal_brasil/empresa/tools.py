"""Funções de tool para o módulo Empresa."""

from mcp_fiscal_brasil._core import get_logger
from mcp_fiscal_brasil.shared.validators import normalizar_cnpj, validate_cnpj_qualquer

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

    Raises:
        ValueError: Se o CNPJ for inválido ou tiver formato incorreto.
    """
    if not validate_cnpj_qualquer(cnpj):
        raise ValueError(
            f"CNPJ inválido: '{cnpj}'. "
            "Verifique o formato e o dígito verificador (ex: '11.222.333/0001-81')."
        )
    cnpj_norm = normalizar_cnpj(cnpj)
    # Loga apenas prefixo para não expor o CNPJ completo em trilhas de observabilidade
    logger.info("tool_consultar_empresa_completa_called", cnpj_prefixo=cnpj_norm[:8] + "****")
    return await _client.get_empresa(cnpj_norm)
