"""Analise consolidada de compliance fiscal de um CNPJ."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp_fiscal_brasil._core import get_logger

from ..cnpj.client import CNPJClient
from ..mei.client import MEIClient
from ..simples.client import SimplesClient
from .schemas import ComplianceFinding, ComplianceReport, RiskLevel

logger = get_logger(__name__)


_SITUACAO_RISCOS: dict[str, RiskLevel] = {
    "ativa": "baixo",
    "ativo": "baixo",
    "suspensa": "medio",
    "inapta": "alto",
    "baixada": "critico",
    "nula": "critico",
}


async def _consultar_seguro(coro: Any, fonte: str) -> tuple[str, Any | None]:
    """Executa coroutine retornando None em qualquer falha (sem bloquear analise)."""
    try:
        result = await coro
        return fonte, result
    except Exception as exc:
        logger.warning("compliance_source_failed", fonte=fonte, error=str(exc))
        return fonte, None


def _risco_situacao(situacao: str | None) -> tuple[RiskLevel, str]:
    if not situacao:
        return "medio", "Situacao cadastral não retornada pela fonte"
    chave = situacao.strip().lower()
    for k, risco in _SITUACAO_RISCOS.items():
        if k in chave:
            return risco, situacao
    return "medio", situacao


def _score_de_risco(risco: RiskLevel) -> int:
    return {"baixo": 90, "medio": 60, "alto": 30, "critico": 5}[risco]


def _consolida_risco(achados: list[ComplianceFinding]) -> RiskLevel:
    if not achados:
        return "baixo"
    severidades = [a.severidade for a in achados]
    if "critico" in severidades:
        return "critico"
    if "alto" in severidades:
        return "alto"
    if "medio" in severidades:
        return "medio"
    return "baixo"


async def analyze_cnpj_compliance(cnpj: str) -> ComplianceReport:
    """
    Analise consolidada de compliance fiscal de um CNPJ brasileiro.

    Consulta em paralelo: dados cadastrais (Receita), regime Simples Nacional,
    status MEI, CNAE principal e secundarios. Retorna um relatório unico com
    score 0-100, risco classificado e achados acionaveis.

    Args:
        cnpj: CNPJ com ou sem formatacao (so digitos são usados).

    Returns:
        ComplianceReport com risco_geral, score, achados e resumo executivo.

    Exemplo de uso por um agente:
        report = await analyze_cnpj_compliance("12.345.678/0001-90")
        if report.risco_geral in ("alto", "critico"):
            # bloquear cadastro de fornecedor
            ...

    Nota:
        Esta tool NAO consulta certidoes negativas reais (somente gera URLs).
        Para validação de certidoes use as ferramentas especificas do modulo certidoes.
    """
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    if len(cnpj_limpo) != 14:
        raise ValueError(f"CNPJ deve ter 14 digitos, recebido {len(cnpj_limpo)}: {cnpj}")

    logger.info("compliance_analysis_started", cnpj=cnpj_limpo)

    cnpj_client = CNPJClient()
    simples_client = SimplesClient()
    mei_client = MEIClient()

    resultados = await asyncio.gather(
        _consultar_seguro(cnpj_client.consultar(cnpj_limpo), "cnpj"),
        _consultar_seguro(simples_client.get_simples_status(cnpj_limpo), "simples"),
        _consultar_seguro(mei_client.get_mei_status(cnpj_limpo), "mei"),
    )
    dados = dict(resultados)

    cnpj_data = dados.get("cnpj")
    simples_data = dados.get("simples")
    mei_data = dados.get("mei")

    if cnpj_data is None:
        raise RuntimeError(
            f"Não foi possivel consultar dados do CNPJ {cnpj_limpo} em nenhuma fonte"
        )

    achados: list[ComplianceFinding] = []
    fontes_ok: list[str] = []

    # Situacao cadastral
    risco_sit, situacao_str = _risco_situacao(cnpj_data.situacao_cadastral)
    if risco_sit != "baixo":
        achados.append(
            ComplianceFinding(
                categoria="situacao_cadastral",
                severidade=risco_sit,
                titulo=f"Situacao cadastral: {situacao_str}",
                detalhe=f"Empresa esta classificada como '{situacao_str}' na Receita Federal.",
                recomendacao=(
                    "Confirmar regularizacao antes de contratar"
                    if risco_sit in ("alto", "critico")
                    else "Monitorar evolução da situacao"
                ),
            )
        )
    fontes_ok.append(getattr(cnpj_data, "origem", "Receita"))

    # Regime tributário
    if simples_data is not None:
        fontes_ok.append("Simples Nacional")
        if not simples_data.simples_nacional:
            achados.append(
                ComplianceFinding(
                    categoria="regime_tributario",
                    severidade="baixo",
                    titulo="Não optante pelo Simples Nacional",
                    detalhe="Empresa não consta como optante do Simples Nacional.",
                )
            )

    if mei_data is not None:
        fontes_ok.append("MEI Receita")

    # CNAE - sem flag por enquanto, mas registra como achado informativo
    if cnpj_data.atividade_principal:
        código = cnpj_data.atividade_principal.código
        descrição = cnpj_data.atividade_principal.descrição
        achados.append(
            ComplianceFinding(
                categoria="atividade",
                severidade="baixo",
                titulo=f"CNAE principal {código}",
                detalhe=descrição,
            )
        )

    # Endereco básico
    if not cnpj_data.endereco or not cnpj_data.endereco.municipio:
        achados.append(
            ComplianceFinding(
                categoria="endereco",
                severidade="medio",
                titulo="Endereco incompleto",
                detalhe="Endereco cadastral incompleto ou não retornado pela fonte.",
                recomendacao="Solicitar comprovante de endereco atualizado.",
            )
        )

    # QSA vazio
    if not cnpj_data.qsa:
        achados.append(
            ComplianceFinding(
                categoria="qsa",
                severidade="medio",
                titulo="Quadro de sócios não disponível",
                detalhe="QSA não retornado, dificultando due diligence de sócios.",
                recomendacao="Solicitar contrato social atualizado.",
            )
        )

    risco_geral = _consolida_risco(achados)
    score = _score_de_risco(risco_geral)

    resumo = (
        f"CNPJ {cnpj_limpo} ({cnpj_data.razao_social}) apresenta risco "
        f"{risco_geral} (score {score}/100). "
        f"Situacao: {cnpj_data.situacao_cadastral or 'não informada'}. "
        f"Foram identificados {len(achados)} achado(s) na analise."
    )

    return ComplianceReport(
        cnpj=cnpj_limpo,
        razao_social=cnpj_data.razao_social,
        risco_geral=risco_geral,
        score=score,
        achados=achados,
        resumo_executivo=resumo,
        fontes_consultadas=fontes_ok,
    )
