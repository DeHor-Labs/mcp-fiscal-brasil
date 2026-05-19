from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.cep.client import CEPClient, validate_cep


def test_validate_cep():
    assert validate_cep("01001-000") is True
    assert validate_cep("01001000") is True
    assert validate_cep("01001") is False


@pytest.fixture
def client():
    return CEPClient()


@pytest.mark.asyncio
async def test_get_address_success(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "cep": "01001000",
            "state": "SP",
            "city": "Sao Paulo",
            "neighborhood": "Se",
            "street": "Praca da Se",
            "service": "viacep",
        }
        result = await client.get_address("01001-000")
        assert result.cep == "01001000"


@pytest.mark.asyncio
async def test_get_address_invalid_format(client):
    with pytest.raises(FiscalNotFoundError):
        await client.get_address("123")


@pytest.mark.asyncio
async def test_get_address_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_address("00000000")
