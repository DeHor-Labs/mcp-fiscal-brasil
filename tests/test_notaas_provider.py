"""Testes do provedor NFS-e opcional Notaas (notaas.com.br).

Cobrem:
- Cobertura publica gratuita de 5.570 municipios (sem chave de API) e fallback offline
- Provedor opt-in NOTAAS_API_KEY (desligado por padrao)
- Consulta de status, emissao e cancelamento de NFS-e via Notaas
- Fallback automatico em consultar_nfse quando o provedor opt-in falha
- Limitador compartilhado (singleton AsyncLimiter)
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from mcp_fiscal_brasil._core import FiscalHTTPError, settings
from mcp_fiscal_brasil.nfse.tools import consultar_cobertura_nfse, consultar_nfse
from mcp_fiscal_brasil.shared import notaas as notaas_provider

COBERTURA_SP_SAMPLE: dict[str, Any] = {
    "total": 1,
    "limit": 10,
    "offset": 0,
    "municipios": [
        {
            "codigo_ibge": "3550308",
            "nome": "São Paulo",
            "uf": "SP",
            "sistema_nfse": "sp_prefeitura",
            "snnfse_aderente": False,
            "suportado": True,
            "status_integracao": "integrado",
            "tipo_integracao": "SOAP mTLS (Paulistana v2)",
        }
    ],
}

STATUS_NFSE_SAMPLE: dict[str, Any] = {
    "id": "b1f29d18-7c4d-4c88-90d2-123456789abc",
    "status": "issued",
    "numeroNfse": "202600000142",
    "chave_acesso": "35497062241403505000184000000000014226073345639378",
    "codigo_verificacao": "ABCD-1234",
    "valor_servicos": 1500.0,
    "valor_iss": 75.0,
    "data_emissao": "2026-07-15T14:22:00Z",
    "prestador": {"cnpj": "41403505000184", "razao_social": "WE DIGI TECNOLOGIA LTDA"},
    "tomador": {"documento": "33000167000101", "razao_social": "CLIENTE EXEMPLO SA"},
}


class _FakeHTTPClient:
    """HTTPClient falso para testes: devolve payload configurado sem tocar a rede."""

    payload: ClassVar[dict[str, Any]] = {}
    should_fail: ClassVar[bool] = False
    ultimo_path: ClassVar[str | None] = None
    ultimo_params: ClassVar[dict[str, Any] | None] = None
    ultimo_headers: ClassVar[dict[str, str] | None] = None
    ultimo_json: ClassVar[dict[str, Any] | None] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeHTTPClient:
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
        _FakeHTTPClient.ultimo_params = params
        _FakeHTTPClient.ultimo_headers = headers
        if _FakeHTTPClient.should_fail:
            raise FiscalHTTPError(
                "Falha simulada Notaas",
                status_code=503,
                url="https://platform.notaas.com.br",
            )
        return _FakeHTTPClient.payload

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        _FakeHTTPClient.ultimo_path = path
        _FakeHTTPClient.ultimo_json = json
        _FakeHTTPClient.ultimo_headers = headers
        if _FakeHTTPClient.should_fail:
            raise FiscalHTTPError(
                "Falha simulada Notaas POST",
                status_code=503,
                url="https://platform.notaas.com.br",
            )
        return _FakeHTTPClient.payload


@pytest.fixture(autouse=True)
def _reset_fake_http() -> None:
    _FakeHTTPClient.payload = {}
    _FakeHTTPClient.should_fail = False
    _FakeHTTPClient.ultimo_path = None
    _FakeHTTPClient.ultimo_params = None
    _FakeHTTPClient.ultimo_headers = None
    _FakeHTTPClient.ultimo_json = None


@pytest.fixture
def provedor_habilitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Habilita o provedor Notaas com chave de teste e HTTPClient mockado."""
    monkeypatch.setattr(settings, "notaas_api_key", "ntaas_test_123456", raising=False)
    monkeypatch.setattr(notaas_provider, "HTTPClient", _FakeHTTPClient)


def test_provedor_desligado_por_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "notaas_api_key", "", raising=False)
    assert notaas_provider.provedor_configurado() is False


def test_limitador_notaas_compartilhado() -> None:
    limitador = notaas_provider._get_limiter()
    assert limitador is notaas_provider._get_limiter()
    cliente_a = notaas_provider._http_client()
    cliente_b = notaas_provider._http_client()
    assert cliente_a._limiter is cliente_b._limiter
    assert cliente_a._limiter is limitador


