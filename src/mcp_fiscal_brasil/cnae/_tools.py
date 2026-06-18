"""Registro das ferramentas CNAE no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import buscar_cnae, consultar_cnae

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas CNAE no servidor FastMCP."""

    @app.tool(
        name="consultar_cnae",
        description=(
            "Consulta uma atividade econômica CNAE pelo código de subclasse (7 dígitos). "
            "Retorna código e descrição oficial da atividade conforme tabela IBGE. "
            "Útil para identificar o ramo de atuação de empresas a partir do código CNAE."
        ),
    )
    async def tool_consultar_cnae(codigo: str) -> dict[str, Any]:
        """Consulta uma atividade economica CNAE pelo codigo de subclasse.

        Busca a descricao oficial da atividade na tabela CNAE do IBGE.
        O codigo de subclasse possui 7 digitos (ex: '6201501' para desenvolvimento de software).

        Args:
            codigo: Codigo da subclasse CNAE com 7 digitos, com ou sem pontuacao.

        Returns:
            dict com 'codigo' e 'descricao' da atividade economica.
        """
        result = await consultar_cnae(codigo)
        return result.model_dump(mode="json")

    @app.tool(
        name="buscar_cnae",
        description=(
            "Busca atividades econômicas CNAE por texto na descrição. "
            "Retorna lista de subclasses que correspondem ao termo pesquisado. "
            "Útil para encontrar o código CNAE a partir do ramo de atividade desejado."
        ),
    )
    async def tool_buscar_cnae(texto: str) -> list[dict[str, Any]]:
        """Busca atividades economicas CNAE por texto na descricao.

        Pesquisa na tabela de subclasses CNAE do IBGE e retorna todas as atividades
        cuja descricao contenha o termo informado.

        Args:
            texto: Termo para busca na descricao das atividades (ex: 'software', 'restaurante').

        Returns:
            Lista de dicts com 'codigo' e 'descricao' das atividades encontradas.
        """
        result = await buscar_cnae(texto)
        return [item.model_dump(mode="json") for item in result]
