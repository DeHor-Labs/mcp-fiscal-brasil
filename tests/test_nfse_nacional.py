"""Testes para NFS-e Nacional via API REST (Sistema Nacional NFS-e).

A API Nacional (adn.nfse.gov.br) exige certificado digital ICP-Brasil + mTLS,
portanto os testes usam mocks. O fallback estático deve sempre funcionar.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_fiscal_brasil.nfse.client import NFSeNacionalClient
from mcp_fiscal_brasil.nfse.tools import consultar_nfse


class TestNFSeNacionalClient:
    """Testes unitários do cliente da API Nacional NFS-e."""

    @pytest.mark.asyncio
    async def test_consultar_por_chave_retorna_dados_mock(self) -> None:
        """Quando a API responde com sucesso, retorna dados estruturados."""
        mock_response = {
            "numero": "12345",
            "municipio": "São Paulo",
            "uf": "SP",
            "prestador": {"cnpj": "33000167000101", "razaoSocial": "EMPRESA TESTE LTDA"},
            "valorServico": "1500.00",
            "valorIss": "75.00",
            "aliquotaIss": "5.00",
        }

        client = NFSeNacionalClient()
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            resultado = await client.consultar_por_chave("CHAVE123456789")

        assert resultado is not None
        assert resultado["numero"] == "12345"
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_consultar_por_chave_retorna_none_em_404(self) -> None:
        """Quando a API retorna 404, deve retornar None (aciona fallback)."""
        client = NFSeNacionalClient()
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resultado = await client.consultar_por_chave("CHAVE_INEXISTENTE")

        assert resultado is None

    @pytest.mark.asyncio
    async def test_consultar_por_chave_retorna_none_em_erro(self) -> None:
        """Quando a API lança exceção, deve retornar None (aciona fallback)."""
        client = NFSeNacionalClient()
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Timeout de conexão")
            resultado = await client.consultar_por_chave("CHAVE_COM_ERRO")

        assert resultado is None


class TestConsultarNFSeComFallback:
    """Testes de integração: tentativa API Nacional + fallback estático."""

    @pytest.mark.asyncio
    async def test_fallback_estatico_quando_api_nacional_indisponivel(self) -> None:
        """Quando a API Nacional falha, cai no fallback com orientações manuais."""
        with patch("mcp_fiscal_brasil.nfse.tools.NFSeNacionalClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.consultar_por_chave = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_instance

            resultado = await consultar_nfse(
                numero="99999",
                municipio="São Paulo",
                uf="SP",
            )

        assert resultado["numero"] == "99999"
        assert resultado["municipio"] == "São Paulo"
        assert resultado["uf"] == "SP"
        # Fallback deve informar onde consultar manualmente
        assert "portal_municipio" in resultado or "status" in resultado

    @pytest.mark.asyncio
    async def test_fallback_estatico_quando_api_nacional_lanca_excecao(self) -> None:
        """Quando o cliente da API lança exceção, cai no fallback."""
        with patch("mcp_fiscal_brasil.nfse.tools.NFSeNacionalClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.consultar_por_chave = AsyncMock(side_effect=Exception("Erro de rede"))
            mock_client_class.return_value = mock_instance

            resultado = await consultar_nfse(
                numero="55555",
                municipio="Belo Horizonte",
                uf="MG",
            )

        assert resultado["numero"] == "55555"
        assert "status" in resultado

    @pytest.mark.asyncio
    async def test_api_nacional_quando_retorna_dados(self) -> None:
        """Quando a API Nacional retorna dados, eles são incluídos na resposta."""
        dados_api = {
            "numero": "77777",
            "municipio": "Brasília",
            "uf": "DF",
            "prestador": {"cnpj": "33000167000101", "razaoSocial": "EMPRESA DF LTDA"},
            "valorServico": "2000.00",
        }

        with patch("mcp_fiscal_brasil.nfse.tools.NFSeNacionalClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.consultar_por_chave = AsyncMock(return_value=dados_api)
            mock_client_class.return_value = mock_instance

            resultado = await consultar_nfse(
                numero="77777",
                municipio="Brasília",
                uf="DF",
            )

        assert resultado["numero"] == "77777"
        assert resultado.get("fonte") == "api_nacional"
