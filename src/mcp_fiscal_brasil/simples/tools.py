"""Ferramentas MCP para Simples Nacional."""

from ..shared.exceptions import ValidationError
from ..shared.validators import validate_cnpj
from .client import SimplesClient
from .schemas import SimplesStatus

_client = SimplesClient()


async def consultar_simples_nacional(cnpj: str) -> SimplesStatus:
    """
    Consulta se uma empresa é optante do Simples Nacional ou MEI.

    Args:
        cnpj: CNPJ da empresa (com ou sem formatação)

    Returns:
        SimplesStatus com situação no Simples e MEI, incluindo datas de opção/exclusão.

    Raises:
        ValidationError: Se o CNPJ for inválido.
        NotFoundError: Se o CNPJ não for encontrado.
        APIError: Em caso de falha na API.
    """
    if not validate_cnpj(cnpj):
        raise ValidationError(
            field="cnpj",
            value=cnpj,
            reason="CNPJ inválido. Verifique os 14 dígitos e o dígito verificador.",
        )
    return await _client.get_simples_status(cnpj)
