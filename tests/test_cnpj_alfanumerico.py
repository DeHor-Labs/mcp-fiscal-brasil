"""Suporte a CNPJ alfanumérico (IN RFB 2.229/2024) em toda a cadeia de consulta.

Cobre as três entradas (ferramenta MCP, API HTTP e SDK async/sync), a rejeição
de CNPJ alfanumérico com dígito verificador errado e o comportamento dos
provedores públicos: a BrasilAPI atende o formato alfanumérico (proxy para o
minha-receita, que valida com a lib go-cnpj) e a ReceitaWS, sem suporte
documentado, é pulada quando o CNPJ contém letras.
"""

from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from mcp_fiscal_brasil._core import FiscalError, settings
from mcp_fiscal_brasil.api import app
from mcp_fiscal_brasil.cnpj.client import CNPJClient
from mcp_fiscal_brasil.cnpj.schemas import CNPJResponse
from mcp_fiscal_brasil.cnpj.tools import consultar_cnpj
from mcp_fiscal_brasil.sdk import FiscalBrasil
from mcp_fiscal_brasil.shared import cpfcnpj as cpfcnpj_provider
from mcp_fiscal_brasil.shared.exceptions import ValidationError

# CNPJ alfanumérico válido (exemplo oficial da IN RFB 2.229/2024) e sua máscara.
CNPJ_ALFA = "12ABC34501DE35"
CNPJ_ALFA_MASCARA = "12.ABC.345/01DE-35"
CNPJ_ALFA_DV_ERRADO = "12ABC34501DE00"
CNPJ_NUM = "00000000000191"
CNPJ_NUM_MASCARA = "00.000.000/0001-91"

CNPJ_PAYLOAD_ALFA: dict[str, Any] = {"status": 1, "cnpj": CNPJ_ALFA, "razao": "EMPRESA ALFA LTDA"}


class _FakeHTTPClient:
    """HTTPClient falso: registra o path chamado e devolve um corpo fixo, sem rede."""

    payload: ClassVar[dict[str, Any]] = {}
    ultimo_path: ClassVar[str | None] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeHTTPClient":
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        _FakeHTTPClient.ultimo_path = path
        return _FakeHTTPClient.payload


@pytest.fixture
def provedor_habilitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Habilita o provedor premium cpfcnpj.com.br com token de teste e HTTP mockado."""
    monkeypatch.setattr(settings, "cpfcnpj_token", "token_de_teste", raising=False)
    monkeypatch.setattr(cpfcnpj_provider, "HTTPClient", _FakeHTTPClient)
    _FakeHTTPClient.payload = CNPJ_PAYLOAD_ALFA
    _FakeHTTPClient.ultimo_path = None


@pytest.fixture
def provedor_desligado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desliga o provedor premium para exercitar somente as fontes públicas."""
    monkeypatch.setattr(settings, "cpfcnpj_token", "", raising=False)


# ---------------------------------------------------------------------------
# Entrada 1: ferramenta MCP (cnpj/tools.py::consultar_cnpj)
# ---------------------------------------------------------------------------


async def test_tool_alfanumerico_chega_no_provedor(provedor_habilitado: None) -> None:
    resposta = await consultar_cnpj(CNPJ_ALFA_MASCARA)
    assert resposta.origem == "cpfcnpj.com.br"
    # A máscara é removida e as letras preservadas em maiúsculas no caminho da URL.
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/6/{CNPJ_ALFA}"


async def test_tool_alfanumerico_dv_errado_rejeitado() -> None:
    with pytest.raises(ValidationError) as exc_info:
        await consultar_cnpj(CNPJ_ALFA_DV_ERRADO)
    assert exc_info.value.field == "cnpj"


async def test_tool_numerico_formatado_continua_ok(provedor_habilitado: None) -> None:
    await consultar_cnpj(CNPJ_NUM_MASCARA)
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/6/{CNPJ_NUM}"


# ---------------------------------------------------------------------------
# Entrada 2: API HTTP (api.py::_validated_cnpj + /v1/cnpj/{cnpj})
# ---------------------------------------------------------------------------


def test_api_alfanumerico_chega_no_provedor(provedor_habilitado: None) -> None:
    client = TestClient(app)
    response = client.get(f"/v1/cnpj/{CNPJ_ALFA}")
    assert response.status_code == 200
    assert response.json()["origem"] == "cpfcnpj.com.br"
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/6/{CNPJ_ALFA}"


def test_api_alfanumerico_dv_errado_400() -> None:
    from unittest.mock import AsyncMock, patch

    client = TestClient(app)
    with patch("mcp_fiscal_brasil.api.consultar_cnpj", AsyncMock()) as consultar:
        response = client.get(f"/v1/cnpj/{CNPJ_ALFA_DV_ERRADO}")
    assert response.status_code == 400
    consultar.assert_not_called()


