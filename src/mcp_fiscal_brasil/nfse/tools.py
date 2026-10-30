"""Ferramentas MCP para NFSe."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from mcp_fiscal_brasil.nfse.client import NFSeNacionalClient, NFSeNacionalUnavailableError
from mcp_fiscal_brasil.shared import notaas as notaas_provider
from mcp_fiscal_brasil.shared.validators import (
    format_chave_nfse,
    normalizar_chave_nfse,
    normalizar_cnpj,
    validate_chave_nfse,
    validate_cnpj_qualquer,
)

logger = logging.getLogger(__name__)

# Portais de consulta por município/sistema (50+ capitais e grandes cidades)
# Formato: "CIDADE/UF": {"portal": "url", "sistema": "tipo_sistema"}
PORTAIS_CONHECIDOS: dict[str, dict[str, str]] = {
    # Capitais Estaduais
    "SAO PAULO/SP": {
        "portal": "https://nfe.prefeitura.sp.gov.br/contribuinte/notasfiscais.aspx",
        "sistema": "ABRASF",
    },
    "RIO DE JANEIRO/RJ": {
        "portal": "https://notacarioca.rio.gov.br/",
        "sistema": "Nota Carioca",
    },
    "BELO HORIZONTE/MG": {"portal": "https://bhiss.pbh.gov.br/nfse/", "sistema": "BHISS"},
    "CURITIBA/PR": {
        "portal": "https://nfse.curitiba.pr.gov.br/",
        "sistema": "Curitiba Proprietary",
    },
    "PORTO ALEGRE/RS": {"portal": "https://nfse.portoalegre.rs.gov.br/", "sistema": "ABRASF"},
    "SALVADOR/BA": {"portal": "https://nfse.salvador.ba.gov.br/", "sistema": "ABRASF"},
    "FORTALEZA/CE": {"portal": "https://www.sefin.fortaleza.ce.gov.br/", "sistema": "ABRASF"},
    "BRASILIA/DF": {"portal": "https://www.nfse.df.gov.br/", "sistema": "ABRASF Nacional"},
    "MANAUS/AM": {"portal": "https://nota.manaus.am.gov.br/", "sistema": "ABRASF Nacional"},
    "RECIFE/PE": {"portal": "https://nfse.recife.pe.gov.br/", "sistema": "ABRASF"},
    "BELEM/PA": {"portal": "https://nfse.belem.pa.gov.br/", "sistema": "ABRASF"},
    "GOIANIA/GO": {"portal": "https://nfse.goiania.go.gov.br/", "sistema": "ABRASF"},
    "SAO LUIS/MA": {"portal": "https://nfse.saoluis.ma.gov.br/", "sistema": "ABRASF"},
    "MACEIO/AL": {"portal": "https://nfse.maceio.al.gov.br/", "sistema": "ISS.net"},
    "CAMPO GRANDE/MS": {"portal": "https://nfse.campogrande.ms.gov.br/", "sistema": "ABRASF"},
    "TERESINA/PI": {"portal": "https://nfse.teresina.pi.gov.br/", "sistema": "ABRASF"},
    "JOAO PESSOA/PB": {"portal": "https://nfse.joaopessoa.pb.gov.br/", "sistema": "ABRASF"},
    "NATAL/RN": {"portal": "https://nfse.natal.rn.gov.br/", "sistema": "ABRASF"},
    "CUIABA/MT": {"portal": "https://nfse.cuiaba.mt.gov.br/", "sistema": "ABRASF"},
    "ARACAJU/SE": {"portal": "https://nfse.aracaju.se.gov.br/", "sistema": "ABRASF"},
    "FLORIANOPOLIS/SC": {
        "portal": "https://nfse.florianopolis.sc.gov.br/",
        "sistema": "ISS.net",
    },
    "VITORIA/ES": {"portal": "https://nfse.vitoria.es.gov.br/", "sistema": "ABRASF"},
    "PORTO VELHO/RO": {"portal": "https://nfse.portovelho.ro.gov.br/", "sistema": "ABRASF"},
    "MACAPA/AP": {"portal": "https://nfse.macapa.ap.gov.br/", "sistema": "ABRASF"},
    "BOA VISTA/RR": {"portal": "https://nfse.boavista.rr.gov.br/", "sistema": "ABRASF"},
    "PALMAS/TO": {"portal": "https://nfse.palmas.to.gov.br/", "sistema": "ABRASF"},
    "RIO BRANCO/AC": {"portal": "https://nfse.riobranco.ac.gov.br/", "sistema": "ABRASF"},
    # Grandes Cidades São Paulo
    "GUARULHOS/SP": {"portal": "https://nfse.guarulhos.sp.gov.br/", "sistema": "ABRASF"},
    "CAMPINAS/SP": {
        "portal": "https://novanfse.campinas.sp.gov.br/",
        "sistema": "Campinas Sistema",
    },
    "SANTOS/SP": {"portal": "https://nfse.santos.sp.gov.br/", "sistema": "ABRASF"},
    "OSASCO/SP": {
        "portal": "https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/Default.aspx",
        "sistema": "ISS.net",
    },
    "SAO BERNARDO DO CAMPO/SP": {"portal": "https://nfse.sbc.sp.gov.br/", "sistema": "ABRASF"},
    "SANTO ANDRE/SP": {"portal": "https://nfse.santoandre.sp.gov.br/", "sistema": "ABRASF"},
    "SOROCABA/SP": {"portal": "https://nfse.sorocaba.sp.gov.br/", "sistema": "ABRASF"},
    "RIBEIRAO PRETO/SP": {
        "portal": "https://nfse.ribeiraopreto.sp.gov.br/",
        "sistema": "ABRASF",
    },
    "JUNDIAI/SP": {"portal": "https://nfse.jundiai.sp.gov.br/", "sistema": "ABRASF"},
    # Grandes Cidades Rio de Janeiro
    "NITEROI/RJ": {"portal": "https://nfse.niteroi.rj.gov.br/", "sistema": "ABRASF Nacional"},
    "DUQUE DE CAXIAS/RJ": {
        "portal": "https://portalcontribuinte.duquedecaxias.rj.gov.br/nfse",
        "sistema": "ABRASF 2.04",
    },
    "NOVA IGUACU/RJ": {"portal": "https://nfse.novaiguacu.rj.gov.br/", "sistema": "ABRASF"},
    # Grandes Cidades Minas Gerais
    "CONTAGEM/MG": {"portal": "https://nfse.contagem.mg.gov.br/", "sistema": "ABRASF"},
    "BETIM/MG": {"portal": "https://nfse.betim.mg.gov.br/", "sistema": "ABRASF"},
    "UBERLANDIA/MG": {"portal": "https://nfse.uberlandia.mg.gov.br/", "sistema": "ABRASF"},
    "JUIZ DE FORA/MG": {"portal": "https://nfse.juizdefora.mg.gov.br/", "sistema": "ABRASF"},
    # Cidades de Santa Catarina
    "JOINVILLE/SC": {"portal": "https://nfse.joinville.sc.gov.br/", "sistema": "ISS.net"},
    "BLUMENAU/SC": {"portal": "https://nfse.blumenau.sc.gov.br/", "sistema": "Simpliss"},
    # Cidades do Paraná
    "LONDRINA/PR": {"portal": "https://nfse.londrina.pr.gov.br/", "sistema": "ABRASF"},
    "MARINGA/PR": {"portal": "https://nfse.maringa.pr.gov.br/", "sistema": "ABRASF"},
    # Cidades do Rio Grande do Sul
    "CANOAS/RS": {"portal": "https://nfse.canoas.rs.gov.br/", "sistema": "ABRASF"},
    "CAXIAS DO SUL/RS": {"portal": "https://nfse.caxiasdosul.rs.gov.br/", "sistema": "ABRASF"},
    # Cidades da Bahia
    "FEIRA DE SANTANA/BA": {
        "portal": "https://nfse.feirasantana.ba.gov.br/",
        "sistema": "ABRASF",
    },
    "ILHEUS/BA": {"portal": "https://nfse.ilheus.ba.gov.br/", "sistema": "ABRASF"},
    # Cidades do Ceará
    "CAUCAIA/CE": {"portal": "https://nfse.caucaia.ce.gov.br/", "sistema": "ABRASF"},
    "JUAZEIRO DO NORTE/CE": {
        "portal": "https://nfse.juazeirodOnorte.ce.gov.br/",
        "sistema": "ABRASF",
    },
    # Cidades de Pernambuco
    "JABOATAO DOS GUARARAPES/PE": {
        "portal": "https://nfse.jaboatao.pe.gov.br/",
        "sistema": "ABRASF",
    },
    "CARUARU/PE": {"portal": "https://nfse.caruaru.pe.gov.br/", "sistema": "ABRASF"},
    # Cidades da Paraíba
    "CAMPINA GRANDE/PB": {
        "portal": "https://nfse.campinagrande.pb.gov.br/",
        "sistema": "ABRASF",
    },
    # Cidades do Rio Grande do Norte
    "PARNAMIRIM/RN": {"portal": "https://nfse.parnamirim.rn.gov.br/", "sistema": "ABRASF"},
    # Cidades de Alagoas
    "RIO LARGO/AL": {"portal": "https://nfse.riolargo.al.gov.br/", "sistema": "ISS.net"},
    # Cidades do Piauí
    "PICOS/PI": {"portal": "https://nfse.picos.pi.gov.br/", "sistema": "ABRASF"},
    # Cidades do Maranhão
    "IMPERATRIZ/MA": {"portal": "https://nfse.imperatriz.ma.gov.br/", "sistema": "ABRASF"},
    # Cidades do Mato Grosso do Sul
    "DOURADOS/MS": {"portal": "https://nfse.dourados.ms.gov.br/", "sistema": "ABRASF"},
    # Cidades do Mato Grosso
    "VARIOS/MT": {
        "portal": "https://www.nfse.gov.br/consultapublica",
        "sistema": "ABRASF Nacional",
    },
    # Cidades de Goiás
    "ANAPOLIS/GO": {"portal": "https://nfse.anapolis.go.gov.br/", "sistema": "ABRASF"},
    # Portal Nacional Unificado
    "BRASIL": {
        "portal": "https://www.nfse.gov.br/consultapublica",
        "sistema": "ABRASF Nacional",
    },
}


def _validar_numero_nfse(numero: str) -> str:
    """Valida e limpa o número ou identificador da NFS-e informado pelo chamador."""
    numero_limpo = numero.strip()
    if not numero_limpo:
        raise ValueError("numero é obrigatório")
    if not all(char.isalnum() or char in ".-/" for char in numero_limpo):
        raise ValueError("numero deve conter apenas letras, números, ponto, hífen ou barra")
    return numero_limpo


def _validar_municipio_nfse(municipio: str) -> str:
    """Valida e limpa o nome do município da NFS-e."""
    municipio_limpo = municipio.strip()
    if not municipio_limpo:
        raise ValueError("municipio é obrigatório")
    if not any(char.isalpha() for char in municipio_limpo):
        raise ValueError("municipio deve conter letras")
    return municipio_limpo


def _validar_uf_nfse(uf: str) -> str:
    """Valida e normaliza a sigla da UF com 2 letras em maiúsculas."""
    uf_limpa = uf.strip().upper()
    if len(uf_limpa) != 2 or not uf_limpa.isalpha():
        raise ValueError("uf deve ser uma sigla com 2 letras")
    return uf_limpa


def _normalizar_chave_municipio(municipio: str) -> str:
    """Remove acentos e normaliza espaços do nome do município para busca em PORTAIS_CONHECIDOS."""
    sem_acentos = "".join(
        char for char in unicodedata.normalize("NFKD", municipio) if not unicodedata.combining(char)
    )
    return " ".join(sem_acentos.upper().split())


def _validar_cnpj_prestador(cnpj_prestador: str | None) -> str | None:
    """Valida e normaliza o CNPJ do prestador (numérico ou alfanumérico) quando informado."""
    if cnpj_prestador is None:
        return None
    if not validate_cnpj_qualquer(cnpj_prestador):
        raise ValueError("cnpj_prestador inválido")
    return normalizar_cnpj(cnpj_prestador)


def _resolver_portal_conhecido(municipio: str, uf_upper: str) -> dict[str, str]:
    """Busca o portal e o sistema municipal de NFS-e no catálogo local PORTAIS_CONHECIDOS."""
    municipio_upper = _normalizar_chave_municipio(municipio)
    chave = f"{municipio_upper}/{uf_upper}"
    portal_info = PORTAIS_CONHECIDOS.get(chave)
    if not portal_info:
        portal_info = PORTAIS_CONHECIDOS.get(municipio_upper)
    if not portal_info:
        portal_info = PORTAIS_CONHECIDOS.get("BRASIL", {})
    return portal_info


async def validar_chave_nfse(chave_acesso: str) -> dict[str, object]:
    """
    Valida o formato e o dígito verificador de uma chave de acesso de NFS-e Nacional (50 posições).

    Não consulta APIs externas - apenas verifica o cálculo matemático (módulo 11)
    e decodifica os campos embutidos na chave (código IBGE do município, UF,
    ambiente gerador, CPF/CNPJ do prestador, número da NFS-e e ano/mês de emissão).

    Args:
        chave_acesso: Chave de acesso da NFS-e Nacional com 50 posições.

    Returns:
        Dicionário com "válido", "chave_formatada" e os campos decodificados quando válida.
    """
    chave_limpa = normalizar_chave_nfse(chave_acesso)
    valido = validate_chave_nfse(chave_limpa)

    resultado: dict[str, object] = {
        "válido": valido,
        "chave_formatada": format_chave_nfse(chave_limpa) if valido else None,
    }

    if valido:
        from ..shared.constants import CODIGO_UF

        cod_uf = int(chave_limpa[:2])
        tp_insc = chave_limpa[8:9]
        insc_fed = chave_limpa[9:23]
        resultado.update(
            {
                "uf": CODIGO_UF.get(cod_uf, f"UF {cod_uf}"),
                "codigo_municipio": chave_limpa[0:7],
                "ambiente_gerador": chave_limpa[7:8],
                "tipo_inscricao": tp_insc,
                "inscricao_federal": insc_fed,
                "cnpj_prestador": insc_fed if tp_insc == "2" else None,
                "cpf_prestador": insc_fed[3:] if tp_insc == "1" else None,
                "número": chave_limpa[23:36],
                "ano_mes_emissao": f"{chave_limpa[38:40]}/{chave_limpa[36:38]}",
                "codigo_numerico": chave_limpa[40:49],
                "digito_verificador": chave_limpa[49],
            }
        )

    return resultado


async def consultar_cobertura_nfse(
    municipio: str | None = None,
    uf: str | None = None,
    codigo_ibge: str | None = None,
) -> dict[str, Any]:
    """
    Consulta a cobertura municipal de NFS-e (engine/provedor ativo, código IBGE e adesão ao ADN).

    Utiliza o catálogo público gratuito da Notaas (5.570 municípios brasileiros) e,
    em caso de indisponibilidade de rede, recorre ao catálogo offline de capitais e
    grandes cidades.

    Args:
        municipio: Nome do município (ex: 'São Paulo', 'Campinas'). Opcional se codigo_ibge for informado.
        uf: Sigla do estado com 2 letras (ex: 'SP', 'MG'). Opcional.
        codigo_ibge: Código IBGE de 7 dígitos (ex: '3550308'). Opcional.

    Returns:
        Dicionário com a lista de municípios encontrados, engine municipal e adesão ao SNNFSE/ADN.
    """
    q = municipio.strip() if municipio else None
    uf_limpa = _validar_uf_nfse(uf) if uf and uf.strip() else None
    ibge_limpo = codigo_ibge.strip() if codigo_ibge else None

    if not q and not uf_limpa and not ibge_limpo:
        raise ValueError("Informe pelo menos um filtro: municipio, uf ou codigo_ibge")

    if ibge_limpo and (len(ibge_limpo) != 7 or not ibge_limpo.isdigit()):
        raise ValueError("codigo_ibge deve conter exatamente 7 dígitos numéricos")

    try:
        dados = await notaas_provider.consultar_cobertura_cidades(
            q=q,
            uf=uf_limpa,
            ibge=ibge_limpo,
        )
        return {
            "fonte": "notaas.com.br",
            "municipios": dados.get("municipios", []),
            "total": dados.get("total", len(dados.get("municipios", []))),
        }
    except Exception as exc:
        logger.warning(
            "Catálogo público Notaas indisponível (%s) - usando fallback offline",
            exc,
        )
        if ibge_limpo:
            return {
                "fonte": "fallback_catalogo_local",
                "municipios": [],
                "total": 0,
                "motivo": (
                    f"Catálogo remoto indisponível: {exc}. "
                    "O catálogo local não permite validar o codigo_ibge informado."
                ),
            }
        portal_info = (
            PORTAIS_CONHECIDOS.get(f"{_normalizar_chave_municipio(q)}/{uf_limpa}")
            if q and uf_limpa
            else None
        )
        if portal_info:
            return {
                "fonte": "fallback_catalogo_local",
                "municipios": [
                    {
                        "nome_municipio": q,
                        "sigla_uf": uf_limpa,
                        "codigo_ibge": ibge_limpo,
                        "sistema_nfse": portal_info.get("sistema", "ABRASF/Proprietario"),
                        "portal_municipio": portal_info.get("portal"),
                    }
                ],
                "total": 1,
            }
        return {
            "fonte": "fallback_catalogo_local",
            "municipios": [],
            "total": 0,
            "motivo": f"Catálogo remoto indisponível: {exc}",
        }


async def consultar_nfse(
    numero: str = "",
    municipio: str = "",
    uf: str = "",
    cnpj_prestador: str | None = None,
    chave_acesso: str | None = None,
    invoice_id: str | None = None,
) -> dict[str, Any]:
    """
    Consulta dados de uma NFSe (Nota Fiscal de Serviço Eletrônica).

    IMPORTANTE: NFSe não possui padrão nacional único. Cada município tem seu próprio
    sistema (ABRASF, ISS.net, Betha, Paulistana, etc.), além do Ambiente de Dados
    Nacional (ADN / SNNFSE).

    Ordem de resolução:
    1. Se ``NOTAAS_API_KEY`` estiver configurado e ``invoice_id`` for informado,
       consulta o provedor opcional Notaas (``GET /api/v1/invoices/{id}/status``).
    2. Se ``chave_acesso`` de 50 posições da NFS-e Nacional for informada (ou se
       ``numero`` for uma chave de 50 posições válida), consulta a API Nacional (ADN).
    3. Caso contrário (ou em caso de falha/404), retorna orientação estruturada
       com o portal e sistema do município (fallback gratuito).

    Args:
        numero: Número da NFSe (obrigatório quando ``chave_acesso`` e ``invoice_id`` não forem informados)
        municipio: Nome do município (ex: 'São Paulo', 'Belo Horizonte')
        uf: Sigla do estado (ex: 'SP', 'MG')
        cnpj_prestador: CNPJ do prestador de serviço (opcional, numérico ou alfanumérico)
        chave_acesso: Chave de acesso de 50 posições da NFS-e Nacional (opcional)
        invoice_id: ID da invoice no provedor opcional Notaas (opcional, requer NOTAAS_API_KEY)

    Returns:
        Dicionário com os dados da NFS-e encontrada ou orientações de consulta para o município.
    """
    municipio = _validar_municipio_nfse(municipio)
    uf_upper = _validar_uf_nfse(uf)
    cnpj_prestador = _validar_cnpj_prestador(cnpj_prestador)

    invoice_id_limpo = (
        notaas_provider.validar_invoice_id(invoice_id)
        if invoice_id is not None and invoice_id.strip()
        else None
    )
    chave_efetiva: str | None = None
    if chave_acesso is not None and chave_acesso.strip():
        if not validate_chave_nfse(chave_acesso):
            raise ValueError(
                "chave_acesso de NFS-e inválida: deve ter 50 posições com dígito verificador correto"
            )
        chave_efetiva = normalizar_chave_nfse(chave_acesso)
        numero = _validar_numero_nfse(numero) if numero.strip() else chave_efetiva[23:36]
    elif invoice_id_limpo is not None and not numero.strip():
        numero = ""
    else:
        if validate_chave_nfse(numero):
            chave_efetiva = normalizar_chave_nfse(numero)
            numero = chave_efetiva[23:36]
        else:
            numero = _validar_numero_nfse(numero)

    # 1. Tenta o provedor opcional Notaas quando NOTAAS_API_KEY está configurado e invoice_id informado.
    if invoice_id_limpo is not None and notaas_provider.provedor_configurado():
        try:
            dados_notaas = await notaas_provider.consultar_status_nfse(invoice_id_limpo)
            return {
                "numero": str(dados_notaas.get("numeroNfse") or numero),
                "invoice_id": invoice_id_limpo,
                "municipio": municipio,
                "uf": uf_upper,
                "fonte": "notaas.com.br",
                "status": str(dados_notaas.get("status", "encontrada")),
                **dados_notaas,
            }
        except Exception as exc:
            logger.warning(
                "Provedor Notaas falhou ao consultar invoice %s: %s - seguindo para fallback",
                invoice_id_limpo,
                exc,
            )

    # 2. Tenta a API do Ambiente de Dados Nacional (ADN) somente quando houver
    # chave de acesso válida de 50 posições (corrige issue #153: não envia número
    # curto de RPS/nota para o endpoint /nfse/{chaveAcesso}).
    api_fallback_motivo: str | None = None
    if chave_efetiva is not None:
        try:
            cliente_nacional = NFSeNacionalClient()
            dados_api = await cliente_nacional.consultar_por_chave(chave_efetiva)
            if dados_api is not None:
                return {
                    "numero": numero,
                    "chave_acesso": chave_efetiva,
                    "municipio": municipio,
                    "uf": uf_upper,
                    "fonte": "api_nacional",
                    "status": "encontrada",
                    **dados_api,
                }
            # None = HTTP 404: nota não encontrada na base nacional
            api_fallback_motivo = (
                "Nota não encontrada na API Nacional (HTTP 404 - ausente ou "
                "certificado ICP-Brasil não configurado)"
            )
            logger.info(
                "API Nacional NFS-e: chave %s retornou 404 - usando fallback municipal",
                chave_efetiva,
            )
        except NFSeNacionalUnavailableError as exc:
            api_fallback_motivo = f"API Nacional indisponível: {exc}"
            logger.warning(
                "API Nacional NFS-e indisponível para chave %s: %s - usando fallback municipal",
                chave_efetiva,
                exc,
            )
        except Exception as exc:
            api_fallback_motivo = f"Erro inesperado na API Nacional: {exc}"
            logger.warning(
                "Erro inesperado ao consultar API Nacional NFS-e para chave %s: %s - usando fallback",
                chave_efetiva,
                exc,
            )
    else:
        api_fallback_motivo = (
            "Consulta na API Nacional requer a chave de acesso de 50 posições da NFS-e "
            "(informe chave_acesso)."
        )

    portal_info = _resolver_portal_conhecido(municipio, uf_upper)

    return {
        "numero": numero,
        **({"invoice_id": invoice_id_limpo} if invoice_id_limpo else {}),
        "municipio": municipio,
        "uf": uf_upper,
        **({"cnpj_prestador": cnpj_prestador} if cnpj_prestador else {}),
        "fonte": "fallback_portal_municipal",
        "status": "consulta_manual_necessaria",
        "api_nacional_motivo": api_fallback_motivo,
        "motivo": (
            "NFSe não possui API pública padronizada nacional. "
            "Cada município gerencia seu próprio sistema de emissão e consulta."
        ),
        "portal_municipio": portal_info.get(
            "portal", f"Acesse o portal da prefeitura de {municipio}/{uf_upper}"
        )
        if portal_info
        else f"Acesse o portal da prefeitura de {municipio}/{uf_upper}",
        "sistema_nfse": portal_info.get("sistema", "ABRASF/Proprietario")
        if portal_info
        else "ABRASF/Proprietario",
        "alternativa": (
            "Para integração automatizada, contrate um emissor NFSe como "
            "Notaas (notaas.com.br), Omie, ContaAzul, NFe.io ou Enotas que suportam múltiplos municípios."
        ),
    }
