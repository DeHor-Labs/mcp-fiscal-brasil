"""Registro das ferramentas IBGE no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import consultar_estado_ibge, consultar_municipios_ibge

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas IBGE no servidor FastMCP."""

    @app.tool(
        name="consultar_municipios_ibge",
        description=(
            "Consulta municípios brasileiros via API IBGE Localidades. "
            "Opcionalmente filtra por UF (sigla do estado). "
            "Retorna id, nome, microrregião e estado de cada município."
        ),
    )
    async def tool_consultar_municipios_ibge(
        uf: str | None = None,
    ) -> list[dict[str, Any]]:
        """Consulta municipios brasileiros via API IBGE Localidades.

        Retorna a lista completa de municipios do Brasil ou apenas os de um estado
        especifico quando a sigla da UF for informada.

        Args:
            uf: Sigla do estado (ex: 'GO', 'SP'). Se omitida, retorna todos os municipios.

        Returns:
            Lista de dicts com 'id', 'nome', 'microrregiao' e 'estado'.
        """
        result = await consultar_municipios_ibge(uf)
        return [item.model_dump(mode="json", exclude_none=True) for item in result]

    @app.tool(
        name="consultar_estado_ibge",
        description=(
            "Consulta os dados de um estado brasileiro pela sigla da UF via API IBGE. "
            "Retorna id, sigla, nome oficial e região geográfica do estado."
        ),
    )
    async def tool_consultar_estado_ibge(uf: str) -> dict[str, Any]:
        """Consulta os dados de um estado (UF) via API IBGE Localidades.

        Retorna as informacoes cadastrais do estado informado, incluindo
        codigo IBGE, sigla, nome oficial e regiao geografica.

        Args:
            uf: Sigla do estado (ex: 'GO', 'SP', 'RJ').

        Returns:
            dict com 'id', 'sigla', 'nome' e 'regiao' do estado.
        """
        result = await consultar_estado_ibge(uf)
        return result.model_dump(mode="json", exclude_none=True)
