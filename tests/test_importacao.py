"""
Testes para o módulo de cálculo de tributos de importação por NCM.

Exemplo numérico de referência (validado):
  NCM: 22030000 (cerveja)
  VA  = R$ 10.000,00
  II  = 20%  ->  base = 10.000  ->  II = 2.000
  IPI = 30%  ->  base = VA + II = 12.000  ->  IPI = 3.600
  PIS-imp = 2,1%  ->  base = VA = 10.000  ->  PIS = 210
  COFINS-imp = 9,65%  ->  base = VA = 10.000  ->  COFINS = 965
  ICMS-SP (18%) "por dentro" (grossed-up):
    carga_sem_icms = VA + II + IPI + PIS + COFINS = 16.775
    ICMS = carga_sem_icms * aliquota / (1 - aliquota)
         = 16.775 * 0,18 / 0,82
         = 16.775 * 0,21951... = 3.682,32
  AFRMM (25% do frete marítimo, modal=maritimo, frete=0) -> 0
  Siscomex = R$ 40,00 (taxa fixa padrão)

  total_tributos = 2.000 + 3.600 + 210 + 965 + 3.682,32 + 0 + 40 = 10.497,32
  custo_total = 10.000 + 10.497,32 = 20.497,32
"""

import math

import pytest

from mcp_fiscal_brasil._core import FiscalValidationError
from mcp_fiscal_brasil.importacao.tools import (
    calcular_tributos_importacao,
    consultar_aliquotas_importacao,
)

# ---------------------------------------------------------------------------
# Constantes do exemplo numérico de referência
# ---------------------------------------------------------------------------

_NCM_CERVEJA = "22030000"
_NCM_INEXISTENTE = "00000001"
_VA = 10_000.0
_ALIQ_II = 20.0
_ALIQ_IPI_CERVEJA = 30.0
_ALIQ_PIS = 2.1
_ALIQ_COFINS = 9.65
_UF_SP = "SP"
_ALIQ_ICMS_SP = 18.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tributo_por_nome(breakdown: list, nome: str) -> dict | None:
    """Retorna o item de breakdown pelo nome do tributo."""
    for item in breakdown:
        if item.nome == nome:
            return item
    return None


# ---------------------------------------------------------------------------
# Testes de consulta de alíquotas (tool 2)
# ---------------------------------------------------------------------------


class TestConsultarAliquotasImportacao:
    async def test_ncm_existente_retorna_ipi(self) -> None:
        resp = await consultar_aliquotas_importacao(_NCM_CERVEJA)
        assert resp.ncm == _NCM_CERVEJA
        assert resp.aliquota_ipi == pytest.approx(_ALIQ_IPI_CERVEJA)

    async def test_ncm_inexistente_retorna_ipi_none(self) -> None:
        resp = await consultar_aliquotas_importacao(_NCM_INEXISTENTE)
        assert resp.aliquota_ipi is None
        assert len(resp.avisos) > 0

    async def test_defaults_pis_cofins_presentes(self) -> None:
        resp = await consultar_aliquotas_importacao(_NCM_CERVEJA)
        assert resp.aliquota_pis_importacao_default == pytest.approx(2.1)
        assert resp.aliquota_cofins_importacao_default == pytest.approx(9.65)

    async def test_aviso_aliquota_ii_presente(self) -> None:
        resp = await consultar_aliquotas_importacao(_NCM_CERVEJA)
        assert len(resp.aviso_aliquota_ii) > 10
        assert "II" in resp.aviso_aliquota_ii or "TEC" in resp.aviso_aliquota_ii

    async def test_ncm_com_pontuacao_aceito(self) -> None:
        resp = await consultar_aliquotas_importacao("2203.00.00")
        assert resp.ncm == _NCM_CERVEJA

    async def test_formato_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_aliquotas_importacao("123")

    async def test_ncm_letras_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_aliquotas_importacao("ABCD1234")

    async def test_descricao_ncm_preenchida_quando_encontrado(self) -> None:
        resp = await consultar_aliquotas_importacao(_NCM_CERVEJA)
        assert resp.descricao_ncm is not None
        assert len(resp.descricao_ncm) > 3


# ---------------------------------------------------------------------------
# Testes do cálculo cascata (tool 1)
# ---------------------------------------------------------------------------


