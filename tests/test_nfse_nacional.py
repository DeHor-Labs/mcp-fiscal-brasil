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
    async def test_consultar_por_chave_retorna_none_quando_get_retorna_none(self) -> None:
        """Quando _get retorna None (erro de rede, auth, 404), consultar_por_chave repassa None.

        _get já captura todas as exceções internamente e retorna None. O double try/except
        em consultar_por_chave foi removido pois era caminho morto (Fix 6).
        """
        client = NFSeNacionalClient()
        with patch.object(client, "_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resultado = await client.consultar_por_chave("CHAVE_COM_ERRO")

        assert resultado is None
        mock_get.assert_called_once_with("/nfse/CHAVE_COM_ERRO")


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
        # Fallback deve informar explicitamente a fonte, status e motivo
        assert resultado["fonte"] == "fallback_portal_municipal"
        assert resultado["status"] == "consulta_manual_necessaria"
        assert resultado["api_nacional_motivo"] is not None
        assert "portal_municipio" in resultado

    @pytest.mark.asyncio
    async def test_fallback_estatico_quando_api_nacional_lanca_excecao(self) -> None:
        """Quando o cliente da API lança exceção de indisponibilidade, cai no fallback."""
        from mcp_fiscal_brasil.nfse.client import NFSeNacionalUnavailableError

        with patch("mcp_fiscal_brasil.nfse.tools.NFSeNacionalClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.consultar_por_chave = AsyncMock(
                side_effect=NFSeNacionalUnavailableError("status=503 path=/nfse/55555")
            )
            mock_client_class.return_value = mock_instance

            resultado = await consultar_nfse(
                numero="55555",
                municipio="Belo Horizonte",
                uf="MG",
            )

        assert resultado["numero"] == "55555"
        assert resultado["fonte"] == "fallback_portal_municipal"
        assert resultado["status"] == "consulta_manual_necessaria"
        assert resultado["api_nacional_motivo"] is not None
        assert "indisponível" in resultado["api_nacional_motivo"]

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
