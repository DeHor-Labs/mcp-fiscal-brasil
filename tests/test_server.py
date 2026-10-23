"""Testes do servidor MCP (rotas HTTP customizadas)."""

from __future__ import annotations

import threading

import pytest
from starlette.testclient import TestClient

from mcp_fiscal_brasil import server
from mcp_fiscal_brasil.nfe.assinatura import AssinaturaResult
from mcp_fiscal_brasil.server import app


def test_health_route_disponivel_no_transporte_http() -> None:
    """FastMCP so expoe /mcp por padrao nos transportes http/sse.

    /health precisa estar registrada explicitamente para o healthcheck do
    Docker funcionar (ver scripts/docker_healthcheck.py) quando o container
    roda com --transport http/sse em vez do stdio padrao.
    """
    http_app = app.http_app(transport="http")
    with TestClient(http_app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("ca_bundle", [None, "PEM de teste"])
async def test_assinatura_executa_fora_do_event_loop(
    monkeypatch: pytest.MonkeyPatch, ca_bundle: str | None
) -> None:
    thread_principal = threading.get_ident()

    def verificar(xml_content: str, ca_bundle: bytes | None = None) -> AssinaturaResult:
        assert threading.get_ident() != thread_principal
        assert xml_content == "<NFe/>"
        assert ca_bundle == bundle_esperado
        return AssinaturaResult(assinatura_valida=True, titular="Teste")

    bundle_esperado = ca_bundle.encode() if ca_bundle else None
    monkeypatch.setattr(server, "validar_assinatura_nfe", verificar)
    resultado = await server.tool_validar_assinatura_nfe("<NFe/>", ca_bundle=ca_bundle)
    assert resultado["assinatura_valida"] is True
    assert resultado["titular"] == "Teste"
