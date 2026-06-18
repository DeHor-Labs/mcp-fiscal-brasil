"""Funções de tool para o módulo MEI."""

from mcp_fiscal_brasil._core import get_logger
from mcp_fiscal_brasil.shared.validators import normalizar_cnpj, validate_cnpj_qualquer

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

    Raises:
        ValueError: Se o CNPJ for inválido ou tiver formato incorreto.
    """
    if not validate_cnpj_qualquer(cnpj):
        raise ValueError(
            f"CNPJ inválido: '{cnpj}'. "
            "Verifique o formato e o dígito verificador (ex: '11.222.333/0001-81')."
        )
    cnpj_norm = normalizar_cnpj(cnpj)
    logger.info("tool_consultar_status_mei_called", cnpj_prefixo=cnpj_norm[:8] + "****")
    return await _client.get_mei_status(cnpj_norm)
