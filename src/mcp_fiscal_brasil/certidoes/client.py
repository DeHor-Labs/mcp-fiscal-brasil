from mcp_fiscal_brasil.cpf.client import validate_cpf

from .schemas import CertidaoURL


def validate_cpf_for_certificate(cpf: str) -> bool:
    """Valida se um CPF é apto para emissão de certidão (validação offline do formato e dígitos)."""
    return validate_cpf(cpf).valido


def get_pgfn_url(cpf_or_cnpj: str) -> CertidaoURL:
    """Gera a URL para consulta da Certidão Conjunta (Receita Federal/PGFN)."""
    clean_doc = "".join(c for c in cpf_or_cnpj if c.isdigit())
    if len(clean_doc) > 11:
        url = "https://solucoes.receita.fazenda.gov.br/Servicos/certidaointernet/PJ/Emitir"
    else:
        url = "https://solucoes.receita.fazenda.gov.br/Servicos/certidaointernet/PF/Emitir"

    return CertidaoURL(
        tipo="PGFN",
        url=url,
        descricao="Certidão Conjunta de Débitos Relativos a Tributos Federais e à Dívida Ativa da União",
        validade_dias_tipico=180,
    )


def get_fgts_url(cnpj: str) -> CertidaoURL:
    """Gera a URL para consulta da Certidão de Regularidade do FGTS."""
    return CertidaoURL(
        tipo="FGTS",
        url="https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf",
        descricao="Certidão de Regularidade do FGTS",
        validade_dias_tipico=30,
    )


def get_cndt_url(cpf_or_cnpj: str) -> CertidaoURL:
    """Gera a URL para consulta da Certidão Negativa de Débitos Trabalhistas (CNDT)."""
    return CertidaoURL(
        tipo="CNDT",
        url="https://cndt-certidao.tst.jus.br/inicio.faces",
        descricao="Certidão Negativa de Débitos Trabalhistas",
        validade_dias_tipico=180,
    )
