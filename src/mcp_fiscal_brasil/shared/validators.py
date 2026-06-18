"""Validadores de documentos fiscais brasileiros (CPF, CNPJ, chave NFe)."""

import re


def _somente_digitos(valor: str) -> str:
    """Remove qualquer caractere não numerico."""
    return re.sub(r"\D", "", valor)


def _valor_char_cnpj(c: str) -> int:
    """Converte caractere para valor no cálculo do CNPJ alfanumérico.

    Conforme IN RFB 2.229/2024: usa código ASCII subtraído de 48.
    Dígitos: '0'=0, '1'=1, ..., '9'=9.
    Letras maiúsculas: 'A'=17, 'B'=18, ..., 'Z'=42.
    """
    return ord(c) - 48


def validate_cpf(cpf: str) -> bool:
    """
    Valida um CPF brasileiro.

    Aceita formatos com ou sem mascara (XXX.XXX.XXX-XX ou XXXXXXXXXXX).
    Retorna False para CPFs com todos os digitos iguais (ex: 111.111.111-11).
    """
    números = _somente_digitos(cpf)

    if len(números) != 11:
        return False

    # Rejeita sequencias repetidas (ex: 00000000000)
    if len(set(números)) == 1:
        return False

    # Valida primeiro digito verificador
    soma = sum(int(números[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto == 10 or resto == 11:
        resto = 0
    if resto != int(números[9]):
        return False

    # Valida segundo digito verificador
    soma = sum(int(números[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto == 10 or resto == 11:
        resto = 0
    if resto != int(números[10]):
        return False

    return True


def validate_cnpj(cnpj: str) -> bool:
    """
    Valida um CNPJ brasileiro.

    Aceita formatos com ou sem mascara (XX.XXX.XXX/XXXX-XX ou XXXXXXXXXXXXXX).
    """
    números = _somente_digitos(cnpj)

    if len(números) != 14:
        return False

    # Rejeita sequencias repetidas
    if len(set(números)) == 1:
        return False

    # Valida primeiro digito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(números[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if digito1 != int(números[12]):
        return False

    # Valida segundo digito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(números[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    if digito2 != int(números[13]):
        return False

    return True


def validate_cnpj_alfanumerico(cnpj: str) -> bool:
    """
    Valida um CNPJ alfanumérico (IN RFB 2.229/2024, vigência jul/2026).

    As 12 primeiras posições podem conter letras maiúsculas (A-Z) ou dígitos.
    As 2 últimas são dígitos verificadores numéricos calculados pelo módulo 11,
    usando o valor ASCII de cada caractere subtraído de 48.

    Esta função NÃO aceita máscaras (pontos, barra, traço) nem letras minúsculas.
    Aceita CNPJs numéricos puros (14 dígitos sem máscara) como caso especial,
    pois o algoritmo é compatível com ambos os formatos.
    Para validar qualquer CNPJ com ou sem máscara, use validate_cnpj_qualquer.
    """
    if len(cnpj) != 14:
        return False

    # Somente letras maiúsculas (A-Z) e dígitos são válidos
    if not re.match(r"^[A-Z0-9]{14}$", cnpj):
        return False

    # Rejeita sequências com todos os caracteres iguais
    if len(set(cnpj)) == 1:
        return False

    # Os 2 últimos caracteres (DVs) devem ser dígitos numéricos
    if not cnpj[12:].isdigit():
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    # Primeiro dígito verificador
    soma = sum(_valor_char_cnpj(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    dv1_esperado = 0 if resto < 2 else 11 - resto
    if dv1_esperado != int(cnpj[12]):
        return False

    # Segundo dígito verificador
    soma = sum(_valor_char_cnpj(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    dv2_esperado = 0 if resto < 2 else 11 - resto
    if dv2_esperado != int(cnpj[13]):
        return False

    return True


def validate_cnpj_qualquer(cnpj: str) -> bool:
    """
    Valida qualquer CNPJ: detecta se é numérico ou alfanumérico e delega.

    CNPJs numéricos (somente dígitos, com ou sem máscara) usam validate_cnpj.
    CNPJs alfanuméricos (contêm letras A-Z, sem máscara) usam validate_cnpj_alfanumerico.

    Tratamento de máscara (comportamento intencional e defensivo):
    - Este dispatcher remove apenas os separadores padrão de CNPJ: ponto, barra e traço.
    - Outros caracteres como espaços tornam o input inválido (retorna False).
    - Isso é diferente de normalizar_cnpj, que usa isalnum() e remove qualquer
      caractere não alfanumérico. A validação rejeita inputs com formato estranho
      antes de normalizar, mantendo fronteiras de entrada bem definidas.
    - Para normalizar antes de validar, use normalizar_cnpj() + validate_cnpj_alfanumerico().
    """
    if not cnpj:
        return False

    # Se após remover máscara numérica sobra algo com 14 chars e sem letras -> numérico
    apenas_digitos = _somente_digitos(cnpj)
    if len(apenas_digitos) == 14 and apenas_digitos == cnpj.replace(".", "").replace(
        "/", ""
    ).replace("-", ""):
        return validate_cnpj(cnpj)

    # Se o CNPJ (sem máscara) contém letras maiúsculas -> alfanumérico
    cnpj_sem_mascara = cnpj.replace(".", "").replace("/", "").replace("-", "").upper()
    if len(cnpj_sem_mascara) == 14:
        return validate_cnpj_alfanumerico(cnpj_sem_mascara)

    return False


def normalizar_cnpj(cnpj: str) -> str:
    """
    Remove a máscara de um CNPJ (numérico ou alfanumérico) e normaliza para maiúsculas.

    Para CNPJs numéricos: remove pontos, barra e traço.
    Para CNPJs alfanuméricos (IN RFB 2.229/2024): preserva as letras, remove máscara.
    Não valida o CNPJ - use validate_cnpj_qualquer antes se necessário.
    """
    return "".join(c for c in cnpj if c.isalnum()).upper()


def validate_chave_nfe(chave: str) -> bool:
    """
    Valida uma chave de acesso de NFe/NFCe (44 digitos).

    A chave e composta por: cUF(2) + AAMM(4) + CNPJ(14) + mod(2) + serie(3)
    + nNF(9) + tpEmis(1) + cNF(8) + cDV(1) = 44 digitos.

    Verifica apenas o digito verificador (modulo 11).
    """
    números = _somente_digitos(chave)

    if len(números) != 44:
        return False

    # Calcula digito verificador pelo modulo 11
    # Pesos ciclo de 2 a 9 aplicados da direita para a esquerda (conforme NT SEFAZ 2011.002)
    pesos_ciclo = list(range(2, 10))  # [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, digito in enumerate(reversed(números[:43])):
        soma += int(digito) * pesos_ciclo[i % len(pesos_ciclo)]

    resto = soma % 11
    if resto == 0 or resto == 1:
        dv_esperado = 0
    else:
        dv_esperado = 11 - resto

    return dv_esperado == int(números[43])


def format_cpf(cpf: str, remover_mascara: bool = False) -> str:
    """
    Formata um CPF com ou sem mascara.

    Se remover_mascara=True, retorna apenas os 11 digitos numericos.
    Caso contrario, retorna no formato XXX.XXX.XXX-XX.
    """
    números = _somente_digitos(cpf)
    if len(números) != 11:
        raise ValueError(f"CPF deve ter 11 digitos, recebeu {len(números)}")

    if remover_mascara:
        return números
    return f"{números[:3]}.{números[3:6]}.{números[6:9]}-{números[9:]}"


def format_cnpj(cnpj: str, remover_mascara: bool = False) -> str:
    """
    Formata um CNPJ com ou sem mascara.

    Se remover_mascara=True, retorna apenas os 14 digitos numericos.
    Caso contrario, retorna no formato XX.XXX.XXX/XXXX-XX.
    """
    números = _somente_digitos(cnpj)
    if len(números) != 14:
        raise ValueError(f"CNPJ deve ter 14 digitos, recebeu {len(números)}")

    if remover_mascara:
        return números
    return f"{números[:2]}.{números[2:5]}.{números[5:8]}/{números[8:12]}-{números[12:]}"


def format_chave_nfe(chave: str) -> str:
    """Formata uma chave NFe em grupos de 4 digitos para legibilidade."""
    números = _somente_digitos(chave)
    if len(números) != 44:
        raise ValueError(f"Chave NFe deve ter 44 digitos, recebeu {len(números)}")
    return " ".join(números[i : i + 4] for i in range(0, 44, 4))
