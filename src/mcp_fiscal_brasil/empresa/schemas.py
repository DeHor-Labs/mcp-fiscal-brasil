from pydantic import BaseModel

from mcp_fiscal_brasil.cnpj.schemas import AtividadeCNAE
from mcp_fiscal_brasil.shared.schemas import Endereco


class EmpresaInfo(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None
    situacao: str
    porte: str | None = None
    natureza_juridica: str | None = None
    simples_nacional: bool
    mei: bool
    atividade_principal: AtividadeCNAE | None = None
    atividades_secundarias: list[AtividadeCNAE] = []
    endereco: Endereco | None = None
