from pydantic import BaseModel


class CertidaoURL(BaseModel):
    tipo: str
    url: str
    descricao: str
    validade_dias_tipico: int | None = None
