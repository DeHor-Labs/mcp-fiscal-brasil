"""Registro das ferramentas CEP no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import consultar_cep

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas CEP no servidor FastMCP."""

    @app.tool(
        name="consultar_cep",
        description=(
            "Consulta o endereço completo a partir de um CEP brasileiro. "
            "Retorna logradouro, bairro, cidade, estado e serviço de origem. "
            "Aceita CEP com ou sem hífen (ex: '01001-000' ou '01001000')."
        ),
    )
    async def tool_consultar_cep(cep: str) -> dict[str, Any]:
        """Consulta o endereco completo de um CEP brasileiro via BrasilAPI.

        Busca os dados de logradouro, bairro, cidade e estado correspondentes
        ao CEP informado. Util para preenchimento de cadastros e validacao de enderecos.

        Args:
            cep: CEP com 8 digitos, com ou sem hifen (ex: '01001-000' ou '01001000').

        Returns:
            dict com cep, state, city, neighborhood, street e service (fonte dos dados).
        """
        from mcp_fiscal_brasil._core import FiscalValidationError

        cep_digits = "".join(c for c in cep if c.isdigit())
        if len(cep_digits) != 8:
            raise FiscalValidationError(
                f"CEP inválido: '{cep}'. Informe 8 dígitos numéricos (ex: '01001-000' ou '01001000').",
                field="cep",
                value=cep,
            )
        result = await consultar_cep(cep_digits)
        return result.model_dump(mode="json", exclude_none=True)
