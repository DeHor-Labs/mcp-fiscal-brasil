"""Schemas Pydantic base para respostas de API."""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Resposta base para todas as ferramentas MCP."""

    sucesso: bool = True
    consultado_em: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class ErrorResponse(BaseResponse):
    """Resposta de erro padronizada."""

    sucesso: bool = False
    codigo_erro: str
    mensagem: str
    detalhes: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(BaseResponse, Generic[T]):
    """Resposta paginada generica."""

    itens: list[T]
    total: int
    pagina: int = 1
    por_pagina: int = 20

    @property
    def total_paginas(self) -> int:
        if self.por_pagina == 0:
            return 0
        return (self.total + self.por_pagina - 1) // self.por_pagina


class Endereco(BaseModel):
    """Endereco padrao brasileiro."""

    logradouro: str | None = None
    número: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    pais: str = "Brasil"

    def formatado(self) -> str:
        partes = []
        if self.logradouro:
            partes.append(self.logradouro)
        if self.número:
            partes.append(f"n. {self.número}")
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(self.bairro)
        if self.municipio:
            cidade = self.municipio
            if self.uf:
                cidade += f"/{self.uf}"
            partes.append(cidade)
        if self.cep:
            partes.append(f"CEP {self.cep}")
        return ", ".join(partes)
