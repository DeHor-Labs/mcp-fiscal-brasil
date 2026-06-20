"""Simulador de transicao da Reforma Tributaria brasileira (LC 214/2025).

Estima o impacto financeiro ano a ano (2026-2033) da substituicao gradual
dos tributos atuais (PIS/COFINS, ICMS, ISS) pelos novos (CBS e IBS).

AVISOS LEGAIS:
- As aliquotas plenas do IBS (~17,7%) e CBS (~8,8%) sao estimativas de
  referencia; nao foram fixadas definitivamente em lei ate a publicacao
  desta versao. Os valores serao definidos pelo CGIBS e Senado Federal.
- Empresas do Simples Nacional e MEI entram no novo sistema somente a
  partir de 2027, com regras especificas ainda em regulamentacao.
- Creditos de IBS/CBS (nao-cumulatividade) nao sao modelados nesta v1.
- ICMS varia por estado; o valor usado e o informado pelo usuario.
- Setores com reducao de aliquota (saude, educacao, cesta basica) possuem
  aliquotas diferenciadas nao modeladas aqui.

Fontes consultadas para o cronograma:
- LC 214/2025 (arts. 6, 7, 337, 343, 346)
  https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm
- SimTax - Transicao ICMS/IBS 2029-2032
  https://simtax.com.br/transicao-do-icms-para-o-ibs-como-funcionara-a-troca-de-carga-entre-2029-e-2032/
- Cronograma Trad & Cavalcanti
  https://www.tradecavalcanti.com.br/publicacoes/cronograma-reforma-tributaria-lei-complementar-214-2025
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Cronograma da transicao (LC 214/2025)
# ---------------------------------------------------------------------------
# 2026: CBS 0,9% + IBS 0,1% - fase de teste (compensavel com PIS/COFINS,
#        impacto liquido ~zero para o contribuinte)
# 2027: CBS plena substitui PIS/COFINS; IPI reduzido (exceto ZFM);
#        IBS: sem efeito sobre ICMS/ISS em 2027-2028 (reducao comeca em 2029)
# 2028: igual 2027 (sem mudanca adicional no ICMS/ISS)
# 2029: IBS sobe para 10% da aliquota plena; ICMS/ISS reduzem para 90%
# 2030: IBS 20%; ICMS/ISS 80%
# 2031: IBS 30%; ICMS/ISS 70%
# 2032: IBS 40%; ICMS/ISS 60%
# 2033: IBS 100%; ICMS/ISS extintos

# Aliquotas de referencia CBS e IBS (ESTIMATIVAS - nao fixadas em lei)
# Expostas como constantes publicas para uso externo e em testes.
CBS_REFERENCIA_PCT = 8.8  # substitui PIS/COFINS a partir de 2027
IBS_REFERENCIA_PCT = 17.7  # substitui ICMS+ISS em 2033 (estimativa)

# Aliases privados mantidos para compatibilidade interna
_CBS_REFERENCIA_PCT = CBS_REFERENCIA_PCT
_IBS_REFERENCIA_PCT = IBS_REFERENCIA_PCT

# PIS/COFINS padrao: regime nao-cumulativo LP/LR ~9,25%; Simples embutido no DAS
_PIS_COFINS_PADRAO_NAO_CUMULATIVO = 9.25
# 3,65% e uma aproximacao conservadora baseada no regime cumulativo (PIS 0,65% + COFINS 3%),
# utilizada para todos os setores do Simples Nacional pois o DAS nao decompoe PIS/COFINS.
_PIS_COFINS_PADRAO_SIMPLES = 3.65

# Fracao do ICMS/ISS que o IBS assume em cada ano de 2029-2032
_FRACAO_IBS_POR_ANO: dict[int, float] = {
    2026: 0.0,
    2027: 0.0,
    2028: 0.0,
    2029: 0.10,
    2030: 0.20,
    2031: 0.30,
    2032: 0.40,
    2033: 1.00,
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _validar_aliquota(nome: str, valor: float | None) -> None:
    """Valida que uma aliquota opcional esta no intervalo [0, 100]."""
    if valor is not None and not (0 <= valor <= 100):
        raise ValueError(f"{nome} deve estar entre 0 e 100 (percentual). Recebido: {valor}.")


# ---------------------------------------------------------------------------
# Schemas de saida
# ---------------------------------------------------------------------------


class ResultadoAnual(BaseModel):
    """Estimativa de carga tributaria para um ano especifico da transicao."""

    ano: int = Field(description="Ano de referencia (2026-2033).")
    carga_regime_atual_pct: float = Field(
        description=(
            "Aliquota efetiva estimada (%) do regime antigo (PIS/COFINS + ICMS ou ISS) "
            "aplicada sobre o faturamento neste ano, ja com o desconto proporcional da transicao."
        )
    )
    carga_regime_novo_pct: float = Field(
        description=(
            "Aliquota efetiva estimada (%) da parte CBS+IBS que passa a incidir "
            "neste ano (IBS na proporcao da transicao + CBS quando aplicavel)."
        )
    )
    carga_total_pct: float = Field(
        description=(
            "Soma da carga antiga com a nova para o ano, representando a tributacao "
            "efetiva estimada sobre o faturamento."
        )
    )
    carga_total_reais: float = Field(
        description="Carga total estimada em reais para o faturamento informado."
    )
    nota_ano: str = Field(
        description="Comentario qualitativo sobre o que muda neste ano especifico."
    )


class SimulacaoReformaResult(BaseModel):
    """Resultado da simulacao de transicao da Reforma Tributaria (LC 214/2025).

    Apresenta a carga tributaria estimada ano a ano (2026-2033), mostrando
    o blend entre os tributos do regime antigo (ICMS/ISS e PIS/COFINS) e
    os novos (CBS e IBS), conforme o cronograma de transicao da LC 214/2025.
    """

    faturamento_anual: float = Field(
        description="Faturamento anual utilizado na simulacao (reais)."
    )
    setor: str = Field(description="Setor informado: comercio, servicos ou industria.")
    regime_atual: str = Field(
        description="Regime tributario atual informado: Simples Nacional, Lucro Presumido ou Lucro Real."
    )
    resultados_por_ano: list[ResultadoAnual] = Field(
        description=(
            "Projecao ano a ano de 2026 a 2033 com a carga estimada do regime "
            "antigo, do regime novo e o total."
        )
    )
    premissas: list[str] = Field(
        description=(
            "Premissas utilizadas no calculo: aliquotas informadas pelo usuario e "
            "valores assumidos quando nao fornecidos."
        )
    )
    avisos: list[str] = Field(
        description=(
            "Disclaimers obrigatorios sobre limitacoes do calculo e incertezas "
            "legislativas que o usuario deve conhecer antes de tomar decisoes."
        )
    )


# ---------------------------------------------------------------------------
# Logica de calculo
# ---------------------------------------------------------------------------


def _aliquota_pis_cofins(
    regime_atual: Literal["Simples Nacional", "Lucro Presumido", "Lucro Real"],
    setor: Literal["comércio", "serviços", "indústria"],
    aliquota_pis_cofins_informada: float | None,
) -> float:
    """Retorna a aliquota efetiva de PIS/COFINS em % para o regime/setor."""
    if aliquota_pis_cofins_informada is not None:
        return aliquota_pis_cofins_informada
    if regime_atual == "Simples Nacional":
        # No Simples, PIS/COFINS esta embutido no DAS; isolamos uma estimativa
        # conservadora baseada no regime cumulativo equivalente
        return _PIS_COFINS_PADRAO_SIMPLES
    if regime_atual == "Lucro Presumido":
        # LP usa regime cumulativo: PIS 0,65% + COFINS 3%
        return 3.65
    # Lucro Real: regime nao-cumulativo 1,65% + 7,6%
    return _PIS_COFINS_PADRAO_NAO_CUMULATIVO


def _aliquota_icms_iss(
    setor: Literal["comércio", "serviços", "indústria"],
    aliquota_icms_atual: float | None,
    aliquota_iss_atual: float | None,
) -> tuple[float, str]:
    """Retorna (aliquota_em_pct, descricao_tributo) para o tributo antigo do setor."""
    if setor == "serviços":
        aliq = aliquota_iss_atual if aliquota_iss_atual is not None else 5.0
        return aliq, "ISS"
    # comercio e industria usam ICMS
    aliq = aliquota_icms_atual if aliquota_icms_atual is not None else 12.0
    return aliq, "ICMS"


def _nota_para_ano(ano: int, regime_atual: str) -> str:
    """Retorna um comentario qualitativo sobre o que ocorre em cada ano."""
    notas: dict[int, str] = {
        2026: (
            "Ano de testes: CBS 0,9% + IBS 0,1% com compensacao no PIS/COFINS. "
            "Impacto liquido adicional proximo de zero para a maioria dos contribuintes."
        ),
        2027: (
            "CBS plena substitui PIS e COFINS. IPI zerado (exceto ZFM). "
            "ICMS e ISS seguem integrais. "
            + (
                "Simples Nacional entra no novo sistema com regras proprias (em regulamentacao)."
                if regime_atual == "Simples Nacional"
                else "IBS ainda nao altera ICMS/ISS neste ano."
            )
        ),
        2028: (
            "Ano de consolidacao da CBS. ICMS e ISS permanecem integrais. "
            "IBS ainda nao afeta tributos estaduais/municipais."
        ),
        2029: (
            "Inicio da reducao do ICMS/ISS: tributos estaduais/municipais recuam "
            "para 90% e IBS assume 10% da carga de referencia."
        ),
        2030: "ICMS/ISS reduzidos para 80%; IBS assume 20% da carga de referencia.",
        2031: "ICMS/ISS reduzidos para 70%; IBS assume 30% da carga de referencia.",
        2032: "ICMS/ISS reduzidos para 60%; IBS assume 40% da carga de referencia.",
        2033: (
            "Extincao de ICMS e ISS. IBS pleno. "
            "Novo sistema de tributacao sobre consumo entra em vigor integral."
        ),
    }
    return notas.get(ano, "")


def _calcular_ano(
    ano: int,
    faturamento: float,
    pis_cofins_pct: float,
    icms_iss_pct: float,
    regime_atual: str,
) -> ResultadoAnual:
    """Calcula a carga tributaria estimada para um ano especifico."""
    fracao_ibs = _FRACAO_IBS_POR_ANO[ano]
    fracao_icms_iss_restante = 1.0 - fracao_ibs

    if ano == 2026:
        # Fase de teste: PIS/COFINS integrais, CBS 0,9% compensavel,
        # IBS 0,1% compensavel. Carga adicional liquida ~zero.
        carga_antiga_pct = pis_cofins_pct + icms_iss_pct
        carga_nova_pct = 0.0  # compensado
    elif ano in (2027, 2028):
        # CBS plena substitui PIS/COFINS; ICMS/ISS integrais; IBS ainda nao reduz ICMS/ISS
        carga_antiga_pct = icms_iss_pct  # PIS/COFINS substituido pela CBS
        carga_nova_pct = _CBS_REFERENCIA_PCT  # CBS plena
    else:
        # 2029-2032: ICMS/ISS decresce, IBS cresce proporcionalmente
        # 2033: ICMS/ISS = 0, IBS = 100% da referencia
        carga_antiga_pct = icms_iss_pct * fracao_icms_iss_restante
        # IBS na proporcao + CBS plena (desde 2027)
        ibs_parcela_pct = _IBS_REFERENCIA_PCT * fracao_ibs
        carga_nova_pct = _CBS_REFERENCIA_PCT + ibs_parcela_pct

    carga_total_pct = carga_antiga_pct + carga_nova_pct
    carga_total_reais = faturamento * carga_total_pct / 100.0

    return ResultadoAnual(
        ano=ano,
        carga_regime_atual_pct=round(carga_antiga_pct, 2),
        carga_regime_novo_pct=round(carga_nova_pct, 2),
        carga_total_pct=round(carga_total_pct, 2),
        carga_total_reais=round(carga_total_reais, 2),
        nota_ano=_nota_para_ano(ano, regime_atual),
    )


# ---------------------------------------------------------------------------
# Funcao publica principal
# ---------------------------------------------------------------------------


def simular_transicao_reforma_tributaria(
    faturamento_anual: float,
    setor: Literal["comércio", "serviços", "indústria"],
    regime_atual: Literal["Simples Nacional", "Lucro Presumido", "Lucro Real"],
    aliquota_icms_atual: float | None = None,
    aliquota_iss_atual: float | None = None,
    aliquota_pis_cofins: float | None = None,
) -> SimulacaoReformaResult:
    """Simula o impacto da transicao da Reforma Tributaria (LC 214/2025) de 2026 a 2033.

    Para cada ano, estima (a) a carga do regime antigo (PIS/COFINS + ICMS ou ISS),
    ja ajustada pela reducao proporcional do cronograma, e (b) a carga do regime novo
    (CBS + IBS), aplicando as aliquotas de referencia na fracao de transicao prevista
    pela LC 214/2025.

    Cronograma (LC 214/2025, arts. 337, 343, 346):
    - 2026: fase de teste - CBS 0,9% + IBS 0,1%, compensavel, impacto liquido ~zero.
    - 2027-2028: CBS plena (ref. ~8,8%) substitui PIS/COFINS; ICMS/ISS integrais.
    - 2029: IBS assume 10% da carga de referencia; ICMS/ISS recuam para 90%.
    - 2030: IBS 20%; ICMS/ISS 80%.
    - 2031: IBS 30%; ICMS/ISS 70%.
    - 2032: IBS 40%; ICMS/ISS 60%.
    - 2033: IBS pleno (ref. ~17,7%); ICMS e ISS extintos.

    Args:
        faturamento_anual: Receita bruta anual em reais. Deve ser positivo.
        setor: Setor da empresa. Determina o tributo estadual/municipal aplicavel.
            - "comércio": usa ICMS (aliquota_icms_atual ou 12% se omitido).
            - "indústria": usa ICMS (mesma logica).
            - "serviços": usa ISS (aliquota_iss_atual ou 5% se omitido).
        regime_atual: Regime tributario federal vigente. Determina a aliquota de
            PIS/COFINS assumida quando aliquota_pis_cofins nao e informada.
            - "Simples Nacional": PIS/COFINS embutido no DAS; estimativa 3,65%.
            - "Lucro Presumido": regime cumulativo PIS 0,65% + COFINS 3% = 3,65%.
            - "Lucro Real": regime nao-cumulativo 1,65% + 7,6% = 9,25%.
        aliquota_icms_atual: Aliquota do ICMS em %, declarada pelo usuario (varia por UF).
            Obrigatoria para precisao maxima em comercio/industria. Se None, assume 12%.
        aliquota_iss_atual: Aliquota do ISS em %, declarada pelo usuario (varia por municipio).
            Obrigatoria para precisao maxima em servicos. Se None, assume 5%.
        aliquota_pis_cofins: Aliquota efetiva de PIS/COFINS em % sobre o faturamento.
            Se None, usa o padrao do regime informado.

    Returns:
        SimulacaoReformaResult com projecao anual 2026-2033, premissas usadas e avisos
        obrigatorios sobre as limitacoes e incertezas do calculo.

    Raises:
        ValueError: se faturamento_anual nao for positivo.

    Exemplo:
        resultado = simular_transicao_reforma_tributaria(
            faturamento_anual=1_200_000,
            setor="comércio",
            regime_atual="Lucro Presumido",
            aliquota_icms_atual=12.0,
        )
        for r in resultado.resultados_por_ano:
            print(r.ano, r.carga_total_pct, "%")
    """
    if faturamento_anual <= 0:
        raise ValueError("faturamento_anual deve ser positivo.")

    _validar_aliquota("aliquota_icms_atual", aliquota_icms_atual)
    _validar_aliquota("aliquota_iss_atual", aliquota_iss_atual)
    _validar_aliquota("aliquota_pis_cofins", aliquota_pis_cofins)

    pis_cofins_pct = _aliquota_pis_cofins(regime_atual, setor, aliquota_pis_cofins)
    icms_iss_pct, nome_tributo_estadual = _aliquota_icms_iss(
        setor, aliquota_icms_atual, aliquota_iss_atual
    )

    resultados = [
        _calcular_ano(ano, faturamento_anual, pis_cofins_pct, icms_iss_pct, regime_atual)
        for ano in range(2026, 2034)
    ]

    # Premissas utilizadas
    premissas: list[str] = [
        f"Faturamento anual: R$ {faturamento_anual:,.2f}.",
        f"Setor: {setor}. Regime atual: {regime_atual}.",
        f"Aliquota {nome_tributo_estadual}: {icms_iss_pct:.1f}% "
        f"({'informada pelo usuario' if (aliquota_iss_atual if setor == 'serviços' else aliquota_icms_atual) is not None else 'valor padrao assumido - varia por estado/municipio'}).",
        f"Aliquota PIS/COFINS: {pis_cofins_pct:.2f}% "
        f"({'informada pelo usuario' if aliquota_pis_cofins is not None else f'padrao para {regime_atual}'}).",
        f"CBS de referencia (estimativa): {_CBS_REFERENCIA_PCT}% (substitui PIS/COFINS a partir de 2027).",
        f"IBS de referencia (estimativa): {_IBS_REFERENCIA_PCT}% (aliquota plena em 2033).",
        "Cronograma IBS/ICMS-ISS (LC 214/2025): 10%/90% em 2029, 20%/80% em 2030, 30%/70% em 2031, 40%/60% em 2032, 100%/0% em 2033.",
        "2026: fase de teste com compensacao; impacto liquido adicional assumido como zero.",
    ]

    # Avisos obrigatorios
    avisos: list[str] = [
        "AVISO - Aliquotas plenas: as aliquotas de referencia do IBS (~17,7%) e CBS (~8,8%) "
        "sao ESTIMATIVAS e ainda nao foram fixadas definitivamente em lei. Serao definidas "
        "pelo Comite Gestor do IBS (CGIBS) e pelo Senado Federal.",
        "AVISO - Simples Nacional e MEI (ESTIMATIVA MUITO APROXIMADA): no Simples Nacional, "
        "PIS/COFINS, ICMS e ISS estao todos embutidos no DAS e nao sao apurados separadamente. "
        "O simulador modela esses tributos como se fossem independentes, o que superestima a "
        "carga atual e distorce a comparacao com o regime novo. Optantes do Simples Nacional e "
        "MEI entram no novo sistema a partir de 2027 com regras proprias ainda em regulamentacao "
        "pelo CGIBS. Use os resultados como referencia de ordem de grandeza, nunca como base "
        "de decisao tributaria.",
        "AVISO - Creditos de IBS/CBS: o modelo de nao-cumulatividade (creditos) do IBS/CBS "
        "nao foi modelado nesta versao. Empresas com cadeias de credito podem ter carga "
        "efetiva significativamente diferente.",
        "AVISO - ICMS/ISS por estado/municipio: o ICMS varia por UF e o ISS varia por municipio. "
        "Use o parametro aliquota_icms_atual ou aliquota_iss_atual para precisao maxima.",
        "AVISO - Setores com aliquota reduzida: saude, educacao, transporte publico, "
        "cesta basica e outros setores beneficiados possuem aliquotas diferenciadas "
        "de IBS/CBS nao modeladas nesta versao.",
        "AVISO - Nao substitui parecer contabil ou juridico. Consulte um contador ou "
        "especialista tributario antes de tomar decisoes baseadas nesta estimativa.",
    ]

    return SimulacaoReformaResult(
        faturamento_anual=faturamento_anual,
        setor=setor,
        regime_atual=regime_atual,
        resultados_por_ano=resultados,
        premissas=premissas,
        avisos=avisos,
    )
