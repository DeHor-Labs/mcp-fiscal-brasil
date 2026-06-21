"""
Registro das ferramentas do módulo de impostos de importação no servidor MCP.

Uso:
    from mcp_fiscal_brasil.importacao._tools import register
    register(app)
"""

from typing import Any

from fastmcp import FastMCP

from .tools import calcular_tributos_importacao, consultar_aliquotas_importacao


def register(app: FastMCP) -> None:
    """Registra as 2 ferramentas de importação no servidor MCP fornecido."""

    @app.tool(
        name="consultar_aliquotas_importacao",
        description=(
            "Consulta alíquotas de referência para cálculo de tributos de importação por NCM. "
            "Purpose: obter a alíquota IPI do banco NCM/TIPI e os defaults de PIS/COFINS-importação "
            "antes de usar calcular_tributos_importacao. "
            "Quando usar: antes de calcular tributos de importação, para verificar a alíquota IPI "
            "do produto e conhecer os defaults de PIS/COFINS aplicáveis. "
            "IMPORTANTE: A alíquota II (Imposto de Importação / TEC) NÃO está disponível offline. "
            "Consulte www.mdic.gov.br e informe manualmente em calcular_tributos_importacao. "
            "Comportamento offline: lê do banco SQLite bundled (TIPI); não requer conexão. "
            "Parâmetro: código NCM com 8 dígitos, com ou sem pontuação "
            "(ex: '22030000' ou '2203.00.00')."
        ),
    )
    async def tool_consultar_aliquotas_importacao(ncm: str) -> dict[str, Any]:
        """Consulta alíquotas de referência para importação por NCM (offline).

        Retorna a aliquota IPI do banco NCM/TIPI, os defaults de PIS/COFINS-importacao
        e um aviso sobre a aliquota II (TEC), que nao esta disponivel offline.

        Args:
            ncm: Codigo NCM com 8 digitos, com ou sem pontuacao
                 (ex.: "22030000" ou "2203.00.00").

        Returns:
            dict com ncm, descricao_ncm, aliquota_ipi, defaults de PIS/COFINS
            e aviso_aliquota_ii.
        """
        resultado = await consultar_aliquotas_importacao(ncm)
        return resultado.model_dump(mode="json", exclude_none=True)

    @app.tool(
        name="calcular_tributos_importacao",
        description=(
            "Calcula os tributos de importação em cascata para um produto classificado por NCM. "
            "Purpose: estimar a carga tributária de importação (II, IPI, PIS/COFINS-importação, "
            "ICMS grossed-up, AFRMM e taxa Siscomex) para planejamento de custo de desembaraço. "
            "Quando usar: ao planejar uma importação e precisar estimar o custo total de tributos. "
            "IMPORTANTE: A alíquota II (aliquota_ii) deve ser informada pelo usuário conforme a "
            "TEC vigente em www.mdic.gov.br. Não há fonte offline estruturada para a TEC. "
            "Cascata: VA -> II -> IPI (base=VA+II) -> PIS/COFINS-imp (base=VA) -> "
            "ICMS por dentro (base=VA+II+IPI+PIS+COFINS) -> AFRMM/Siscomex. "
            "DISCLAIMER: Estimativa para planejamento. Não substitui SISCOMEX nem despachante. "
            "Antidumping, regimes especiais, acordos bilaterais e alíquotas diferenciadas "
            "de PIS/COFINS estão fora do escopo do MVP. "
            "Parâmetros: ncm (8 dígitos), valor_aduaneiro (R$), uf_importador (sigla UF), "
            "aliquota_ii (% TEC), modal (maritimo/aereo/terrestre/postal), "
            "frete_maritimo (R$, apenas modal marítimo), aliquota_pis (default 2,1%), "
            "aliquota_cofins (default 9,65%), aliquota_ipi_override (sobrescreve banco NCM)."
        ),
    )
    async def tool_calcular_tributos_importacao(
        ncm: str,
        valor_aduaneiro: float,
        uf_importador: str,
        aliquota_ii: float,
        modal: str = "maritimo",
        frete_maritimo: float = 0.0,
        aliquota_pis: float = 2.1,
        aliquota_cofins: float = 9.65,
        aliquota_ipi_override: float | None = None,
    ) -> dict[str, Any]:
        """Calcula tributos de importacao em cascata para um NCM (offline para IPI/ICMS).

        Ordem: VA -> II -> IPI (VA+II) -> PIS/COFINS-imp (VA) ->
        ICMS por dentro (VA+II+IPI+PIS+COFINS) -> AFRMM -> Siscomex.

        A aliquota II (TEC) deve ser informada pelo usuario (nao ha fonte offline).
        A aliquota IPI vem do banco NCM/TIPI bundled, mas pode ser sobrescrita.
        A aliquota ICMS vem da tabela interna de aliquotas estaduais.

        DISCLAIMER: Estimativa para planejamento. Nao substitui SISCOMEX nem despachante.
        Antidumping, regimes especiais e acordos bilaterais nao sao cobertos.

        Args:
            ncm: Codigo NCM com 8 digitos (ex.: "22030000" ou "2203.00.00").
            valor_aduaneiro: Valor Aduaneiro (VA) em R$. Deve ser positivo.
            uf_importador: Sigla da UF do importador para calculo do ICMS (ex.: "SP").
            aliquota_ii: Aliquota do II (TEC) em percentual (ex.: 20.0). Informar
                         conforme a Tarifa Aduaneira do Brasil (www.mdic.gov.br).
            modal: Modal de transporte: "maritimo", "aereo", "terrestre" ou "postal".
                   Afeta o AFRMM (apenas maritimo). Padrao: "maritimo".
            frete_maritimo: Valor do frete maritimo em R$ para calculo do AFRMM.
                            Relevante apenas quando modal="maritimo". Padrao: 0.0.
            aliquota_pis: Aliquota do PIS-Importacao em % (padrao: 2,1%).
            aliquota_cofins: Aliquota do COFINS-Importacao em % (padrao: 9,65%).
            aliquota_ipi_override: Se informado, sobrescreve a aliquota IPI do banco NCM.

        Returns:
            dict com ncm, modal, valor_aduaneiro, breakdown (lista de tributos com base,
            aliquota e valor), total_tributos, custo_total, avisos e disclaimers.
        """
        resultado = await calcular_tributos_importacao(
            ncm=ncm,
            valor_aduaneiro=valor_aduaneiro,
            uf_importador=uf_importador,
            aliquota_ii=aliquota_ii,
            modal=modal,  # type: ignore[arg-type]
            frete_maritimo=frete_maritimo,
            aliquota_pis=aliquota_pis,
            aliquota_cofins=aliquota_cofins,
            aliquota_ipi_override=aliquota_ipi_override,
        )
        return resultado.model_dump(mode="json", exclude_none=True)
