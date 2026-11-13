from datetime import date

from pydantic import BaseModel


class SimplesStatus(BaseModel):
    cnpj: str
    simples_nacional: bool | None
    data_opcao: date | None = None
    data_exclusao: date | None = None
    mei: bool | None
    data_opcao_mei: date | None = None
    data_exclusao_mei: date | None = None
    fonte_confirmada: bool = True
