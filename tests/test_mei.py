from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.mei.client import MEIClient


@pytest.fixture
def client():
    return MEIClient()


@pytest.mark.asyncio
async def test_get_mei_status_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"simples": {"optante": True}, "simei": {"optante": True}}
        result = await client.get_mei_status("123")
        assert result.mei is True
        assert result.simples_nacional is True


@pytest.mark.asyncio
async def test_get_mei_status_fallback_format(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"mei": False, "simples_nacional": False}
        result = await client.get_mei_status("123")
        assert result.mei is False
        assert result.simples_nacional is False


@pytest.mark.asyncio
async def test_get_mei_status_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_mei_status("123")
