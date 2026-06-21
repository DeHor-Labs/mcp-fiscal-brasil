"""
Módulo de cálculo de tributos de importação por NCM.

Ferramentas disponíveis:
- ``calcular_tributos_importacao``: calcula a cascata completa de tributos
  (II, IPI, PIS/COFINS-importação, ICMS, AFRMM/Siscomex) a partir do
  valor aduaneiro e das alíquotas informadas.
- ``consultar_aliquotas_importacao``: retorna alíquota IPI do banco NCM
  e os defaults de PIS/COFINS-importação, com aviso sobre a alíquota II.

DISCLAIMER: Este módulo produz estimativas para fins de planejamento fiscal.
Não substitui o cálculo oficial pelo SISCOMEX nem a conferência por
despachante aduaneiro ou contador especializado em comércio exterior.
Antidumping, regimes especiais, acordos bilaterais e benefícios fiscais
estaduais específicos estão fora do escopo do MVP.
"""

from ._tools import register
from .tools import calcular_tributos_importacao, consultar_aliquotas_importacao

__all__ = [
    "calcular_tributos_importacao",
    "consultar_aliquotas_importacao",
    "register",
]
