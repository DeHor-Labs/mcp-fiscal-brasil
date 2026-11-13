"""Comparativo entre regimes tributarios brasileiros.

Calculo simplificado, baseado em premissas publicas e tabelas vigentes em 2025.
Não substitui parecer de contador. Util para estimativa rápida e direcionamento.
"""

from __future__ import annotations

from typing import Literal

from .schemas import TaxRegimeComparison, TaxRegimeOption

_LIMITE_MEI = 81_000.0
_LIMITE_SIMPLES = 4_800_000.0
_LIMITE_LUCRO_PRESUMIDO = 78_000_000.0

_AnexoFaixa = tuple[float, float, float]

_ANEXO_I: list[_AnexoFaixa] = [
    (180_000.0, 4.00, 0.0),
    (360_000.0, 7.30, 5_940.0),
    (720_000.0, 9.50, 13_860.0),
    (1_800_000.0, 10.70, 22_500.0),
    (3_600_000.0, 14.30, 87_300.0),
    (4_800_000.0, 19.00, 378_000.0),
]

_ANEXO_II: list[_AnexoFaixa] = [
    (180_000.0, 4.50, 0.0),
    (360_000.0, 7.80, 5_940.0),
    (720_000.0, 10.00, 13_860.0),
    (1_800_000.0, 11.20, 22_500.0),
    (3_600_000.0, 14.70, 85_500.0),
    (4_800_000.0, 30.00, 720_000.0),
]

_ANEXO_III: list[_AnexoFaixa] = [
    (180_000.0, 6.00, 0.0),
    (360_000.0, 11.20, 9_360.0),
    (720_000.0, 13.50, 17_640.0),
    (1_800_000.0, 16.00, 35_640.0),
    (3_600_000.0, 21.00, 125_640.0),
    (4_800_000.0, 33.00, 648_000.0),
]

_ANEXO_V: list[_AnexoFaixa] = [
    (180_000.0, 15.50, 0.0),
    (360_000.0, 18.00, 4_500.0),
    (720_000.0, 19.50, 9_900.0),
    (1_800_000.0, 20.50, 17_100.0),
    (3_600_000.0, 23.00, 62_100.0),
    (4_800_000.0, 30.50, 540_000.0),
]


def _aliquota_efetiva_simples(rbt12: float, tabela: list[_AnexoFaixa]) -> float:
    for limite, nominal, parcela_deduzir in tabela:
        if rbt12 <= limite:
            return (rbt12 * nominal / 100.0 - parcela_deduzir) / rbt12 * 100.0
    raise ValueError("faturamento acima do limite do Simples Nacional")


def _tabela_simples(
    setor: Literal["comércio", "serviços", "indústria"],
    folha: float | None,
    faturamento: float,
) -> list[_AnexoFaixa]:
    if setor == "comércio":
        return _ANEXO_I
    if setor == "indústria":
        return _ANEXO_II
    fator_r = (folha or 0) / faturamento if faturamento > 0 else 0
    if fator_r >= 0.28:
        return _ANEXO_III
    return _ANEXO_V


def _calc_simples(
    faturamento: float,
    setor: Literal["comércio", "serviços", "indústria"],
    folha: float | None,
) -> tuple[bool, float | None, float | None, str | None]:
    if faturamento > _LIMITE_SIMPLES:
        return (
            False,
            None,
            None,
            "Faturamento excede o limite anual do Simples Nacional (R$ 4,8 milhoes).",
        )

    tabela = _tabela_simples(setor, folha, faturamento)
    aliquota = _aliquota_efetiva_simples(faturamento, tabela)
    imposto = faturamento * aliquota / 100
    return True, aliquota, imposto, None


def _calc_lucro_presumido(
    faturamento: float, setor: Literal["comércio", "serviços", "indústria"]
) -> tuple[bool, float | None, float | None, str | None]:
    if faturamento > _LIMITE_LUCRO_PRESUMIDO:
        return (
            False,
            None,
            None,
            "Faturamento excede o limite anual do Lucro Presumido (R$ 78 milhoes).",
        )
    if setor == "serviços":
        presuncao = 0.32
    else:
        presuncao = 0.08
    base_irpj = faturamento * presuncao
    irpj = base_irpj * 0.15
    csll = base_irpj * 0.09
    pis_cofins = faturamento * 0.0365
    if setor == "serviços":
        outros = faturamento * 0.05
    else:
        outros = faturamento * 0.12
    total = irpj + csll + pis_cofins + outros
    aliquota_efetiva = total / faturamento * 100
    return True, aliquota_efetiva, total, None


def _calc_lucro_real_simplificado(
    faturamento: float, setor: Literal["comércio", "serviços", "indústria"]
) -> tuple[bool, float | None, float | None, str | None]:
    margem = 0.15
    lucro = faturamento * margem
    irpj = lucro * 0.15
    adicional = max(0.0, lucro - 240_000) * 0.10
    csll = lucro * 0.09
    pis_cofins = faturamento * 0.0925
    if setor == "serviços":
        outros = faturamento * 0.05
    else:
        outros = faturamento * 0.12
    total = irpj + adicional + csll + pis_cofins + outros
    aliquota_efetiva = total / faturamento * 100
    return True, aliquota_efetiva, total, None


