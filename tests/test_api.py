"""Testes do FastAPI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from cachetools import TTLCache
from fastapi.testclient import TestClient

from mcp_fiscal_brasil import __version__
from mcp_fiscal_brasil import api as api_module
from mcp_fiscal_brasil._core.config import settings as api_settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError
from mcp_fiscal_brasil.agentic.schemas import ComplianceReport
from mcp_fiscal_brasil.api import app
from mcp_fiscal_brasil.nfe.schemas import StatusSEFAZResponse

client = TestClient(app)


@pytest.fixture(autouse=True)
def _status_sefaz_cache_isolado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada teste começa com um cache de status SEFAZ vazio e isolado dos demais."""
    monkeypatch.setattr(
        api_module,
        "_status_sefaz_cache",
        TTLCache(maxsize=32, ttl=api_module._STATUS_SEFAZ_CACHE_TTL_SEGUNDOS),
    )


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


def test_fiscal_certificado_status_sem_certificado_configurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_settings, "nfe_certificado_path", "")
    monkeypatch.setattr(api_settings, "nfe_certificado_senha", "")

    response = client.get("/v1/fiscal/certificado/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configurado"] is False
    assert data["valido"] is None
    assert "cnpj" not in data
    assert "titular" not in data


def test_status_sefaz_uf_invalida_retorna_400() -> None:
    """UF invalida e erro de input do chamador: 400 mesmo sem certificado configurado."""
    response = client.get("/v1/nfe/status-sefaz", params={"uf": "XX"})
    assert response.status_code == 400


def test_status_sefaz_sem_certificado_retorna_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem certificado configurado, a rota responde 503 em vez de fingir sucesso vazio."""
    monkeypatch.setattr(api_settings, "nfe_certificado_path", "")
    monkeypatch.setattr(api_settings, "nfe_certificado_senha", "")

    response_uf = client.get("/v1/nfe/status-sefaz", params={"uf": "SP"})
    assert response_uf.status_code == 503

    response_todas = client.get("/v1/nfe/status-sefaz")
    assert response_todas.status_code == 503


def _fake_status(uf: str) -> StatusSEFAZResponse:
    return StatusSEFAZResponse(uf=uf, status="OPERACIONAL", descrição="Servico em Operacao")


def test_status_sefaz_falha_pontual_de_uma_uf_e_omitida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha pontual (FiscalHTTPError) em uma UF nao derruba a chamada inteira com 500."""
    monkeypatch.setattr(api_settings, "nfe_certificado_path", "/fake/cert.pfx")
    monkeypatch.setattr(api_settings, "nfe_certificado_senha", "fake-senha")

    async def _consulta(uf: str) -> StatusSEFAZResponse:
        if uf == "SP":
            raise FiscalHTTPError(message="falha de rede", status_code=0, url="https://sefaz")
        return _fake_status(uf)

    with patch("mcp_fiscal_brasil.api.consultar_status_sefaz", AsyncMock(side_effect=_consulta)):
        response = client.get("/v1/nfe/status-sefaz")

    assert response.status_code == 200
    ufs = {item["uf"] for item in response.json()["ufs"]}
    assert "SP" not in ufs
    assert "MG" in ufs


def test_status_sefaz_cache_evita_nova_consulta_dentro_da_janela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segunda chamada para a mesma UF dentro de 60s usa o cache, sem nova consulta SOAP."""
    monkeypatch.setattr(api_settings, "nfe_certificado_path", "/fake/cert.pfx")
    monkeypatch.setattr(api_settings, "nfe_certificado_senha", "fake-senha")

    mock_consulta = AsyncMock(return_value=_fake_status("SP"))
    with patch("mcp_fiscal_brasil.api.consultar_status_sefaz", mock_consulta):
        primeira = client.get("/v1/nfe/status-sefaz", params={"uf": "SP"})
        segunda = client.get("/v1/nfe/status-sefaz", params={"uf": "SP"})

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert primeira.json() == segunda.json()
    mock_consulta.assert_called_once()


def test_nfe_validate_aceita_xml_inline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_settings, "mcp_fiscal_file_base_dir", str(tmp_path))
    fake_report = SimpleNamespace(model_dump=lambda **_: {"valida_estruturalmente": True})

    with patch(
        "mcp_fiscal_brasil.api.validate_nfe_full", AsyncMock(return_value=fake_report)
    ) as validate:
        response = client.post("/v1/nfe/validate", json={"xml": "<NFe>conteudo</NFe>"})

    assert response.status_code == 200
    assert response.json() == {"valida_estruturalmente": True}
    validate.assert_called_once()
    # O arquivo temporario criado para a validacao inline nao deve sobreviver a chamada
    assert list(tmp_path.glob("*.xml")) == []


def test_nfe_validate_xml_inline_excede_tamanho_maximo() -> None:
    xml_grande = "<NFe>" + ("a" * (5 * 1024 * 1024 + 1)) + "</NFe>"
    response = client.post("/v1/nfe/validate", json={"xml": xml_grande})
    assert response.status_code == 413


def test_nfe_validate_sem_xml_e_sem_xml_path_retorna_400() -> None:
    response = client.post("/v1/nfe/validate", json={})
    assert response.status_code == 400
