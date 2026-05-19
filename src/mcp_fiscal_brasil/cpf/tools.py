"""Ferramentas MCP para CPF."""

from .client import validate_cpf
from .schemas import CPFValidation


async def validar_cpf_tool(cpf: str) -> CPFValidation:
    """
    Valida o dígito verificador de um CPF brasileiro.

    Não consulta APIs externas - apenas verifica o cálculo matemático.
    A Receita Federal não disponibiliza API pública para consulta de dados de CPF.

    Args:
        cpf: Número do CPF com ou sem formatação (ex: '123.456.789-09' ou '12345678909')

    Returns:
        CPFValidation indicando se o CPF é matematicamente válido.
    """
    return validate_cpf(cpf)
