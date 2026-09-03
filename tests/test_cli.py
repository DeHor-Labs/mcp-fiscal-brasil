"""Testes do CLI typer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from mcp_fiscal_brasil.agentic.schemas import (
    ComplianceReport,
    TaxRegimeComparison,
    TaxRegimeOption,
)
from mcp_fiscal_brasil.cli import app
from mcp_fiscal_brasil.simples.schemas import SimplesStatus

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "mcp-fiscal-brasil" in result.stdout


def test_cli_regimes_setor_invalido() -> None:
    result = runner.invoke(app, ["regimes", "--faturamento", "100000", "--setor", "invalido"])
    assert result.exit_code != 0


def test_cli_regimes_calculo_valido() -> None:
    result = runner.invoke(
        app,
        [
            "regimes",
            "--faturamento",
            "500000",
            "--setor",
            "serviços",
            "--folha",
            "180000",
        ],
    )
    assert result.exit_code == 0
    assert (
        "melhor_opcao" in result.stdout
        or "Melhor" in result.stdout
        or "simples" in result.stdout.lower()
    )


def test_cli_regimes_json_output() -> None:
    result = runner.invoke(
        app,
        ["regimes", "--faturamento", "500000", "--setor", "serviços", "--json"],
    )
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert "melhor_opcao" in data


def test_cli_compliance_via_mock() -> None:
    with patch("mcp_fiscal_brasil.cli.analyze_cnpj_compliance") as mock:
        mock.return_value = ComplianceReport(
            cnpj="12345678000190",
            razao_social="EMPRESA TESTE",
            risco_geral="baixo",
            score=85,
            achados=[],
            resumo_executivo="OK.",
            fontes_consultadas=["BrasilAPI"],
        )
        # AsyncMock para asyncio.run
        mock.return_value = mock.return_value
        mock.side_effect = None
        mock_async = AsyncMock(return_value=mock.return_value)

        with patch("mcp_fiscal_brasil.cli.analyze_cnpj_compliance", mock_async):
            result = runner.invoke(app, ["compliance", "12345678000190", "--json"])

    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    assert data["razao_social"] == "EMPRESA TESTE"


def test_cli_regimes_grande_empresa() -> None:
    result = runner.invoke(
        app,
        ["regimes", "--faturamento", "20000000", "--setor", "indústria", "--json"],
    )
    assert result.exit_code == 0
    import json

    data = json.loads(result.stdout)
    # Empresa grande não usa simples
    assert data["melhor_opcao"] in ("lucro_presumido", "lucro_real")


def _fake_regime() -> TaxRegimeComparison:
    return TaxRegimeComparison(
        cenario_faturamento_anual=500_000,
        cenario_setor="serviços",
        folha_pagamento_anual=180_000,
        opcoes=[
            TaxRegimeOption(
                regime="simples_nacional",
                aplicavel=True,
                aliquota_efetiva_estimada=11.2,
                imposto_anual_estimado=56000,
                pros=["unificado"],
                contras=[],
            ),
        ],
        melhor_opcao="simples_nacional",
        economia_anual_vs_pior=10000,
        observacoes="ok",
    )


def test_cli_regimes_pretty_output() -> None:
    result = runner.invoke(
        app,
        ["regimes", "--faturamento", "500000", "--setor", "serviços"],
    )
    assert result.exit_code == 0
    # pretty output uses key: value
    assert ":" in result.stdout


def test_cli_simples_cnpj_invalido_vira_json_sem_traceback() -> None:
    """CNPJ com digito verificador invalido: erro de negocio, JSON, codigo 1."""
    result = runner.invoke(app, ["simples", "00000000000000", "--json"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    data = json.loads(result.stdout)
    assert data == {
        "ok": False,
        "erro": "CNPJ inválido",
        "tipo": "FiscalNotFoundError",
        "cnpj": "00000000000000",
    }


def test_cli_simples_sucesso_json() -> None:
    mock_client = AsyncMock()
    mock_client.get_simples_status.return_value = SimplesStatus(
        cnpj="33000167000101", simples_nacional=False, mei=False
    )
    with patch("mcp_fiscal_brasil.cli.SimplesClient", return_value=mock_client):
        result = runner.invoke(app, ["simples", "33000167000101", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["simples_nacional"] is False
    assert data["mei"] is False


def test_cli_simples_erro_inesperado_vira_json_codigo_2() -> None:
    """Erro que nao e FiscalError: JSON estruturado, sem traceback, codigo 2."""
    mock_client = AsyncMock()
    mock_client.get_simples_status.side_effect = RuntimeError("boom")
    with patch("mcp_fiscal_brasil.cli.SimplesClient", return_value=mock_client):
        result = runner.invoke(app, ["simples", "33000167000101", "--json"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    data = json.loads(result.stdout)
    assert data == {
        "ok": False,
        "erro": "boom",
        "tipo": "RuntimeError",
        "cnpj": "33000167000101",
    }


def test_cli_compliance_erro_inesperado_vira_json_codigo_2() -> None:
    mock_async = AsyncMock(side_effect=RuntimeError("todas as fontes falharam"))
    with patch("mcp_fiscal_brasil.cli.analyze_cnpj_compliance", mock_async):
        result = runner.invoke(app, ["compliance", "12345678000190", "--json"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["tipo"] == "RuntimeError"
    assert data["cnpj"] == "12345678000190"


def test_cli_regimes_setor_invalido_json_estruturado() -> None:
    result = runner.invoke(app, ["regimes", "--faturamento", "100000", "--setor", "invalido"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["tipo"] == "ValueError"
