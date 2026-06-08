"""Testes das ferramentas de NFSe."""

from __future__ import annotations

import pytest

from mcp_fiscal_brasil.nfse.tools import consultar_nfse


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
