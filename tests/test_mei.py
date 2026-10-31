from unittest.mock import MagicMock, patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.mei.client import MEIClient
from mcp_fiscal_brasil.mei.schemas import MEIStatus


@pytest.fixture
def client() -> MEIClient:
    return MEIClient()


@pytest.fixture
def cnpj_digits(cnpj_valido: str) -> str:
    return "".join(c for c in cnpj_valido if c.isdigit())


@pytest.mark.asyncio
async def test_get_mei_status_success(client: MEIClient, cnpj_digits: str) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "opcao_pelo_mei": True,
            "opcao_pelo_simples": True,
            "data_opcao_pelo_mei": "2021-03-15",
        }
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is True
        assert result.simples_nacional is True
        assert result.fonte_confirmada is True
        mock_get.assert_called_once()
        assert "/cnpj/v1/" in mock_get.call_args.args[0]


@pytest.mark.asyncio
async def test_get_mei_status_fallback_simples_apos_404_cnpj(
    client: MEIClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = [
            FiscalHTTPError("Not found", 404, "http://test/cnpj"),
            {"simples": {"optante": False}, "simei": {"optante": False}},
        ]
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is False
        assert result.simples_nacional is False
        assert result.fonte_confirmada is True
        assert mock_get.call_count == 2
        assert "/simples/v1/" in mock_get.call_args_list[1].args[0]


@pytest.mark.asyncio
async def test_get_mei_status_404_ambos_endpoints_nao_confirmado(
    client: MEIClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is None
        assert result.simples_nacional is None
        assert result.fonte_confirmada is False
        assert result.cnpj == cnpj_digits
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_get_mei_status_usa_cnpj_opcao_pelo_mei(
    client: MEIClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "opcao_pelo_mei": True,
            "data_opcao_pelo_mei": "2021-03-15",
            "opcao_pelo_simples": True,
        }
        result = await client.get_mei_status(cnpj_digits)
        assert isinstance(result, MEIStatus)
        assert result.mei is True
        assert result.simples_nacional is True
        assert result.fonte_confirmada is True
        assert result.data_opcao_mei is not None


@pytest.mark.asyncio
async def test_get_mei_status_cnpj_opcao_null_nao_confirmado(
    client: MEIClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"opcao_pelo_mei": None, "opcao_pelo_simples": None}
        result = await client.get_mei_status(cnpj_digits)
        assert result.mei is None
        assert result.simples_nacional is None
        assert result.fonte_confirmada is False


@pytest.mark.asyncio
async def test_get_mei_status_cnpj_invalido_nao_bate_na_api(
    client: MEIClient, cnpj_invalido: str
) -> None:
    with patch.object(MEIClient, "_http_client", new=MagicMock()) as mock_http_client:
        with pytest.raises(FiscalNotFoundError):
            await client.get_mei_status(cnpj_invalido)
        mock_http_client.assert_not_called()
