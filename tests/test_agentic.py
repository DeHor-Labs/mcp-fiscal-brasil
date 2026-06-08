"""Testes das tools agenticas (alto nivel)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_fiscal_brasil import server as mcp_server
from mcp_fiscal_brasil.agentic import (
    analyze_cnpj_compliance,
    compare_tax_regimes,
    consultar_empresas_lote,
    risk_score_supplier,
)
from mcp_fiscal_brasil.agentic.regimes import (
    _calc_lucro_presumido,
    _calc_mei,
    _calc_simples,
)
from mcp_fiscal_brasil.agentic.schemas import (
    ComplianceFinding,
    ComplianceReport,
    SupplierRiskBatchItem,
    SupplierRiskBatchResult,
    TaxRegimeComparison,
)
from mcp_fiscal_brasil.cnpj.schemas import AtividadeCNAE, CNPJResponse
from mcp_fiscal_brasil.shared.schemas import Endereco


def _cnpj_ativo() -> CNPJResponse:
    return CNPJResponse(
        cnpj="12345678000190",
        razao_social="EMPRESA TESTE LTDA",
        nome_fantasia="Teste",
        situacao_cadastral="ATIVA",
        natureza_juridica="206-2",
        porte="Pequena",
        capital_social=10000.0,
        data_abertura=date(2020, 1, 1),
        atividade_principal=AtividadeCNAE(
            código="6201500", descrição="Desenvolvimento de software"
        ),
        atividades_secundarias=[],
        endereco=Endereco(
            logradouro="Rua A",
            número="100",
            bairro="Centro",
            municipio="Goiânia",
            uf="GO",
            cep="74000000",
        ),
        telefone=None,
        email=None,
        qsa=[],
        origem="BrasilAPI",
    )


def _cnpj_baixado() -> CNPJResponse:
    return CNPJResponse(
        cnpj="98765432000100",
        razao_social="EMPRESA INATIVA",
        nome_fantasia=None,
        situacao_cadastral="BAIXADA",
        natureza_juridica="206-2",
        porte=None,
        capital_social=None,
        atividade_principal=None,
        atividades_secundarias=[],
        endereco=Endereco(),
        telefone=None,
        email=None,
        qsa=[],
        origem="BrasilAPI",
    )


# ---------------------------------------------------------------------------
# consultar_empresas_lote
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consultar_empresas_lote_retoma_resumos_e_erros() -> None:
    cnpj_ok = "12.345.678/0001-90"
    cnpj_baixo = "98.765.432/0001-00"
    cnpj_falha = "12.345.678"

    with patch("mcp_fiscal_brasil.agentic.supplier.analyze_cnpj_compliance") as mock_compliance:

        async def fake_analyze(value: str) -> ComplianceReport:
            if value == cnpj_ok:
                return ComplianceReport(
                    cnpj="12345678000190",
                    razao_social="Fornecedor OK",
                    risco_geral="baixo",
                    score=90,
                    achados=[],
                    resumo_executivo="Ativo e regular.",
                    fontes_consultadas=["BrasilAPI"],
                )
            if value == cnpj_baixo:
                return ComplianceReport(
                    cnpj="98765432000100",
                    razao_social="Fornecedor Baixado",
                    risco_geral="critico",
                    score=5,
                    achados=[
                        ComplianceFinding(
                            categoria="situacao_cadastral",
                            severidade="critico",
                            titulo="Empresa baixada",
                            detalhe="Baixada da receita.",
                        )
                    ],
                    resumo_executivo="Inapta para contratação.",
                    fontes_consultadas=["BrasilAPI"],
                )
            raise RuntimeError("Falha simulada")

        mock_compliance.side_effect = fake_analyze

        resultado = await consultar_empresas_lote(
            [cnpj_ok, cnpj_falha, cnpj_baixo],
            criterios_estritos=True,
        )

    assert resultado.total_consultados == 3
    assert resultado.total_processados == 2
    assert resultado.criterios_estritos is True
    assert len(resultado.erros) == 1
    assert resultado.resultados[1].erro is not None
    assert "Falha simulada" in (resultado.resultados[1].erro or "")
    assert resultado.resultados[0].resumo_compliance is not None
    assert resultado.resultados[0].score_fornecedor is not None
    assert resultado.resultados[2].score_fornecedor is not None
    assert resultado.resultados[0].score_fornecedor.score == 80
    assert resultado.resultados[0].score_fornecedor.recomendacao == "aprovar"
    assert resultado.resultados[2].score_fornecedor.recomendacao == "recusar"
    assert mock_compliance.call_count == 3


@pytest.mark.asyncio
async def test_tool_consultar_empresas_lote_valida_e_repassa_cnpjs() -> None:
    retorno = SupplierRiskBatchResult(
        total_consultados=2,
        criterios_estritos=True,
        total_processados=2,
        resultados=[
            SupplierRiskBatchItem(cnpj="33000167000101"),
            SupplierRiskBatchItem(cnpj="33000167000101"),
        ],
    )

    with patch(
        "mcp_fiscal_brasil.server.consultar_empresas_lote",
        AsyncMock(return_value=retorno),
    ) as mock_tool:
        resposta = await mcp_server.tool_consultar_empresas_lote(
            ["33.000.167/0001-01", "33.000.167/0001-01"],
            criterios_estritos=True,
        )

    assert resposta["total_consultados"] == 2
    assert resposta["criterios_estritos"] is True
    mock_tool.assert_awaited_once_with(
        ["33000167000101", "33000167000101"],
        criterios_estritos=True,
    )


@pytest.mark.asyncio
async def test_tool_consultar_empresas_lote_rejeita_cnpjs_invalidos() -> None:
    with pytest.raises(ValueError, match=r"CNPJ\(s\) inválido\(s\) no lote"):
        await mcp_server.tool_consultar_empresas_lote(["12.345.678/0001-90", "11.111.111/1111-11"])


@pytest.mark.asyncio
async def test_tool_consultar_empresas_lote_rejeita_tamanho_excedido() -> None:
    lotes_validos = ["33.000.167/0001-01"] * 51
    with pytest.raises(ValueError, match="máximo permitido é 50"):
        await mcp_server.tool_consultar_empresas_lote(lotes_validos)


# ---------------------------------------------------------------------------
# analyze_cnpj_compliance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compliance_empresa_ativa() -> None:
    with (
        patch("mcp_fiscal_brasil.agentic.compliance.CNPJClient") as mock_cnpj_class,
        patch("mcp_fiscal_brasil.agentic.compliance.SimplesClient") as mock_simples_class,
        patch("mcp_fiscal_brasil.agentic.compliance.MEIClient") as mock_mei_class,
    ):
        cnpj_inst = MagicMock()
        cnpj_inst.consultar = AsyncMock(return_value=_cnpj_ativo())
        mock_cnpj_class.return_value = cnpj_inst

        simples_inst = MagicMock()
        simples_inst.get_simples_status = AsyncMock(side_effect=Exception("offline"))
        mock_simples_class.return_value = simples_inst

        mei_inst = MagicMock()
        mei_inst.get_mei_status = AsyncMock(side_effect=Exception("offline"))
        mock_mei_class.return_value = mei_inst

        report = await analyze_cnpj_compliance("12.345.678/0001-90")

    assert isinstance(report, ComplianceReport)
    assert report.cnpj == "12345678000190"
    assert report.risco_geral in ("baixo", "medio")
    assert report.score >= 50
    assert "BrasilAPI" in report.fontes_consultadas


@pytest.mark.asyncio
async def test_compliance_empresa_baixada_eleva_risco() -> None:
    with (
        patch("mcp_fiscal_brasil.agentic.compliance.CNPJClient") as mock_cnpj_class,
        patch("mcp_fiscal_brasil.agentic.compliance.SimplesClient") as mock_simples_class,
        patch("mcp_fiscal_brasil.agentic.compliance.MEIClient") as mock_mei_class,
    ):
        cnpj_inst = MagicMock()
        cnpj_inst.consultar = AsyncMock(return_value=_cnpj_baixado())
        mock_cnpj_class.return_value = cnpj_inst
        mock_simples_class.return_value = MagicMock(
            get_simples_status=AsyncMock(side_effect=Exception())
        )
        mock_mei_class.return_value = MagicMock(get_mei_status=AsyncMock(side_effect=Exception()))

        report = await analyze_cnpj_compliance("98765432000100")

    assert report.risco_geral == "critico"
    assert report.score < 30
    assert any(a.categoria == "situacao_cadastral" for a in report.achados)


@pytest.mark.asyncio
async def test_compliance_cnpj_invalido_levanta() -> None:
    with pytest.raises(ValueError, match="14 digitos"):
        await analyze_cnpj_compliance("123")


# ---------------------------------------------------------------------------
# compare_tax_regimes
# ---------------------------------------------------------------------------


def test_compare_tax_regimes_servicos_pequena_empresa() -> None:
    resultado = compare_tax_regimes(
        faturamento_anual=300_000,
        setor="serviços",
        folha_pagamento_anual=120_000,
    )
    assert isinstance(resultado, TaxRegimeComparison)
    assert resultado.melhor_opcao in ("simples_nacional", "mei")
    assert resultado.economia_anual_vs_pior >= 0
    assert len(resultado.opcoes) >= 3


def test_compare_tax_regimes_grande_empresa_exclui_simples() -> None:
    resultado = compare_tax_regimes(
        faturamento_anual=10_000_000,
        setor="indústria",
        folha_pagamento_anual=2_000_000,
    )
    simples = next(o for o in resultado.opcoes if o.regime == "simples_nacional")
    assert not simples.aplicavel
    assert "limite" in (simples.motivo_inaplicavel or "").lower()
    assert resultado.melhor_opcao in ("lucro_presumido", "lucro_real")


def test_compare_tax_regimes_faturamento_negativo_levanta() -> None:
    with pytest.raises(ValueError):
        compare_tax_regimes(faturamento_anual=-100, setor="comércio")


def test_calc_mei_dentro_limite() -> None:
    aplicavel, _aliq, imposto, motivo = _calc_mei(60_000, "comércio")
    assert aplicavel is True
    assert imposto is not None
    assert imposto < 1500
    assert motivo is None


def test_calc_mei_excede_limite() -> None:
    aplicavel, _aliq, _imposto, motivo = _calc_mei(100_000, "serviços")
    assert aplicavel is False
    assert motivo is not None
    assert "81" in motivo


def test_calc_simples_fator_r_servicos() -> None:
    # Folha alta -> anexo III (mais barato)
    aplicavel_alto, aliq_alto, _imp_alto, _ = _calc_simples(500_000, "serviços", 200_000)
    # Folha baixa -> anexo V (mais caro)
    aplicavel_baixo, aliq_baixo, _imp_baixo, _ = _calc_simples(500_000, "serviços", 10_000)
    assert aplicavel_alto and aplicavel_baixo
    assert aliq_alto is not None and aliq_baixo is not None
    assert aliq_alto < aliq_baixo


def test_calc_lucro_presumido_aplicavel() -> None:
    aplicavel, _aliq, imp, motivo = _calc_lucro_presumido(2_000_000, "comércio")
    assert aplicavel is True
    assert imp is not None
    assert motivo is None


# ---------------------------------------------------------------------------
# risk_score_supplier
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_score_supplier_empresa_ativa_aprovado() -> None:
    with patch("mcp_fiscal_brasil.agentic.supplier.analyze_cnpj_compliance") as mock_compliance:
        mock_compliance.return_value = ComplianceReport(
            cnpj="12345678000190",
            razao_social="EMPRESA TESTE LTDA",
            risco_geral="baixo",
            score=92,
            achados=[],
            resumo_executivo="Empresa regular.",
            fontes_consultadas=["BrasilAPI"],
        )
        resultado = await risk_score_supplier("12.345.678/0001-90")
    assert resultado.recomendacao == "aprovar"
    assert resultado.score >= 80


@pytest.mark.asyncio
async def test_risk_score_supplier_criterios_estritos_reduz_score() -> None:
    with patch("mcp_fiscal_brasil.agentic.supplier.analyze_cnpj_compliance") as mock_compliance:
        mock_compliance.return_value = ComplianceReport(
            cnpj="12345678000190",
            razao_social="EMPRESA TESTE LTDA",
            risco_geral="baixo",
            score=85,
            achados=[],
            resumo_executivo="Regular.",
            fontes_consultadas=["BrasilAPI"],
        )
        normal = await risk_score_supplier("12.345.678/0001-90", criterios_estritos=False)
        estrito = await risk_score_supplier("12.345.678/0001-90", criterios_estritos=True)
    assert estrito.score == normal.score - 10
    assert any("Criterios estritos" in f for f in estrito.fatores)


@pytest.mark.asyncio
async def test_risk_score_supplier_empresa_baixada_recusa() -> None:
    with patch("mcp_fiscal_brasil.agentic.supplier.analyze_cnpj_compliance") as mock_compliance:
        from mcp_fiscal_brasil.agentic.schemas import ComplianceFinding

        mock_compliance.return_value = ComplianceReport(
            cnpj="98765432000100",
            razao_social="INATIVA",
            risco_geral="critico",
            score=5,
            achados=[
                ComplianceFinding(
                    categoria="situacao_cadastral",
                    severidade="critico",
                    titulo="Empresa baixada",
                    detalhe="Baixada na Receita.",
                )
            ],
            resumo_executivo="Critico.",
            fontes_consultadas=["BrasilAPI"],
        )
        resultado = await risk_score_supplier("98765432000100")
    assert resultado.recomendacao == "recusar"
    assert resultado.risco == "critico"
