"""MCP Fiscal Brasil - Servidor MCP e SDK Python para o sistema fiscal brasileiro."""

__version__ = "0.2.0"
__author__ = "Nikolas de Hor"
__description__ = (
    "Servidor MCP para integrar IAs com o sistema fiscal brasileiro. "
    "Consulte CNPJ, NFe, NFSe, SPED, eSocial e mais via linguagem natural."
)

# SDK publica - disponivel como `from mcp_fiscal_brasil import FiscalBrasil`
from .cep import CEPClient, Endereco, validate_cep
from .certidoes import (
    CertidaoURL,
    get_cndt_url,
    get_fgts_url,
    get_pgfn_url,
    validate_cpf_for_certificate,
)

# Novos módulos (Fase 2)
from .cnae import CNAEActivity, CNAEClass, CNAEClient
from .cpf import CPFValidation, unformat_cpf
from .empresa import EmpresaClient, EmpresaInfo
from .ibge import Estado, IBGEClient, Municipio
from .mei import MEIClient, MEIStatus
from .sdk import FiscalBrasil

# Validadores offline - disponivel como `from mcp_fiscal_brasil import validate_cpf`
from .shared.validators import (
    format_chave_nfe,
    format_cnpj,
    format_cpf,
    validate_chave_nfe,
    validate_cnpj,
    validate_cpf,
)
from .simples import SimplesClient, SimplesStatus

__all__ = [
    "CEPClient",
    "CNAEActivity",
    "CNAEClass",
    "CNAEClient",
    "CPFValidation",
    "CertidaoURL",
    "EmpresaClient",
    "EmpresaInfo",
    "Endereco",
    "Estado",
    "FiscalBrasil",
    "IBGEClient",
    "MEIClient",
    "MEIStatus",
    "Municipio",
    "SimplesClient",
    "SimplesStatus",
    "format_chave_nfe",
    "format_cnpj",
    "format_cpf",
    "get_cndt_url",
    "get_fgts_url",
    "get_pgfn_url",
    "unformat_cpf",
    "validate_cep",
    "validate_chave_nfe",
    "validate_cnpj",
    "validate_cpf",
    "validate_cpf_for_certificate",
]
