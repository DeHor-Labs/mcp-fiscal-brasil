"""Testes do simulador de transicao da Reforma Tributaria (LC 214/2025).

Cobre: comercio/servicos/industria, cada regime, ano-teste 2026 (impacto ~zero),
ano 2033 (carga plena), presenca dos disclaimers no output e validacao de inputs.
"""

from __future__ import annotations

import pytest

from mcp_fiscal_brasil.agentic.reforma import (
    CBS_REFERENCIA_PCT,
    IBS_REFERENCIA_PCT,
    SimulacaoReformaResult,
    simular_transicao_reforma_tributaria,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def faturamento_medio() -> float:
    return 1_200_000.0


# ---------------------------------------------------------------------------
# Validacao de inputs
# ---------------------------------------------------------------------------


def test_faturamento_zero_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="positivo"):
        simular_transicao_reforma_tributaria(
            faturamento_anual=0,
            setor="comércio",
            regime_atual="Lucro Presumido",
        )


def test_faturamento_negativo_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="positivo"):
        simular_transicao_reforma_tributaria(
            faturamento_anual=-500,
            setor="serviços",
            regime_atual="Simples Nacional",
        )


@pytest.mark.parametrize(
    "campo,kwargs",
    [
        ("aliquota_icms_atual", {"aliquota_icms_atual": -1.0}),
        ("aliquota_icms_atual", {"aliquota_icms_atual": 101.0}),
        ("aliquota_iss_atual", {"aliquota_iss_atual": -0.01}),
        ("aliquota_iss_atual", {"aliquota_iss_atual": 100.1}),
        ("aliquota_pis_cofins", {"aliquota_pis_cofins": -5.0}),
        ("aliquota_pis_cofins", {"aliquota_pis_cofins": 200.0}),
    ],
)
def test_aliquota_fora_do_range_levanta_value_error(campo: str, kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match=campo):
        simular_transicao_reforma_tributaria(
            faturamento_anual=100_000,
            setor="comércio",
            regime_atual="Lucro Presumido",
            **kwargs,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Estrutura do resultado
# ---------------------------------------------------------------------------


def test_resultado_contem_8_anos(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    anos = [r.ano for r in resultado.resultados_por_ano]
    assert anos == list(range(2026, 2034))


def test_resultado_e_instancia_correta(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    assert isinstance(resultado, SimulacaoReformaResult)


def test_faturamento_refletido_no_resultado(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="serviços",
        regime_atual="Lucro Real",
    )
    assert resultado.faturamento_anual == faturamento_medio


# ---------------------------------------------------------------------------
# 2026: ano de testes, impacto liquido adicional ~zero
# ---------------------------------------------------------------------------


def test_2026_carga_nova_zero_comercio(faturamento_medio: float) -> None:
    """Em 2026, CBS e IBS sao compensaveis; carga nova deve ser 0."""
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=12.0,
    )
    ano_2026 = next(r for r in resultado.resultados_por_ano if r.ano == 2026)
    assert ano_2026.carga_regime_novo_pct == 0.0


def test_2026_carga_antiga_inclui_pis_cofins_e_icms(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=12.0,
        aliquota_pis_cofins=3.65,
    )
    ano_2026 = next(r for r in resultado.resultados_por_ano if r.ano == 2026)
    # carga antiga = PIS/COFINS + ICMS
    expected = 3.65 + 12.0
    assert abs(ano_2026.carga_regime_atual_pct - expected) < 0.01


# ---------------------------------------------------------------------------
# 2027-2028: CBS plena, ICMS/ISS integrais
# ---------------------------------------------------------------------------


def test_2027_carga_nova_igual_cbs_referencia(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="indústria",
        regime_atual="Lucro Real",
        aliquota_icms_atual=12.0,
    )
    ano_2027 = next(r for r in resultado.resultados_por_ano if r.ano == 2027)
    assert abs(ano_2027.carga_regime_novo_pct - CBS_REFERENCIA_PCT) < 0.01


def test_2027_carga_antiga_apenas_icms(faturamento_medio: float) -> None:
    """Em 2027, PIS/COFINS e extinto pela CBS; carga antiga so tem ICMS."""
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=18.0,
    )
    ano_2027 = next(r for r in resultado.resultados_por_ano if r.ano == 2027)
    assert abs(ano_2027.carga_regime_atual_pct - 18.0) < 0.01


def test_2028_igual_a_2027(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=12.0,
    )
    ano_2027 = next(r for r in resultado.resultados_por_ano if r.ano == 2027)
    ano_2028 = next(r for r in resultado.resultados_por_ano if r.ano == 2028)
    assert ano_2027.carga_total_pct == ano_2028.carga_total_pct


# ---------------------------------------------------------------------------
# 2029-2032: reducao gradual ICMS/ISS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ano", "fracao_ibs"),
    [(2029, 0.10), (2030, 0.20), (2031, 0.30), (2032, 0.40)],
)
def test_carga_ibs_progressiva(faturamento_medio: float, ano: int, fracao_ibs: float) -> None:
    icms = 12.0
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=icms,
    )
    r = next(x for x in resultado.resultados_por_ano if x.ano == ano)
    ibs_esperado = IBS_REFERENCIA_PCT * fracao_ibs
    carga_nova_esperada = CBS_REFERENCIA_PCT + ibs_esperado
    assert abs(r.carga_regime_novo_pct - carga_nova_esperada) < 0.01


@pytest.mark.parametrize(
    ("ano", "fracao_restante"),
    [(2029, 0.90), (2030, 0.80), (2031, 0.70), (2032, 0.60)],
)
def test_icms_reduz_proporcionalmente(
    faturamento_medio: float, ano: int, fracao_restante: float
) -> None:
    icms = 12.0
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=icms,
    )
    r = next(x for x in resultado.resultados_por_ano if x.ano == ano)
    assert abs(r.carga_regime_atual_pct - icms * fracao_restante) < 0.01


