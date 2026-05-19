from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.simples.client import SimplesClient


@pytest.fixture
def client():
    return SimplesClient()


@pytest.mark.asyncio
async def test_get_simples_status_success_simples_format(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "simples_nacional": True,
            "mei": False,
            "data_opcao_simples": "2020-01-01",
        }
        result = await client.get_simples_status("123")
        assert result.simples_nacional is True
        assert result.mei is False
        assert result.data_opcao is not None


@pytest.mark.asyncio
async def test_get_simples_status_success_brasilapi_format(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "simples": {"optante": True, "data_opcao": "2020-01-01"},
            "simei": {"optante": True, "data_opcao": "2020-01-01"},
        }
        result = await client.get_simples_status("123")
        assert result.simples_nacional is True
        assert result.mei is True


@pytest.mark.asyncio
async def test_get_simples_status_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_simples_status("123")
