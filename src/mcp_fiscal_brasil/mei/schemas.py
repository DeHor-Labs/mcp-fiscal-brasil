from datetime import date

from pydantic import BaseModel


class MEIStatus(BaseModel):
    cnpj: str
    mei: bool | None
    data_opcao_mei: date | None = None
    data_exclusao_mei: date | None = None
    simples_nacional: bool | None
    fonte_confirmada: bool = True
