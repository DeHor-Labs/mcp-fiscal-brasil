"""
Consulta real de status operacional das SEFAZ via NfeStatusServico4.

Cada UF delega a autorizacao de NF-e a um de tres grupos de webservice:
- Estado com estrutura propria (AM, BA, GO, MG, MS, MT, PE, PR, RS, SP).
- SVRS (Sefaz Virtual do Rio Grande do Sul): AC, AL, AP, CE, DF, ES, PA, PB,
  PI, RJ, RN, RO, RR, SC, SE, TO.
- SVAN (Sefaz Virtual do Ambiente Nacional): MA.

Fonte dos endpoints: config publica mantida pelo projeto sped-nfe
(nfephp-org/sped-nfe, storage/wsnfe_4.00_mod55.xml), conferida URL por URL
contra o arquivo atual do repositorio antes de aceitar. Uma divergencia real
foi corrigida durante essa conferencia: RS tem webservice proprio
(nfe.sefazrs.rs.gov.br), distinto do SVRS (nfe.svrs.rs.gov.br, que RS opera
para OUTRAS UFs sem infraestrutura propria) - RS nao deve ser tratado como
membro do grupo SVRS. Todas as chamadas exigem mTLS com certificado A1 (nao
ha consulta de status sem certificado - e uma exigencia da camada de
transporte dos webservices SEFAZ, nao apenas de operacoes que gravam dados).
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from lxml import etree

from .._core.errors import (
    FiscalConfigurationError,
    FiscalHTTPError,
    FiscalValidationError,
)
from .._core.logging import get_logger
from ..shared.constants import UF_CODES
from ._soap_mtls import carregar_pkcs12, criar_ssl_context_em_memoria
from ._soap_mtls import enviar_soap as _enviar_soap_mtls

logger = get_logger(__name__)

Ambiente = Literal["producao", "homologacao"]

_NS_NFE = "http://www.portalfiscal.inf.br/nfe"

# Endpoints NfeStatusServico4 por grupo autorizador (producao, homologacao).
# Conferidos contra nfephp-org/sped-nfe (storage/wsnfe_4.00_mod55.xml) em 2026-07-18.
_ENDPOINTS_GRUPO: dict[str, dict[Ambiente, str]] = {
    "AM": {
        "producao": "https://nfe.sefaz.am.gov.br/services2/services/NfeStatusServico4",
        "homologacao": "https://homnfe.sefaz.am.gov.br/services2/services/NfeStatusServico4",
    },
    "BA": {
        "producao": "https://nfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
        "homologacao": "https://hnfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
    },
    "GO": {
        "producao": "https://nfe.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
        "homologacao": "https://homolog.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
    },
    "MG": {
        "producao": "https://nfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
        "homologacao": "https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
    },
    "MS": {
        "producao": "https://nfe.sefaz.ms.gov.br/ws/NFeStatusServico4",
        "homologacao": "https://hom.nfe.sefaz.ms.gov.br/ws/NFeStatusServico4",
    },
    "MT": {
        "producao": "https://nfe.sefaz.mt.gov.br/nfews/v2/services/NfeStatusServico4",
        "homologacao": "https://homologacao.sefaz.mt.gov.br/nfews/v2/services/NfeStatusServico4",
    },
    "PE": {
        "producao": "https://nfe.sefaz.pe.gov.br/nfe-service/services/NFeStatusServico4",
        "homologacao": "https://nfehomolog.sefaz.pe.gov.br/nfe-service/services/NFeStatusServico4",
    },
    "PR": {
        "producao": "https://nfe.sefa.pr.gov.br/nfe/NFeStatusServico4",
        "homologacao": "https://homologacao.nfe.sefa.pr.gov.br/nfe/NFeStatusServico4",
    },
    # RS tem webservice proprio (dominio sefazrs.rs.gov.br), diferente do SVRS
    # (dominio svrs.rs.gov.br) que RS opera em nome de outras UFs.
    "RS": {
        "producao": "https://nfe.sefazrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        "homologacao": "https://nfe-homologacao.sefazrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
    },
    "SP": {
        "producao": "https://nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        "homologacao": "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
    },
    "SVRS": {
        "producao": "https://nfe.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
        "homologacao": "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NfeStatusServico4.asmx",
    },
    "SVAN": {
        "producao": "https://www.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        "homologacao": "https://hom.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
    },
}

# UF -> grupo autorizador. UFs ausentes daqui usam sua propria sigla como grupo
# (ou seja, tem estrutura propria - ver _ENDPOINTS_GRUPO).
_UF_PARA_GRUPO: dict[str, str] = {
    "MA": "SVAN",
    "AC": "SVRS",
    "AL": "SVRS",
    "AP": "SVRS",
    "CE": "SVRS",
    "DF": "SVRS",
    "ES": "SVRS",
    "PA": "SVRS",
    "PB": "SVRS",
    "PI": "SVRS",
    "RJ": "SVRS",
    "RN": "SVRS",
    "RO": "SVRS",
    "RR": "SVRS",
    "SC": "SVRS",
    "SE": "SVRS",
    "TO": "SVRS",
}

# cStat de retorno da consulta de status (Manual de Orientacao do Contribuinte NFe).
_CSTAT_OPERACIONAL = 107
_CSTAT_INSTAVEL = 108
_CSTAT_INDISPONIVEL = 109


def _endpoint_para_uf(uf: str, ambiente: Ambiente) -> str:
    grupo = _UF_PARA_GRUPO.get(uf, uf)
    endpoints = _ENDPOINTS_GRUPO.get(grupo)
    if endpoints is None:
        # UF invalida e um erro de input do chamador, nao uma falta de
        # configuracao do servidor - por isso FiscalValidationError, nao
        # FiscalConfigurationError (reservada a certificado A1 ausente).
        raise FiscalValidationError(
            message=f"Nenhum endpoint NfeStatusServico4 mapeado para UF '{uf}' (grupo '{grupo}').",
            field="uf",
            value=uf,
        )
    return endpoints[ambiente]


@lru_cache(maxsize=1)
def _obter_ssl_context(caminho_certificado: str, senha: str) -> ssl.SSLContext:
    """Monta (e cacheia) o SSLContext do certificado A1 para a vida do processo.

    lru_cache evita recarregar o .pfx do disco a cada UF consultada (uma
    varredura completa consulta ~11 endpoints distintos). Cache por processo:
    um certificado novo exige reiniciar o servico (ou chamar
    ``_obter_ssl_context.cache_clear()`` em testes).
    """
    chave_pem, cert_pem, chain_pem = carregar_pkcs12(caminho_certificado, senha)
    return criar_ssl_context_em_memoria(chave_pem, cert_pem, chain_pem)


def _montar_body(uf: str, ambiente: Ambiente) -> str:
    tp_amb = "1" if ambiente == "producao" else "2"
    cod_uf = UF_CODES.get(uf)
    if cod_uf is None:
        # SVRS/SVAN sao grupos de webservice (_endpoint_para_uf), nao UFs -
        # cUF no XML sempre exige a UF real solicitante, nunca o grupo.
        raise FiscalValidationError(
            message=f"UF '{uf}' nao possui codigo IBGE mapeado para consulta de status.",
            field="uf",
            value=uf,
        )
    return (
        f'<consStatServ versao="4.00" xmlns="{_NS_NFE}">'
        f"<tpAmb>{tp_amb}</tpAmb>"
        f"<cUF>{cod_uf}</cUF>"
        "<xServ>STATUS</xServ>"
        "</consStatServ>"
    )


def _texto(root: etree._Element, tag: str) -> str | None:
    el = root.find(f"{{{_NS_NFE}}}{tag}")
    return el.text if el is not None else None


@dataclass(frozen=True)
class StatusSefazReal:
    """Resultado de uma consulta real de status a um webservice SEFAZ."""

    uf: str
    status: Literal["OPERACIONAL", "INSTAVEL", "INDISPONIVEL"]
    codigo: int | None
    descricao: str | None
    data_recebimento: str | None
    tempo_medio_ms: str | None


async def consultar_status_real(
    uf: str,
    caminho_certificado: str,
    senha: str,
    ambiente: Ambiente = "producao",
    timeout: float = 15.0,
) -> StatusSefazReal:
    """
    Consulta o status real do webservice SEFAZ de uma UF via NfeStatusServico4.

    Requer certificado digital A1 configurado (mTLS e exigencia de transporte
    de todos os webservices SEFAZ, incluindo consulta de status).

    Raises:
        FiscalConfigurationError: certificado digital A1 nao configurado.
        FiscalValidationError: UF sem endpoint mapeado, ou certificado invalido
            (senha errada, arquivo corrompido).
        FiscalHTTPError: falha de rede ou cStat de rejeicao inesperado.
    """
    if not caminho_certificado or not senha:
        raise FiscalConfigurationError(
            message=(
                "Certificado digital A1 nao configurado (NFE_CERTIFICADO_PATH / "
                "NFE_CERTIFICADO_SENHA). Consulta de status SEFAZ exige certificado."
            )
        )

    endpoint = _endpoint_para_uf(uf, ambiente)
    # _obter_ssl_context e sincrono (carrega .pfx do disco + monta SSLContext);
    # roda em thread separada para nao bloquear o event loop na primeira
    # chamada por processo (lru_cache evita repetir o custo nas seguintes).
    ssl_ctx = await asyncio.to_thread(_obter_ssl_context, caminho_certificado, senha)
    body_content = _montar_body(uf, ambiente)

    logger.info("sefaz_status_real_started", uf=uf, ambiente=ambiente, endpoint=endpoint)

    body_el = await _enviar_soap_mtls(
        endpoint, body_content, ssl_ctx, namespace=_NS_NFE, timeout=timeout
    )

    cstat_raw = _texto(body_el, "cStat")
    if cstat_raw is None:
        raise FiscalHTTPError(
            message="Resposta da SEFAZ sem cStat.",
            status_code=200,
            url=endpoint,
        )

    cstat = int(cstat_raw)
    xmotivo = _texto(body_el, "xMotivo")
    dh_recbto = _texto(body_el, "dhRecbto")
    t_med = _texto(body_el, "tMed")

    if cstat == _CSTAT_OPERACIONAL:
        status: Literal["OPERACIONAL", "INSTAVEL", "INDISPONIVEL"] = "OPERACIONAL"
    elif cstat == _CSTAT_INSTAVEL:
        status = "INSTAVEL"
    elif cstat == _CSTAT_INDISPONIVEL:
        status = "INDISPONIVEL"
    else:
        raise FiscalHTTPError(
            message=f"SEFAZ retornou cStat inesperado para consulta de status: {cstat} ({xmotivo}).",
            status_code=200,
            url=endpoint,
            detail={"cStat": cstat, "xMotivo": xmotivo},
        )

    return StatusSefazReal(
        uf=uf,
        status=status,
        codigo=cstat,
        descricao=xmotivo,
        data_recebimento=dh_recbto,
        tempo_medio_ms=t_med,
    )


@dataclass(frozen=True)
class StatusCertificado:
    """Estado do certificado digital A1 configurado no servidor fiscal."""

    configurado: bool
    ambiente: str
    cnpj: str | None = None
    titular: str | None = None
    validade_fim: datetime | None = None
    valido: bool | None = None
    erro: str | None = None


def obter_status_certificado(
    caminho_certificado: str,
    senha: str,
    ambiente: str,
) -> StatusCertificado:
    """
    Retorna metadados do certificado A1 configurado, sem expor a chave privada.

    Usado pelo endpoint GET /v1/fiscal/certificado/status: o chamador so ve
    "configurado / titular / validade", nunca o arquivo ou a senha.
    """
    if not caminho_certificado or not senha:
        return StatusCertificado(configurado=False, ambiente=ambiente)

    from cryptography import x509

    from .assinatura import _extrair_cn, _extrair_cnpj_cpf

    try:
        _, cert_pem, _ = carregar_pkcs12(caminho_certificado, senha)
        cert = x509.load_pem_x509_certificate(cert_pem)
    except Exception as exc:
        logger.warning(
            "certificado_status_load_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return StatusCertificado(configurado=True, ambiente=ambiente, erro=str(exc))

    cn = _extrair_cn(cert)
    cnpj = _extrair_cnpj_cpf(cn)

    try:
        validade_fim: datetime | None = cert.not_valid_after_utc
    except AttributeError:
        try:
            validade_fim = cert.not_valid_after
        except Exception as exc:
            logger.warning("certificado_not_valid_after_indisponivel", error=str(exc))
            validade_fim = None

    valido: bool | None = None
    if validade_fim is not None:
        if validade_fim.tzinfo is None:
            validade_fim = validade_fim.replace(tzinfo=timezone.utc)
        valido = validade_fim > datetime.now(timezone.utc)

    return StatusCertificado(
        configurado=True,
        ambiente=ambiente,
        cnpj=cnpj,
        titular=cn,
        validade_fim=validade_fim,
        valido=valido,
    )


__all__ = [
    "StatusCertificado",
    "StatusSefazReal",
    "consultar_status_real",
    "obter_status_certificado",
]
