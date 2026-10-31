from unittest.mock import MagicMock, patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.mei.client import MEIClient


@pytest.fixture
def client():
    return MEIClient()


@pytest.fixture
def cnpj_digits(cnpj_valido: str) -> str:
    return "".join(c for c in cnpj_valido if c.isdigit())


@pytest.mark.asyncio
async def test_get_mei_status_success(client, cnpj_digits):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"simples": {"optante": True}, "simei": {"optante": True}}
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is True
        assert result.simples_nacional is True
        assert result.fonte_confirmada is True


@pytest.mark.asyncio
async def test_get_mei_status_fallback_format(client, cnpj_digits):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"mei": False, "simples_nacional": False}
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is False
        assert result.simples_nacional is False


@pytest.mark.asyncio
async def test_get_mei_status_404_nao_optante_nao_e_erro(client, cnpj_digits):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is False
        assert result.simples_nacional is False
        assert result.fonte_confirmada is False
        assert result.cnpj == cnpj_digits


@pytest.mark.asyncio
async def test_get_mei_status_cnpj_invalido_nao_bate_na_api(client, cnpj_invalido):
    with patch.object(MEIClient, "_http_client", new=MagicMock()) as mock_http_client:
        with pytest.raises(FiscalNotFoundError):
            await client.get_mei_status(cnpj_invalido)
        mock_http_client.assert_not_called()
