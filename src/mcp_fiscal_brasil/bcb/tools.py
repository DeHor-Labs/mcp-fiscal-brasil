"""Funções de tool para o módulo BCB."""

from __future__ import annotations

from datetime import date

from mcp_fiscal_brasil._core import get_logger

from .client import BCBClient
from .schemas import CorrecaoMonetariaResponse, PTAXResponse, SerieBCB

logger = get_logger(__name__)

_client = BCBClient()


async def taxa_selic(
    data_inicio: date,
    data_fim: date | None = None,
) -> list[SerieBCB]:
    """
    Consulta a taxa Selic efetiva diária (SGS série 11) para um período.

    Args:
        data_inicio: Data de início do período (inclusive).
        data_fim: Data de fim do período (inclusive). Se omitida, usa a data de hoje.

    Returns:
        Lista de pontos diários com data e taxa Selic em % ao dia.
    """
    logger.info("tool_taxa_selic_called", data_inicio=str(data_inicio), data_fim=str(data_fim))
    return await _client.taxa_selic(data_inicio, data_fim)


async def ipca_periodo(
    data_inicio: date,
    data_fim: date | None = None,
) -> list[SerieBCB]:
    """
    Consulta o IPCA acumulado mensal (SGS série 433) para um período.

    Args:
        data_inicio: Data de início do período (inclusive).
        data_fim: Data de fim do período (inclusive). Se omitida, usa a data de hoje.

    Returns:
        Lista de pontos mensais com data e variação do IPCA em %.
    """
    logger.info("tool_ipca_periodo_called", data_inicio=str(data_inicio), data_fim=str(data_fim))
    return await _client.ipca_periodo(data_inicio, data_fim)


async def ptax_data(data: date, moeda: str = "USD") -> PTAXResponse:
    """
    Consulta a cotação PTAX (compra/venda) do Banco Central para uma data e moeda.

    Args:
        data: Data da cotação (deve ser dia útil).
        moeda: Código da moeda (ex: 'USD', 'EUR'). Padrão: 'USD'.

    Returns:
        PTAXResponse com cotação de compra e venda.
    """
    logger.info("tool_ptax_data_called", data=str(data), moeda=moeda)
    return await _client.ptax_data(data, moeda)


async def calcular_correcao_monetaria(
    valor: float,
    data_inicio: date,
    data_fim: date,
    indice: str = "IPCA",
) -> CorrecaoMonetariaResponse:
    """
    Calcula a correção monetária de um valor entre duas datas.

    Args:
        valor: Valor original a ser corrigido (em reais).
        data_inicio: Data de início da correção.
        data_fim: Data de fim da correção.
        indice: Índice de correção: 'IPCA' ou 'SELIC'. Padrão: 'IPCA'.

    Returns:
        CorrecaoMonetariaResponse com fator acumulado e valor corrigido.
    """
    logger.info(
        "tool_calcular_correcao_monetaria_called",
        valor=valor,
        data_inicio=str(data_inicio),
        data_fim=str(data_fim),
        indice=indice,
    )
    return await _client.calcular_correcao_monetaria(valor, data_inicio, data_fim, indice)
