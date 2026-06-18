"""Testes para os módulos do Lote C: CEP, CNAE, IBGE, MEI e Empresa (tools + _tools)."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_fiscal_brasil.cep.schemas import Endereco
from mcp_fiscal_brasil.cep.tools import consultar_cep
from mcp_fiscal_brasil.cnae.schemas import CNAEActivity
from mcp_fiscal_brasil.cnae.tools import buscar_cnae, consultar_cnae
from mcp_fiscal_brasil.empresa.schemas import EmpresaInfo
from mcp_fiscal_brasil.empresa.tools import consultar_empresa_completa
from mcp_fiscal_brasil.ibge.schemas import Estado, Municipio
from mcp_fiscal_brasil.ibge.tools import consultar_estado_ibge, consultar_municipios_ibge
from mcp_fiscal_brasil.mei.schemas import MEIStatus
from mcp_fiscal_brasil.mei.tools import consultar_status_mei

# ---------------------------------------------------------------------------
# CEP tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_cep_delega_ao_client() -> None:
    esperado = Endereco(
        cep="74001970",
        state="GO",
        city="Goiânia",
        neighborhood="Centro",
        street="Avenida Goiás",
    )
    with patch(
        "mcp_fiscal_brasil.cep.tools._client.get_address",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_cep("74001-970")

    assert result.cep == "74001970"
    assert result.state == "GO"


# ---------------------------------------------------------------------------
# CNAE tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_cnae_delega_ao_client() -> None:
    esperado = CNAEActivity(
        código="6201501", descrição="Desenvolvimento de programas de computador sob encomenda"
    )
    with patch(
        "mcp_fiscal_brasil.cnae.tools._client.get_activity",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_cnae("6201501")

    assert result.código == "6201501"


@pytest.mark.asyncio
async def test_buscar_cnae_delega_ao_client() -> None:
    esperado = [
        CNAEActivity(
            código="6201501", descrição="Desenvolvimento de programas de computador sob encomenda"
        ),
        CNAEActivity(
            código="6202300",
            descrição="Desenvolvimento e licenciamento de programas de computador customizáveis",
        ),
    ]
    with patch(
        "mcp_fiscal_brasil.cnae.tools._client.get_activities",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await buscar_cnae("software")

    assert len(result) == 2
    assert result[0].código == "6201501"


# ---------------------------------------------------------------------------
# IBGE tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_municipios_ibge_sem_uf() -> None:
    esperado = [
        Municipio(id=5208707, nome="Goiânia"),
        Municipio(id=3550308, nome="São Paulo"),
    ]
    with patch(
        "mcp_fiscal_brasil.ibge.tools._client.get_municipalities",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_municipios_ibge()

    assert len(result) == 2


@pytest.mark.asyncio
async def test_consultar_municipios_ibge_com_uf() -> None:
    esperado = [Municipio(id=5208707, nome="Goiânia", estado="GO")]
    with patch(
        "mcp_fiscal_brasil.ibge.tools._client.get_municipalities",
        new_callable=AsyncMock,
        return_value=esperado,
    ) as mock:
        result = await consultar_municipios_ibge("GO")

    mock.assert_called_once_with("GO")
    assert result[0].nome == "Goiânia"


@pytest.mark.asyncio
async def test_consultar_estado_ibge_retorna_estado() -> None:
    esperado = Estado(id=52, sigla="GO", nome="Goiás", regiao="Centro-Oeste")
    with patch(
        "mcp_fiscal_brasil.ibge.tools._client.get_state",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_estado_ibge("GO")

    assert result.sigla == "GO"
    assert result.regiao == "Centro-Oeste"


# ---------------------------------------------------------------------------
# MEI tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_status_mei_retorna_status() -> None:
    esperado = MEIStatus(cnpj="11222333000181", mei=True, simples_nacional=True)
    with patch(
        "mcp_fiscal_brasil.mei.tools._client.get_mei_status",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_status_mei("11222333000181")

    assert result.mei is True
    assert result.simples_nacional is True


@pytest.mark.asyncio
async def test_consultar_status_mei_nao_optante() -> None:
    # CNPJ válido (dígitos verificadores corretos) diferente do optante
    cnpj_nao_optante = "11222333000262"
    esperado = MEIStatus(cnpj=cnpj_nao_optante, mei=False, simples_nacional=False)
    with patch(
        "mcp_fiscal_brasil.mei.tools._client.get_mei_status",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_status_mei(cnpj_nao_optante)

    assert result.mei is False


# ---------------------------------------------------------------------------
# Empresa tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_empresa_completa_retorna_info() -> None:
    esperado = EmpresaInfo(
        cnpj="11222333000181",
        razao_social="Empresa Teste Ltda",
        situacao="ATIVA",
        natureza_juridica="206-2",
        simples_nacional=True,
        mei=False,
    )
    with patch(
        "mcp_fiscal_brasil.empresa.tools._client.get_empresa",
        new_callable=AsyncMock,
        return_value=esperado,
    ):
        result = await consultar_empresa_completa("11222333000181")

    assert result.razao_social == "Empresa Teste Ltda"
    assert result.simples_nacional is True
    assert result.mei is False


# ---------------------------------------------------------------------------
# Smoke test: register() cria ferramentas sem erro
# ---------------------------------------------------------------------------


def test_cep_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.cep._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert "consultar_cep" in calls


def test_bcb_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.bcb._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert set(calls) == {"taxa_selic", "ipca_periodo", "ptax_data", "calcular_correcao_monetaria"}


def test_cnae_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.cnae._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert set(calls) == {"consultar_cnae", "buscar_cnae"}


def test_ibge_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.ibge._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert set(calls) == {"consultar_municipios_ibge", "consultar_estado_ibge"}


def test_mei_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.mei._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert "consultar_status_mei" in calls


def test_empresa_register_nao_levanta_excecao() -> None:
    from mcp_fiscal_brasil.empresa._tools import register

    calls: list[str] = []

    class FakeApp:
        def tool(self, **kwargs):  # type: ignore[override]
            calls.append(kwargs.get("name", ""))

            def decorator(fn):  # type: ignore[return]
                return fn

            return decorator

    register(FakeApp())
    assert "consultar_empresa_completa" in calls
