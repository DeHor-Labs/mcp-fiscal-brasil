"""Schemas Pydantic para o módulo BCB (Banco Central do Brasil)."""

from datetime import date

from pydantic import BaseModel


class SerieBCB(BaseModel):
    """Ponto de dados de uma série temporal do SGS/BCB."""

    data: date
    valor: float


class PTAXResponse(BaseModel):
    """Cotação PTAX do dólar (ou outra moeda) para uma data específica."""

    data: date
    moeda: str
    compra: float
    venda: float


class CorrecaoMonetariaResponse(BaseModel):
    """Resultado do cálculo de correção monetária."""

    valor_original: float
    data_inicio: date
    data_fim: date
    indice: str
    fator_acumulado: float
    valor_corrigido: float
