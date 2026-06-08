"""Score de risco de fornecedor combinando compliance + heuristica."""

from __future__ import annotations

import asyncio
from typing import Literal

from mcp_fiscal_brasil._core import get_logger

from .compliance import analyze_cnpj_compliance
from .schemas import (
    ComplianceReport,
    SupplierRiskBatchItem,
    SupplierRiskBatchResult,
    SupplierRiskScore,
)


def _normaliza_cnpj(cnpj: str) -> str:
    """Normaliza CNPJ para apenas dígitos."""
    return "".join(d for d in cnpj if d.isdigit())


def _erro_consulta(cnpj: str, erro: Exception | str) -> str:
    return f"{_normaliza_cnpj(cnpj)}: {erro}"


logger = get_logger(__name__)

_MAX_CONCORRENTE = 4


def _recomendacao(
    score: int,
) -> Literal["aprovar", "aprovar_com_ressalvas", "investigar", "recusar"]:
    if score >= 80:
        return "aprovar"
    if score >= 60:
        return "aprovar_com_ressalvas"
    if score >= 30:
        return "investigar"
    return "recusar"


async def risk_score_supplier(cnpj: str, criterios_estritos: bool = False) -> SupplierRiskScore:
    """
    Calcula score de risco para due diligence de fornecedor.

    Baseia-se em ComplianceReport e aplica ajustes para o contexto de
    contratacao de fornecedor (mais conservador que compliance geral).

    Args:
        cnpj: CNPJ do fornecedor (com ou sem formatacao).
        criterios_estritos: Se True, reduz tolerancia (subtrai 10 pontos do score).
            Usar quando contratante tem politica anti-corrupcao agressiva.

    Returns:
        SupplierRiskScore com recomendacao acionavel.

    Exemplo:
        score = await risk_score_supplier("12.345.678/0001-90", criterios_estritos=True)
        if score.recomendacao == "recusar":
            # bloquear cadastro
            ...
    """
    compliance = await analyze_cnpj_compliance(cnpj)
    return _score_from_compliance(compliance, criterios_estritos=criterios_estritos)


def _score_from_compliance(
    compliance: ComplianceReport,
    criterios_estritos: bool = False,
) -> SupplierRiskScore:
    """Converte um relatório de compliance em score de fornecedor."""
    score = compliance.score
    fatores: list[str] = []

    if compliance.risco_geral == "baixo":
        fatores.append("Situacao cadastral regular")
    if compliance.razao_social:
        fatores.append(f"Empresa identificada: {compliance.razao_social}")

    for achado in compliance.achados:
        if achado.severidade in ("alto", "critico"):
            score -= 15
            fatores.append(f"NEGATIVO: {achado.titulo}")
        elif achado.severidade == "medio":
            score -= 5
            fatores.append(f"Atencao: {achado.titulo}")

    if criterios_estritos:
        score -= 10
        fatores.append("Criterios estritos aplicados (-10)")

    score = max(0, min(100, score))

    if score >= 80:
        risco = "baixo"
    elif score >= 60:
        risco = "medio"
    elif score >= 30:
        risco = "alto"
    else:
        risco = "critico"

    return SupplierRiskScore(
        cnpj=compliance.cnpj,
        razao_social=compliance.razao_social,
        risco=risco,
        score=score,
        fatores=fatores,
        recomendacao=_recomendacao(score),
    )


async def consultar_empresas_lote(
    cnpjs: list[str],
    criterios_estritos: bool = False,
) -> SupplierRiskBatchResult:
    """
    Consulta em lote CNPJs para consolidar compliance e score de risco.

    Para cada CNPJ, combina:
      - analyze_cnpj_compliance (contexto de compliance)
      - risk_score_supplier (score para tomada de decisão de fornecedor)

    A resposta devolve por-item resultados de sucesso e erro, facilitando a priorização
    de contato com fornecedores em cadastros de alto volume.

    Args:
        cnpjs: Lista de CNPJs (com ou sem formatação).
        criterios_estritos: Se True, repassa para risco e ajusta mais conservadoramente.
    """
    semaforo = asyncio.Semaphore(_MAX_CONCORRENTE)

    async def _processa_um(indice: int, cnpj: str) -> tuple[int, SupplierRiskBatchItem]:
        item = SupplierRiskBatchItem(cnpj=_normaliza_cnpj(cnpj))

        async with semaforo:
            try:
                compliance = await analyze_cnpj_compliance(cnpj)
                item.resumo_compliance = compliance
                item.score_fornecedor = _score_from_compliance(
                    compliance,
                    criterios_estritos=criterios_estritos,
                )
            except Exception as exc:
                item.erro = _erro_consulta(cnpj, exc)
                logger.error(
                    "consultar_empresas_lote.item_falhou",
                    cnpj=item.cnpj,
                    indice=indice,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )

        return indice, item

    tarefas = [_processa_um(indice, cnpj) for indice, cnpj in enumerate(cnpjs)]
    resultados = sorted(await asyncio.gather(*tarefas))
    resultados_ordenados = [item for _, item in resultados]

    erros = [item.erro for item in resultados_ordenados if item.erro is not None]
    total_processados = sum(1 for item in resultados_ordenados if item.erro is None)

    return SupplierRiskBatchResult(
        total_consultados=len(cnpjs),
        criterios_estritos=criterios_estritos,
        resultados=resultados_ordenados,
        total_processados=total_processados,
        erros=erros,
    )
