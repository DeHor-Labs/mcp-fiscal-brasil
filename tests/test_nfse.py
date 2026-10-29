"""Testes das ferramentas de NFSe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_fiscal_brasil.nfse.tools import (
    consultar_cobertura_nfse,
    consultar_nfse,
    validar_chave_nfse,
)


@pytest.mark.asyncio
async def test_consultar_nfse_normaliza_entrada() -> None:
    resultado = await consultar_nfse(
        numero=" 123 ",
        municipio=" São Paulo ",
        uf=" sp ",
        cnpj_prestador="33.000.167/0001-01",
    )

    assert resultado["numero"] == "123"
    assert resultado["municipio"] == "São Paulo"
    assert resultado["uf"] == "SP"
    assert resultado["status"] == "consulta_manual_necessaria"
    assert "Notaas" in resultado["alternativa"]


@pytest.mark.asyncio
async def test_consultar_nfse_aceita_cnpj_alfanumerico() -> None:
    resultado = await consultar_nfse(
        numero="123",
        municipio="São Paulo",
        uf="SP",
        cnpj_prestador="AB.123.CD0/0001-08",
    )
    assert resultado["cnpj_prestador"] == "AB123CD0000108"


@pytest.mark.asyncio
async def test_consultar_nfse_municipio_com_acento_encontra_portal() -> None:
    with patch("mcp_fiscal_brasil.nfse.tools.NFSeNacionalClient") as mock_client_class:
        client = MagicMock()
        client.consultar_por_chave = AsyncMock(return_value=None)
        mock_client_class.return_value = client

        resultado = await consultar_nfse(numero="123", municipio="Goiânia", uf="GO")

    assert resultado["portal_municipio"] == "https://nfse.goiania.go.gov.br/"
    assert resultado["sistema_nfse"] == "ABRASF"


@pytest.mark.asyncio
async def test_consultar_nfse_rejeita_entrada_invalida() -> None:
    with pytest.raises(ValueError, match="numero é obrigatório"):
        await consultar_nfse(numero=" ", municipio="São Paulo", uf="SP")

    with pytest.raises(ValueError, match="uf deve ser uma sigla"):
        await consultar_nfse(numero="123", municipio="São Paulo", uf="S1")

    with pytest.raises(ValueError, match="cnpj_prestador inválido"):
        await consultar_nfse(
            numero="123",
            municipio="São Paulo",
            uf="SP",
            cnpj_prestador="12.345.678/0001-90",
        )


@pytest.mark.asyncio
async def test_validar_chave_nfse_valida_e_decompoe() -> None:
    chave = "35497062241403505000184000000000014226073345639378"
    resultado = await validar_chave_nfse(chave)

    assert resultado["válido"] is True
    assert resultado["codigo_municipio"] == "3549706"
    assert resultado["uf"] == "SP"
    assert resultado["tipo_inscricao"] == "2"
    assert resultado["inscricao_federal"] == "41403505000184"
    assert resultado["cnpj_prestador"] == "41403505000184"
    assert resultado["número"] == "0000000000142"
    assert resultado["ano_mes_emissao"] == "07/26"
    assert resultado["digito_verificador"] == "8"


@pytest.mark.asyncio
async def test_validar_chave_nfse_invalida_retorna_falso() -> None:
    chave_dv_errado = "35497062241403505000184000000000014226073345639370"
    resultado = await validar_chave_nfse(chave_dv_errado)

    assert resultado["válido"] is False
    assert resultado["chave_formatada"] is None


@pytest.mark.asyncio
async def test_consultar_cobertura_nfse_fallback_local() -> None:
    from mcp_fiscal_brasil._core import FiscalHTTPError

    with patch(
        "mcp_fiscal_brasil.nfse.tools.notaas_provider.consultar_cobertura_cidades",
        new_callable=AsyncMock,
        side_effect=FiscalHTTPError(
            "offline", status_code=503, url="https://platform.notaas.com.br"
        ),
    ):
        resultado = await consultar_cobertura_nfse(municipio="São Paulo", uf="SP")

    assert resultado["fonte"] == "fallback_catalogo_local"
    assert resultado["total"] == 1
    assert resultado["municipios"][0]["sistema_nfse"] == "ABRASF"


@pytest.mark.asyncio
async def test_consultar_cobertura_nfse_fallback_local_municipio_ausente() -> None:
    from mcp_fiscal_brasil._core import FiscalHTTPError

    with patch(
        "mcp_fiscal_brasil.nfse.tools.notaas_provider.consultar_cobertura_cidades",
        new_callable=AsyncMock,
        side_effect=FiscalHTTPError(
            "offline", status_code=503, url="https://platform.notaas.com.br"
        ),
    ):
        resultado = await consultar_cobertura_nfse(municipio="Cidade Inexistente XYZ", uf="SP")

    assert resultado["fonte"] == "fallback_catalogo_local"
    assert resultado["total"] == 0
    assert resultado["municipios"] == []
    assert "motivo" in resultado
