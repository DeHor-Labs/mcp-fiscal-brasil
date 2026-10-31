"""Comparativo entre regimes tributarios brasileiros.

Calculo simplificado, baseado em premissas publicas e tabelas vigentes em 2025.
Não substitui parecer de contador. Util para estimativa rápida e direcionamento.
"""

from __future__ import annotations

from typing import Literal

from .schemas import (
    CompareTaxRegimesRequest,
    TaxRegimeComparison,
    TaxRegimeOption,
)

_LIMITE_MEI = 81_000.0
_LIMITE_SIMPLES = 4_800_000.0
_LIMITE_LUCRO_PRESUMIDO = 78_000_000.0
_FATOR_R_MIN = 0.28
_SIMPLES_EXPORT_REMAINING = 0.509
_PIS_COFINS_LP = 0.0365
_PIS_COFINS_LR = 0.0925
_PRESUNCAO_SERVICOS = 0.32
_PRESUNCAO_OUTROS = 0.08

_AnexoFaixa = tuple[float, float, float]
_CalcResult = tuple[bool, float | None, float | None, str | None]
_Setor = Literal["comércio", "serviços", "indústria"]

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
    setor: _Setor,
    folha: float | None,
    faturamento: float,
) -> list[_AnexoFaixa]:
    if setor == "comércio":
        return _ANEXO_I
    if setor == "indústria":
        return _ANEXO_II
    fator_r = (folha or 0) / faturamento if faturamento > 0 else 0
    if fator_r >= _FATOR_R_MIN:
        return _ANEXO_III
    return _ANEXO_V


def _aplica_exportacao_simples(aliquota: float, setor: _Setor, exportacao: bool) -> float:
    if not exportacao:
        return aliquota
    if setor != "serviços":
        return aliquota
    return aliquota * _SIMPLES_EXPORT_REMAINING


def _calc_simples(
    faturamento: float,
    setor: _Setor,
    folha: float | None,
    exportacao_servicos: bool = False,
) -> _CalcResult:
    if faturamento > _LIMITE_SIMPLES:
        return (
            False,
            None,
            None,
            "Faturamento excede o limite anual do Simples Nacional (R$ 4,8 milhoes).",
        )
    tabela = _tabela_simples(setor, folha, faturamento)
    aliquota = _aplica_exportacao_simples(
        _aliquota_efetiva_simples(faturamento, tabela),
        setor,
        exportacao_servicos,
    )
    return True, aliquota, faturamento * aliquota / 100, None


def _iss_valor(faturamento: float, setor: _Setor, exportacao: bool, aliquota_iss: float) -> float:
    if setor != "serviços":
        return faturamento * 0.12
    if exportacao:
        return 0.0
    return faturamento * (aliquota_iss / 100.0)


def _calc_lucro_presumido(
    faturamento: float,
    setor: _Setor,
    exportacao_servicos: bool = False,
    aliquota_iss: float = 5.0,
) -> _CalcResult:
    if faturamento > _LIMITE_LUCRO_PRESUMIDO:
        return (
            False,
            None,
            None,
            "Faturamento excede o limite anual do Lucro Presumido (R$ 78 milhoes).",
        )
    presuncao = _PRESUNCAO_SERVICOS if setor == "serviços" else _PRESUNCAO_OUTROS
    base_irpj = faturamento * presuncao
    irpj = base_irpj * 0.15
    adicional = max(0.0, base_irpj - 240_000.0) * 0.10
    csll = base_irpj * 0.09
    pis_cofins = 0.0 if exportacao_servicos and setor == "serviços" else faturamento * _PIS_COFINS_LP
    iss = _iss_valor(faturamento, setor, exportacao_servicos, aliquota_iss)
    total = irpj + adicional + csll + pis_cofins + iss
    return True, total / faturamento * 100, total, None


