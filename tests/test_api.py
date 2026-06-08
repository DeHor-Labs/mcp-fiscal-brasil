"""Testes do FastAPI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from mcp_fiscal_brasil import __version__
from mcp_fiscal_brasil._core.config import settings as api_settings
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
            "setor": "serviços",
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
        params={"faturamento_anual": 0, "setor": "comércio"},
    )
    assert response.status_code == 422


def test_agentic_compliance_via_api() -> None:
    fake = ComplianceReport(
        cnpj="11222333000181",
        razao_social="EMPRESA TESTE",
        risco_geral="baixo",
        score=85,
        achados=[],
        resumo_executivo="OK.",
        fontes_consultadas=["BrasilAPI"],
    )
    with patch("mcp_fiscal_brasil.api.analyze_cnpj_compliance", AsyncMock(return_value=fake)):
        response = client.get("/v1/agentic/compliance/11222333000181")
    assert response.status_code == 200
    data = response.json()
    assert data["razao_social"] == "EMPRESA TESTE"
    assert data["score"] == 85


def test_cnpj_lookup_rejeita_cnpj_invalido() -> None:
    with patch("mcp_fiscal_brasil.api.consultar_cnpj", AsyncMock()) as consultar:
        response = client.get("/v1/cnpj/123")
    assert response.status_code == 400
    consultar.assert_not_called()


def test_agentic_compliance_rejeita_cnpj_com_digito_invalido() -> None:
    with patch("mcp_fiscal_brasil.api.analyze_cnpj_compliance", AsyncMock()) as compliance:
        response = client.get("/v1/agentic/compliance/12345678000190")
    assert response.status_code == 400
    compliance.assert_not_called()


def test_nfe_validate_rejeita_caminho_fora_do_diretorio_permitido(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_dir = tmp_path / "allowed"
    base_dir.mkdir()
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(base_dir))

    response = client.post(
        "/v1/nfe/validate",
        json={"xml_path": str(tmp_path / "fora_do_diretorio.xml")},
    )
    assert response.status_code == 403


def test_nfe_validate_rejeita_path_traversal_relativo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_dir = tmp_path / "allowed"
    base_dir.mkdir()
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(base_dir))

    response = client.post(
        "/v1/nfe/validate",
        json={"xml_path": str(base_dir / "../escape.xml")},
    )
    assert response.status_code == 403


def test_nfe_validate_arquivo_inexistente_dentro_do_diretorio_permitido(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(tmp_path))
    response = client.post(
        "/v1/nfe/validate",
        json={"xml_path": str(tmp_path / "nao_existe.xml")},
    )
    assert response.status_code == 404


def test_nfe_validate_retorna_erro_controlado_quando_base_dir_indisponivel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked_base = tmp_path / "base-file"
    blocked_base.write_text("not a directory")
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(blocked_base))

    with patch("mcp_fiscal_brasil.api.validate_nfe_full", AsyncMock()) as validate:
        response = client.post(
            "/v1/nfe/validate",
            json={"xml_path": str(blocked_base / "nfe.xml")},
        )

    assert response.status_code == 500
    assert "Diretório base de arquivos indisponível" in response.json()["detail"]
    validate.assert_not_called()


def test_sped_summarize_rejeita_caminho_fora_do_diretorio_permitido(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_dir = tmp_path / "allowed"
    base_dir.mkdir()
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(base_dir))

    response = client.post(
        "/v1/sped/summarize",
        json={"file_path": str(tmp_path / "fora_do_diretorio.txt")},
    )
    assert response.status_code == 403


def test_sped_summarize_arquivo_inexistente_dentro_do_diretorio_permitido(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(tmp_path))
    response = client.post(
        "/v1/sped/summarize",
        json={"file_path": str(tmp_path / "nao_existe.txt")},
    )
    assert response.status_code == 404
