"""Funções de tool para o módulo IBGE."""

import re

from mcp_fiscal_brasil._core import FiscalValidationError, get_logger

from .client import IBGEClient
from .schemas import Estado, Municipio

logger = get_logger(__name__)

_client = IBGEClient()

_UF_PATTERN = re.compile(r"^[A-Z]{2}$")

_UFS_BRASILEIRAS = {
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
}


def _validar_uf(uf: str, field: str = "uf") -> str:
    """Sanitiza e valida uma sigla de UF brasileira. Retorna a sigla em maiúsculo."""
    uf_norm = uf.strip().upper()
    if not _UF_PATTERN.match(uf_norm) or uf_norm not in _UFS_BRASILEIRAS:
        raise FiscalValidationError(
            f"Sigla de UF inválida: '{uf}'. "
            f"Informe uma sigla válida de estado brasileiro (ex: 'GO', 'SP', 'RJ').",
            field=field,
            value=uf,
        )
    return uf_norm


async def consultar_municipios_ibge(uf: str | None = None) -> list[Municipio]:
    """
    Consulta municípios brasileiros, opcionalmente filtrados por UF.

    Args:
        uf: Sigla do estado com 2 letras (ex: 'GO', 'SP'). Se omitida, retorna todos.

    Returns:
        Lista de Municipio com id, nome, microrregião e estado.

    Raises:
        FiscalValidationError: Se a sigla de UF for inválida.
    """
    uf_norm = _validar_uf(uf) if uf is not None else None
    logger.info("tool_consultar_municipios_ibge_called", uf=uf_norm)
    return await _client.get_municipalities(uf_norm)


async def consultar_estado_ibge(uf: str) -> Estado:
    """
    Consulta os dados de um estado brasileiro pela sigla da UF.

    Args:
        uf: Sigla do estado com 2 letras (ex: 'GO', 'SP', 'RJ').

    Returns:
        Estado com id, sigla, nome e região.

    Raises:
        FiscalValidationError: Se a sigla de UF for inválida.
    """
    uf_norm = _validar_uf(uf)
    logger.info("tool_consultar_estado_ibge_called", uf=uf_norm)
    return await _client.get_state(uf_norm)
