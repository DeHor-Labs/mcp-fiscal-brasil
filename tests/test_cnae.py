from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.cnae.client import CNAEClient


@pytest.fixture
def client():
    return CNAEClient()


@pytest.mark.asyncio
async def test_get_activities_success(client):
    """get_activities usa get_list pois /subclasses (sem codigo) retorna lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        # A API IBGE retorna 'descricao' sem acento
        mock_get.return_value = [{"id": "0111301", "descricao": "Cultivo de arroz"}]
        result = await client.get_activities()
        assert len(result) == 1
        assert result[0].código == "0111301"
        assert result[0].descrição == "Cultivo de arroz"


@pytest.mark.asyncio
async def test_get_activity_success(client):
    """get_activity usa get() pois /subclasses/{code} retorna objeto, nao lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "id": "6201501",
            "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
        }
        result = await client.get_activity("6201501")
        assert result.código == "6201501"
        assert "COMPUTADOR" in result.descrição


@pytest.mark.asyncio
async def test_get_activity_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_activity("9999999")


@pytest.mark.asyncio
async def test_get_classes_success(client):
    """get_classes usa get_list pois /classes (sem codigo) retorna lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [
            {
                "id": "01113",
                "descricao": "Cultivo de cereais",
                "grupo": {"descricao": "Grupo 1", "divisao": {"descricao": "Divisao 1"}},
            }
        ]
        result = await client.get_classes()
        assert len(result) == 1
        assert result[0].código == "01113"
        assert result[0].descrição == "Cultivo de cereais"
        assert result[0].grupo == "Grupo 1"
        assert result[0].divisao == "Divisao 1"


@pytest.mark.asyncio
async def test_get_class_success(client):
    """get_class usa get() pois /classes/{code} retorna objeto, nao lista."""
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "id": "62015",
            "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
            "grupo": {
                "id": "620",
                "descricao": "ATIVIDADES DOS SERVICOS DE TI",
                "divisao": {
                    "id": "62",
                    "descricao": "ATIVIDADES DOS SERVICOS DE TI",
                },
            },
        }
        result = await client.get_class("62015")
        assert result.código == "62015"
        assert "COMPUTADOR" in result.descrição
        assert result.grupo == "ATIVIDADES DOS SERVICOS DE TI"
        assert result.divisao == "ATIVIDADES DOS SERVICOS DE TI"


@pytest.mark.asyncio
async def test_get_class_not_found(client):
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_class("99999")
