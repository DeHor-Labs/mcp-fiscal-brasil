"""Testes para o módulo BCB (Banco Central do Brasil)."""

from datetime import date
from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.bcb.client import BCBClient
from mcp_fiscal_brasil.bcb.schemas import CorrecaoMonetariaResponse, PTAXResponse, SerieBCB


@pytest.fixture
def client() -> BCBClient:
    return BCBClient()


# ---------------------------------------------------------------------------
# taxa_selic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_taxa_selic_retorna_serie(client: BCBClient) -> None:
    payload = [
        {"data": "01/01/2024", "valor": "0.085894"},
        {"data": "02/01/2024", "valor": "0.085894"},
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.taxa_selic(date(2024, 1, 1), date(2024, 1, 2))

    assert len(result) == 2
    assert isinstance(result[0], SerieBCB)
    assert result[0].data == date(2024, 1, 1)
    assert result[0].valor == pytest.approx(0.085894)


@pytest.mark.asyncio
async def test_taxa_selic_sem_data_fim_usa_hoje(client: BCBClient) -> None:
    payload = [{"data": "01/01/2024", "valor": "0.085894"}]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.taxa_selic(date(2024, 1, 1))

    assert len(result) == 1


@pytest.mark.asyncio
async def test_taxa_selic_sem_dados_levanta_not_found(client: BCBClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=[]):
        with pytest.raises(FiscalNotFoundError):
            await client.taxa_selic(date(2024, 1, 1), date(2024, 1, 1))


@pytest.mark.asyncio
async def test_taxa_selic_http_404_levanta_not_found(client: BCBClient) -> None:
    with patch(
        "mcp_fiscal_brasil._core.http.HTTPClient.get_list",
        side_effect=FiscalHTTPError("Not found", 404, "http://test"),
    ):
        with pytest.raises(FiscalNotFoundError):
            await client.taxa_selic(date(2024, 1, 1))


# ---------------------------------------------------------------------------
# ipca_periodo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ipca_periodo_retorna_serie(client: BCBClient) -> None:
    payload = [
        {"data": "01/01/2024", "valor": "0,42"},
        {"data": "01/02/2024", "valor": "0,83"},
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.ipca_periodo(date(2024, 1, 1), date(2024, 2, 1))

    assert len(result) == 2
    assert result[1].valor == pytest.approx(0.83)


@pytest.mark.asyncio
async def test_ipca_periodo_ignora_entradas_invalidas(client: BCBClient) -> None:
    payload = [
        {"data": "01/01/2024", "valor": "0,42"},
        {"data": "", "valor": ""},  # entrada inválida, deve ser ignorada
        {"data": "01/03/2024", "valor": "0,55"},
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.ipca_periodo(date(2024, 1, 1), date(2024, 3, 1))

    assert len(result) == 2


# ---------------------------------------------------------------------------
# ptax_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ptax_data_retorna_cotacao(client: BCBClient) -> None:
    payload = {"value": [{"cotacaoCompra": 4.9500, "cotacaoVenda": 4.9506}]}
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get", return_value=payload):
        result = await client.ptax_data(date(2024, 1, 2), "USD")

    assert isinstance(result, PTAXResponse)
    assert result.moeda == "USD"
    assert result.compra == pytest.approx(4.9500)
    assert result.venda == pytest.approx(4.9506)


@pytest.mark.asyncio
async def test_ptax_data_sem_cotacao_levanta_not_found(client: BCBClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get", return_value={"value": []}):
        with pytest.raises(FiscalNotFoundError):
            await client.ptax_data(date(2024, 1, 6), "USD")  # sábado sem cotação


@pytest.mark.asyncio
async def test_ptax_data_http_404_levanta_not_found(client: BCBClient) -> None:
    with patch(
        "mcp_fiscal_brasil._core.http.HTTPClient.get",
        side_effect=FiscalHTTPError("Not found", 404, "http://test"),
    ):
        with pytest.raises(FiscalNotFoundError):
            await client.ptax_data(date(2024, 1, 2), "EUR")


# ---------------------------------------------------------------------------
# calcular_correcao_monetaria
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calcular_correcao_monetaria_ipca(client: BCBClient) -> None:
    # Dois meses de IPCA: 0,42% e 0,83%
    payload = [
        {"data": "01/01/2024", "valor": "0,42"},
        {"data": "01/02/2024", "valor": "0,83"},
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.calcular_correcao_monetaria(
            valor=1000.0,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 2, 1),
            indice="IPCA",
        )

    assert isinstance(result, CorrecaoMonetariaResponse)
    assert result.valor_original == 1000.0
    assert result.indice == "IPCA"
    # fator = (1 + 0.0042) * (1 + 0.0083) = 1.01253486
    assert result.fator_acumulado == pytest.approx(1.01253486, rel=1e-4)
    assert result.valor_corrigido == pytest.approx(1012.53, rel=1e-3)


@pytest.mark.asyncio
async def test_calcular_correcao_monetaria_selic(client: BCBClient) -> None:
    payload = [{"data": "01/01/2024", "valor": "0.085894"}]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list", return_value=payload):
        result = await client.calcular_correcao_monetaria(
            valor=500.0,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 1),
            indice="SELIC",
        )

    assert result.indice == "SELIC"
    assert result.valor_original == 500.0


@pytest.mark.asyncio
async def test_calcular_correcao_monetaria_indice_invalido(client: BCBClient) -> None:
    with pytest.raises(ValueError, match="não suportado"):
        await client.calcular_correcao_monetaria(
            valor=100.0,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 1, 1),
            indice="IGP-M",
        )


# ---------------------------------------------------------------------------
# Validação de boundary nas tools (calcular_correcao_monetaria e ptax_data)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correcao_monetaria_valor_negativo_levanta_erro() -> None:
    from mcp_fiscal_brasil._core import FiscalValidationError
    from mcp_fiscal_brasil.bcb.tools import calcular_correcao_monetaria

    with pytest.raises(FiscalValidationError, match="valor"):
        await calcular_correcao_monetaria(
            valor=-100.0,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 3, 1),
        )


@pytest.mark.asyncio
async def test_correcao_monetaria_datas_invertidas_levanta_erro() -> None:
    from mcp_fiscal_brasil._core import FiscalValidationError
    from mcp_fiscal_brasil.bcb.tools import calcular_correcao_monetaria

    with pytest.raises(FiscalValidationError, match="data_inicio"):
        await calcular_correcao_monetaria(
            valor=100.0,
            data_inicio=date(2024, 6, 1),
            data_fim=date(2024, 1, 1),
        )


@pytest.mark.asyncio
async def test_correcao_monetaria_indice_invalido_levanta_erro() -> None:
    from mcp_fiscal_brasil._core import FiscalValidationError
    from mcp_fiscal_brasil.bcb.tools import calcular_correcao_monetaria

    with pytest.raises(FiscalValidationError, match="IGP-M"):
        await calcular_correcao_monetaria(
            valor=100.0,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 3, 1),
            indice="IGP-M",
        )


@pytest.mark.asyncio
async def test_ptax_moeda_invalida_levanta_erro() -> None:
    from mcp_fiscal_brasil._core import FiscalValidationError
    from mcp_fiscal_brasil.bcb.tools import ptax_data

    with pytest.raises(FiscalValidationError, match="moeda"):
        await ptax_data(date(2024, 1, 2), moeda="DOLAR")


@pytest.mark.asyncio
async def test_ptax_moeda_com_numeros_levanta_erro() -> None:
    from mcp_fiscal_brasil._core import FiscalValidationError
    from mcp_fiscal_brasil.bcb.tools import ptax_data

    with pytest.raises(FiscalValidationError, match="moeda"):
        await ptax_data(date(2024, 1, 2), moeda="US1")
