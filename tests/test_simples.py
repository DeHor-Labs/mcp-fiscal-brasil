from unittest.mock import MagicMock, patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.simples.client import SimplesClient


@pytest.fixture
def client() -> SimplesClient:
    return SimplesClient()


@pytest.fixture
def cnpj_digits(cnpj_valido: str) -> str:
    return "".join(c for c in cnpj_valido if c.isdigit())


@pytest.mark.asyncio
async def test_get_simples_status_success_simples_format(
    client: SimplesClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "simples_nacional": True,
            "mei": False,
            "data_opcao_simples": "2020-01-01",
        }
        result = await client.get_simples_status(cnpj_digits)
        assert result.simples_nacional is True
        assert result.mei is False
        assert result.data_opcao is not None


@pytest.mark.asyncio
async def test_get_simples_status_success_brasilapi_format(
    client: SimplesClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "simples": {"optante": True, "data_opcao": "2020-01-01"},
            "simei": {"optante": True, "data_opcao": "2020-01-01"},
        }
        result = await client.get_simples_status(cnpj_digits)
        assert result.simples_nacional is True
        assert result.mei is True


@pytest.mark.asyncio
async def test_get_simples_status_404_ambos_endpoints_nao_confirmado(
    client: SimplesClient, cnpj_digits: str
) -> None:
    """Se /simples e /cnpj retornam 404, fonte_confirmada fica False."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Recurso não encontrado", 404, "http://test")
        result = await client.get_simples_status(cnpj_digits)
        assert result.simples_nacional is False
        assert result.mei is False
        assert result.cnpj == cnpj_digits
        assert result.fonte_confirmada is False
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_get_simples_status_404_simples_usa_cnpj_opcao_pelo_simples(
    client: SimplesClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = [
            FiscalHTTPError("Not found", 404, "http://test/simples"),
            {
                "opcao_pelo_simples": True,
                "data_opcao_pelo_simples": "2020-01-01",
                "opcao_pelo_mei": False,
            },
        ]
        result = await client.get_simples_status(cnpj_digits)
        assert result.simples_nacional is True
        assert result.mei is False
        assert result.fonte_confirmada is True
        assert result.data_opcao is not None


@pytest.mark.asyncio
async def test_get_simples_status_cnpj_opcao_null_nao_confirmado(
    client: SimplesClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = [
            FiscalHTTPError("Not found", 404, "http://test/simples"),
            {"opcao_pelo_simples": None, "opcao_pelo_mei": None},
        ]
        result = await client.get_simples_status(cnpj_digits)
        assert result.simples_nacional is False
        assert result.mei is False
        assert result.fonte_confirmada is False


@pytest.mark.asyncio
async def test_get_simples_status_aceita_cnpj_alfanumerico(client: SimplesClient) -> None:
    """CNPJ alfanumerico (IN RFB 2.229/2024) com DVs validos deve bater na API
    em vez de ser rejeitado localmente como 'invalido'."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {"simples_nacional": True, "mei": False}
        result = await client.get_simples_status("AB123CD0000108")
        assert result.simples_nacional is True
        assert result.cnpj == "AB123CD0000108"
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_simples_status_cnpj_invalido_nao_bate_na_api(
    client: SimplesClient, cnpj_invalido: str
) -> None:
    """CNPJ com digito verificador invalido de fato: FiscalNotFoundError sem
    nenhuma chamada de rede (short-circuit local)."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        with pytest.raises(FiscalNotFoundError):
            await client.get_simples_status(cnpj_invalido)
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_simples_status_erro_500_propaga(
    client: SimplesClient, cnpj_digits: str
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Erro interno do servidor", 500, "http://test")
        with pytest.raises(FiscalHTTPError) as exc_info:
            await client.get_simples_status(cnpj_digits)
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_simples_status_timeout_propaga_como_fiscal_error(
    client: SimplesClient, cnpj_digits: str
) -> None:
    """Timeout ja chega como FiscalHTTPError (status_code=None) via HTTPClient;
    o client de Simples nao deve engolir isso como 'nao encontrado'."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError(
            "Falha de comunicação com serviço externo", None, "http://test"
        )
        with pytest.raises(FiscalHTTPError) as exc_info:
            await client.get_simples_status(cnpj_digits)
        assert exc_info.value.status_code is None


@pytest.mark.asyncio
async def test_get_simples_status_valida_offline_sem_chamar_api(
    client: SimplesClient, cnpj_invalido: str
) -> None:
    """Garante que a validacao roda antes de instanciar/abrir o HTTPClient."""
    with patch.object(SimplesClient, "_http_client", new=MagicMock()) as mock_http_client:
        with pytest.raises(FiscalNotFoundError):
            await client.get_simples_status(cnpj_invalido)
        mock_http_client.assert_not_called()
