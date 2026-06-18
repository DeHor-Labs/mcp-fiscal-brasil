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
        moeda: Código da moeda ISO 4217 com 3 letras (ex: 'USD', 'EUR'). Padrão: 'USD'.

    Returns:
        PTAXResponse com cotação de compra e venda.

    Raises:
        FiscalValidationError: Se o código de moeda estiver fora do formato ISO 4217.
    """
    logger.info("tool_ptax_data_called", data=str(data), moeda=moeda)
    return await _client.ptax_data(data, moeda)


_INDICES_VALIDOS = {"IPCA", "SELIC"}


async def calcular_correcao_monetaria(
    valor: float,
    data_inicio: date,
    data_fim: date,
    indice: str = "IPCA",
) -> CorrecaoMonetariaResponse:
    """
    Calcula a correção monetária de um valor entre duas datas.

    Args:
        valor: Valor original a ser corrigido (em reais). Deve ser >= 0.
        data_inicio: Data de início da correção.
        data_fim: Data de fim da correção. Deve ser >= data_inicio.
        indice: Índice de correção: 'IPCA' ou 'SELIC'. Padrão: 'IPCA'.

    Returns:
        CorrecaoMonetariaResponse com fator acumulado e valor corrigido.

    Raises:
        FiscalValidationError: Se valor < 0, datas invertidas ou índice inválido.
    """
    from mcp_fiscal_brasil._core import FiscalValidationError

    indice_norm = indice.strip().upper()
    if indice_norm not in _INDICES_VALIDOS:
        raise FiscalValidationError(
            f"Índice de correção inválido: '{indice}'. "
            f"Use um dos seguintes: {', '.join(sorted(_INDICES_VALIDOS))}.",
            field="indice",
            value=indice,
        )
    if valor < 0:
        raise FiscalValidationError(
            f"Valor inválido: {valor}. O valor a corrigir deve ser >= 0.",
            field="valor",
            value=str(valor),
        )
    if data_inicio > data_fim:
        raise FiscalValidationError(
            f"Período inválido: data_inicio ({data_inicio}) é posterior a data_fim ({data_fim}).",
            field="data_inicio",
            value=str(data_inicio),
        )
    logger.info(
        "tool_calcular_correcao_monetaria_called",
        valor=valor,
        data_inicio=str(data_inicio),
        data_fim=str(data_fim),
        indice=indice_norm,
    )
    return await _client.calcular_correcao_monetaria(valor, data_inicio, data_fim, indice_norm)
