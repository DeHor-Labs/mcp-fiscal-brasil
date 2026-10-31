"""Registro das ferramentas MEI no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import consultar_status_mei, orientar_regularizacao_mei

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas MEI no servidor MCP."""

    @app.tool(
        name="consultar_status_mei",
        description=(
            "Consulta o status de MEI (Microempreendedor Individual) e Simples Nacional "
            "de um CNPJ via BrasilAPI. Retorna se a empresa é optante pelo MEI e/ou Simples "
            "Nacional, com as respectivas datas de opção e exclusão quando disponíveis."
        ),
    )
    async def tool_consultar_status_mei(cnpj: str) -> dict[str, Any]:
        result = await consultar_status_mei(cnpj)
        return result.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="orientar_regularizacao_mei",
        description=(
            "Orienta o fluxo manual de regularização de MEI/Simei abandonado "
            "(e-CAC → PGMEI → DASN-SIMEI → comprovante CNPJ). Não faz login Gov.br; "
            "retorna passos estruturados e URLs oficiais. Use quando o CNPJ estiver "
            "INAPTA por omissão de DASN-SIMEI ou o usuário pedir como regularizar MEI."
        ),
    )
    async def tool_orientar_regularizacao_mei(
        cnpj: str | None = None,
        anos_omitidos: list[int] | None = None,
        receita_zero: bool = True,
    ) -> dict[str, Any]:
        result = await orientar_regularizacao_mei(
            cnpj=cnpj,
            anos_omitidos=anos_omitidos,
            receita_zero=receita_zero,
        )
        return result.model_dump(mode="json", exclude_none=True)
