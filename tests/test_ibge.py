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
        mock_get.return_value = [{"id": 35, "sigla": "SP", "nome": "Sao Paulo"}]
        result = await client.get_states()
        assert len(result) == 1
        assert result[0].sigla == "SP"


@pytest.mark.asyncio
async def test_get_state_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_state("XX")


@pytest.mark.asyncio
async def test_get_municipalities_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [{"id": 3550308, "nome": "Sao Paulo"}]
        result = await client.get_municipalities("SP")
        assert len(result) == 1
        assert result[0].id == 3550308


@pytest.mark.asyncio
async def test_get_municipality_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [{"id": 3550308, "nome": "Sao Paulo"}]
        result = await client.get_municipality(3550308)
        assert result.id == 3550308