def _calc_mei(
    faturamento: float, setor: Literal["comércio", "serviços", "indústria"]
) -> tuple[bool, float | None, float | None, str | None]:
    if faturamento > _LIMITE_MEI:
        return False, None, None, "Faturamento excede o limite anual do MEI (R$ 81 mil)."
    mensal = 80 if setor == "serviços" else 75
    total = mensal * 12
    aliquota_efetiva = total / faturamento * 100 if faturamento else 0
    return True, aliquota_efetiva, total, None


def compare_tax_regimes(
    faturamento_anual: float,
    setor: Literal["comércio", "serviços", "indústria"],
    folha_pagamento_anual: float | None = None,
) -> TaxRegimeComparison:
    """
    Compara regimes tributarios brasileiros (MEI, Simples, Lucro Presumido, Lucro Real).

    Estimativa rápida baseada em tabelas publicas vigentes. NAO substitui parecer
    de contador. Util para direcionamento em decisões de planejamento tributário.

    Args:
        faturamento_anual: Receita bruta anual em reais.
        setor: Setor da empresa (impacta anexo do Simples e presuncoes do LP).
        folha_pagamento_anual: Folha anual em reais. Importante para Fator R no Simples
            (serviços): se folha/faturamento >= 28%, usa Anexo III (mais barato).

    Returns:
        TaxRegimeComparison com opcoes avaliadas, melhor regime e economia estimada.

    Exemplo:
        resultado = compare_tax_regimes(
            faturamento_anual=500_000,
            setor="serviços",
            folha_pagamento_anual=180_000,
        )
        print(resultado.melhor_opcao)  # "simples_nacional"
        print(resultado.economia_anual_vs_pior)  # economia vs pior opção
    """
    if faturamento_anual <= 0:
        raise ValueError("faturamento_anual deve ser positivo")

    opcoes_calc = [
        ("mei", _calc_mei(faturamento_anual, setor)),
        ("simples_nacional", _calc_simples(faturamento_anual, setor, folha_pagamento_anual)),
        ("lucro_presumido", _calc_lucro_presumido(faturamento_anual, setor)),
        ("lucro_real", _calc_lucro_real_simplificado(faturamento_anual, setor)),
    ]

    opcoes: list[TaxRegimeOption] = []
    for regime, (aplicavel, alíquota, imposto, motivo) in opcoes_calc:
        pros: list[str] = []
        contras: list[str] = []
        if regime == "mei":
            pros = ["Tributacao fixa mensal", "Burocracia minima"]
            contras = ["Limite baixo de faturamento", "Restrito a algumas atividades"]
        elif regime == "simples_nacional":
            pros = ["Recolhimento unificado (DAS)", "Aliquotas progressivas"]
            contras = ["Limite de R$ 4,8 mi anual", "Limitacoes em serviços especificos"]
        elif regime == "lucro_presumido":
            pros = ["Calculo simples", "Aproveitamento de margens altas"]
            contras = ["PIS/COFINS cumulativos", "Pode pagar imposto sobre lucro inexistente"]
        else:
            pros = [
                "Sem teto de faturamento",
                "PIS/COFINS não-cumulativos com creditos",
                "Imposto sobre lucro real",
            ]
            contras = [
                "Burocracia alta (escrituracao completa)",
                "Custo contabil maior",
                "Antecipacoes mensais",
            ]
        opcoes.append(
            TaxRegimeOption(
                regime=regime,
                aplicavel=aplicavel,
                motivo_inaplicavel=motivo,
                aliquota_efetiva_estimada=alíquota,
                imposto_anual_estimado=imposto,
                pros=pros,
                contras=contras,
            )
        )

    aplicaveis = [o for o in opcoes if o.aplicavel and o.imposto_anual_estimado is not None]
    if not aplicaveis:
        raise RuntimeError("Nenhum regime aplicavel ao cenário fornecido")

    aplicaveis.sort(key=lambda o: o.imposto_anual_estimado or float("inf"))
    melhor = aplicaveis[0]
    pior_aplicavel = aplicaveis[-1]
    economia = (pior_aplicavel.imposto_anual_estimado or 0) - (melhor.imposto_anual_estimado or 0)

    obs = (
        "Estimativa simplificada usando tabelas publicas vigentes em 2025. "
        "Simples Nacional usa alíquota efetiva da LC 123/2006 art. 18 §1º-A "
        "(nominal com parcela a deduzir). Considera presuncoes médias de ICMS/ISS. "
        "Não inclui Anexo IV, beneficios estaduais nem regimes especiais. "
        "Consulte contador para decisão final."
    )

    return TaxRegimeComparison(
        cenario_faturamento_anual=faturamento_anual,
        cenario_setor=setor,
        folha_pagamento_anual=folha_pagamento_anual,
        opcoes=[*aplicaveis, *(o for o in opcoes if not o.aplicavel)],
        melhor_opcao=melhor.regime,
        economia_anual_vs_pior=economia,
        observacoes=obs,
    )