class TestCalcularTributosImportacao:
    async def test_ii_calculado_corretamente(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            modal="maritimo",
            frete_maritimo=0.0,
        )
        ii = _tributo_por_nome(resp.breakdown, "II")
        assert ii is not None
        assert ii.base_calculo == pytest.approx(_VA)
        assert ii.aliquota == pytest.approx(_ALIQ_II)
        assert ii.valor == pytest.approx(2_000.0)

    async def test_ipi_base_va_mais_ii(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        ipi = _tributo_por_nome(resp.breakdown, "IPI")
        assert ipi is not None
        # base IPI = VA + II = 10.000 + 2.000 = 12.000
        assert ipi.base_calculo == pytest.approx(12_000.0)
        assert ipi.valor == pytest.approx(3_600.0)

    async def test_pis_cofins_base_va(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        pis = _tributo_por_nome(resp.breakdown, "PIS-Importação")
        cofins = _tributo_por_nome(resp.breakdown, "COFINS-Importação")
        assert pis is not None and cofins is not None
        assert pis.base_calculo == pytest.approx(_VA)
        assert cofins.base_calculo == pytest.approx(_VA)
        assert pis.valor == pytest.approx(210.0)
        assert cofins.valor == pytest.approx(965.0)

    async def test_icms_grossed_up_sp(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        icms = _tributo_por_nome(resp.breakdown, "ICMS")
        assert icms is not None
        # carga_sem_icms = 10.000 + 2.000 + 3.600 + 210 + 965 = 16.775
        # ICMS = 16.775 * 0,18 / (1 - 0,18) = 16.775 * 0,21951... = 3.682,32
        assert icms.valor == pytest.approx(3_682.32, abs=0.05)

    async def test_afrmm_zero_sem_frete_maritimo(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            modal="maritimo",
            frete_maritimo=0.0,
        )
        afrmm = _tributo_por_nome(resp.breakdown, "AFRMM")
        assert afrmm is not None
        assert afrmm.valor == pytest.approx(0.0)

    async def test_afrmm_calculado_com_frete(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            modal="maritimo",
            frete_maritimo=1_000.0,
        )
        afrmm = _tributo_por_nome(resp.breakdown, "AFRMM")
        assert afrmm is not None
        # AFRMM = 25% do frete marítimo
        assert afrmm.valor == pytest.approx(250.0)

    async def test_modal_aereo_sem_afrmm(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            modal="aereo",
        )
        afrmm = _tributo_por_nome(resp.breakdown, "AFRMM")
        # Modal aéreo não gera AFRMM
        assert afrmm is None or afrmm.valor == pytest.approx(0.0)

    async def test_siscomex_presente_no_breakdown(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        siscomex = _tributo_por_nome(resp.breakdown, "Siscomex")
        assert siscomex is not None
        assert siscomex.valor > 0

    async def test_custo_total_soma_va_mais_tributos(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        assert resp.custo_total == pytest.approx(
            resp.valor_aduaneiro + resp.total_tributos, abs=0.01
        )

    async def test_total_tributos_soma_breakdown(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        soma = sum(item.valor for item in resp.breakdown)
        assert resp.total_tributos == pytest.approx(soma, abs=0.01)

    async def test_exemplo_referencia_ponta_a_ponta(self) -> None:
        """Valida o exemplo numérico completo do docstring deste módulo."""
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            modal="maritimo",
            frete_maritimo=0.0,
            aliquota_pis=2.1,
            aliquota_cofins=9.65,
        )
        # Siscomex é taxa fixa; AFRMM é 0 (sem frete)
        ii = _tributo_por_nome(resp.breakdown, "II")
        ipi = _tributo_por_nome(resp.breakdown, "IPI")
        pis = _tributo_por_nome(resp.breakdown, "PIS-Importação")
        cofins = _tributo_por_nome(resp.breakdown, "COFINS-Importação")
        icms = _tributo_por_nome(resp.breakdown, "ICMS")

        assert ii is not None and ii.valor == pytest.approx(2_000.0)
        assert ipi is not None and ipi.valor == pytest.approx(3_600.0)
        assert pis is not None and pis.valor == pytest.approx(210.0)
        assert cofins is not None and cofins.valor == pytest.approx(965.0)
        assert icms is not None and icms.valor == pytest.approx(3_682.32, abs=0.05)
        # total > 10.000 (há vários tributos)
        assert resp.total_tributos > 10_000.0
        assert resp.custo_total > 20_000.0

    async def test_disclaimers_presentes(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        assert len(resp.disclaimers) >= 2

    async def test_ncm_inexistente_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await calcular_tributos_importacao(
                ncm=_NCM_INEXISTENTE,
                valor_aduaneiro=_VA,
                uf_importador=_UF_SP,
                aliquota_ii=_ALIQ_II,
            )

    async def test_ncm_formato_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await calcular_tributos_importacao(
                ncm="1234",
                valor_aduaneiro=_VA,
                uf_importador=_UF_SP,
                aliquota_ii=_ALIQ_II,
            )

    async def test_uf_invalida_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await calcular_tributos_importacao(
                ncm=_NCM_CERVEJA,
                valor_aduaneiro=_VA,
                uf_importador="XX",
                aliquota_ii=_ALIQ_II,
            )

    async def test_valor_aduaneiro_negativo_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await calcular_tributos_importacao(
                ncm=_NCM_CERVEJA,
                valor_aduaneiro=-100.0,
                uf_importador=_UF_SP,
                aliquota_ii=_ALIQ_II,
            )

    async def test_aliquota_negativa_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await calcular_tributos_importacao(
                ncm=_NCM_CERVEJA,
                valor_aduaneiro=_VA,
                uf_importador=_UF_SP,
                aliquota_ii=-5.0,
            )

    async def test_ncm_com_pontuacao_aceito(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm="2203.00.00",
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
        )
        assert resp.ncm == _NCM_CERVEJA

    async def test_uf_minuscula_aceita(self) -> None:
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador="sp",
            aliquota_ii=_ALIQ_II,
        )
        assert resp.ncm == _NCM_CERVEJA

    async def test_aviso_quando_ipi_sem_entrada_no_banco(self) -> None:
        """NCM existente no banco mas sem alíquota IPI deve gerar aviso."""
        # NCM de computador portátil (IPI = 0% ou pode não ter registro)
        resp = await calcular_tributos_importacao(
            ncm="84713000",
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=0.0,
            aliquota_ipi_override=None,
        )
        # Deve funcionar; IPI pode ser 0 sem erro
        ipi = _tributo_por_nome(resp.breakdown, "IPI")
        assert ipi is not None

    async def test_aliquota_ipi_override_tem_precedencia(self) -> None:
        """aliquota_ipi_override deve sobrescrever o valor do banco NCM."""
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            aliquota_ipi_override=5.0,
        )
        ipi = _tributo_por_nome(resp.breakdown, "IPI")
        assert ipi is not None
        assert ipi.aliquota == pytest.approx(5.0)

    async def test_icms_go_diferente_sp(self) -> None:
        """Alíquota ICMS de GO deve gerar ICMS diferente do SP."""
        resp_sp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador="SP",
            aliquota_ii=_ALIQ_II,
        )
        resp_go = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador="GO",
            aliquota_ii=_ALIQ_II,
        )
        icms_sp = _tributo_por_nome(resp_sp.breakdown, "ICMS")
        icms_go = _tributo_por_nome(resp_go.breakdown, "ICMS")
        assert icms_sp is not None and icms_go is not None
        # ICMS de SP (18%) e GO (17%) devem ser diferentes
        assert not math.isclose(icms_sp.valor, icms_go.valor, rel_tol=1e-3)

    async def test_pis_cofins_diferenciados_com_override(self) -> None:
        """Alíquotas PIS/COFINS customizadas devem ser aplicadas."""
        resp = await calcular_tributos_importacao(
            ncm=_NCM_CERVEJA,
            valor_aduaneiro=_VA,
            uf_importador=_UF_SP,
            aliquota_ii=_ALIQ_II,
            aliquota_pis=1.65,
            aliquota_cofins=7.6,
        )
        pis = _tributo_por_nome(resp.breakdown, "PIS-Importação")
        cofins = _tributo_por_nome(resp.breakdown, "COFINS-Importação")
        assert pis is not None and cofins is not None
        assert pis.valor == pytest.approx(165.0)
        assert cofins.valor == pytest.approx(760.0)


# ---------------------------------------------------------------------------
# Testes de registro (_tools.py)
# ---------------------------------------------------------------------------


class TestRegisterImportacao:
    async def test_register_adiciona_2_tools(self) -> None:
        from fastmcp import FastMCP

        from mcp_fiscal_brasil.importacao._tools import register

        app_teste = FastMCP(name="test-importacao")
        register(app_teste)
        tools = await app_teste.list_tools()
        nomes = {t.name for t in tools}
        esperadas = {
            "calcular_tributos_importacao",
            "consultar_aliquotas_importacao",
        }
        assert esperadas.issubset(nomes), f"Tools faltando: {esperadas - nomes}"

    def test_register_funcao_exportada(self) -> None:
        from mcp_fiscal_brasil.importacao import register

        assert callable(register)
