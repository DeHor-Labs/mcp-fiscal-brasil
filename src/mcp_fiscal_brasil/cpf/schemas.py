from pydantic import BaseModel


class CPFValidation(BaseModel):
    cpf_formatado: str
    valido: bool
    digitos_verificadores_ok: bool
