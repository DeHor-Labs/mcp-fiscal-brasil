"""Ferramentas de negócio do módulo tabelas fiscais."""

import asyncio

from mcp_fiscal_brasil._core import FiscalValidationError, get_logger

from .loader import (
    ICMS_ALIQUOTA_INTERNA,
    buscar_aliquota_icms,
    buscar_cest,
    buscar_cfop,
    buscar_ncm,
    validar_cst,
)
from .schemas import (
    CESTResponse,
    CFOPResponse,
    CSTResponse,
    ICMSAliquotaResponse,
    NCMResponse,
)

logger = get_logger(__name__)

_UFS_VALIDAS = set(ICMS_ALIQUOTA_INTERNA.keys())


def _ncm_limpo(ncm: str) -> str:
    return ncm.replace(".", "").replace("-", "").strip()


async def consultar_ncm(ncm: str) -> NCMResponse:
    """
    Consulta os dados de um código NCM (offline).

    Args:
        ncm: Código NCM com 8 dígitos, com ou sem pontuação
             (ex: '8471.30.19' ou '84713019').

    Returns:
        NCMResponse com código, descrição, alíquota IPI e unidade tributável.

    Raises:
        FiscalValidationError: Se o formato do NCM for inválido.
        FiscalValidationError: Se o NCM não for encontrado na tabela.
    """
    codigo_limpo = _ncm_limpo(ncm)
    if not codigo_limpo.isdigit() or len(codigo_limpo) != 8:
        raise FiscalValidationError(
            f"Formato de NCM inválido: '{ncm}'. Informe 8 dígitos numéricos "
            "(ex: '84713019' ou '8471.30.19').",
            field="ncm",
            value=ncm,
        )

    logger.info("ncm_lookup", ncm=codigo_limpo)
    dado = await asyncio.to_thread(buscar_ncm, codigo_limpo)

    if dado is None:
        raise FiscalValidationError(
            f"NCM '{codigo_limpo}' não encontrado. "
            "O banco NCM pode estar incompleto; execute scripts/build_tabelas_db.py "
            "para popular a tabela TIPI completa.",
            field="ncm",
            value=ncm,
        )

    return NCMResponse(
        codigo=dado["codigo"],
        descricao=dado["descricao"],
        aliquota_ipi=dado.get("aliquota_ipi"),
        unidade_tributavel=dado.get("unidade_tributavel"),
        ex_tipi=dado.get("ex_tipi"),
        capitulo=dado["codigo"][:2],
        posicao=dado["codigo"][:4],
    )


async def consultar_cfop(cfop: str) -> CFOPResponse:
    """
    Consulta os dados de um código CFOP (offline).

    Args:
        cfop: Código CFOP com 4 dígitos (ex: '5102' ou '6.102').

    Returns:
        CFOPResponse com código, descrição, tipo (entrada/saída) e aplicação.

    Raises:
        FiscalValidationError: Se o CFOP for inválido ou não encontrado.
    """
    codigo_norm = cfop.replace(".", "").strip()
    if not codigo_norm.isdigit() or len(codigo_norm) != 4:
        raise FiscalValidationError(
            f"Formato de CFOP inválido: '{cfop}'. Informe 4 dígitos numéricos "
            "(ex: '5102' ou '6102').",
            field="cfop",
            value=cfop,
        )

    logger.info("cfop_lookup", cfop=codigo_norm)
    dado = buscar_cfop(codigo_norm)

    if dado is None:
        raise FiscalValidationError(
            f"CFOP '{codigo_norm}' não encontrado na tabela. "
            "Verifique o código conforme o Convênio SINIEF.",
            field="cfop",
            value=cfop,
        )

    return CFOPResponse(
        codigo=dado["codigo"],
        descricao=dado["descricao"],
        tipo=dado["tipo"],
        aplicacao=dado["aplicacao"],
        grupo=dado["grupo"],
    )


async def validar_cst_tool(cst: str, regime: str) -> CSTResponse:
    """
    Valida um código CST ou CSOSN conforme o regime tributário (offline).

    Args:
        cst: Código CST (3 dígitos para ICMS, 2 dígitos para PIS/COFINS/IPI)
             ou CSOSN (3 dígitos) para o Simples Nacional (ex: '000', '101', '50').
        regime: Regime tributário: 'normal' (Lucro Real ou Presumido)
                ou 'simples' (Simples Nacional).

    Returns:
        CSTResponse com valido, descricao, regime e tabela de origem.

    Raises:
        FiscalValidationError: Se o regime informado for inválido.
    """
    regime_lower = regime.strip().lower()
    if regime_lower not in ("normal", "simples"):
        raise FiscalValidationError(
            f"Regime tributário inválido: '{regime}'. "
            "Use 'normal' (Lucro Real/Presumido) ou 'simples' (Simples Nacional).",
            field="regime",
            value=regime,
        )

    logger.info("cst_validation", cst=cst, regime=regime_lower)
    resultado = validar_cst(cst, regime_lower)

    return CSTResponse(
        cst=resultado["cst"],
        valido=resultado["valido"],
        descricao=resultado.get("descricao"),
        regime=resultado["regime"],
        tabela=resultado.get("tabela"),
    )


