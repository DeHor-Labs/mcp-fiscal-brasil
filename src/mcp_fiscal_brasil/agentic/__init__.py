"""Ferramentas de alto nivel orientadas a agentes de IA.

O modulo `agentic` reune tools compostas que combinam multiplos clientes
de baixo nivel (cnpj, simples, cnae, certidoes, nfe, sped) em respostas
estruturadas otimizadas para uso por LLMs (Claude, GPT, Gemini).

Cada tool expoe:
- Inputs simples (CNPJ, XML path, lista de fornecedores)
- Outputs ricos via pydantic (campos auto-documentados)
- Docstrings detalhadas com exemplos
"""

from .compliance import analyze_cnpj_compliance
from .nfe import validate_nfe_full
from .reforma import SimulacaoReformaResult, simular_transicao_reforma_tributaria
from .regimes import compare_tax_regimes
from .schemas import (
    ComplianceReport,
    NFeValidationReport,
    SPEDSummary,
    SupplierRiskBatchItem,
    SupplierRiskBatchResult,
    SupplierRiskScore,
    TaxRegimeComparison,
)
from .sped import summarize_sped
from .supplier import consultar_empresas_lote, risk_score_supplier

__all__ = [
    "ComplianceReport",
    "NFeValidationReport",
    "SPEDSummary",
    "SimulacaoReformaResult",
    "SupplierRiskBatchItem",
    "SupplierRiskBatchResult",
    "SupplierRiskScore",
    "TaxRegimeComparison",
    "analyze_cnpj_compliance",
    "compare_tax_regimes",
    "consultar_empresas_lote",
    "risk_score_supplier",
    "simular_transicao_reforma_tributaria",
    "summarize_sped",
    "validate_nfe_full",
]
