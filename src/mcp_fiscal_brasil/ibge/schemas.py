from pydantic import BaseModel


class Estado(BaseModel):
    id: int
    sigla: str
    nome: str
    regiao: str | None = None


class Municipio(BaseModel):
    id: int
    nome: str
    microrregiao: str | None = None
    estado: str | None = None
