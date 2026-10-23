from datetime import date

from pydantic import BaseModel


class SimplesStatus(BaseModel):
    cnpj: str
    simples_nacional: bool
    data_opcao: date | None = None
    data_exclusao: date | None = None
    mei: bool
    data_opcao_mei: date | None = None
    data_exclusao_mei: date | None = None
    fonte_confirmada: bool = True
    """False quando o resultado veio de um 404 da BrasilAPI: pode significar
    'não optante' de fato ou apenas que a fonte não confirmou o dado (endpoint
    fora do ar, CNPJ inexistente etc). True = dado retornado pela API normalmente."""
