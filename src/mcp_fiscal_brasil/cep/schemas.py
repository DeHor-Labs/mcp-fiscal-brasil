from pydantic import BaseModel


class Endereco(BaseModel):
    cep: str
    state: str
    city: str
    neighborhood: str
    street: str
    service: str | None = None
