"""Testes offline para o módulo tabelas fiscais estáticas."""

import pytest

from mcp_fiscal_brasil._core import FiscalValidationError
from mcp_fiscal_brasil.tabelas.loader import (
    CFOP_TABLE,
    CSOSN_TABLE,
    CST_ICMS_NORMAL,
    CST_IPI_ENTRADA,
    CST_IPI_SAIDA,
    CST_PIS_COFINS,
    ICMS_ALIQUOTA_INTERNA,
    buscar_aliquota_icms,
    buscar_cest,
    buscar_cfop,
    buscar_ncm,
    validar_cst,
)
from mcp_fiscal_brasil.tabelas.tools import (
    consultar_aliquota_icms,
    consultar_cest,
    consultar_cfop,
    consultar_ncm,
    validar_cst_tool,
)

# ---------------------------------------------------------------------------
# Testes do loader (camada de dados)
# ---------------------------------------------------------------------------


class TestCFOPLoader:
    def test_cfop_saida_estadual_existe(self) -> None:
        dado = buscar_cfop("5102")
        assert dado is not None
        assert dado["tipo"] == "saida"
        assert dado["aplicacao"] == "estadual"
        assert dado["codigo"] == "5102"

    def test_cfop_entrada_interestadual_existe(self) -> None:
        dado = buscar_cfop("2101")
        assert dado is not None
        assert dado["tipo"] == "entrada"
        assert dado["aplicacao"] == "interestadual"

    def test_cfop_exportacao_existe(self) -> None:
        dado = buscar_cfop("7101")
        assert dado is not None
        assert dado["aplicacao"] == "exterior"
        assert dado["tipo"] == "saida"

    def test_cfop_inexistente_retorna_none(self) -> None:
        assert buscar_cfop("9999") is None

    def test_cfop_com_ponto_normalizado(self) -> None:
        dado = buscar_cfop("5.102")
        assert dado is not None
        assert dado["codigo"] == "5102"

    def test_tabela_cfop_cobre_grupos_principais(self) -> None:
        grupos = {"1", "2", "3", "5", "6", "7"}
        grupos_presentes = {k[0] for k in CFOP_TABLE}
        assert grupos.issubset(grupos_presentes)

    def test_cfop_retorno_contem_campos_obrigatorios(self) -> None:
        dado = buscar_cfop("1101")
        assert dado is not None
        for campo in ("codigo", "descricao", "tipo", "aplicacao", "grupo"):
            assert campo in dado, f"Campo ausente: {campo}"

    def test_cfop_grupo_extraido_corretamente(self) -> None:
        dado = buscar_cfop("6102")
        assert dado is not None
        assert dado["grupo"] == "6"


class TestCSTLoader:
    def test_cst_icms_normal_valido(self) -> None:
        resultado = validar_cst("000", "normal")
        assert resultado["valido"] is True
        assert resultado["tabela"] == "CST_ICMS"
        assert "Nacional" in resultado["descricao"]

    def test_cst_icms_isento_valido(self) -> None:
        resultado = validar_cst("040", "normal")
        assert resultado["valido"] is True
        assert resultado["descricao"] is not None

    def test_cst_icms_invalido_normal(self) -> None:
        resultado = validar_cst("999", "normal")
        assert resultado["valido"] is False
        assert resultado["descricao"] is None

    def test_csosn_simples_valido(self) -> None:
        resultado = validar_cst("101", "simples")
        assert resultado["valido"] is True
        assert resultado["tabela"] == "CSOSN"
        assert "Simples" in resultado["descricao"]

    def test_csosn_400_nao_tributada(self) -> None:
        resultado = validar_cst("400", "simples")
        assert resultado["valido"] is True
        assert "Não tributada" in resultado["descricao"]

    def test_csosn_invalido_simples(self) -> None:
        resultado = validar_cst("999", "simples")
        assert resultado["valido"] is False

    def test_cst_pis_cofins_valido(self) -> None:
        resultado = validar_cst("01", "normal")
        assert resultado["valido"] is True
        assert resultado["tabela"] == "CST_PIS_COFINS"

    def test_cst_ipi_entrada_valido(self) -> None:
        resultado = validar_cst("00", "normal")
        assert resultado["valido"] is True

    def test_cst_ipi_saida_valido(self) -> None:
        resultado = validar_cst("50", "normal")
        assert resultado["valido"] is True

    def test_cst_normaliza_maiusculas(self) -> None:
        resultado = validar_cst("000", "NORMAL")
        assert resultado["valido"] is True

    def test_tabelas_cst_nao_vazias(self) -> None:
        assert len(CST_ICMS_NORMAL) > 50
        assert len(CSOSN_TABLE) >= 10
        assert len(CST_PIS_COFINS) >= 20
        assert len(CST_IPI_ENTRADA) >= 7
        assert len(CST_IPI_SAIDA) >= 7


