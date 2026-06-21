"""
Testes para extração de valores numéricos do parser SPED.

Cobre:
- _to_float: conversão segura de string com vírgula decimal para float
- listar_registros_sped: campos indexados (lista, não string bruta)
- summarize_sped / metricas_chave: soma de PIS (M210), COFINS (M610) e ICMS (E110)
- Registro 0110: leitura do regime PIS/COFINS
- Casos de borda: campo vazio, None, múltiplas ocorrências do mesmo registro

Layout fiscal utilizado (fontes oficiais):
  EFD-Contribuicoes - Guia Prático EFD Contribuições, Ato COTEPE/ICMS 65/2013:
    M210 campo[7]  = VL_CONT_PERIODO (contribuição PIS a recolher no período)
    M610 campo[7]  = VL_CONT_PERIODO (contribuição COFINS a recolher no período)
    0110 campo[1]  = COD_INC_TRIB (1=cumulativo, 2=nao-cumulativo)
  EFD ICMS/IPI - Guia Prático EFD ICMS/IPI, Ato COTEPE/ICMS 44/2018 (versão 018):
    E110 layout (15 campos, 01 a 15):
      campo 02 (índice  0) = VL_TOT_DEBITOS    - débitos BRUTOS por saídas (informativo)
      campo 03 (índice  1) = VL_AJ_DEBITOS
      campo 04 (índice  2) = VL_TOT_AJ_DEBITOS
      campo 05 (índice  3) = VL_ESTORNOS_CRED
      campo 06 (índice  4) = VL_TOT_CREDITOS
      campo 07 (índice  5) = VL_AJ_CREDITOS
      campo 08 (índice  6) = VL_TOT_AJ_CREDITOS
      campo 09 (índice  7) = VL_ESTORNOS_DEB
      campo 10 (índice  8) = VL_SLD_CREDOR_ANT
      campo 11 (índice  9) = VL_SLD_APURADO    - saldo devedor (débitos - créditos)
      campo 12 (índice 10) = VL_TOT_DED
      campo 13 (índice 11) = VL_ICMS_RECOLHER  - ICMS líquido a recolher (comparável com pis/cofins)
      campo 14 (índice 12) = VL_SLD_CREDOR_TRANSPORTAR
      campo 15 (índice 13) = DEB_ESP
"""

from pathlib import Path

import pytest

from mcp_fiscal_brasil.agentic.sped import summarize_sped
from mcp_fiscal_brasil.sped.tools import (
    _to_float,
    listar_registros_sped,
)

# ---------------------------------------------------------------------------
# _to_float: conversão de string com vírgula decimal
# ---------------------------------------------------------------------------


def test_to_float_virgula_decimal() -> None:
    """Valor com vírgula como separador decimal deve ser convertido para float."""
    assert _to_float("3708500,27") == pytest.approx(3708500.27)


def test_to_float_inteiro_sem_virgula() -> None:
    """Valor inteiro sem vírgula deve funcionar."""
    assert _to_float("1000") == pytest.approx(1000.0)


def test_to_float_zero() -> None:
    """Zero string deve retornar 0.0."""
    assert _to_float("0") == pytest.approx(0.0)


def test_to_float_string_vazia_retorna_zero() -> None:
    """String vazia deve retornar 0.0 sem lançar exceção."""
    assert _to_float("") == pytest.approx(0.0)


def test_to_float_none_retorna_zero() -> None:
    """None deve retornar 0.0 sem lançar exceção."""
    assert _to_float(None) == pytest.approx(0.0)


def test_to_float_espacos_em_branco_retorna_zero() -> None:
    """String com apenas espaços deve retornar 0.0."""
    assert _to_float("   ") == pytest.approx(0.0)


def test_to_float_valor_negativo() -> None:
    """Valor negativo com vírgula deve ser convertido corretamente."""
    assert _to_float("-500,50") == pytest.approx(-500.50)


def test_to_float_ponto_tratado_como_milhar() -> None:
    """No SPED, ponto é separador de milhar, não decimal (Guia Prático EFD).

    "1234.56" sem vírgula: ponto é removido como milhar, resultado é 123456.0.
    Valores en-US com ponto decimal não ocorrem em arquivos SPED oficiais.
    """
    assert _to_float("1234.56") == pytest.approx(123456.0)


# ---------------------------------------------------------------------------
# _to_float: separador de milhar (ponto) - formato TOTVS/Protheus
# ---------------------------------------------------------------------------


