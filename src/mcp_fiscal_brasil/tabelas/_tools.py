"""
Registro das ferramentas do módulo tabelas no servidor MCP.

Uso:
    from mcp_fiscal_brasil.tabelas._tools import register
    register(app)
"""

from typing import Any

from fastmcp import FastMCP

from .tools import (
    consultar_aliquota_icms,
    consultar_cest,
    consultar_cfop,
    consultar_ncm,
    validar_cst_tool,
)


def register(app: FastMCP) -> None:
    """Registra as 5 ferramentas de tabelas fiscais no servidor MCP fornecido."""

    @app.tool(
        name="consultar_ncm",
        description=(
            "Consulta a Nomenclatura Comum do Mercosul (NCM) de um produto. "
            "Purpose: identificar a classificação fiscal de mercadorias para emissão de NF-e, "
            "cálculo de IPI e preenchimento do SPED. "
            "Quando usar: ao emitir nota fiscal, fazer importação/exportação ou calcular tributos. "
            "Comportamento offline: lê do banco SQLite bundled; não requer conexão. "
            "AVISO: o banco pode conter apenas uma amostra da TIPI completa (~10.515 registros); "
            "execute scripts/build_tabelas_db.py para popular a tabela completa. "
            "Formato do parâmetro: 8 dígitos numéricos, com ou sem pontuação "
            "(ex: '84713019' ou '8471.30.19')."
        ),
    )
    async def tool_consultar_ncm(ncm: str) -> dict[str, Any]:
        """Consulta a Nomenclatura Comum do Mercosul (NCM/TIPI) de um produto.

        Retorna a descricao, aliquota de IPI, unidade tributavel e eventual excecao TIPI
        para o codigo de 8 digitos informado. Operacao offline a partir do banco bundled.

        Args:
            ncm: Codigo NCM com 8 digitos numericos, com ou sem pontucao
                 (ex.: "84713019" ou "8471.30.19").

        Returns:
            dict com codigo, descricao, aliquota_ipi, unidade_tributavel, ex_tipi,
            capitulo e posicao.
        """
        resultado = await consultar_ncm(ncm)
        return resultado.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="consultar_cfop",
        description=(
            "Consulta o Código Fiscal de Operações e Prestações (CFOP). "
            "Purpose: identificar a natureza jurídica de uma operação fiscal para preenchimento "
            "de NF-e, SPED EFD-ICMS/IPI e escrituração contábil. "
            "Quando usar: ao emitir nota fiscal, classificar entradas/saídas ou analisar "
            "obrigações acessórias. "
            "Comportamento offline: lê dicionário em memória com todos os grupos CFOP; "
            "não requer conexão. "
            "Formato do parâmetro: 4 dígitos numéricos (ex: '5102', '6101', '1556'). "
            "Grupos: 1/2/3 = entradas (estadual/interestadual/exterior); "
            "5/6/7 = saídas (estadual/interestadual/exterior)."
        ),
    )
    async def tool_consultar_cfop(cfop: str) -> dict[str, Any]:
        """Consulta os dados de um Codigo Fiscal de Operacoes e Prestacoes (CFOP).

        Retorna a descricao completa, o tipo (entrada ou saida) e o ambito da operacao
        (estadual, interestadual ou exterior). Operacao offline a partir de dicionario em memoria.

        Args:
            cfop: Codigo CFOP com 4 digitos numericos (ex.: "5102", "6101", "2556").

        Returns:
            dict com codigo, descricao, tipo, aplicacao e grupo.
        """
        resultado = await consultar_cfop(cfop)
        return resultado.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="validar_cst",
        description=(
            "Valida um Código de Situação Tributária (CST) ou Código de Situação da Operação "
            "no Simples Nacional (CSOSN). "
            "Purpose: confirmar se o código informado é válido para o regime tributário "
            "antes de emitir NF-e ou escriturar no SPED. "
            "Quando usar: ao preencher o campo CST/CSOSN na NF-e ou no SPED EFD. "
            "Comportamento offline: valida contra tabelas em memória (ICMS, PIS/COFINS, IPI, CSOSN); "
            "não requer conexão. "
            "Parâmetro 'regime': use 'normal' para Lucro Real/Presumido/Arbitrado ou "
            "'simples' para Simples Nacional. "
            "Parâmetro 'cst': 3 dígitos para CST ICMS (ex: '000', '040'), "
            "2 dígitos para CST PIS/COFINS/IPI (ex: '01', '50'), "
            "3 dígitos para CSOSN (ex: '101', '400')."
        ),
    )
    async def tool_validar_cst(cst: str, regime: str) -> dict[str, Any]:
        """Valida um codigo CST (Codigo de Situacao Tributaria) ou CSOSN conforme o regime fiscal.

        Verifica se o codigo informado existe na tabela correspondente ao regime tributario
        e retorna sua descricao. Cobre: CST ICMS (3 digitos), CST PIS/COFINS (2 digitos),
        CST IPI (2 digitos) e CSOSN (3 digitos para Simples Nacional).

        Args:
            cst: Codigo a validar. Exemplos: "000" (CST ICMS), "50" (CST PIS/COFINS),
                 "101" (CSOSN Simples Nacional).
            regime: Regime tributario: "normal" (Lucro Real, Presumido ou Arbitrado)
                    ou "simples" (Simples Nacional).

        Returns:
            dict com cst, valido, descricao, regime e tabela de origem.
        """
        resultado = await validar_cst_tool(cst, regime)
        return resultado.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="consultar_cest",
        description=(
            "Consulta o Código Especificador da Substituição Tributária (CEST). "
            "Purpose: identificar produtos sujeitos à substituição tributária do ICMS, "
            "conforme Convênio ICMS 92/2015 e suas atualizações. "
            "Quando usar: ao emitir NF-e com produtos sujeitos ao ICMS-ST. "
            "Comportamento offline: lê do banco SQLite bundled. "
            "AVISO: o banco pode conter apenas uma amostra; execute scripts/build_tabelas_db.py "
            "para popular a tabela completa. "
            "Formato do parâmetro: 7 dígitos numéricos, com ou sem pontuação "
            "(ex: '0100700' ou '01.007.00')."
        ),
    )
    async def tool_consultar_cest(cest: str) -> dict[str, Any]:
        """Consulta os dados de um Codigo Especificador da Substituicao Tributaria (CEST).

        Retorna a descricao do segmento/produto e a lista de NCMs relacionados.
        Operacao offline a partir do banco SQLite bundled.

        Args:
            cest: Codigo CEST com 7 digitos numericos, com ou sem pontuacao
                  (ex.: "0100700" ou "01.007.00").

        Returns:
            dict com cest, descricao, segmento e ncm_relacionados.
        """
        resultado = await consultar_cest(cest)
        return resultado.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="consultar_aliquota_icms",
        description=(
            "Consulta as alíquotas do ICMS para operações interestaduais entre contribuintes. "
            "Purpose: calcular o DIFAL (Diferencial de Alíquota) e a alíquota interestadual "
            "aplicável na emissão de NF-e, conforme EC 87/2015 e Resolução SF 22/2008. "
            "Quando usar: ao emitir NF-e interestadual, calcular DIFAL ou verificar a "
            "carga tributária de operações entre estados. "
            "Comportamento offline: calcula a partir de tabelas em memória; não requer conexão. "
            "NOTA: não cobre a alíquota de 4% para bens importados (Resolução SF 13/2012). "
            "Parâmetros: siglas de UF em maiúsculo (ex: 'SP', 'MG', 'RJ')."
        ),
    )
    async def tool_consultar_aliquota_icms(uf_origem: str, uf_destino: str) -> dict[str, Any]:
        """Consulta as aliquotas do ICMS para operacao interestadual entre contribuintes.

        Retorna a aliquota interestadual aplicavel (7% ou 12% conforme origem/destino),
        a aliquota interna do estado de destino e o diferencial de aliquota (DIFAL),
        calculado conforme a EC 87/2015 e a Resolucao SF 22/2008.

        Args:
            uf_origem: Sigla da UF de origem (ex.: "SP", "MG", "GO").
            uf_destino: Sigla da UF de destino (ex.: "RJ", "BA", "CE").

        Returns:
            dict com uf_origem, uf_destino, aliquota_interestadual,
            aliquota_interna_destino, diferencial_aliquota e fundamento.
        """
        resultado = await consultar_aliquota_icms(uf_origem, uf_destino)
        return resultado.model_dump(mode="json", exclude_none=True)
