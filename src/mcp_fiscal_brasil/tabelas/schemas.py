"""Schemas Pydantic para consultas de tabelas fiscais estáticas."""

from pydantic import Field

from ..shared.schemas import BaseResponse


class NCMResponse(BaseResponse):
    """Resposta de consulta de NCM (Nomenclatura Comum do Mercosul)."""

    codigo: str = Field(description="Código NCM com 8 dígitos")
    descricao: str = Field(description="Descrição do produto conforme TIPI")
    aliquota_ipi: float | None = Field(default=None, description="Alíquota do IPI em percentual")
    unidade_tributavel: str | None = Field(
        default=None, description="Unidade tributável (ex: UN, KG, L)"
    )
    ex_tipi: str | None = Field(default=None, description="Código de exceção TIPI (EX), se existir")
    capitulo: str = Field(description="Capítulo TIPI (primeiros 2 dígitos)")
    posicao: str = Field(description="Posição TIPI (primeiros 4 dígitos)")


class CFOPResponse(BaseResponse):
    """Resposta de consulta de CFOP (Código Fiscal de Operações e Prestações)."""

    codigo: str = Field(description="Código CFOP com 4 dígitos")
    descricao: str = Field(description="Descrição da operação ou prestação")
    tipo: str = Field(description="Tipo da operação: 'entrada' ou 'saida'")
    aplicacao: str = Field(
        description="Âmbito da operação: 'estadual', 'interestadual' ou 'exterior'"
    )
    grupo: str = Field(description="Número do grupo CFOP (1=entrada est., 2=entrada int., etc.)")


class CSTResponse(BaseResponse):
    """Resposta de validação de CST/CSOSN (Código de Situação Tributária)."""

    cst: str = Field(description="Código CST ou CSOSN informado")
    valido: bool = Field(description="Indica se o código é válido para o regime informado")
    descricao: str | None = Field(default=None, description="Descrição do código, se válido")
    regime: str = Field(
        description="Regime tributário: 'normal' (Lucro Real/Presumido) ou 'simples'"
    )
    tabela: str | None = Field(
        default=None,
        description="Tabela de origem: 'CST_ICMS', 'CSOSN', 'CST_PIS_COFINS', 'CST_IPI'",
    )


class CESTResponse(BaseResponse):
    """Resposta de consulta de CEST (Código Especificador da Substituição Tributária)."""

    cest: str = Field(description="Código CEST com 7 dígitos")
    descricao: str = Field(description="Descrição do segmento/produto")
    segmento: str = Field(description="Número do segmento CEST (primeiros 2 dígitos)")
    ncm_relacionados: list[str] = Field(
        default_factory=list,
        description="Lista de códigos NCM relacionados a este CEST",
    )


class ICMSAliquotaResponse(BaseResponse):
    """Resposta de consulta de alíquota interestadual do ICMS."""

    uf_origem: str = Field(description="UF de origem da operação (sigla, ex: SP)")
    uf_destino: str = Field(description="UF de destino da operação (sigla, ex: MG)")
    aliquota_interestadual: float = Field(
        description="Alíquota interestadual do ICMS em percentual"
    )
    aliquota_interna_destino: float = Field(
        description="Alíquota interna do ICMS no estado de destino em percentual"
    )
    diferencial_aliquota: float = Field(
        description="Diferencial de alíquota (DIFAL = alíquota interna - alíquota interestadual)"
    )
    fundamento: str = Field(
        description="Fundamento legal da alíquota (ex: Resolução SF 13/2012, EC 87/2015)"
    )
