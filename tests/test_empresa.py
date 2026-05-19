from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalNotFoundError
from mcp_fiscal_brasil.cnpj.schemas import CNPJResponse
from mcp_fiscal_brasil.empresa.client import EmpresaClient
from mcp_fiscal_brasil.simples.schemas import SimplesStatus


@pytest.fixture
def client():
    return EmpresaClient()


@pytest.mark.asyncio
async def test_get_empresa_success(client):
    with (
        patch("mcp_fiscal_brasil.cnpj.client.CNPJClient.consultar") as mock_cnpj,
        patch("mcp_fiscal_brasil.simples.client.SimplesClient.get_simples_status") as mock_simples,
    ):
        mock_cnpj.return_value = CNPJResponse(cnpj="123", razao_social="Teste", situacao_cadastral="ATIVA", origem="ReceitaWS", natureza_juridica="Teste")
        mock_simples.return_value = SimplesStatus(cnpj="123", simples_nacional=True, mei=True)

        result = await client.get_empresa("123")
        assert result.cnpj == "123"
        assert result.razao_social == "Teste"
        assert result.simples_nacional is True
        assert result.mei is True


@pytest.mark.asyncio
async def test_get_empresa_cnpj_not_found(client):
    with (
        patch("mcp_fiscal_brasil.cnpj.client.CNPJClient.consultar") as mock_cnpj,
        patch("mcp_fiscal_brasil.simples.client.SimplesClient.get_simples_status"),
    ):
        mock_cnpj.side_effect = FiscalNotFoundError("Not found", "Resource", "unknown")
        with pytest.raises(FiscalNotFoundError):
            await client.get_empresa("123")


@pytest.mark.asyncio
async def test_get_empresa_simples_fails(client):
    with (
        patch("mcp_fiscal_brasil.cnpj.client.CNPJClient.consultar") as mock_cnpj,
        patch("mcp_fiscal_brasil.simples.client.SimplesClient.get_simples_status") as mock_simples,
    ):
        mock_cnpj.return_value = CNPJResponse(cnpj="123", razao_social="Teste", situacao_cadastral="ATIVA", origem="ReceitaWS", natureza_juridica="Teste")
        mock_simples.side_effect = FiscalNotFoundError("Not found", "Resource", "unknown")

        result = await client.get_empresa("123")
        assert result.cnpj == "123"
        assert result.simples_nacional is False
        assert result.mei is False