def _calc_lucro_real_simplificado(
    faturamento: float,
    setor: _Setor,
    margem_lucro_real: float = 0.15,
    exportacao_servicos: bool = False,
    aliquota_iss: float = 5.0,
) -> _CalcResult:
    lucro = faturamento * margem_lucro_real
    irpj = lucro * 0.15
    adicional = max(0.0, lucro - 240_000.0) * 0.10
    csll = lucro * 0.09
    pis_cofins = 0.0 if exportacao_servicos and setor == "serviços" else faturamento * _PIS_COFINS_LR
    iss = _iss_valor(faturamento, setor, exportacao_servicos, aliquota_iss)
    total = irpj + adicional + csll + pis_cofins + iss
    return True, total / faturamento * 100, total, None


def _calc_mei(faturamento: float, setor: _Setor) -> _CalcResult:
    if faturamento > _LIMITE_MEI:
        return False, None, None, "Faturamento excede o limite anual do MEI (R$ 81 mil)."
    mensal = 80 if setor == "serviços" else 75
    total = mensal * 12
    aliquota_efetiva = total / faturamento * 100 if faturamento else 0
    return True, aliquota_efetiva, total, None


def _irpf_mensal(base: float) -> float:
    if base <= 2259.20:
        return 0.0
    if base <= 2826.65:
        return base * 0.075 - 169.44
    if base <= 3751.05:
        return base * 0.15 - 381.44
    if base <= 4664.68:
        return base * 0.225 - 662.77
    return base * 0.275 - 896.00


def _estimar_custo_pessoal_folha(folha_anual: float) -> float:
    if folha_anual <= 0:
        return 0.0
    inss = folha_anual * 0.11
    base_mensal = (folha_anual - inss) / 12.0
    return inss + _irpf_mensal(base_mensal) * 12.0


def _usa_fator_r(setor: _Setor, folha: float | None, faturamento: float) -> bool:
    if setor != "serviços":
        return False
    if not folha or faturamento <= 0:
        return False
    return (folha / faturamento) >= _FATOR_R_MIN


def _pros_contras(regime: str) -> tuple[list[str], list[str]]:
    if regime == "mei":
        return (
            ["Tributacao fixa mensal", "Burocracia minima"],
            ["Limite baixo de faturamento", "Restrito a algumas atividades"],
        )
    if regime == "simples_nacional":
        return (
            ["Recolhimento unificado (DAS)", "Aliquotas progressivas"],
            ["Limite de R$ 4,8 mi anual", "Limitacoes em serviços especificos"],
        )
    if regime == "lucro_presumido":
        return (
            ["Calculo simples", "Aproveitamento de margens altas"],
            ["PIS/COFINS cumulativos", "Pode pagar imposto sobre lucro inexistente"],
        )
    return (
        [
            "Sem teto de faturamento",
            "PIS/COFINS não-cumulativos com creditos",
            "Imposto sobre lucro real",
        ],
        [
            "Burocracia alta (escrituracao completa)",
            "Custo contabil maior",
            "Antecipacoes mensais",
        ],
    )


def _custo_ranqueamento(opcao: TaxRegimeOption) -> float:
    if opcao.custo_total_estimado is not None:
        return opcao.custo_total_estimado
    if opcao.imposto_anual_estimado is not None:
        return opcao.imposto_anual_estimado
    return float("inf")


def _montar_observacoes(request: CompareTaxRegimesRequest) -> str:
    partes = [
        "Estimativa simplificada com tabelas publicas vigentes em 2025.",
        "Simples usa alíquota efetiva (LC 123/2006 art. 18 §1º-A).",
        "Nao inclui Anexo IV, beneficios estaduais nem regimes especiais.",
    ]
    if request.exportacao_servicos and request.setor == "serviços":
        partes.append(
            "Exportacao de servicos: LP/Real sem ISS/PIS/Cofins; "
            "Simples com reducao aproximada de ISS/PIS/Cofins no DAS "
            "(LC 123 art. 18 §§ 4º-A e 14; MP 2.158-35 art. 14)."
        )
    if request.estimar_custo_fator_r:
        partes.append(
            "Ranking do Simples com Fator R inclui estimativa simplificada de INSS (11%) "
            "+ IRPF mensal sobre a folha informada."
        )
    partes.append(
        f"ISS municipal {request.aliquota_iss:.2f}% (quando aplicavel); "
        f"margem Lucro Real {request.margem_lucro_real * 100:.1f}%."
    )
    partes.append("Consulte contador para decisao final.")
    return " ".join(partes)


