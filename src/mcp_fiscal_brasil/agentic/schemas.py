"""Schemas de saida das tools agenticas.

Cada modelo e desenhado para ser auto-explicativo quando serializado para
um LLM. Campos com `description` rica ajudam o agente a entender o significado
sem precisar consultar documentacao externa.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["baixo", "medio", "alto", "critico"]


class ComplianceFinding(BaseModel):
    """Um achado isolado de uma analise de compliance fiscal."""

    categoria: Literal[
        "situacao_cadastral",
        "regime_tributario",
        "atividade",
        "endereco",
        "certidoes",
        "qsa",
    ] = Field(description="Categoria do achado dentro da analise.")
    severidade: RiskLevel = Field(description="Severidade do achado.")
    titulo: str = Field(description="Resumo curto do achado.")
    detalhe: str = Field(description="Descricao detalhada explicando o porque.")
    recomendacao: str | None = Field(
        default=None, description="Acao sugerida ao operador, quando aplicavel."
    )


class ComplianceReport(BaseModel):
    """Relatorio agregado de compliance fiscal de um CNPJ.

    Combina dados de CNPJ, Simples Nacional, MEI, CNAE e certidoes em uma
    visao unica orientada a decisão (contratar, recusar, investigar).
    """

    cnpj: str = Field(description="CNPJ analisado (somente digitos).")
    razao_social: str = Field(description="Razao social conforme Receita Federal.")
    risco_geral: RiskLevel = Field(description="Risco consolidado da empresa.")
    score: int = Field(
        ge=0,
        le=100,
        description="Score de 0 (critico) a 100 (excelente). Combina situacao, regime, atividade.",
    )
    achados: list[ComplianceFinding] = Field(
        default_factory=list, description="Lista de achados detalhados."
    )
    resumo_executivo: str = Field(
        description="Paragrafo unico em pt-BR resumindo a situacao para um humano."
    )
    fontes_consultadas: list[str] = Field(
        default_factory=list,
        description="Fontes que responderam com sucesso (ex: BrasilAPI, ReceitaWS).",
    )


class TaxRegimeOption(BaseModel):
    """Comparativo de um regime tributário para um cenário especifico."""

    regime: Literal["simples_nacional", "lucro_presumido", "lucro_real", "mei"]
    aplicavel: bool = Field(description="Se o regime e legalmente acessivel ao perfil.")
    motivo_inaplicavel: str | None = Field(
        default=None,
        description="Quando aplicavel=False, motivo curto (ex: faturamento excede limite).",
    )
    aliquota_efetiva_estimada: float | None = Field(
        default=None,
        description="Aliquota efetiva estimada (%) sobre faturamento, considerando anexo/setor.",
    )
    imposto_anual_estimado: float | None = Field(
        default=None, description="Imposto anual estimado em reais para o cenário fornecido."
    )
    pros: list[str] = Field(default_factory=list, description="Vantagens do regime.")
    contras: list[str] = Field(default_factory=list, description="Desvantagens do regime.")


class TaxRegimeComparison(BaseModel):
    """Comparativo entre regimes tributarios para um cenário."""

    cenario_faturamento_anual: float = Field(
        description="Faturamento anual usado no cálculo (reais)."
    )
    cenario_setor: Literal["comércio", "serviços", "indústria"] = Field(
        description="Setor da empresa (impacta anexo do Simples)."
    )
    folha_pagamento_anual: float | None = Field(
        default=None, description="Folha de pagamento anual usada no Fator R (opcional)."
    )
    opcoes: list[TaxRegimeOption] = Field(
        description="Opcoes avaliadas, do mais ao menos vantajoso."
    )
    melhor_opcao: Literal["simples_nacional", "lucro_presumido", "lucro_real", "mei"] = Field(
        description="Regime recomendado considerando aplicabilidade e custo."
    )
    economia_anual_vs_pior: float = Field(
        description="Economia anual estimada do melhor versus pior regime aplicavel."
    )
    observacoes: str = Field(
        description="Notas qualitativas: limitacoes do cálculo, premissas, alertas."
    )


class SupplierRiskScore(BaseModel):
    """Score de risco de um fornecedor para due diligence."""

    cnpj: str
    razao_social: str
    risco: RiskLevel
    score: int = Field(ge=0, le=100, description="0=critico, 100=excelente.")
    fatores: list[str] = Field(
        description="Fatores que contribuiram para o score (positivos e negativos)."
    )
    recomendacao: Literal["aprovar", "aprovar_com_ressalvas", "investigar", "recusar"] = Field(
        description="Recomendacao binaria/quaternaria de contratacao."
    )
    data_analise: date = Field(default_factory=date.today)


class SupplierRiskBatchItem(BaseModel):
    """Resultado por fornecedor em avaliação em lote."""

    cnpj: str = Field(description="CNPJ consultado (somente dígitos).")
    resumo_compliance: ComplianceReport | None = Field(
        default=None,
        description="Resumo consolidado de compliance para este CNPJ, se a consulta teve sucesso.",
    )
    score_fornecedor: SupplierRiskScore | None = Field(
        default=None,
        description="Score de risco de fornecedor para este CNPJ, se a análise de risco tiver sucesso.",
    )
    erro: str | None = Field(
        default=None,
        description="Mensagem de erro agregada para este CNPJ quando há falha parcial ou total.",
    )


class SupplierRiskBatchResult(BaseModel):
    """Resultado consolidado da consulta de múltiplos CNPJs."""

    total_consultados: int = Field(description="Quantidade de CNPJs recebidos na solicitação.")
    criterios_estritos: bool = Field(description="Flag usada para reduzir o score de risco.")
    resultados: list[SupplierRiskBatchItem] = Field(
        description="Resultado individual por CNPJ consultado."
    )
    total_processados: int = Field(
        description="Quantidade de CNPJs com consulta concluída com sucesso."
    )
    erros: list[str] = Field(
        default_factory=list, description="Erros agregados por CNPJ durante a análise."
    )


class NFeValidationIssue(BaseModel):
    """Problema individual detectado em validação de NFe."""

    severidade: RiskLevel
    código: str = Field(description="Codigo curto do tipo de problema (ex: CHAVE_INVALIDA).")
    descrição: str
    campo: str | None = Field(default=None, description="Campo XML afetado, se aplicavel.")


class NFeValidationReport(BaseModel):
    """Relatorio completo de validação de uma NFe (XML)."""

    chave_acesso: str = Field(description="Chave de 44 digitos.")
    valida_estruturalmente: bool = Field(description="XML bem-formado e schema-compatible.")
    chave_consistente: bool = Field(description="Digito verificador da chave bate com o conteudo.")
    emissor_ativo: bool | None = Field(
        default=None, description="Se conseguiu confirmar emissor ativo via CNPJ lookup."
    )
    issues: list[NFeValidationIssue] = Field(default_factory=list)
    cnpj_emissor: str | None = None
    cnpj_destinatario: str | None = None
    valor_total: float | None = None
    data_emissao: date | None = None
    resumo: str = Field(description="Sumario em uma frase do estado da NFe.")


class SPEDSummary(BaseModel):
    """Sumario executivo de um arquivo SPED."""

    arquivo: str = Field(description="Nome do arquivo SPED analisado.")
    tipo: Literal["fiscal", "contribuicoes", "ecf", "ecd"] = Field(description="Tipo do SPED.")
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    total_registros: int = Field(ge=0, description="Numero total de registros válidos.")
    total_blocos: int = Field(ge=0)
    cnpj: str | None = None
    razao_social: str | None = None
    inconsistencias: list[str] = Field(
        default_factory=list, description="Inconsistencias estruturais encontradas."
    )
    metricas_chave: dict[str, float] = Field(
        default_factory=dict,
        description="Metricas extraidas (ex: faturamento total, total icms, total pis_cofins).",
    )
    resumo: str = Field(description="Paragrafo executivo em pt-BR.")
