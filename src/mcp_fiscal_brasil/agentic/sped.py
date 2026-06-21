"""Sumarizacao executiva de arquivos SPED."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp_fiscal_brasil._core import get_logger

from ..sped.tools import (
    CAMPO_0110_REGIME,
    CAMPO_E110_RECOLHER,
    CAMPO_E110_TOT_DEBITOS,
    CAMPO_VALOR,
    REGIME_0110,
    _parse_linha_sped,
    _to_float,
    analisar_sped,
)
from .schemas import SPEDSummary

logger = get_logger(__name__)


_TIPO_MAP: dict[str, Literal["fiscal", "contribuicoes", "ecf", "ecd"]] = {
    "EFD-ICMS-IPI": "fiscal",
    "EFD-Contribuicoes": "contribuicoes",
    "ECD": "ecd",
    "ECF": "ecf",
}

# Mapeamento de registro -> chave de métrica no SPEDSummary.metricas_chave.
# Usado apenas para M210 e M610 (VL_CONT_PER, valor a recolher do período).
# O registro E110 é processado separadamente porque expõe dois campos distintos.
_METRICA_REGISTRO: dict[str, str] = {
    "M210": "pis_total",
    "M610": "cofins_total",
}


def _extrair_metricas_financeiras(conteudo: str) -> dict[str, float]:
    """Extrai e soma valores monetários de registros fiscais relevantes.

    Varre as linhas do arquivo SPED uma única vez, acumulando os valores
    dos registros M210, M610 e E110 nas métricas correspondentes.
    Também captura o regime PIS/COFINS do registro 0110.

    Semântica dos valores retornados (importante para comparações):
      - pis_total, cofins_total e icms_a_recolher são valores A RECOLHER do
        período, já líquidos de créditos e deduções. São comparáveis entre si.
      - icms_total_debitos é o total BRUTO de débitos por saídas/prestações,
        ANTES de subtrair créditos e deduções. Serve como informativo sobre o
        volume de operações tributadas, mas NÃO deve ser somado aos demais para
        calcular carga fiscal total.

    Fontes dos campos (Guia Prático EFD ICMS/IPI, Ato COTEPE/ICMS 44/2018):
      M210 campo 7 (índice 6) = VL_CONT_PER  - PIS a recolher no período
      M610 campo 7 (índice 6) = VL_CONT_PER  - COFINS a recolher no período
      E110 campo 2 (índice 0) = VL_TOT_DEBITOS   - débitos BRUTOS de ICMS
      E110 campo 13 (índice 11) = VL_ICMS_RECOLHER - ICMS a recolher (líquido)

    Args:
        conteudo: Texto completo do arquivo SPED (separado por pipes).

    Returns:
        Dicionário com as métricas extraídas:
          - pis_total: soma de VL_CONT_PER de todos os M210 (a recolher no período)
          - cofins_total: soma de VL_CONT_PER de todos os M610 (a recolher no período)
          - icms_total_debitos: soma de VL_TOT_DEBITOS do E110 (débitos BRUTOS, informativo)
          - icms_a_recolher: soma de VL_ICMS_RECOLHER do E110 (valor líquido a recolher)
          - regime_pis_cofins: 0.0=nao detectado, 1.0=cumulativo, 2.0=nao-cumulativo
    """
    acumuladores: dict[str, float] = {
        "pis_total": 0.0,
        "cofins_total": 0.0,
        "icms_total_debitos": 0.0,
        "icms_a_recolher": 0.0,
        "regime_pis_cofins": 0.0,
    }

    for linha in conteudo.strip().splitlines():
        linha = linha.strip()
        if not linha:
            continue
        campos = _parse_linha_sped(linha)
        if not campos:
            continue

        registro = campos[0]
        campos_dados = campos[1:]  # sem o campo REG

        if registro in CAMPO_VALOR:
            idx = CAMPO_VALOR[registro]
            if idx < len(campos_dados):
                metrica = _METRICA_REGISTRO[registro]
                acumuladores[metrica] += _to_float(campos_dados[idx])

        elif registro == "E110":
            # VL_TOT_DEBITOS: débitos BRUTOS (campo 02, índice 0) - informativo
            if CAMPO_E110_TOT_DEBITOS < len(campos_dados):
                acumuladores["icms_total_debitos"] += _to_float(
                    campos_dados[CAMPO_E110_TOT_DEBITOS]
                )
            # VL_ICMS_RECOLHER: valor líquido a recolher (campo 13, índice 11)
            if CAMPO_E110_RECOLHER < len(campos_dados):
                acumuladores["icms_a_recolher"] += _to_float(campos_dados[CAMPO_E110_RECOLHER])

        elif registro == "0110" and CAMPO_0110_REGIME < len(campos_dados):
            cod = campos_dados[CAMPO_0110_REGIME].strip()
            if cod in REGIME_0110:
                # Semântica: o ÚLTIMO registro 0110 encontrado vence, o que é
                # correto para arquivos de período único. Em arquivos multi-período
                # (concatenados), pode haver mais de um 0110; se os regimes
                # diferirem, registramos aviso pois a comparação entre períodos
                # pode ser inválida.
                anterior = acumuladores["regime_pis_cofins"]
                novo = float(cod)
                if anterior != 0.0 and anterior != novo:
                    logger.warning(
                        "divergencia_regime_pis_cofins",
                        regime_anterior=anterior,
                        regime_novo=novo,
                        mensagem=(
                            "Arquivo contém múltiplos registros 0110 com regimes distintos. "
                            "Será mantido o último encontrado. Comparações entre períodos "
                            "podem ser inválidas."
                        ),
                    )
                acumuladores["regime_pis_cofins"] = novo

    return acumuladores


async def summarize_sped(file_path: str | Path) -> SPEDSummary:
    """
    Sumarizacao executiva de um arquivo SPED.

    Le o arquivo, identifica tipo (Fiscal, Contribuicoes, ECF, ECD), extrai
    período, empresa, total de registros e produz resumo em pt-BR.

    Para EFD-Contribuicoes extrai pis_total (M210 VL_CONT_PER) e
    cofins_total (M610 VL_CONT_PER) - ambos valores a recolher no período.
    Para EFD ICMS/IPI extrai dois campos do E110:
      - icms_a_recolher (VL_ICMS_RECOLHER, campo 13): valor LÍQUIDO a recolher,
        comparável com pis_total e cofins_total.
      - icms_total_debitos (VL_TOT_DEBITOS, campo 02): total BRUTO de débitos
        por saídas/prestações, informativo, NÃO comparável com os demais.
    O regime PIS/COFINS (0110 COD_INC_TRIB) é capturado como regime_pis_cofins
    (1.0=cumulativo, 2.0=nao-cumulativo).

    Args:
        file_path: Caminho para arquivo .txt do SPED.

    Returns:
        SPEDSummary com período, empresa, metricas e resumo executivo.

    Exemplo:
        sumário = await summarize_sped("/tmp/sped_fiscal_201912.txt")
        print(sumário.resumo)
        for metrica, valor in sumário.metricas_chave.items():
            print(f"{metrica}: {valor}")
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo SPED não encontrado: {file_path}")

    conteudo = path.read_text(encoding="latin-1")
    analise = await analisar_sped(conteudo, nome_arquivo=path.name)
    metricas_financeiras = _extrair_metricas_financeiras(conteudo)

    tipo_norm = _TIPO_MAP.get(analise.tipo_sped, "fiscal")

    cnpj = None
    razao = None
    periodo_ini = None
    periodo_fim = None
    total_registros = 0
    tipos_registros: dict[str, int] = {}

    if analise.abertura:
        cnpj = analise.abertura.cnpj
        razao = analise.abertura.nome_empresarial

    if analise.resumo:
        periodo_ini = analise.resumo.periodo_inicial
        periodo_fim = analise.resumo.periodo_final
        total_registros = analise.resumo.total_registros
        tipos_registros = analise.resumo.tipos_registros
        if not cnpj:
            cnpj = analise.resumo.cnpj
        if not razao:
            razao = analise.resumo.razao_social

    total_blocos = len({k[0] for k in tipos_registros if k})

    metricas: dict[str, float] = {
        "total_registros": float(total_registros),
        "tipos_distintos": float(len(tipos_registros)),
        **metricas_financeiras,
    }

    inconsistencias = list(analise.erros) + [f"AVISO: {a}" for a in analise.avisos]

    periodo_str = ""
    if periodo_ini and periodo_fim:
        periodo_str = f" entre {periodo_ini.isoformat()} e {periodo_fim.isoformat()}"
    elif periodo_ini:
        periodo_str = f" iniciado em {periodo_ini.isoformat()}"

    empresa_str = f" para {razao}" if razao else ""
    regime_str = ""
    cod_regime = int(metricas_financeiras.get("regime_pis_cofins", 0.0))
    if cod_regime in (1, 2):
        nome_regime = REGIME_0110.get(str(cod_regime), "")
        regime_str = f" Regime PIS/COFINS: {nome_regime}."

    resumo = (
        f"Arquivo SPED {analise.tipo_sped}{empresa_str}{periodo_str}: "
        f"{total_registros} registros válidos em {total_blocos} blocos."
        f"{regime_str} "
        f"{len(inconsistencias)} inconsistencia(s) identificada(s)."
    )

    return SPEDSummary(
        arquivo=path.name,
        tipo=tipo_norm,
        periodo_inicio=periodo_ini,
        periodo_fim=periodo_fim,
        total_registros=total_registros,
        total_blocos=total_blocos,
        cnpj=cnpj,
        razao_social=razao,
        inconsistencias=inconsistencias,
        metricas_chave=metricas,
        resumo=resumo,
    )
