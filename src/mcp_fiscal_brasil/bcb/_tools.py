"""Registro das ferramentas BCB no servidor MCP."""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp_fiscal_brasil._core import get_logger

from .tools import calcular_correcao_monetaria, ipca_periodo, ptax_data, taxa_selic

logger = get_logger(__name__)


def register(app: Any) -> None:
    """Registra as ferramentas BCB no servidor FastMCP."""

    @app.tool(
        name="taxa_selic",
        description=(
            "Consulta a taxa Selic efetiva diária do Banco Central do Brasil (BCB/SGS série 11) "
            "para um período. Retorna lista de pontos diários com data e taxa em % ao dia. "
            "Útil para cálculos de juros, correção monetária e análise de política monetária."
        ),
    )
    async def tool_taxa_selic(
        data_inicio: date,
        data_fim: date | None = None,
    ) -> list[dict[str, Any]]:
        """Consulta a taxa Selic efetiva diaria (SGS serie 11) para um periodo.

        Retorna os pontos diarios publicados pelo Banco Central do Brasil no Sistema
        Gerenciador de Series Temporais (SGS). Cada ponto contem a data e a taxa
        percentual ao dia.

        Args:
            data_inicio: Data de inicio do periodo (inclusive), formato YYYY-MM-DD.
            data_fim: Data de fim do periodo (inclusive). Se omitida, usa a data de hoje.

        Returns:
            Lista de dicts com 'data' (YYYY-MM-DD) e 'valor' (taxa % ao dia).
        """
        result = await taxa_selic(data_inicio, data_fim)
        return [item.model_dump(mode="json") for item in result]

    @app.tool(
        name="ipca_periodo",
        description=(
            "Consulta o IPCA (Índice de Preços ao Consumidor Amplo) acumulado mensal "
            "do Banco Central do Brasil (BCB/SGS série 433) para um período. "
            "Retorna variação percentual mensal. Útil para cálculos de inflação e correção monetária."
        ),
    )
    async def tool_ipca_periodo(
        data_inicio: date,
        data_fim: date | None = None,
    ) -> list[dict[str, Any]]:
        """Consulta o IPCA acumulado mensal (SGS serie 433) para um periodo.

        Retorna a variacao percentual mensal do IPCA publicada pelo IBGE e disponibilizada
        no SGS do Banco Central. Frequencia mensal.

        Args:
            data_inicio: Data de inicio do periodo (inclusive), formato YYYY-MM-DD.
            data_fim: Data de fim do periodo (inclusive). Se omitida, usa a data de hoje.

        Returns:
            Lista de dicts com 'data' (YYYY-MM-DD) e 'valor' (variacao % no mes).
        """
        result = await ipca_periodo(data_inicio, data_fim)
        return [item.model_dump(mode="json") for item in result]

    @app.tool(
        name="ptax_data",
        description=(
            "Consulta a cotação PTAX oficial do Banco Central do Brasil (compra e venda) "
            "para uma data e moeda específicas. A PTAX é a taxa de câmbio de referência "
            "usada em contratos e operações cambiais. Só disponível para dias úteis."
        ),
    )
    async def tool_ptax_data(
        data: date,
        moeda: str = "USD",
    ) -> dict[str, Any]:
        """Consulta a cotacao PTAX (compra/venda) do Banco Central para uma data e moeda.

        A PTAX e a cotacao oficial de fechamento do cambio, divulgada pelo BCB via OData.
        Disponivel apenas para dias uteis em que houve pregao cambial.

        Args:
            data: Data da cotacao (deve ser dia util), formato YYYY-MM-DD.
            moeda: Codigo da moeda conforme padrao BCB (ex: 'USD', 'EUR'). Padrao: 'USD'.

        Returns:
            dict com 'data', 'moeda', 'compra' e 'venda' em reais.
        """
        result = await ptax_data(data, moeda)
        return result.model_dump(mode="json")

    @app.tool(
        name="calcular_correcao_monetaria",
        description=(
            "Calcula a correção monetária de um valor entre duas datas usando IPCA ou Selic. "
            "Busca as séries históricas do Banco Central do Brasil e aplica o fator acumulado "
            "ao valor informado. Útil para atualização de dívidas, contratos e obrigações fiscais."
        ),
    )
    async def tool_calcular_correcao_monetaria(
        valor: float,
        data_inicio: date,
        data_fim: date,
        indice: str = "IPCA",
    ) -> dict[str, Any]:
        """Calcula a correcao monetaria de um valor entre duas datas.

        Consulta a serie historica do BCB para o indice solicitado (IPCA ou Selic),
        calcula o fator de correcao acumulado e aplica ao valor original.

        Args:
            valor: Valor original a ser corrigido (em reais).
            data_inicio: Data de inicio da correcao, formato YYYY-MM-DD.
            data_fim: Data de fim da correcao, formato YYYY-MM-DD.
            indice: Indice de correcao: 'IPCA' ou 'SELIC'. Padrao: 'IPCA'.

        Returns:
            dict com valor_original, data_inicio, data_fim, indice, fator_acumulado e valor_corrigido.
        """
        result = await calcular_correcao_monetaria(valor, data_inicio, data_fim, indice)
        return result.model_dump(mode="json")
