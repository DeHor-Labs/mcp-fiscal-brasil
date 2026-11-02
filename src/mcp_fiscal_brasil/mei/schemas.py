from datetime import date

from pydantic import BaseModel, Field, field_validator

_ANO_MIN_DASN = 2007


class MEIStatus(BaseModel):
    cnpj: str
    mei: bool
    data_opcao_mei: date | None = None
    data_exclusao_mei: date | None = None
    simples_nacional: bool


class RegularizacaoMeiPasso(BaseModel):
    ordem: int = Field(description="Ordem de execução do passo (1-based).")
    titulo: str = Field(description="Título curto do passo.")
    detalhe: str = Field(description="Instrução operacional em pt-BR.")
    url: str | None = Field(default=None, description="URL oficial relacionada, se houver.")


class RegularizacaoMeiRequest(BaseModel):
    cnpj: str | None = Field(
        default=None,
        description="CNPJ opcional para contextualizar a orientação.",
    )
    anos_omitidos: list[int] | None = Field(
        default=None,
        description=(
            "Anos-calendário de DASN-SIMEI omitidos (2007 até o ano-calendário "
            "anterior ao corrente). Anos inválidos geram erro."
        ),
    )
    receita_zero: bool = Field(
        default=True,
        description="Se True, orienta declaração com receita 0,00 (MEI sem movimento).",
    )

    @field_validator("anos_omitidos")
    @classmethod
    def validar_anos_omitidos(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        ano_max = date.today().year - 1
        normalizados = sorted({int(a) for a in value})
        invalidos = [a for a in normalizados if a < _ANO_MIN_DASN or a > ano_max]
        if invalidos:
            raise ValueError(
                f"anos_omitidos fora do intervalo declarável "
                f"({_ANO_MIN_DASN}–{ano_max}): {invalidos}"
            )
        return normalizados


class RegularizacaoMeiResponse(BaseModel):
    status: str = Field(description="Sempre consulta_manual_necessaria (sem API de login Gov.br).")
    cnpj: str | None = None
    anos_omitidos: list[int] = Field(default_factory=list)
    receita_zero: bool = True
    passos: list[RegularizacaoMeiPasso]
    avisos: list[str]
    links_oficiais: dict[str, str]