class TestICMSLoader:
    def test_aliquota_sp_para_rj(self) -> None:
        dado = buscar_aliquota_icms("SP", "RJ")
        assert dado is not None
        assert dado["aliquota_interestadual"] == 7.0
        assert dado["uf_origem"] == "SP"
        assert dado["uf_destino"] == "RJ"

    def test_aliquota_sp_para_ba(self) -> None:
        dado = buscar_aliquota_icms("SP", "BA")
        assert dado is not None
        assert dado["aliquota_interestadual"] == 12.0

    def test_aliquota_rj_para_sp(self) -> None:
        dado = buscar_aliquota_icms("RJ", "SP")
        assert dado is not None
        assert dado["aliquota_interestadual"] == 7.0

    def test_difal_calculado(self) -> None:
        dado = buscar_aliquota_icms("SP", "GO")
        assert dado is not None
        esperado = dado["aliquota_interna_destino"] - dado["aliquota_interestadual"]
        assert abs(dado["diferencial_aliquota"] - esperado) < 0.001

    def test_uf_invalida_retorna_none(self) -> None:
        assert buscar_aliquota_icms("XX", "SP") is None
        assert buscar_aliquota_icms("SP", "XX") is None

    def test_todas_27_ufs_cobertas(self) -> None:
        assert len(ICMS_ALIQUOTA_INTERNA) == 27

    def test_aliquotas_internas_no_intervalo_esperado(self) -> None:
        for uf, aliq in ICMS_ALIQUOTA_INTERNA.items():
            assert 16.0 <= aliq <= 25.0, f"Alíquota suspeita para {uf}: {aliq}%"

    def test_fundamento_legal_presente(self) -> None:
        dado = buscar_aliquota_icms("MG", "CE")
        assert dado is not None
        assert "EC 87/2015" in dado["fundamento"]


class TestNCMLoader:
    def test_ncm_existente_retorna_dados(self) -> None:
        dado = buscar_ncm("84713000")
        assert dado is not None
        assert dado["codigo"] == "84713000"
        assert (
            "portáteis" in dado["descricao"].lower() or "processamento" in dado["descricao"].lower()
        )

    def test_ncm_inexistente_retorna_none(self) -> None:
        dado = buscar_ncm("00000000")
        assert dado is None

    def test_ncm_com_pontuacao_normalizada(self) -> None:
        dado = buscar_ncm("8471.30.00")
        # pode não existir no subconjunto, mas não deve lançar exceção
        # (busca ncm limpo sem pontuação)
        # se existir, código deve estar limpo
        if dado is not None:
            assert "." not in dado["codigo"]

    def test_ncm_cerveja_com_ipi(self) -> None:
        dado = buscar_ncm("22030000")
        assert dado is not None
        assert dado["aliquota_ipi"] == 30.0


class TestCESTLoader:
    def test_cest_existente_retorna_dados(self) -> None:
        dado = buscar_cest("0100700")
        assert dado is not None
        assert dado["cest"] == "0100700"
        assert isinstance(dado["ncm_relacionados"], list)

    def test_cest_inexistente_retorna_none(self) -> None:
        dado = buscar_cest("9999999")
        assert dado is None

    def test_cest_cerveja_com_ncm(self) -> None:
        dado = buscar_cest("0200100")
        assert dado is not None
        assert "22030000" in dado["ncm_relacionados"]

    def test_cest_com_pontuacao_normalizada(self) -> None:
        dado = buscar_cest("02.001.00")
        assert dado is not None
        assert dado["cest"] == "0200100"


# ---------------------------------------------------------------------------
# Testes das tools (camada de negócio / async)
# ---------------------------------------------------------------------------


class TestConsultarCFOP:
    async def test_cfop_valido_retorna_response(self) -> None:
        resp = await consultar_cfop("5102")
        assert resp.codigo == "5102"
        assert resp.tipo == "saida"
        assert resp.aplicacao == "estadual"

    async def test_cfop_entrada_valido(self) -> None:
        resp = await consultar_cfop("1556")
        assert resp.tipo == "entrada"

    async def test_cfop_formato_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_cfop("AB12")

    async def test_cfop_inexistente_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_cfop("9999")

    async def test_cfop_comprimento_errado_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_cfop("510")

    async def test_cfop_com_ponto_aceito(self) -> None:
        resp = await consultar_cfop("5.102")
        assert resp.codigo == "5102"

    async def test_cfop_response_contem_grupo(self) -> None:
        resp = await consultar_cfop("6101")
        assert resp.grupo == "6"