async def consultar_cest(cest: str) -> CESTResponse:
    """
    Consulta os dados de um código CEST (offline).

    Args:
        cest: Código CEST com 7 dígitos, com ou sem pontuação
              (ex: '01.007.00' ou '0100700').

    Returns:
        CESTResponse com código, descrição, segmento e NCMs relacionados.

    Raises:
        FiscalValidationError: Se o formato do CEST for inválido.
        FiscalValidationError: Se o CEST não for encontrado na tabela.
    """
    codigo_limpo = cest.replace(".", "").strip()
    if not codigo_limpo.isdigit() or len(codigo_limpo) != 7:
        raise FiscalValidationError(
            f"Formato de CEST inválido: '{cest}'. Informe 7 dígitos numéricos "
            "(ex: '0100700' ou '01.007.00').",
            field="cest",
            value=cest,
        )

    logger.info("cest_lookup", cest=codigo_limpo)
    dado = await asyncio.to_thread(buscar_cest, codigo_limpo)

    if dado is None:
        raise FiscalValidationError(
            f"CEST '{codigo_limpo}' não encontrado. "
            "O banco CEST pode estar incompleto; execute scripts/build_tabelas_db.py "
            "para popular a tabela completa (Convênio ICMS 92/2015).",
            field="cest",
            value=cest,
        )

    return CESTResponse(
        cest=dado["cest"],
        descricao=dado["descricao"],
        segmento=dado["cest"][:2],
        ncm_relacionados=dado.get("ncm_relacionados", []),
    )


async def consultar_aliquota_icms(uf_origem: str, uf_destino: str) -> ICMSAliquotaResponse:
    """
    Consulta as alíquotas do ICMS para uma operação interestadual (offline).

    Retorna a alíquota interestadual (7% ou 12% conforme Resolução SF 22/2008),
    a alíquota interna do estado de destino e o diferencial de alíquota (DIFAL),
    conforme EC 87/2015.

    NOTA: Não cobre a alíquota de 4% aplicável a bens importados
    (Resolução SF 13/2012). Para operações com mercadorias importadas,
    a alíquota interestadual é sempre 4%.

    Args:
        uf_origem: Sigla da UF de origem da operação (ex: 'SP', 'MG').
        uf_destino: Sigla da UF de destino da operação (ex: 'RJ', 'GO').

    Returns:
        ICMSAliquotaResponse com alíquotas e fundamento legal.

    Raises:
        FiscalValidationError: Se alguma UF for inválida.
    """
    uf_o = uf_origem.strip().upper()
    uf_d = uf_destino.strip().upper()

    if uf_o not in _UFS_VALIDAS:
        raise FiscalValidationError(
            f"UF de origem inválida: '{uf_origem}'. "
            f"UFs válidas: {', '.join(sorted(_UFS_VALIDAS))}.",
            field="uf_origem",
            value=uf_origem,
        )
    if uf_d not in _UFS_VALIDAS:
        raise FiscalValidationError(
            f"UF de destino inválida: '{uf_destino}'. "
            f"UFs válidas: {', '.join(sorted(_UFS_VALIDAS))}.",
            field="uf_destino",
            value=uf_destino,
        )

    logger.info("icms_aliquota_lookup", uf_origem=uf_o, uf_destino=uf_d)
    dado = buscar_aliquota_icms(uf_o, uf_d)

    if dado is None:
        raise FiscalValidationError(
            f"Não foi possível calcular a alíquota para {uf_o} -> {uf_d}.",
            field="uf_origem",
            value=uf_origem,
        )

    return ICMSAliquotaResponse(
        uf_origem=dado["uf_origem"],
        uf_destino=dado["uf_destino"],
        aliquota_interestadual=dado["aliquota_interestadual"],
        aliquota_interna_destino=dado["aliquota_interna_destino"],
        diferencial_aliquota=dado["diferencial_aliquota"],
        fundamento=dado["fundamento"],
    )
