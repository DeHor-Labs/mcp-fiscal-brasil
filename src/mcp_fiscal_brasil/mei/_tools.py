"""Registro das ferramentas MEI no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import consultar_status_mei

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas MEI no servidor FastMCP."""

    @app.tool(
        name="consultar_status_mei",
        description=(
            "Consulta o status de MEI (Microempreendedor Individual) e Simples Nacional "
            "de um CNPJ via BrasilAPI. Retorna se a empresa é optante pelo MEI e/ou Simples "
            "Nacional, com as respectivas datas de opção e exclusão quando disponíveis."
        ),
    )
    async def tool_consultar_status_mei(cnpj: str) -> dict[str, Any]:
        """Consulta o status MEI e Simples Nacional de um CNPJ.

        Verifica junto ao Simples Nacional se o CNPJ informado e optante pelo MEI
        (Microempreendedor Individual) e/ou pelo Simples Nacional, retornando as
        datas de opcao e exclusao quando disponiveis.

        Args:
            cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao
                (ex: '11.222.333/0001-81' ou '11222333000181').

        Returns:
            dict com 'cnpj', 'mei' (bool), 'simples_nacional' (bool),
            'data_opcao_mei' e 'data_exclusao_mei' (quando disponiveis).
        """
        cnpj_digits = "".join(c for c in cnpj if c.isdigit())
        if len(cnpj_digits) != 14:
            raise ValueError(
                f"CNPJ inválido: '{cnpj}'. Informe 14 dígitos numéricos (ex: '11.222.333/0001-81' ou '11222333000181')."
            )
        result = await consultar_status_mei(cnpj_digits)
        return result.model_dump(mode="json", exclude_none=True)