# ---------------------------------------------------------------------------
# Entrada 3: SDK (sdk.py::consultar_cnpj async/sync + validar_cnpj)
# ---------------------------------------------------------------------------


async def test_sdk_async_alfanumerico_chega_no_provedor(provedor_habilitado: None) -> None:
    resposta = await FiscalBrasil().consultar_cnpj(CNPJ_ALFA_MASCARA)
    assert resposta.origem == "cpfcnpj.com.br"
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/6/{CNPJ_ALFA}"


async def test_sdk_async_alfanumerico_dv_errado_rejeitado() -> None:
    with pytest.raises(ValueError):
        await FiscalBrasil().consultar_cnpj(CNPJ_ALFA_DV_ERRADO)


def test_sdk_sync_alfanumerico_chega_no_provedor(provedor_habilitado: None) -> None:
    resposta = FiscalBrasil().consultar_cnpj_sync(CNPJ_ALFA_MASCARA)
    assert resposta.origem == "cpfcnpj.com.br"
    assert _FakeHTTPClient.ultimo_path == f"/token_de_teste/6/{CNPJ_ALFA}"


def test_sdk_validar_cnpj_alfanumerico() -> None:
    fiscal = FiscalBrasil()
    assert fiscal.validar_cnpj(CNPJ_ALFA) is True
    assert fiscal.validar_cnpj(CNPJ_ALFA_MASCARA) is True
    assert fiscal.validar_cnpj(CNPJ_ALFA_DV_ERRADO) is False
    # CNPJ numérico continua válido.
    assert fiscal.validar_cnpj(CNPJ_NUM_MASCARA) is True


# ---------------------------------------------------------------------------
# Comportamento dos provedores públicos (BrasilAPI vs ReceitaWS)
# ---------------------------------------------------------------------------


async def test_brasilapi_atende_alfanumerico(
    provedor_desligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    recebidos: list[str] = []

    async def _fake_brasil_api(self: CNPJClient, cnpj: str) -> CNPJResponse:
        recebidos.append(cnpj)
        return CNPJResponse(
            cnpj=cnpj,
            razao_social="EMPRESA BRASILAPI",
            situacao_cadastral="ATIVA",
            natureza_juridica="LTDA",
            origem="BrasilAPI",
        )

    monkeypatch.setattr(CNPJClient, "_consultar_brasil_api", _fake_brasil_api)
    resposta = await CNPJClient().consultar(CNPJ_ALFA_MASCARA)
    assert resposta.origem == "BrasilAPI"
    # A BrasilAPI recebe o CNPJ alfanumérico normalizado (com letras).
    assert recebidos == [CNPJ_ALFA]


async def test_receitaws_pulada_para_alfanumerico(
    provedor_desligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _brasil_api_falha(self: CNPJClient, cnpj: str) -> CNPJResponse:
        raise FiscalError("BrasilAPI indisponível")

    async def _receitaws_nao_deve_ser_chamada(self: CNPJClient, cnpj: str) -> CNPJResponse:
        raise AssertionError("ReceitaWS não deve ser consultada para CNPJ alfanumérico")

    monkeypatch.setattr(CNPJClient, "_consultar_brasil_api", _brasil_api_falha)
    monkeypatch.setattr(CNPJClient, "_consultar_receita_ws", _receitaws_nao_deve_ser_chamada)

    with pytest.raises(FiscalError) as exc_info:
        await CNPJClient().consultar(CNPJ_ALFA)
    assert "alfanumérico" in str(exc_info.value)


async def test_receitaws_fallback_preservado_para_numerico(
    provedor_desligado: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _brasil_api_falha(self: CNPJClient, cnpj: str) -> CNPJResponse:
        raise FiscalError("BrasilAPI indisponível")

    async def _fake_receitaws(self: CNPJClient, cnpj: str) -> CNPJResponse:
        return CNPJResponse(
            cnpj=cnpj,
            razao_social="EMPRESA RECEITAWS",
            situacao_cadastral="ATIVA",
            natureza_juridica="LTDA",
            origem="ReceitaWS",
        )

    monkeypatch.setattr(CNPJClient, "_consultar_brasil_api", _brasil_api_falha)
    monkeypatch.setattr(CNPJClient, "_consultar_receita_ws", _fake_receitaws)

    resposta = await CNPJClient().consultar(CNPJ_NUM)
    assert resposta.origem == "ReceitaWS"


async def test_tool_rejeita_espacos_mesmo_com_digito_valido() -> None:
    """validate_cnpj_qualquer roda sobre o valor bruto: espacos nao sao mascara aceita."""
    with pytest.raises(ValidationError) as exc_info:
        await consultar_cnpj("33 000 167 0001 01")
    assert exc_info.value.field == "cnpj"
