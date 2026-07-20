"""Testes do servidor MCP (rotas HTTP customizadas)."""

from __future__ import annotations

from starlette.testclient import TestClient

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
