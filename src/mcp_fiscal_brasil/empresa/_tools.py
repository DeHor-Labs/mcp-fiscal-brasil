"""Registro das ferramentas Empresa no servidor MCP."""

from __future__ import annotations

from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import consultar_empresa_completa

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas Empresa no servidor FastMCP."""

    @app.tool(
        name="consultar_empresa_completa",
        description=(
            "Consulta dados enriquecidos de uma empresa brasileira combinando informações "
            "da Receita Federal (CNPJ) e do Simples Nacional em uma única chamada. "
            "Retorna razão social, situação cadastral, porte, regime tributário (MEI/Simples), "
            "CNAE principal e secundárias, endereço e natureza jurídica."
        ),
    )
    async def tool_consultar_empresa_completa(cnpj: str) -> dict[str, Any]:
        """Consulta dados completos e enriquecidos de uma empresa pelo CNPJ.

        Combina em paralelo os dados da Receita Federal (razao social, CNAE, endereco, QSA)
        com a situacao no Simples Nacional (MEI, optante Simples). Ideal para due diligence,
        cadastro de fornecedores e analise de regime tributario.

        Args:
            cnpj: Numero do CNPJ com 14 digitos, com ou sem formatacao
                (ex: '11.222.333/0001-81' ou '11222333000181').

        Returns:
            dict com cnpj, razao_social, nome_fantasia, situacao, porte, natureza_juridica,
            simples_nacional, mei, atividade_principal, atividades_secundarias e endereco.
        """
        result = await consultar_empresa_completa(cnpj)
        return result.model_dump(mode="json", exclude_none=True)
