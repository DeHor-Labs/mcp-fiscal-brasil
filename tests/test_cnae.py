from unittest.mock import patch

import pytest

from mcp_fiscal_brasil._core.errors import FiscalHTTPError, FiscalNotFoundError
from mcp_fiscal_brasil.cnae.client import CNAEClient
from mcp_fiscal_brasil.cnae.schemas import CNAEActivity


@pytest.fixture
def client() -> CNAEClient:
    return CNAEClient()


@pytest.mark.asyncio
async def test_get_activities_success(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [{"id": "0111301", "descricao": "Cultivo de arroz"}]
        result = await client.get_activities()
        assert len(result) == 1
        assert result[0].código == "0111301"
        assert result[0].descrição == "Cultivo de arroz"
        dumped = result[0].model_dump()
        assert "descricao" in dumped and "descrição" not in dumped
        assert dumped["descricao"] == "Cultivo de arroz"


@pytest.mark.asyncio
async def test_get_activities_filtra_busca_localmente(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = [
            {"id": "4929902", "descricao": "TRANSPORTE RODOVIARIO"},
            {
                "id": "6201501",
                "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
            },
            {"id": "1830003", "descricao": "REPRODUCAO DE SOFTWARE EM QUALQUER SUPORTE"},
        ]
        result = await client.get_activities(search="software")
        assert [item.código for item in result] == ["1830003"]
        assert all(item.descrição for item in result)


@pytest.mark.asyncio
async def test_get_activities_sem_busca_nao_corta_em_50(client: CNAEClient) -> None:
    payload = [
        {"id": f"{i:07d}", "descricao": f"Atividade {i}"} for i in range(60)
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = payload
        result = await client.get_activities()
        assert len(result) == 60


@pytest.mark.asyncio
async def test_get_activities_search_vazio_nao_corta_em_50(client: CNAEClient) -> None:
    payload = [
        {"id": f"{i:07d}", "descricao": f"Atividade {i}"} for i in range(60)
    ]
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_get:
        mock_get.return_value = payload
        result = await client.get_activities(search="")
        assert len(result) == 60
        mock_get.assert_called_once_with("/subclasses", params=None)


def test_cnae_activity_roundtrip_model_dump_validate() -> None:
    activity = CNAEActivity(código="6201501", descrição="Software")
    restored = CNAEActivity.model_validate(activity.model_dump())
    assert restored.código == "6201501"
    assert restored.descrição == "Software"


@pytest.mark.asyncio
async def test_get_activity_lista_invalida_vira_not_found(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError(
            "A resposta não é um objeto JSON válido.", 200, "http://test"
        )
        with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_list:
            mock_list.side_effect = FiscalHTTPError(
                "A resposta não é uma lista JSON válida.", 200, "http://test"
            )
            with pytest.raises(FiscalNotFoundError):
                await client.get_activity("6201501")


@pytest.mark.asyncio
async def test_get_activity_success(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.return_value = {
            "id": "6201501",
            "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
        }
        result = await client.get_activity("6201501")
        assert result.código == "6201501"
        assert "COMPUTADOR" in result.descrição


@pytest.mark.asyncio
async def test_get_activity_aceita_lista_quando_api_devolver_array(
    client: CNAEClient,
) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError(
            "A resposta não é um objeto JSON válido.", 200, "http://test"
        )
        with patch("mcp_fiscal_brasil._core.http.HTTPClient.get_list") as mock_list:
            mock_list.return_value = [
                {
                    "id": "6201501",
                    "descricao": "DESENVOLVIMENTO DE PROGRAMAS DE COMPUTADOR SOB ENCOMENDA",
                }
            ]
            result = await client.get_activity("6201501")
        assert result.código == "6201501"
        assert "COMPUTADOR" in result.descrição


@pytest.mark.asyncio
async def test_get_activity_not_found(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_activity("9999999")


@pytest.mark.asyncio
async def test_get_classes_success(client: CNAEClient) -> None:
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
async def test_get_class_success(client: CNAEClient) -> None:
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
async def test_get_class_not_found(client: CNAEClient) -> None:
    with patch("mcp_fiscal_brasil._core.http.HTTPClient.get") as mock_get:
        mock_get.side_effect = FiscalHTTPError("Not found", 404, "http://test")
        with pytest.raises(FiscalNotFoundError):
            await client.get_class("99999")
