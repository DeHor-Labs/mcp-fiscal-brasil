"""Fixtures compartilhadas para os testes."""

import pytest


@pytest.fixture
def cnpj_valido() -> str:
    """CNPJ válido para testes (Petrobras)."""
    return "33.000.167/0001-01"


@pytest.fixture
def cnpj_invalido() -> str:
    return "11.111.111/1111-11"


@pytest.fixture
def cpf_valido() -> str:
    """CPF válido para testes (gerado matematicamente)."""
    return "529.982.247-25"


@pytest.fixture
def cpf_invalido() -> str:
    return "111.111.111-11"


@pytest.fixture
def chave_nfe_valida() -> str:
    """Chave NFe válida para testes (chave publica de exemplo)."""
    # cUF=35(SP) AAMM=2301 CNPJ=12345678000190 mod=55 serie=001
    # nNF=000000001 tpEmis=1 cNF=00000001 cDV=8.
    return "35230112345678000190550010000000011000000018"


@pytest.fixture
def sped_abertura_sample() -> str:
    """Amostra de arquivo SPED EFD-ICMS/IPI para testes."""
    return (
        "|0000|015|0|N||EMPRESA TESTE LTDA|12345678000195||SP|123456789|3550308|||0|\n"
        "|0001|0|\n"
        "|0005|EMPRESA TESTE|12345-678|RUA DAS FLORES|100||CENTRO|3550308|SP|11 1234-5678|contato@empresa.com.br|\n"
        "|0990|3|\n"
        "|9001|0|\n"
        "|9990|2|\n"
        "|9999|5|\n"
    )
