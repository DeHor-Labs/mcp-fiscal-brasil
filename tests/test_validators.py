"""Testes para validadores de documentos fiscais."""

import pytest

from mcp_fiscal_brasil.shared.validators import (
    format_cnpj,
    format_cpf,
    normalizar_cnpj,
    validate_chave_nfe,
    validate_cnpj,
    validate_cnpj_alfanumerico,
    validate_cnpj_qualquer,
    validate_cpf,
)


class TestValidateCPF:
    def test_cpf_valido_com_mascara(self) -> None:
        assert validate_cpf("529.982.247-25") is True

    def test_cpf_valido_sem_mascara(self) -> None:
        assert validate_cpf("52998224725") is True

    def test_cpf_digitos_repetidos(self) -> None:
        assert validate_cpf("111.111.111-11") is False
        assert validate_cpf("000.000.000-00") is False

    def test_cpf_tamanho_errado(self) -> None:
        assert validate_cpf("123") is False
        assert validate_cpf("123456789012") is False

    def test_cpf_digito_verificador_errado(self) -> None:
        assert validate_cpf("529.982.247-26") is False


class TestValidateCNPJ:
    def test_cnpj_valido_com_mascara(self) -> None:
        assert validate_cnpj("33.000.167/0001-01") is True

    def test_cnpj_valido_sem_mascara(self) -> None:
        assert validate_cnpj("33000167000101") is True

    def test_cnpj_digitos_repetidos(self) -> None:
        assert validate_cnpj("11.111.111/1111-11") is False

    def test_cnpj_tamanho_errado(self) -> None:
        assert validate_cnpj("123") is False

    def test_cnpj_digito_verificador_errado(self) -> None:
        assert validate_cnpj("33.000.167/0001-02") is False


class TestValidateChaveNFe:
    def test_chave_valida_44_digitos(self) -> None:
        # Chave real da NF-e com DV correto: cUF=35 (SP), AAMM=2401,
        # CNPJ=12345678000195, mod=55, serie=001, nNF=000000123, tpEmis=1,
        # cNF=00000001, cDV=1 (calculado pelo módulo 11)
        chave = "35240112345678000195550010000001231000000011"
        assert len(chave) == 44
        assert validate_chave_nfe(chave) is True

    def test_chave_tamanho_errado(self) -> None:
        assert validate_chave_nfe("1234") is False
        assert validate_chave_nfe("123456789012345678901234567890123456789012345") is False

    def test_chave_com_espacos(self) -> None:
        # Espacos são removidos pelo validador
        assert validate_chave_nfe("1234 5678") is False  # ainda tamanho errado sem espacos


class TestFormatCPF:
    def test_formata_sem_mascara(self) -> None:
        assert format_cpf("52998224725") == "529.982.247-25"

    def test_remove_mascara(self) -> None:
        assert format_cpf("529.982.247-25", remover_mascara=True) == "52998224725"

    def test_tamanho_errado_levanta_erro(self) -> None:
        with pytest.raises(ValueError):
            format_cpf("123")


class TestFormatCNPJ:
    def test_formata_sem_mascara(self) -> None:
        assert format_cnpj("33000167000101") == "33.000.167/0001-01"

    def test_remove_mascara(self) -> None:
        assert format_cnpj("33.000.167/0001-01", remover_mascara=True) == "33000167000101"

    def test_tamanho_errado_levanta_erro(self) -> None:
        with pytest.raises(ValueError):
            format_cnpj("123")