@pytest.mark.asyncio
async def test_consultar_cobertura_publica_sem_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "notaas_api_key", "", raising=False)
    monkeypatch.setattr(notaas_provider, "HTTPClient", _FakeHTTPClient)
    _FakeHTTPClient.payload = COBERTURA_SP_SAMPLE

    resultado = await consultar_cobertura_nfse(
        municipio="São Paulo",
        uf="SP",
        codigo_ibge="3550308",
    )

    assert resultado["fonte"] == "notaas.com.br"
    assert resultado["total"] == 1
    assert resultado["municipios"][0]["codigo_ibge"] == "3550308"
    assert _FakeHTTPClient.ultimo_path == "/api/v1/cobertura/cidades"
    assert _FakeHTTPClient.ultimo_params == {
        "limit": 10,
        "q": "São Paulo",
        "uf": "SP",
        "ibge": "3550308",
    }


@pytest.mark.asyncio
async def test_consultar_status_sem_api_key_levanta_erro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "notaas_api_key", "", raising=False)
    with pytest.raises(FiscalHTTPError, match="NOTAAS_API_KEY"):
        await notaas_provider.consultar_status_nfse("b1f29d18-7c4d-4c88-90d2-123456789abc")


@pytest.mark.asyncio
async def test_consultar_nfse_usa_provedor_notaas_quando_configurado(
    provedor_habilitado: None,
) -> None:
    _FakeHTTPClient.payload = STATUS_NFSE_SAMPLE

    resultado = await consultar_nfse(
        numero="142",
        municipio="São José do Rio Preto",
        uf="SP",
        invoice_id="b1f29d18-7c4d-4c88-90d2-123456789abc",
    )

    assert resultado["fonte"] == "notaas.com.br"
    assert resultado["status"] == "issued"
    assert resultado["numero"] == "202600000142"
    assert resultado["codigo_verificacao"] == "ABCD-1234"
    assert _FakeHTTPClient.ultimo_path == (
        "/api/v1/invoices/b1f29d18-7c4d-4c88-90d2-123456789abc/status"
    )
    assert _FakeHTTPClient.ultimo_headers == {
        "x-api-key": "ntaas_test_123456",
    }


@pytest.mark.asyncio
async def test_consultar_nfse_faz_fallback_quando_notaas_falha(
    provedor_habilitado: None,
) -> None:
    _FakeHTTPClient.should_fail = True

    resultado = await consultar_nfse(
        numero="142",
        municipio="São Paulo",
        uf="SP",
        invoice_id="b1f29d18-7c4d-4c88-90d2-123456789abc",
    )

    assert resultado["fonte"] == "fallback_portal_municipal"
    assert resultado["status"] == "consulta_manual_necessaria"
    assert (
        resultado["portal_municipio"]
        == "https://nfe.prefeitura.sp.gov.br/contribuinte/notasfiscais.aspx"
    )


@pytest.mark.asyncio
async def test_emitir_e_cancelar_nfse_via_provedor(
    provedor_habilitado: None,
) -> None:
    _FakeHTTPClient.payload = {"id": "inv_123", "status": "queued"}
    emissao = await notaas_provider.emitir_nfse({"valor_servicos": 500.0})
    assert emissao["id"] == "inv_123"
    assert _FakeHTTPClient.ultimo_path == "/api/v1/emitir"

    _FakeHTTPClient.payload = {"id": "inv_123", "status": "cancelling"}
    cancelamento = await notaas_provider.cancelar_nfse("inv_123", motivo="Erro de preenchimento")
    assert cancelamento["status"] == "cancelling"
    assert _FakeHTTPClient.ultimo_path == "/api/v1/cancelar"
    assert _FakeHTTPClient.ultimo_json == {
        "invoiceId": "inv_123",
        "motivo": "Erro de preenchimento",
    }


@pytest.mark.asyncio
async def test_rejeita_invoice_id_invalido_ou_traversal(
    provedor_habilitado: None,
) -> None:
    for invalido in ("..", "../status", "inv/123", "inv com espaco", "a" * 129):
        with pytest.raises(ValueError, match="invoice_id inválido"):
            await notaas_provider.consultar_status_nfse(invalido)
        with pytest.raises(ValueError, match="invoice_id inválido"):
            await notaas_provider.cancelar_nfse(invalido)