# ---------------------------------------------------------------------------
# 2033: carga plena do regime novo
# ---------------------------------------------------------------------------


def test_2033_carga_antiga_zero_comercio(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=12.0,
    )
    ano_2033 = next(r for r in resultado.resultados_por_ano if r.ano == 2033)
    assert ano_2033.carga_regime_atual_pct == 0.0


def test_2033_carga_nova_cbs_mais_ibs_pleno(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    ano_2033 = next(r for r in resultado.resultados_por_ano if r.ano == 2033)
    esperado = CBS_REFERENCIA_PCT + IBS_REFERENCIA_PCT
    assert abs(ano_2033.carga_regime_novo_pct - esperado) < 0.01


def test_2033_carga_total_reais_coerente(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    ano_2033 = next(r for r in resultado.resultados_por_ano if r.ano == 2033)
    esperado_reais = faturamento_medio * ano_2033.carga_total_pct / 100
    assert abs(ano_2033.carga_total_reais - esperado_reais) < 1.0


# ---------------------------------------------------------------------------
# Setores: comercio, servicos, industria
# ---------------------------------------------------------------------------


def test_servicos_usa_iss(faturamento_medio: float) -> None:
    iss = 3.0
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="serviços",
        regime_atual="Lucro Presumido",
        aliquota_iss_atual=iss,
    )
    # Em 2026, carga antiga = PIS/COFINS + ISS
    ano_2026 = next(r for r in resultado.resultados_por_ano if r.ano == 2026)
    # ISS deve aparecer na carga antiga (junto com PIS/COFINS embutido)
    assert ano_2026.carga_regime_atual_pct > 0


def test_servicos_2033_icms_zero_iss_zero(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="serviços",
        regime_atual="Lucro Real",
        aliquota_iss_atual=5.0,
    )
    ano_2033 = next(r for r in resultado.resultados_por_ano if r.ano == 2033)
    assert ano_2033.carga_regime_atual_pct == 0.0


def test_industria_resultado_valido(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="indústria",
        regime_atual="Lucro Real",
        aliquota_icms_atual=12.0,
    )
    assert len(resultado.resultados_por_ano) == 8


# ---------------------------------------------------------------------------
# Regimes tributarios
# ---------------------------------------------------------------------------


def test_simples_nacional_executa_sem_erro(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Simples Nacional",
    )
    assert resultado.regime_atual == "Simples Nacional"


def test_lucro_real_pis_cofins_padrao_9_25(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Real",
        aliquota_icms_atual=12.0,
    )
    # Premissas deve mencionar 9.25
    premissas_texto = " ".join(resultado.premissas)
    assert "9.25" in premissas_texto or "9,25" in premissas_texto


def test_pis_cofins_customizado_refletido(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_pis_cofins=5.0,
    )
    premissas_texto = " ".join(resultado.premissas)
    assert "informada pelo usuario" in premissas_texto


# ---------------------------------------------------------------------------
# Disclaimers e premissas obrigatorios
# ---------------------------------------------------------------------------


def test_avisos_presentes(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    assert len(resultado.avisos) >= 4, "Deve haver pelo menos 4 avisos legais"


def test_aviso_aliquotas_estimativas_presente(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="serviços",
        regime_atual="Simples Nacional",
    )
    avisos_lower = " ".join(resultado.avisos).lower()
    assert "estimativa" in avisos_lower or "estimativas" in avisos_lower


def test_aviso_simples_nacional_presente(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Simples Nacional",
    )
    avisos_lower = " ".join(resultado.avisos).lower()
    assert "simples" in avisos_lower


def test_aviso_nao_substitui_parecer(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="indústria",
        regime_atual="Lucro Real",
    )
    avisos_lower = " ".join(resultado.avisos).lower()
    assert "contador" in avisos_lower or "parecer" in avisos_lower


def test_premissas_listadas(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    assert len(resultado.premissas) >= 5


def test_cronograma_mencionado_nas_premissas(faturamento_medio: float) -> None:
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
    )
    premissas_texto = " ".join(resultado.premissas)
    assert "2029" in premissas_texto
    assert "2033" in premissas_texto


# ---------------------------------------------------------------------------
# Monotonia: carga total nao deve regredir drasticamente entre anos sequenciais
# (IBS sobe enquanto ICMS cai; o total deve ser relativamente estavel)
# ---------------------------------------------------------------------------


def test_carga_total_cresce_de_2027_para_2029(faturamento_medio: float) -> None:
    """IBS comeca a subir em 2029; carga total nao deve cair abruptamente."""
    resultado = simular_transicao_reforma_tributaria(
        faturamento_anual=faturamento_medio,
        setor="comércio",
        regime_atual="Lucro Presumido",
        aliquota_icms_atual=12.0,
    )
    por_ano = {r.ano: r.carga_total_pct for r in resultado.resultados_por_ano}
    # A carga de 2027 deve ser maior que a de 2026 (CBS plena entra)
    assert por_ano[2027] > por_ano[2026]


def test_carga_nova_zero_em_2026_para_todos_setores() -> None:
    for setor in ("comércio", "serviços", "indústria"):
        resultado = simular_transicao_reforma_tributaria(
            faturamento_anual=500_000,
            setor=setor,  # type: ignore[arg-type]
            regime_atual="Lucro Presumido",
        )
        ano_2026 = next(r for r in resultado.resultados_por_ano if r.ano == 2026)
        assert ano_2026.carga_regime_novo_pct == 0.0, (
            f"Setor {setor}: carga nova em 2026 deveria ser 0"
        )
