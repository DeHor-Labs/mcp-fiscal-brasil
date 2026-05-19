from .schemas import CPFValidation


def unformat_cpf(cpf: str) -> str:
    """Remove a formatação do CPF, retornando apenas números."""
    return "".join(c for c in cpf if c.isdigit())


def format_cpf(cpf: str) -> str:
    """Formata uma string de números como CPF (XXX.XXX.XXX-XX)."""
    clean = unformat_cpf(cpf)
    if len(clean) != 11:
        return cpf  # Retorna original se não tem 11 dígitos
    return f"{clean[:3]}.{clean[3:6]}.{clean[6:9]}-{clean[9:]}"


def _calcular_digito_cpf(cpf_parcial: str) -> str:
    """Calcula um dígito verificador do CPF."""
    soma = 0
    peso = len(cpf_parcial) + 1
    for digito in cpf_parcial:
        soma += int(digito) * peso
        peso -= 1

    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def validate_cpf(cpf: str) -> CPFValidation:
    """Valida um CPF usando o algoritmo dos dígitos verificadores."""
    clean_cpf = unformat_cpf(cpf)

    # Formato básico
    if len(clean_cpf) != 11 or len(set(clean_cpf)) == 1:
        return CPFValidation(cpf_formatado=cpf, valido=False, digitos_verificadores_ok=False)

    cpf_9 = clean_cpf[:9]
    dv1 = _calcular_digito_cpf(cpf_9)
    dv2 = _calcular_digito_cpf(cpf_9 + dv1)

    digitos_ok = clean_cpf[9:] == (dv1 + dv2)

    return CPFValidation(
        cpf_formatado=format_cpf(clean_cpf), valido=digitos_ok, digitos_verificadores_ok=digitos_ok
    )
