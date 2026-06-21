"""Schemas Pydantic para o módulo de cálculo de tributos de importação."""

from __future__ import annotations

from pydantic import Field

from ..shared.schemas import BaseResponse


class TributoItem(BaseResponse):
    """Detalhe de um tributo individual no breakdown da importação."""

    nome: str = Field(description="Nome do tributo (ex: II, IPI, PIS-Importação)")
    base_calculo: float = Field(description="Base de cálculo utilizada, em R$")
    aliquota: float = Field(description="Alíquota aplicada, em %")
    valor: float = Field(description="Valor calculado do tributo, em R$")
    fundamento: str = Field(description="Fundamento legal ou nota sobre o cálculo")


class TributosImportacaoResponse(BaseResponse):
    """
    Resultado do cálculo de tributos de importação em cascata.

    DISCLAIMER: Os valores são estimativas para planejamento. Não substituem
    o cálculo oficial pelo SISCOMEX nem a conferência por despachante aduaneiro
    ou contador especializado em comércio exterior. Antidumping, regimes especiais,
    acordos bilaterais e benefícios fiscais estaduais específicos estão fora do
    escopo deste simulador.
    """

    ncm: str = Field(description="Código NCM com 8 dígitos informado")
    modal: str = Field(description="Modal de transporte utilizado")
    valor_aduaneiro: float = Field(description="Valor aduaneiro (VA) base do cálculo, em R$")
    breakdown: list[TributoItem] = Field(
        description="Detalhamento de cada tributo na ordem de cascata"
    )
    total_tributos: float = Field(description="Soma de todos os tributos calculados, em R$")
    custo_total: float = Field(
        description="Valor aduaneiro + total de tributos (custo de desembaraço estimado), em R$"
    )
    avisos: list[str] = Field(
        default_factory=list,
        description="Avisos sobre parâmetros estimados ou situações que exigem conferência",
    )
    disclaimers: list[str] = Field(
        default_factory=list,
        description="Disclaimers legais obrigatórios sobre o escopo da simulação",
    )


class AliquotasImportacaoResponse(BaseResponse):
    """
    Alíquotas de referência para cálculo de tributos de importação por NCM.

    DISCLAIMER: A alíquota II (TEC) não está disponível em fonte estruturada
    offline e deve ser informada pelo usuário com base na Tarifa Externa Comum
    vigente (www.mdic.gov.br / Tarifa Aduaneira do Brasil). Os demais valores
    são defaults para planejamento e podem divergir da tributação efetiva.
    """

    ncm: str = Field(description="Código NCM com 8 dígitos consultado")
    descricao_ncm: str | None = Field(
        default=None, description="Descrição do produto conforme TIPI, se encontrada"
    )
    aliquota_ipi: float | None = Field(
        default=None,
        description="Alíquota IPI do banco NCM/TIPI, em %. None se NCM não encontrado.",
    )
    aliquota_pis_importacao_default: float = Field(
        description="Alíquota default de PIS-Importação (%), base: art. 1º Lei 10.865/2004"
    )
    aliquota_cofins_importacao_default: float = Field(
        description="Alíquota default de COFINS-Importação (%), base: art. 1º Lei 10.865/2004"
    )
    aviso_aliquota_ii: str = Field(
        description=(
            "Aviso sobre a alíquota II (Imposto de Importação / TEC): não há fonte "
            "estruturada offline. Informe aliquota_ii ao chamar calcular_tributos_importacao."
        )
    )
    avisos: list[str] = Field(
        default_factory=list,
        description="Avisos adicionais sobre o NCM ou as alíquotas retornadas",
    )
