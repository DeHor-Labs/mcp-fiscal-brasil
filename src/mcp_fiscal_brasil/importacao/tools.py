"""
Lógica de negócio do módulo de cálculo de tributos de importação por NCM.

Cascata de cálculo (ordem obrigatória):
  1. VA  - Valor Aduaneiro (base, fornecido pelo usuário)
  2. II  - Imposto de Importação: base = VA, alíquota informada pelo usuário (TEC)
  3. IPI - Imposto sobre Produtos Industrializados: base = VA + II, alíquota do banco NCM
  4. PIS-Importação: base = VA, alíquota default 2,1% (Lei 10.865/2004, art. 1º)
  5. COFINS-Importação: base = VA, alíquota default 9,65% (Lei 10.865/2004, art. 1º)
  6. ICMS "por dentro" (grossed-up):
       carga_sem_icms = VA + II + IPI + PIS + COFINS
       ICMS = carga_sem_icms * aliq_icms / (1 - aliq_icms)
     Alíquota interna da UF importadora (tabela ICMS_ALIQUOTA_INTERNA).
  7. AFRMM - Adicional ao Frete para Renovação da Marinha Mercante (25% do frete marítimo).
     Aplica-se apenas ao modal marítimo. (Lei 10.893/2004, art. 4º)
  8. Siscomex - Taxa fixa de R$ 40,00 por declaração de importação (CAMEX).

DISCLAIMER: Antidumping, regimes especiais, acordos bilaterais, Drawback, ZFM/ALC,
benefícios fiscais estaduais específicos e alíquotas diferenciadas de PIS/COFINS
(ex: produtos farmacêuticos, máquinas, veículos) estão fora do escopo do MVP.
A alíquota II (TEC) não está disponível em fonte offline estruturada e deve ser
informada pelo usuário.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from mcp_fiscal_brasil._core import FiscalValidationError, get_logger
from mcp_fiscal_brasil.tabelas.loader import ICMS_ALIQUOTA_INTERNA, buscar_ncm

from .schemas import AliquotasImportacaoResponse, TributoItem, TributosImportacaoResponse

logger = get_logger(__name__)

# Alíquotas default de PIS/COFINS-Importação (Lei 10.865/2004, regime geral)
_DEFAULT_PIS_IMPORTACAO: float = 2.1
_DEFAULT_COFINS_IMPORTACAO: float = 9.65

# Alíquota AFRMM (Lei 10.893/2004, art. 4º)
_ALIQ_AFRMM: float = 25.0

# Taxa Siscomex: R$ 40,00 por declaração de importação (Portaria CAMEX 54/2022)
_TAXA_SISCOMEX: float = 40.0

# UFs válidas (mesmas do loader de ICMS)
_UFS_VALIDAS: frozenset[str] = frozenset(ICMS_ALIQUOTA_INTERNA.keys())

_MODAIS_VALIDOS: frozenset[str] = frozenset({"maritimo", "aereo", "terrestre", "postal"})

_DISCLAIMERS: list[str] = [
    (
        "DISCLAIMER: Os valores calculados são estimativas para planejamento fiscal e NÃO "
        "substituem o cálculo oficial pelo SISCOMEX nem a conferência por despachante aduaneiro "
        "ou contador especializado em comércio exterior."
    ),
    (
        "Antidumping, regimes especiais (ex.: Drawback, Recof), acordos bilaterais (Mercosul, "
        "ALADI), benefícios de ZFM/ALC e alíquotas diferenciadas de PIS/COFINS-importação "
        "(farmacêuticos, máquinas, veículos) estão fora do escopo deste simulador MVP."
    ),
    (
        "A alíquota II (TEC) deve ser verificada na Tarifa Aduaneira do Brasil vigente "
        "(www.mdic.gov.br). Regimes de ex-tarifário podem reduzi-la substancialmente."
    ),
]


def _ncm_limpo(ncm: str) -> str:
    """Remove pontuação e espaços do código NCM."""
    return ncm.replace(".", "").replace("-", "").strip()


def _validar_ncm_formato(ncm: str) -> str:
    """Valida e retorna o NCM limpo (8 dígitos)."""
    codigo = _ncm_limpo(ncm)
    if not codigo.isdigit() or len(codigo) != 8:
        raise FiscalValidationError(
            f"Formato de NCM inválido: '{ncm}'. Informe 8 dígitos numéricos "
            "(ex: '22030000' ou '2203.00.00').",
            field="ncm",
            value=ncm,
        )
    return codigo


def _validar_uf(uf: str, field: str = "uf_importador") -> str:
    """Valida e retorna a UF em maiúsculas."""
    uf_upper = uf.strip().upper()
    if uf_upper not in _UFS_VALIDAS:
        raise FiscalValidationError(
            f"UF inválida: '{uf}'. UFs válidas: {', '.join(sorted(_UFS_VALIDAS))}.",
            field=field,
            value=uf,
        )
    return uf_upper


def _calcular_icms_por_dentro(carga_sem_icms: float, aliquota_icms: float) -> float:
    """
    Calcula o ICMS "por dentro" (grossed-up) na importação.

    Na importação, o ICMS é calculado "por dentro": ele integra sua própria base.
    Fórmula: ICMS = carga_sem_icms * aliq / (1 - aliq)

    Args:
        carga_sem_icms: Soma de VA + II + IPI + PIS + COFINS.
        aliquota_icms: Alíquota interna da UF em percentual (ex: 18.0).

    Returns:
        Valor do ICMS em R$.
    """
    aliq = aliquota_icms / 100.0
    return round(carga_sem_icms * aliq / (1.0 - aliq), 2)


def _buscar_dados_ncm_sync(codigo: str) -> dict[str, Any] | None:
    """Wrapper síncrono para buscar NCM no banco SQLite."""
    return buscar_ncm(codigo)


async def consultar_aliquotas_importacao(ncm: str) -> AliquotasImportacaoResponse:
    """
    Consulta alíquotas de referência para importação por NCM (offline).

    Retorna a alíquota IPI do banco NCM/TIPI, os defaults de PIS/COFINS-importação
    e um aviso sobre a alíquota II (TEC), que não está disponível em fonte estruturada
    offline e deve ser informada pelo usuário.

    Args:
        ncm: Código NCM com 8 dígitos, com ou sem pontuação
             (ex: '22030000' ou '2203.00.00').

    Returns:
        AliquotasImportacaoResponse com alíquota IPI, defaults de PIS/COFINS e aviso sobre II.

    Raises:
        FiscalValidationError: Se o formato do NCM for inválido.
    """
    codigo = _validar_ncm_formato(ncm)
    logger.info("consultar_aliquotas_importacao", ncm=codigo)

    dado_ncm = await asyncio.to_thread(_buscar_dados_ncm_sync, codigo)

    avisos: list[str] = []
    aliquota_ipi: float | None = None
    descricao_ncm: str | None = None

    if dado_ncm is None:
        avisos.append(
            f"NCM '{codigo}' não encontrado no banco TIPI bundled. "
            "Execute scripts/build_tabelas_db.py para popular a tabela completa. "
            "A alíquota IPI não pôde ser determinada offline."
        )
    else:
        descricao_ncm = dado_ncm.get("descricao")
        aliquota_ipi = dado_ncm.get("aliquota_ipi")
        if aliquota_ipi is None:
            avisos.append(
                f"NCM '{codigo}' encontrado no banco mas sem alíquota IPI registrada. "
                "Pode ser posição genérica (capítulo/posição) ou produto com IPI = 0%. "
                "Verifique a TIPI vigente."
            )

    return AliquotasImportacaoResponse(
        ncm=codigo,
        descricao_ncm=descricao_ncm,
        aliquota_ipi=aliquota_ipi,
        aliquota_pis_importacao_default=_DEFAULT_PIS_IMPORTACAO,
        aliquota_cofins_importacao_default=_DEFAULT_COFINS_IMPORTACAO,
        aviso_aliquota_ii=(
            "A alíquota do II (Imposto de Importação / TEC) NÃO está disponível em fonte "
            "estruturada offline. Consulte a Tarifa Aduaneira do Brasil vigente em "
            "www.mdic.gov.br e informe aliquota_ii ao chamar calcular_tributos_importacao. "
            "Ex-tarifários podem reduzir substancialmente a alíquota TEC."
        ),
        avisos=avisos,
    )


async def calcular_tributos_importacao(
    ncm: str,
    valor_aduaneiro: float,
    uf_importador: str,
    aliquota_ii: float,
    modal: Literal["maritimo", "aereo", "terrestre", "postal"] = "maritimo",
    frete_maritimo: float = 0.0,
    aliquota_pis: float = _DEFAULT_PIS_IMPORTACAO,
    aliquota_cofins: float = _DEFAULT_COFINS_IMPORTACAO,
    aliquota_ipi_override: float | None = None,
) -> TributosImportacaoResponse:
    """
    Calcula os tributos de importação em cascata para um produto classificado por NCM.

    Ordem de cálculo:
      VA -> II -> IPI (base VA+II) -> PIS/COFINS-importação (base VA) ->
      ICMS "por dentro" (base VA+II+IPI+PIS+COFINS) -> AFRMM/Siscomex.

    DISCLAIMER: Os valores são estimativas para planejamento. Não substituem o
    cálculo oficial pelo SISCOMEX nem a conferência por despachante aduaneiro
    ou contador especializado. A alíquota II (TEC) deve ser informada pelo usuário
    conforme a Tarifa Aduaneira do Brasil vigente (www.mdic.gov.br).
    Antidumping, regimes especiais, acordos bilaterais e alíquotas diferenciadas
    de PIS/COFINS estão fora do escopo do MVP.

    Args:
        ncm: Código NCM com 8 dígitos (ex: '22030000' ou '2203.00.00').
        valor_aduaneiro: Valor Aduaneiro (VA) em R$. Deve ser positivo.
        uf_importador: Sigla da UF do importador para cálculo do ICMS (ex: 'SP').
        aliquota_ii: Alíquota do II (Imposto de Importação / TEC) em percentual
                     (ex: 20.0 para 20%). Deve ser >= 0. Informe conforme a TEC
                     vigente (www.mdic.gov.br). Antidumping NÃO incluído.
        modal: Modal de transporte. Valores: 'maritimo', 'aereo', 'terrestre',
               'postal'. Afeta o AFRMM (apenas modal marítimo). Padrão: 'maritimo'.
        frete_maritimo: Valor do frete marítimo em R$ (para cálculo do AFRMM).
                        Relevante apenas quando modal='maritimo'. Padrão: 0.0.
        aliquota_pis: Alíquota do PIS-Importação em % (padrão: 2,1%).
                      Use para PIS diferenciado (produtos específicos da Lei 10.865/2004).
                      AVISO: alíquotas diferenciadas exigem conferência com contador.
        aliquota_cofins: Alíquota do COFINS-Importação em % (padrão: 9,65%).
                         Use para COFINS diferenciado. AVISO: idem ao PIS.
        aliquota_ipi_override: Se informado, substitui a alíquota IPI do banco NCM.
                               Útil quando o NCM não está no banco ou para conferir
                               com a TIPI atualizada.

    Returns:
        TributosImportacaoResponse com breakdown por tributo, total e custo total.

    Raises:
        FiscalValidationError: Se NCM inválido, UF inválida, valor_aduaneiro <= 0,
                               alíquota negativa ou NCM não encontrado no banco.
    """
    # --- Validações de entrada ---
    codigo = _validar_ncm_formato(ncm)
    uf = _validar_uf(uf_importador)

    if valor_aduaneiro <= 0:
        raise FiscalValidationError(
            f"valor_aduaneiro deve ser positivo. Recebido: {valor_aduaneiro}.",
            field="valor_aduaneiro",
            value=str(valor_aduaneiro),
        )
    if aliquota_ii < 0:
        raise FiscalValidationError(
            f"aliquota_ii não pode ser negativa. Recebido: {aliquota_ii}.",
            field="aliquota_ii",
            value=str(aliquota_ii),
        )
    if aliquota_pis < 0:
        raise FiscalValidationError(
            f"aliquota_pis não pode ser negativa. Recebido: {aliquota_pis}.",
            field="aliquota_pis",
            value=str(aliquota_pis),
        )
    if aliquota_cofins < 0:
        raise FiscalValidationError(
            f"aliquota_cofins não pode ser negativa. Recebido: {aliquota_cofins}.",
            field="aliquota_cofins",
            value=str(aliquota_cofins),
        )
    modal_lower = modal.strip().lower()
    if modal_lower not in _MODAIS_VALIDOS:
        raise FiscalValidationError(
            f"Modal inválido: '{modal}'. Use: {', '.join(sorted(_MODAIS_VALIDOS))}.",
            field="modal",
            value=modal,
        )

    logger.info(
        "calcular_tributos_importacao",
        ncm=codigo,
        uf=uf,
        va=valor_aduaneiro,
        aliq_ii=aliquota_ii,
        modal=modal_lower,
    )

    # --- Busca NCM no banco ---
    dado_ncm = await asyncio.to_thread(_buscar_dados_ncm_sync, codigo)
    if dado_ncm is None:
        raise FiscalValidationError(
            f"NCM '{codigo}' não encontrado no banco TIPI bundled. "
            "Execute scripts/build_tabelas_db.py para popular a tabela completa, "
            "ou verifique se o NCM está correto.",
            field="ncm",
            value=ncm,
        )

    avisos: list[str] = []

    # --- Determina alíquota IPI ---
    aliq_ipi: float
    if aliquota_ipi_override is not None:
        aliq_ipi = aliquota_ipi_override
        avisos.append(
            f"Alíquota IPI informada manualmente ({aliq_ipi}%) sobrescreve o valor do banco NCM."
        )
    else:
        aliq_ipi_banco = dado_ncm.get("aliquota_ipi")
        if aliq_ipi_banco is None:
            aliq_ipi = 0.0
            avisos.append(
                f"Alíquota IPI não encontrada no banco para NCM '{codigo}'. "
                "Assumindo IPI = 0%. Verifique a TIPI vigente."
            )
        else:
            aliq_ipi = float(aliq_ipi_banco)

    # --- Alíquota ICMS interna da UF importadora ---
    aliq_icms = ICMS_ALIQUOTA_INTERNA[uf]

    # --- Aviso sobre PIS/COFINS diferenciados ---
    if aliquota_pis != _DEFAULT_PIS_IMPORTACAO or aliquota_cofins != _DEFAULT_COFINS_IMPORTACAO:
        avisos.append(
            "Alíquotas de PIS/COFINS-importação customizadas informadas. "
            "Alíquotas diferenciadas dependem da classificação do produto na Lei 10.865/2004. "
            "Confirme com contador especializado em comércio exterior."
        )
    else:
        avisos.append(
            f"PIS-Importação {aliquota_pis}% e COFINS-Importação {aliquota_cofins}% "
            "são alíquotas-padrão da Lei 10.865/2004 (regime geral). Produtos farmacêuticos, "
            "máquinas, veículos e alimentos podem ter alíquotas diferenciadas."
        )

    # -------------------------------------------------------------------------
    # Cálculo em cascata
    # -------------------------------------------------------------------------

    # 1. Valor Aduaneiro (VA) - base raiz
    va = round(valor_aduaneiro, 2)

    # 2. II - Imposto de Importação
    valor_ii = round(va * aliquota_ii / 100.0, 2)
    item_ii = TributoItem(
        nome="II",
        base_calculo=va,
        aliquota=aliquota_ii,
        valor=valor_ii,
        fundamento=(
            "Decreto-Lei 37/1966 e Decreto 6.759/2009 (Reg. Aduaneiro). "
            "Alíquota TEC informada pelo usuário (www.mdic.gov.br)."
        ),
    )

    # 3. IPI - Imposto sobre Produtos Industrializados (base = VA + II)
    base_ipi = round(va + valor_ii, 2)
    valor_ipi = round(base_ipi * aliq_ipi / 100.0, 2)
    item_ipi = TributoItem(
        nome="IPI",
        base_calculo=base_ipi,
        aliquota=aliq_ipi,
        valor=valor_ipi,
        fundamento=(
            "Lei 4.502/1964, Decreto 7.212/2010 (RIPI). "
            "Base = VA + II. Alíquota da TIPI (banco NCM bundled)."
        ),
    )

    # 4. PIS-Importação (base = VA)
    valor_pis = round(va * aliquota_pis / 100.0, 2)
    item_pis = TributoItem(
        nome="PIS-Importação",
        base_calculo=va,
        aliquota=aliquota_pis,
        valor=valor_pis,
        fundamento=(
            "Lei 10.865/2004, art. 1º. Base = VA. "
            "Alíquota padrão 2,1% (regime geral); pode haver alíquotas diferenciadas."
        ),
    )

    # 5. COFINS-Importação (base = VA)
    valor_cofins = round(va * aliquota_cofins / 100.0, 2)
    item_cofins = TributoItem(
        nome="COFINS-Importação",
        base_calculo=va,
        aliquota=aliquota_cofins,
        valor=valor_cofins,
        fundamento=(
            "Lei 10.865/2004, art. 1º. Base = VA. "
            "Alíquota padrão 9,65% (regime geral); pode haver alíquotas diferenciadas."
        ),
    )

    # 6. ICMS "por dentro" (grossed-up)
    # Base = VA + II + IPI + PIS + COFINS (antes do ICMS, pois ele integra a própria base)
    carga_sem_icms = round(va + valor_ii + valor_ipi + valor_pis + valor_cofins, 2)
    valor_icms = _calcular_icms_por_dentro(carga_sem_icms, aliq_icms)
    item_icms = TributoItem(
        nome="ICMS",
        base_calculo=carga_sem_icms,
        aliquota=aliq_icms,
        valor=valor_icms,
        fundamento=(
            f"RICMS/{uf} (alíquota interna {aliq_icms}%). "
            "Cálculo 'por dentro': ICMS = (VA+II+IPI+PIS+COFINS) * aliq / (1-aliq). "
            "Base: Convênio ICMS 87/2002 e Res. Senado Federal 13/2012."
        ),
    )

    # 7. AFRMM - Adicional ao Frete para Renovação da Marinha Mercante
    valor_afrmm = 0.0
    if modal_lower == "maritimo" and frete_maritimo > 0:
        valor_afrmm = round(frete_maritimo * _ALIQ_AFRMM / 100.0, 2)
    item_afrmm = TributoItem(
        nome="AFRMM",
        base_calculo=frete_maritimo if modal_lower == "maritimo" else 0.0,
        aliquota=_ALIQ_AFRMM if modal_lower == "maritimo" else 0.0,
        valor=valor_afrmm,
        fundamento=(
            "Lei 10.893/2004, art. 4º. Alíquota 25% sobre o frete marítimo. "
            "Aplica-se apenas ao modal marítimo."
        ),
    )

    # 8. Taxa Siscomex (taxa fixa por declaração de importação)
    item_siscomex = TributoItem(
        nome="Siscomex",
        base_calculo=1.0,
        aliquota=0.0,
        valor=_TAXA_SISCOMEX,
        fundamento=(
            "Portaria CAMEX 54/2022. Taxa fixa de R$ 40,00 por declaração de importação. "
            "Valor estimado; varia por adição/produto na DI."
        ),
    )

    # --- Consolidação ---
    breakdown: list[TributoItem] = [
        item_ii,
        item_ipi,
        item_pis,
        item_cofins,
        item_icms,
        item_afrmm,
        item_siscomex,
    ]

    total_tributos = round(sum(item.valor for item in breakdown), 2)
    custo_total = round(va + total_tributos, 2)

    return TributosImportacaoResponse(
        ncm=codigo,
        modal=modal_lower,
        valor_aduaneiro=va,
        breakdown=breakdown,
        total_tributos=total_tributos,
        custo_total=custo_total,
        avisos=avisos,
        disclaimers=_DISCLAIMERS,
    )
