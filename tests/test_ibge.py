from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.ibge.client import IBGEClient


@pytest.fixture
def client():
    return IBGEClient()


@pytest.mark.asyncio
async def test_get_states_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [{"id": 35, "sigla": "SP", "nome": "São Paulo"}]
        result = await client.get_states()
        assert len(result) == 1
        assert result[0].sigla == "SP"


@pytest.mark.asyncio
async def test_get_state_success(client):
    """get_state usa get() pois /estados/{uf} retorna objeto, nao lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "id": 35,
            "sigla": "SP",
            "nome": "São Paulo",
            "regiao": {"id": 3, "sigla": "SE", "nome": "Sudeste"},
        }
        result = await client.get_state("SP")
        assert result.sigla == "SP"
        assert result.nome == "São Paulo"
        assert result.regiao == "Sudeste"


@pytest.mark.asyncio
async def test_get_state_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_state("XX")


@pytest.mark.asyncio
async def test_get_municipalities_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [{"id": 3550308, "nome": "São Paulo"}]
        result = await client.get_municipalities("SP")
        assert len(result) == 1
        assert result[0].id == 3550308


@pytest.mark.asyncio
async def test_get_municipality_success(client):
    """get_municipality usa get() pois /municipios/{code} retorna objeto, nao lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "id": 3550308,
            "nome": "São Paulo",
            "microrregiao": {
                "id": 35061,
                "nome": "São Paulo",
                "mesorregiao": {
                    "id": 3515,
                    "nome": "Metropolitana de São Paulo",
                    "UF": {"id": 35, "sigla": "SP", "nome": "São Paulo"},
                },
            },
        }
        result = await client.get_municipality(3550308)
        assert result.id == 3550308
        assert result.nome == "São Paulo"
        assert result.estado == "SP"


@pytest.mark.asyncio
async def test_get_municipality_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_municipality(9999999)