class TestValidarCST:
    async def test_cst_icms_normal_valido(self) -> None:
        resp = await validar_cst_tool("000", "normal")
        assert resp.valido is True
        assert resp.regime == "normal"

    async def test_csosn_simples_valido(self) -> None:
        resp = await validar_cst_tool("101", "simples")
        assert resp.valido is True
        assert resp.tabela == "CSOSN"

    async def test_regime_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await validar_cst_tool("000", "outro")

    async def test_cst_invalido_retorna_falso(self) -> None:
        resp = await validar_cst_tool("999", "normal")
        assert resp.valido is False
        assert resp.descricao is None

    async def test_cst_pis_cofins_no_regime_normal(self) -> None:
        resp = await validar_cst_tool("01", "normal")
        assert resp.valido is True
        assert resp.tabela == "CST_PIS_COFINS"

    async def test_cst_response_contem_regime(self) -> None:
        resp = await validar_cst_tool("040", "normal")
        assert resp.regime == "normal"


class TestConsultarAliquotaICMS:
    async def test_sp_para_mg(self) -> None:
        resp = await consultar_aliquota_icms("SP", "MG")
        assert resp.aliquota_interestadual == 7.0
        assert resp.uf_origem == "SP"
        assert resp.uf_destino == "MG"

    async def test_sp_para_ba(self) -> None:
        resp = await consultar_aliquota_icms("SP", "BA")
        assert resp.aliquota_interestadual == 12.0

    async def test_difal_positivo_para_estado_com_aliquota_maior(self) -> None:
        # SP (18%) -> MA (22%): DIFAL = 22 - 12 = 10
        resp = await consultar_aliquota_icms("SP", "MA")
        assert resp.diferencial_aliquota > 0

    async def test_uf_origem_invalida_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_aliquota_icms("XX", "SP")

    async def test_uf_destino_invalida_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_aliquota_icms("SP", "ZZ")

    async def test_uf_minuscula_aceita(self) -> None:
        resp = await consultar_aliquota_icms("sp", "rj")
        assert resp.uf_origem == "SP"
        assert resp.uf_destino == "RJ"

    async def test_fundamento_presente(self) -> None:
        resp = await consultar_aliquota_icms("GO", "SP")
        assert len(resp.fundamento) > 10

    async def test_operacao_intraestadual_difal_zero(self) -> None:
        # Operação dentro do mesmo estado: DIFAL deve ser zero
        resp = await consultar_aliquota_icms("SP", "SP")
        assert resp.uf_origem == "SP"
        assert resp.uf_destino == "SP"
        assert resp.diferencial_aliquota == 0.0
        assert "intraestadual" in resp.fundamento.lower()


class TestConsultarNCM:
    async def test_ncm_valido_retorna_response(self) -> None:
        resp = await consultar_ncm("84713000")
        assert resp.codigo == "84713000"
        assert resp.capitulo == "84"
        assert resp.posicao == "8471"

    async def test_ncm_formato_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_ncm("1234")

    async def test_ncm_letras_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_ncm("ABCD1234")

    async def test_ncm_inexistente_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_ncm("00000000")

    async def test_ncm_com_pontuacao_aceito(self) -> None:
        # 84713000 existe na amostra
        resp = await consultar_ncm("8471.30.00")
        assert resp.codigo == "84713000"


class TestConsultarCEST:
    async def test_cest_valido_retorna_response(self) -> None:
        resp = await consultar_cest("0200100")
        assert resp.cest == "0200100"
        assert resp.segmento == "02"

    async def test_cest_com_pontuacao_aceito(self) -> None:
        resp = await consultar_cest("02.001.00")
        assert resp.cest == "0200100"

    async def test_cest_formato_invalido_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_cest("123")

    async def test_cest_inexistente_levanta_erro(self) -> None:
        with pytest.raises(FiscalValidationError):
            await consultar_cest("9999999")

    async def test_cest_ncm_relacionados_lista(self) -> None:
        resp = await consultar_cest("0200100")
        assert isinstance(resp.ncm_relacionados, list)
        assert len(resp.ncm_relacionados) > 0


# ---------------------------------------------------------------------------
# Testes de registro (_tools.py / register)
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_adiciona_5_tools(self) -> None:
        from fastmcp import FastMCP

        from mcp_fiscal_brasil.tabelas._tools import register

        app_teste = FastMCP(name="test")
        register(app_teste)
        tools = await app_teste.list_tools()
        nomes = {t.name for t in tools}
        esperadas = {
            "consultar_ncm",
            "consultar_cfop",
            "validar_cst",
            "consultar_cest",
            "consultar_aliquota_icms",
        }
        assert esperadas.issubset(nomes), f"Tools faltando: {esperadas - nomes}"

    def test_register_funcao_exportada(self) -> None:
        from mcp_fiscal_brasil.tabelas import register

        assert callable(register)
