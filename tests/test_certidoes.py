from mcp_fiscal_brasil.certidoes.client import (
    get_cndt_url,
    get_fgts_url,
    get_pgfn_url,
    validate_cpf_for_certificate,
)


def test_validate_cpf_for_certificate():
    assert validate_cpf_for_certificate("12345678909") is True
    assert validate_cpf_for_certificate("11111111111") is False


def test_get_pgfn_url():
    result = get_pgfn_url("12345678909")
    assert result.tipo == "PGFN"
    assert "PF/Emitir" in result.url

    result_pj = get_pgfn_url("00000000000191")
    assert "PJ/Emitir" in result_pj.url


def test_get_fgts_url():
    result = get_fgts_url("00000000000191")
    assert result.tipo == "FGTS"


def test_get_cndt_url():
    result = get_cndt_url("00000000000191")
    assert result.tipo == "CNDT"
