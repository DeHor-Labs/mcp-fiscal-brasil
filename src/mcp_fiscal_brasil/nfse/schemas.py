"""Schemas para NFSe."""

from datetime import datetime

from ..shared.schemas import BaseResponse


class NFSeResponse(BaseResponse):
    """Dados de uma NFSe consultada."""

    numero: str
    municipio: str
    uf: str
    prestador_cnpj: str | None = None
    prestador_razao_social: str | None = None
    tomador_cnpj_cpf: str | None = None
    tomador_razao_social: str | None = None
    data_emissao: datetime | None = None
    descricao_servico: str | None = None
    valor_servico: float | None = None
    valor_iss: float | None = None
    aliquota_iss: float | None = None
    codigo_municipio_servico: str | None = None
    codigo_cnae: str | None = None
    situacao: str | None = None
    observacoes: str | None = None
