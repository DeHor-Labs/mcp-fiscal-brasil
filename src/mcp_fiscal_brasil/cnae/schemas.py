from pydantic import BaseModel


class CNAEActivity(BaseModel):
    codigo: str
    descricao: str


class CNAEClass(BaseModel):
    codigo: str
    descricao: str
    grupo: str | None = None
    divisao: str | None = None