def test_to_float_milhar_e_decimal() -> None:
    """Valor com ponto de milhar E vírgula decimal deve ser convertido corretamente.

    Formato exportado por ERPs como TOTVS/Protheus: "3.708.500,27".
    Sem este fix, "3.708.500,27" -> "3.708.500.27" -> ValueError -> 0.0 (bug).
    """
    assert _to_float("3.708.500,27") == pytest.approx(3708500.27)


def test_to_float_milhar_simples() -> None:
    """Valor com um único ponto de milhar e vírgula decimal."""
    assert _to_float("1.500,00") == pytest.approx(1500.0)


def test_to_float_sem_milhar_regressao() -> None:
    """Regressão: valor sem separador de milhar deve continuar funcionando."""
    assert _to_float("3708500,27") == pytest.approx(3708500.27)


def test_to_float_cem_reais() -> None:
    """Valor simples de centenas com vírgula decimal."""
    assert _to_float("100,00") == pytest.approx(100.0)


def test_to_float_negativo_com_milhar() -> None:
    """Valor negativo com ponto de milhar e vírgula decimal."""
    assert _to_float("-1.500,00") == pytest.approx(-1500.0)


# ---------------------------------------------------------------------------
# listar_registros_sped: campos indexados (lista, não string bruta)
# ---------------------------------------------------------------------------


_SPED_CONTRIBUICOES_SAMPLE = """\
|0000|006|1|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|31012024|
|0110|2|IN|
|M210|PIS|0,00|0,00|3708500,27|0,00|0,00|3708500,27|0,00|0,00|0,00|3708500,27|0,00|1,65|
|M610|COFINS|0,00|0,00|17033125,40|0,00|0,00|17033125,40|0,00|0,00|0,00|17033125,40|0,00|7,60|
|9999|4|
"""

_SPED_ICMS_IPI_SAMPLE = """\
|0000|015|0|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|31012024|
|E110|2900000,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|0,00|2900000,00|0,00|2900000,00|0,00|0,00|
|9999|3|
"""
# E110 acima (sem créditos): VL_TOT_DEBITOS (idx 0) = 2900000,00
#   VL_SLD_APURADO (idx 9) = 2900000,00, VL_TOT_DED (idx 10) = 0,00
#   VL_ICMS_RECOLHER (idx 11) = 2900000,00  -> débitos == a recolher (sem créditos)

# Sample com créditos: débitos brutos DIFEREM do valor a recolher
_SPED_ICMS_COM_CREDITOS_SAMPLE = """\
|0000|015|0|N||EMPRESA CREDORA LTDA|12345678000195||SP|111111111|3550308||A|0|01012024|31012024|
|E110|5000000,00|0,00|0,00|0,00|1500000,00|0,00|0,00|0,00|0,00|3500000,00|200000,00|3300000,00|0,00|0,00|
|9999|3|
"""
# E110 acima (com créditos e deduções):
#   VL_TOT_DEBITOS    (idx  0) = 5000000,00  - bruto informativo
#   VL_TOT_CREDITOS   (idx  4) = 1500000,00  - créditos de entradas
#   VL_SLD_APURADO    (idx  9) = 3500000,00  - saldo devedor (5M - 1.5M)
#   VL_TOT_DED        (idx 10) =  200000,00  - deduções (incentivos etc.)
#   VL_ICMS_RECOLHER  (idx 11) = 3300000,00  - valor líquido a recolher (3.5M - 200k)
# Prova que icms_total_debitos != icms_a_recolher


async def test_listar_registros_retorna_campos_como_lista() -> None:
    """listar_registros_sped deve retornar campos como lista indexável, não string bruta."""
    registros = await listar_registros_sped(_SPED_CONTRIBUICOES_SAMPLE, "M210")

    assert len(registros) == 1
    campos = registros[0]["campos"]
    # campos deve ser uma lista
    assert isinstance(campos, list), f"Esperado list, obtido {type(campos)}"
    # campo[7] (índice 7 do registro, mas campos[1:] então índice 6 na lista) = VL_CONT_PERIODO
    # Layout M210: REG|COD_CONT|VL_REC_BRT|VL_BC_CONT|ALIQ_CONT|QUANT_BC_CONT|VL_CONT_APUR|VL_AJUS_ACRES|VL_AJUS_REDUC|VL_CONT_DIFER|VL_CONT_DIFER_ANT|VL_CONT_PER|ALIQ_CONT_OPT
    # Índice 0 da lista campos = COD_CONT, índice 6 = VL_CONT_PER (campo 7 do registro)
    assert _to_float(campos[6]) == pytest.approx(3708500.27)