def compare_tax_regimes(
    faturamento_anual: float,
    setor: _Setor,
    folha_pagamento_anual: float | None = None,
    *,
    exportacao_servicos: bool = False,
    aliquota_iss: float = 5.0,
    margem_lucro_real: float = 0.15,
    estimar_custo_fator_r: bool = True,
) -> TaxRegimeComparison:
    if faturamento_anual <= 0:
        raise ValueError("faturamento_anual deve ser positivo")
    request = CompareTaxRegimesRequest(
        faturamento_anual=faturamento_anual,
        setor=setor,
        folha_pagamento_anual=folha_pagamento_anual,
        exportacao_servicos=exportacao_servicos,
        aliquota_iss=aliquota_iss,
        margem_lucro_real=margem_lucro_real,
        estimar_custo_fator_r=estimar_custo_fator_r,
    )
    return _compare_from_request(request)


def _compare_from_request(request: CompareTaxRegimesRequest) -> TaxRegimeComparison:
    fat = request.faturamento_anual
    setor = request.setor
    folha = request.folha_pagamento_anual
    exportacao = request.exportacao_servicos
    opcoes_calc = [
        ("mei", _calc_mei(fat, setor)),
        ("simples_nacional", _calc_simples(fat, setor, folha, exportacao)),
        (
            "lucro_presumido",
            _calc_lucro_presumido(fat, setor, exportacao, request.aliquota_iss),
        ),
        (
            "lucro_real",
            _calc_lucro_real_simplificado(
                fat,
                setor,
                request.margem_lucro_real,
                exportacao,
                request.aliquota_iss,
            ),
        ),
    ]
    custo_fator_r: float | None = None
    if (
        request.estimar_custo_fator_r
        and _usa_fator_r(setor, folha, fat)
        and folha is not None
    ):
        custo_fator_r = _estimar_custo_pessoal_folha(folha)

    opcoes: list[TaxRegimeOption] = []
    for regime, (aplicavel, aliquota, imposto, motivo) in opcoes_calc:
        pros, contras = _pros_contras(regime)
        pessoal = custo_fator_r if regime == "simples_nacional" else None
        total = None
        if imposto is not None:
            total = imposto + (pessoal or 0.0)
        if pessoal and regime == "simples_nacional":
            contras = [
                *contras,
                "Custo pessoal do Fator R (INSS/IRPF) incluido no custo_total_estimado",
            ]
        opcoes.append(
            TaxRegimeOption(
                regime=regime,  # type: ignore[arg-type]
                aplicavel=aplicavel,
                motivo_inaplicavel=motivo,
                aliquota_efetiva_estimada=aliquota,
                imposto_anual_estimado=imposto,
                custo_pessoal_fator_r_estimado=pessoal,
                custo_total_estimado=total,
                pros=pros,
                contras=contras,
            )
        )

    aplicaveis = [o for o in opcoes if o.aplicavel and o.imposto_anual_estimado is not None]
    if not aplicaveis:
        raise RuntimeError("Nenhum regime aplicavel ao cenário fornecido")

    aplicaveis.sort(key=_custo_ranqueamento)
    melhor = aplicaveis[0]
    pior = aplicaveis[-1]
    economia = _custo_ranqueamento(pior) - _custo_ranqueamento(melhor)

    return TaxRegimeComparison(
        cenario_faturamento_anual=fat,
        cenario_setor=setor,
        folha_pagamento_anual=folha,
        exportacao_servicos=exportacao,
        aliquota_iss=request.aliquota_iss,
        margem_lucro_real=request.margem_lucro_real,
        opcoes=[*aplicaveis, *(o for o in opcoes if not o.aplicavel)],
        melhor_opcao=melhor.regime,
        economia_anual_vs_pior=economia,
        observacoes=_montar_observacoes(request),
    )
