"""Testes do FastAPI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from mcp_fiscal_brasil import __version__
from mcp_fiscal_brasil.agentic.schemas import ComplianceReport
from mcp_fiscal_brasil.api import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert data["service"] == "mcp-fiscal-brasil"


def test_root_serves_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "MCP Fiscal Brasil" in response.text


def test_openapi_docs_disponivel() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "MCP Fiscal Brasil"


def test_agentic_regimes_via_api() -> None:
    response = client.get(
        "/v1/agentic/regimes",
        params={
            "faturamento_anual": 500_000,
            "setor": "servicos",
            "folha_pagamento_anual": 180_000,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "melhor_opcao" in data
    assert data["cenario_faturamento_anual"] == 500_000


def test_agentic_regimes_setor_invalido() -> None:
    response = client.get(
        "/v1/agentic/regimes",
        params={"faturamento_anual": 100_000, "setor": "invalido"},
    )
    assert response.status_code == 422


def test_agentic_regimes_faturamento_zero() -> None:
    response = client.get(
        "/v1/agentic/regimes",
        params={"faturamento_anual": 0, "setor": "comercio"},
    )
    assert response.status_code == 422


def test_agentic_compliance_via_api() -> None:
    fake = ComplianceReport(
        cnpj="12345678000190",
        razao_social="EMPRESA TESTE",
        risco_geral="baixo",
        score=85,
        achados=[],
        resumo_executivo="OK.",
        fontes_consultadas=["BrasilAPI"],
    )
    with patch("mcp_fiscal_brasil.api.analyze_cnpj_compliance", AsyncMock(return_value=fake)):
        response = client.get("/v1/agentic/compliance/12345678000190")
    assert response.status_code == 200
    data = response.json()
    assert data["razao_social"] == "EMPRESA TESTE"
    assert data["score"] == 85


def test_nfe_validate_arquivo_inexistente() -> None:
    response = client.post("/v1/nfe/validate", json={"xml_path": "/tmp/nao_existe.xml"})
    assert response.status_code == 404


def test_sped_summarize_arquivo_inexistente() -> None:
    response = client.post("/v1/sped/summarize", json={"file_path": "/tmp/nao_existe.txt"})
    assert response.status_code == 404