class TestValidateCNPJAlfanumerico:
    """Testes para validação de CNPJ alfanumérico (IN RFB 2.229/2024, vigência jul/2026).

    CNPJs fictícios com DVs calculados pelo algoritmo módulo 11 com conversão ASCII-48:
    - AB123CD0000108 (DVs calculados: 0,8)
    - XY987EF0000279 (DVs calculados: 7,9)
    """

    def test_cnpj_alfanumerico_valido(self) -> None:
        # AB123CD00001 + DVs 08
        assert validate_cnpj_alfanumerico("AB123CD0000108") is True

    def test_cnpj_alfanumerico_segundo_exemplo_valido(self) -> None:
        # XY987EF00002 + DVs 79
        assert validate_cnpj_alfanumerico("XY987EF0000279") is True

    def test_cnpj_alfanumerico_dv2_errado(self) -> None:
        # DV1 correto é 0, DV2 correto é 8 -> usar DV2=9 invalida
        assert validate_cnpj_alfanumerico("AB123CD0000109") is False

    def test_cnpj_alfanumerico_dv1_errado(self) -> None:
        # DV1 correto é 0 -> usar DV1=1 invalida (AB123CD000011X com qualquer DV2)
        assert validate_cnpj_alfanumerico("AB123CD0000118") is False

    def test_cnpj_alfanumerico_tamanho_errado(self) -> None:
        assert validate_cnpj_alfanumerico("AB123CD00001") is False
        assert validate_cnpj_alfanumerico("AB123CD000010812345") is False

    def test_cnpj_alfanumerico_letras_minusculas_invalido(self) -> None:
        # CNPJ alfanumérico usa somente letras maiúsculas
        assert validate_cnpj_alfanumerico("ab123cd0000108") is False

    def test_cnpj_numerico_aceito_por_alfanumerico(self) -> None:
        # CNPJs numéricos existentes continuam válidos (backward compat)
        assert validate_cnpj_alfanumerico("33000167000101") is True

    def test_cnpj_alfanumerico_todos_iguais_invalido(self) -> None:
        # Sequências com 14 chars idênticos devem ser rejeitadas pelo check de uniformidade.
        # Usar "00000000000000" (numérico uniforme) para testar especificamente esse caminho,
        # pois "AAAAAAAAAAAAAA" seria rejeitado antes pelo check de DVs (cnpj[12:] deve ser dígito).
        assert validate_cnpj_alfanumerico("00000000000000") is False


class TestValidateCNPJQualquer:
    """Testes para o dispatcher que detecta formato e delega."""

    def test_cnpj_numerico_valido(self) -> None:
        assert validate_cnpj_qualquer("33.000.167/0001-01") is True

    def test_cnpj_numerico_invalido(self) -> None:
        assert validate_cnpj_qualquer("33.000.167/0001-02") is False

    def test_cnpj_alfanumerico_valido(self) -> None:
        assert validate_cnpj_qualquer("AB123CD0000108") is True

    def test_cnpj_alfanumerico_invalido(self) -> None:
        assert validate_cnpj_qualquer("AB123CD0000109") is False

    def test_cnpj_vazio_invalido(self) -> None:
        assert validate_cnpj_qualquer("") is False

    def test_cnpj_tamanho_errado_invalido(self) -> None:
        assert validate_cnpj_qualquer("123") is False


class TestNormalizarCNPJ:
    """Testes para normalizar_cnpj: remove máscara e normaliza para maiúsculas."""

    def test_cnpj_numerico_com_mascara(self) -> None:
        # Máscara padrão numérica: pontos, barra e traço removidos
        assert normalizar_cnpj("33.000.167/0001-01") == "33000167000101"

    def test_cnpj_alfanumerico_com_mascara(self) -> None:
        # Máscara alfanumérica: caracteres não-alfanuméricos (pontos, barra, traço) removidos
        # "AB.123.CD0/0001-08" tem 18 chars; sem máscara = "AB123CD0000108" (14 chars)
        assert normalizar_cnpj("AB.123.CD0/0001-08") == "AB123CD0000108"

    def test_minusculas_convertidas_para_maiusculas(self) -> None:
        # Letras minúsculas devem ser convertidas para maiúsculas
        assert normalizar_cnpj("ab123cd0000108") == "AB123CD0000108"

    def test_ja_normalizado_retorna_igual(self) -> None:
        # CNPJ já normalizado (sem máscara, maiúsculas) deve retornar igual
        assert normalizar_cnpj("33000167000101") == "33000167000101"