async def test_listar_registros_m610_campos_como_lista() -> None:
    """M610 deve retornar campos como lista com VL_CONT_PERIODO extraível."""
    registros = await listar_registros_sped(_SPED_CONTRIBUICOES_SAMPLE, "M610")

    assert len(registros) == 1
    campos = registros[0]["campos"]
    assert isinstance(campos, list)
    # M610 tem mesmo layout que M210 para o campo 7
    assert _to_float(campos[6]) == pytest.approx(17033125.40)


async def test_listar_registros_e110_campos_como_lista() -> None:
    """E110 deve retornar campos como lista com VL_TOT_DEBITOS e VL_ICMS_RECOLHER extraíveis.

    Layout E110 (Guia Prático EFD ICMS/IPI, Ato COTEPE/ICMS 44/2018):
      campo 02 (índice  0) = VL_TOT_DEBITOS   - débitos BRUTOS
      campo 13 (índice 11) = VL_ICMS_RECOLHER - valor líquido a recolher
    """
    registros = await listar_registros_sped(_SPED_ICMS_IPI_SAMPLE, "E110")

    assert len(registros) == 1
    campos = registros[0]["campos"]
    assert isinstance(campos, list)
    # VL_TOT_DEBITOS = índice 0 (campo 02 do registro, após remover REG)
    assert _to_float(campos[0]) == pytest.approx(2900000.00)
    # VL_ICMS_RECOLHER = índice 11 (campo 13 do registro, após remover REG)
    assert _to_float(campos[11]) == pytest.approx(2900000.00)


async def test_listar_registros_multiplas_ocorrencias() -> None:
    """Múltiplos registros M210 (um por período num arquivo multi-período) devem todos ser retornados."""
    conteudo = """\
|0000|006|1|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|31022024|
|M210|PIS|0,00|0,00|1000,00|0,00|0,00|1000,00|0,00|0,00|0,00|1000,00|0,00|1,65|
|M210|PIS|0,00|0,00|2000,00|0,00|0,00|2000,00|0,00|0,00|0,00|2000,00|0,00|1,65|
|9999|3|
"""
    registros = await listar_registros_sped(conteudo, "M210")

    assert len(registros) == 2
    assert _to_float(registros[0]["campos"][6]) == pytest.approx(1000.00)
    assert _to_float(registros[1]["campos"][6]) == pytest.approx(2000.00)


