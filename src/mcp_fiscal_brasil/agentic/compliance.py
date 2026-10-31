"""Analise consolidada de compliance fiscal de um CNPJ."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp_fiscal_brasil._core import get_logger

from ..cnpj.client import CNPJClient
from ..mei.client import MEIClient
from ..shared.validators import normalizar_cnpj
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


_URL_ECAC = "https://cav.receita.fazenda.gov.br/autenticacao/login"
_URL_PGMEI = "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/pgmei.app/Identificacao"
_URL_DASN = "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/dasnsimei.app/Identificacao"
_URL_COMPROVANTE = (
    "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp"
)


def _fonte_confirma_mei(status: Any | None) -> bool:
    if status is None or not getattr(status, "mei", False):
        return False
    return bool(getattr(status, "fonte_confirmada", True))


def _simei_confirmado(simples_data: Any | None, mei_data: Any | None) -> bool:
    return _fonte_confirma_mei(mei_data) or _fonte_confirma_mei(simples_data)


def _motivo_indica_omissao(motivo: str | None, situacao_str: str) -> bool:
    texto = f"{motivo or ''} {situacao_str}".casefold()
    return "omiss" in texto


def _achado_situacao(
    risco_sit: RiskLevel,
    situacao_str: str,
    simples_data: Any | None,
    mei_data: Any | None,
    motivo_situacao: str | None = None,
) -> ComplianceFinding:
    situacao_l = situacao_str.casefold()
    is_inapta = "inapta" in situacao_l
    is_omissao = _motivo_indica_omissao(motivo_situacao, situacao_str)
    if (not is_inapta and not is_omissao) or risco_sit not in ("alto", "critico"):
        recomendacao = (
            "Confirmar regularizacao antes de contratar"
            if risco_sit in ("alto", "critico")
            else "Monitorar evolução da situacao"
        )
        return ComplianceFinding(
            categoria="situacao_cadastral",
            severidade=risco_sit,
            titulo=f"Situacao cadastral: {situacao_str}",
            detalhe=f"Empresa esta classificada como '{situacao_str}' na Receita Federal.",
            recomendacao=recomendacao,
        )

    simei = _simei_confirmado(simples_data, mei_data)
    passos = [
        f"Abrir o e-CAC e conferir a causa da situação e pendências: {_URL_ECAC}",
    ]
    if simei:
        passos.extend(
            [
                (
                    "Com Simei/MEI confirmado: entregar a DASN-SIMEI ano a ano, "
                    "do mais antigo ao mais recente (receita 0,00 se sem movimento; "
                    f"prazo normal até maio do ano seguinte): {_URL_DASN}"
                ),
                (
                    "Em paralelo, quitar no PGMEI os DAS mensais devidos "
                    f"(INSS do MEI mesmo sem receita). O pagamento do DAS não é "
                    f"condição para transmitir a DASN: {_URL_PGMEI}"
                ),
                (
                    "Atraso na DASN sujeita a multa (mínimo R$ 50,00 — LC 123/2006 art. 38); "
                    "verifique o DARF gerado após a transmissão."
                ),
            ]
        )
    else:
        passos.append(
            "Identificar no e-CAC a obrigação pendente (DASN-SIMEI só se for/foi Simei; "
            "senão DEFIS, PGDAS-D, DCTF, ECF, EFD etc.) e transmitir cada uma. "
            "Natureza 213-5 (EI) sozinha não prova MEI."
        )
    passos.append(
        "Após sanar as pendências, reemitir o comprovante CNPJ e confirmar "
        f"saída de INAPTA para ATIVA: {_URL_COMPROVANTE} "
        "(reversão processada diariamente pela RFB; INAPTA prolongada pode levar a baixa de ofício)."
    )
    if is_omissao:
        causa = (
            f"Motivo cadastral indica omissão"
            f"{f' ({motivo_situacao})' if motivo_situacao else ''} "
            "(IN RFB 2.119/2022). "
        )
    else:
        causa = (
            "Não afirme omissão sem conferir o motivo no e-CAC/comprovante; "
            "INAPTA pode ter outras causas (IN RFB 2.119/2022). "
        )
    detalhe = (
        f"Empresa classificada como '{situacao_str}' na Receita Federal. "
        f"{causa}"
        "Confirme no e-CAC quais obrigações faltam antes de contratar ou emitir documentos fiscais."
    )
    recomendacao = (
        "Transmitir as declarações omitidas via e-CAC/DASN-SIMEI (Simei confirmado); "
        "quitar DAS/multas em separado no PGMEI quando devidos."
        if simei
        else "Consultar e-CAC, identificar a obrigação pendente e transmitir antes de contratar."
    )
    return ComplianceFinding(
        categoria="situacao_cadastral",
        severidade=risco_sit,
        titulo=f"Situacao cadastral: {situacao_str}",
        detalhe=detalhe,
        recomendacao=recomendacao,
        proximos_passos=passos,
    )


async def analyze_cnpj_compliance(cnpj: str) -> ComplianceReport:
    """
    Analise consolidada de compliance fiscal de um CNPJ brasileiro.

    Consulta em paralelo: dados cadastrais (Receita), regime Simples Nacional,
    status MEI, CNAE principal e secundarios. Retorna um relatório unico com
    score 0-100, risco classificado e achados acionaveis.

    Args:
        cnpj: CNPJ numerico ou alfanumerico (IN RFB 2.229/2024), com ou sem formatacao.

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
    # normalizar_cnpj preserva letras (CNPJ alfanumérico, IN RFB 2.229/2024) em vez
    # de descartá-las como o antigo strip por isdigit(). A validação aqui é só de
    # comprimento (o dígito verificador é validado nas entradas consultar_cnpj/API/SDK).
    cnpj_limpo = normalizar_cnpj(cnpj)
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

    risco_sit, situacao_str = _risco_situacao(cnpj_data.situacao_cadastral)
    if risco_sit != "baixo":
        achados.append(
            _achado_situacao(
                risco_sit,
                situacao_str,
                simples_data,
                mei_data,
                getattr(cnpj_data, "motivo_situacao_cadastral", None),
            )
        )
    fontes_ok.append(getattr(cnpj_data, "origem", "Receita"))

    if simples_data is not None:
        if getattr(simples_data, "fonte_confirmada", True):
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
        else:
            achados.append(
                ComplianceFinding(
                    categoria="regime_tributario",
                    severidade="medio",
                    titulo="Simples Nacional não confirmado pela fonte",
                    detalhe=(
                        "A consulta ao endpoint Simples/CNPJ não confirmou o "
                        "enquadramento; mei/simples_nacional=false não é negativo definitivo."
                    ),
                    recomendacao="Consultar e-CAC ou comprovante oficial da RFB.",
                )
            )

    if mei_data is not None:
        if getattr(mei_data, "fonte_confirmada", True):
            fontes_ok.append("MEI Receita")
        else:
            achados.append(
                ComplianceFinding(
                    categoria="regime_tributario",
                    severidade="medio",
                    titulo="Status MEI não confirmado pela fonte",
                    detalhe=(
                        "A consulta MEI não foi confirmada (fonte_confirmada=false); "
                        "mei=false não representa negativa definitiva."
                    ),
                    recomendacao="Consultar e-CAC ou comprovante oficial da RFB.",
                )
            )

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
