from mcp_fiscal_brasil.cpf.client import format_cpf, unformat_cpf, validate_cpf


def test_validate_cpf_valid():
    result = validate_cpf("12345678909")
    assert result.cpf_formatado == "123.456.789-09"
    assert result.valido is True


def test_validate_cpf_invalid_length():
    result = validate_cpf("123")
    assert result.valido is False


def test_validate_cpf_invalid_digits():
    result = validate_cpf("12345678900")
    assert result.valido is False


def test_validate_cpf_same_digits():
    result = validate_cpf("11111111111")
    assert result.valido is False


def test_format_unformat():
    assert format_cpf("12345678901") == "123.456.789-01"
    assert format_cpf("123") == "123"
    assert unformat_cpf("123.456.789-01") == "12345678901"