async def test_listar_registros_campo_vazio_retorna_zero() -> None:
    """Campo vazio num registro deve converter para 0.0 sem erro."""
    conteudo = """\
|0000|006|1|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|31012024|
|M210|PIS|0,00|0,00||0,00|0,00||0,00|0,00|0,00||0,00|1,65|
|9999|2|
"""
    registros = await listar_registros_sped(conteudo, "M210")

    assert len(registros) == 1
    campos = registros[0]["campos"]
    # Campo vazio deve converter para 0.0
    assert _to_float(campos[4]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# metricas_chave: PIS, COFINS e ICMS em summarize_sped
# ---------------------------------------------------------------------------


async def test_summarize_sped_contribuicoes_pis_cofins_em_metricas(
    tmp_path: Path,
) -> None:
    """summarize_sped deve preencher pis_total e cofins_total em metricas_chave."""
    arquivo = tmp_path / "efd_contrib.txt"
    arquivo.write_text(_SPED_CONTRIBUICOES_SAMPLE, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    assert "pis_total" in resumo.metricas_chave, (
        f"Chave pis_total ausente. Chaves presentes: {list(resumo.metricas_chave)}"
    )
    assert "cofins_total" in resumo.metricas_chave, (
        f"Chave cofins_total ausente. Chaves presentes: {list(resumo.metricas_chave)}"
    )
    assert resumo.metricas_chave["pis_total"] == pytest.approx(3708500.27)
    assert resumo.metricas_chave["cofins_total"] == pytest.approx(17033125.40)


async def test_summarize_sped_icms_a_recolher_em_metricas(tmp_path: Path) -> None:
    """summarize_sped deve preencher icms_a_recolher (VL_ICMS_RECOLHER, campo 13) em metricas_chave."""
    arquivo = tmp_path / "efd_icms.txt"
    arquivo.write_text(_SPED_ICMS_IPI_SAMPLE, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    assert "icms_a_recolher" in resumo.metricas_chave, (
        f"Chave icms_a_recolher ausente. Chaves presentes: {list(resumo.metricas_chave)}"
    )
    assert resumo.metricas_chave["icms_a_recolher"] == pytest.approx(2900000.00)


async def test_summarize_sped_icms_total_debitos_em_metricas(tmp_path: Path) -> None:
    """summarize_sped deve preencher icms_total_debitos (VL_TOT_DEBITOS, campo 02) em metricas_chave."""
    arquivo = tmp_path / "efd_icms.txt"
    arquivo.write_text(_SPED_ICMS_IPI_SAMPLE, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    assert "icms_total_debitos" in resumo.metricas_chave, (
        f"Chave icms_total_debitos ausente. Chaves presentes: {list(resumo.metricas_chave)}"
    )
    assert resumo.metricas_chave["icms_total_debitos"] == pytest.approx(2900000.00)


async def test_summarize_sped_icms_com_creditos_distingue_bruto_de_recolher(
    tmp_path: Path,
) -> None:
    """Quando há créditos, icms_total_debitos (bruto) deve diferir de icms_a_recolher (líquido).

    Este teste prova que os dois campos são semanticamente distintos:
      - icms_total_debitos = 5.000.000 (débitos BRUTOS de saídas)
      - icms_a_recolher   = 3.300.000 (após deduzir créditos 1.5M e deduções 200k)
    Somar icms_total_debitos com pis_total/cofins_total para calcular carga fiscal
    seria um erro: o valor correto para comparação é icms_a_recolher.
    """
    arquivo = tmp_path / "efd_icms_creditos.txt"
    arquivo.write_text(_SPED_ICMS_COM_CREDITOS_SAMPLE, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    tot_debitos = resumo.metricas_chave["icms_total_debitos"]
    a_recolher = resumo.metricas_chave["icms_a_recolher"]

    assert tot_debitos == pytest.approx(5000000.00)
    assert a_recolher == pytest.approx(3300000.00)
    # A distinção é o ponto central: bruto != líquido quando há créditos/deduções
    assert tot_debitos != pytest.approx(a_recolher)


async def test_summarize_sped_multiplos_m210_soma_corretamente(tmp_path: Path) -> None:
    """Múltiplos M210 no mesmo arquivo devem ser somados em pis_total."""
    conteudo = """\
|0000|006|1|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|28022024|
|0110|2|IN|
|M210|PIS|0,00|0,00|1000000,00|0,00|0,00|1000000,00|0,00|0,00|0,00|1000000,00|0,00|1,65|
|M210|PIS|0,00|0,00|500000,00|0,00|0,00|500000,00|0,00|0,00|0,00|500000,00|0,00|1,65|
|9999|4|
"""
    arquivo = tmp_path / "efd_multi_m210.txt"
    arquivo.write_text(conteudo, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    assert resumo.metricas_chave["pis_total"] == pytest.approx(1500000.00)


async def test_summarize_sped_sem_registros_imposto_retorna_zero(tmp_path: Path) -> None:
    """Arquivo sem M210/M610/E110 deve retornar 0.0 para as métricas (não ausente)."""
    conteudo = """\
|0000|015|0|N||EMPRESA TESTE LTDA|08177641000128||GO|12345678|5208707||A|0|01012024|31012024|
|9999|2|
"""
    arquivo = tmp_path / "efd_vazio.txt"
    arquivo.write_text(conteudo, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    # Para EFD ICMS/IPI (tipo 0), ambas as chaves de ICMS devem existir e ser 0.0
    assert resumo.metricas_chave.get("icms_total_debitos", -1.0) == pytest.approx(0.0)
    assert resumo.metricas_chave.get("icms_a_recolher", -1.0) == pytest.approx(0.0)


async def test_summarize_sped_regime_cumulativo_lido_de_0110(tmp_path: Path) -> None:
    """Registro 0110 com COD_INC_TRIB=1 deve ser lido e indicar regime cumulativo."""
    conteudo = """\
|0000|006|1|N||EMPRESA CUMULATIVA LTDA|11222333000181||SP|987654321|3550308||A|0|01012024|31012024|
|0110|1|IN|
|M210|PIS|0,00|0,00|100,00|0,00|0,00|100,00|0,00|0,00|0,00|100,00|0,00|0,65|
|9999|3|
"""
    arquivo = tmp_path / "efd_cumulativo.txt"
    arquivo.write_text(conteudo, encoding="latin-1")

    resumo = await summarize_sped(str(arquivo))

    # Regime deve ser capturado em metricas_chave ou no resumo
    assert "regime_pis_cofins" in resumo.metricas_chave or "cumulativo" in resumo.resumo.lower()
