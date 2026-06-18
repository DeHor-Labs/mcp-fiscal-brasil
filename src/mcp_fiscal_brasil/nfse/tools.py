"""Ferramentas MCP para NFSe."""

import logging

from mcp_fiscal_brasil.nfse.client import NFSeNacionalClient, NFSeNacionalUnavailableError
from mcp_fiscal_brasil.shared.validators import validate_cnpj

logger = logging.getLogger(__name__)


def _validar_numero_nfse(numero: str) -> str:
    numero_limpo = numero.strip()
    if not numero_limpo:
        raise ValueError("numero é obrigatório")
    if not all(char.isalnum() or char in ".-/" for char in numero_limpo):
        raise ValueError("numero deve conter apenas letras, números, ponto, hífen ou barra")
    return numero_limpo


def _validar_municipio_nfse(municipio: str) -> str:
    municipio_limpo = municipio.strip()
    if not municipio_limpo:
        raise ValueError("municipio é obrigatório")
    if not any(char.isalpha() for char in municipio_limpo):
        raise ValueError("municipio deve conter letras")
    return municipio_limpo


def _validar_uf_nfse(uf: str) -> str:
    uf_limpa = uf.strip().upper()
    if len(uf_limpa) != 2 or not uf_limpa.isalpha():
        raise ValueError("uf deve ser uma sigla com 2 letras")
    return uf_limpa


def _validar_cnpj_prestador(cnpj_prestador: str | None) -> str | None:
    if cnpj_prestador is None:
        return None
    if not validate_cnpj(cnpj_prestador):
        raise ValueError("cnpj_prestador inválido")
    return "".join(char for char in cnpj_prestador if char.isdigit())


async def consultar_nfse(
    numero: str,
    municipio: str,
    uf: str,
    cnpj_prestador: str | None = None,
) -> dict[str, str]:
    """
    Consulta dados de uma NFSe (Nota Fiscal de Serviço Eletrônica).

    IMPORTANTE: NFSe não possui padrão nacional. Cada município tem seu próprio
    sistema (ABRASF, ISS.net, Betha, Curitiba, etc.). Esta ferramenta fornece
    orientações sobre como consultar a NFSe no município informado.

    Args:
        numero: Número da NFSe
        municipio: Nome do município (ex: 'São Paulo', 'Belo Horizonte')
        uf: Sigla do estado (ex: 'SP', 'MG')
        cnpj_prestador: CNPJ do prestador de serviço (opcional)

    Returns:
        Dicionário com orientações de consulta para o município.
    """
    numero = _validar_numero_nfse(numero)
    municipio = _validar_municipio_nfse(municipio)
    uf_upper = _validar_uf_nfse(uf)
    cnpj_prestador = _validar_cnpj_prestador(cnpj_prestador)

    # Tenta a API do Ambiente de Dados Nacional (ADN) primeiro.
    # A API exige certificado ICP-Brasil + mTLS.
    # - None -> 404 (nota não encontrada): fallback com motivo específico
    # - NFSeNacionalUnavailableError -> 5xx/timeout/rede: fallback com motivo de indisponibilidade
    api_fallback_motivo: str | None = None
    try:
        cliente_nacional = NFSeNacionalClient()
        dados_api = await cliente_nacional.consultar_por_chave(numero)
        if dados_api is not None:
            return {
                "numero": numero,
                "municipio": municipio,
                "uf": uf_upper,
                "fonte": "api_nacional",
                "status": "encontrada",
                **dados_api,
            }
        # None = HTTP 404: nota não encontrada na base nacional
        api_fallback_motivo = "Nota não encontrada na API Nacional (HTTP 404 - ausente ou certificado ICP-Brasil não configurado)"
        logger.info(
            "API Nacional NFS-e: nota %s retornou 404 - usando fallback municipal",
            numero,
        )
    except NFSeNacionalUnavailableError as exc:
        api_fallback_motivo = f"API Nacional indisponível: {exc}"
        logger.warning(
            "API Nacional NFS-e indisponível para nota %s: %s - usando fallback municipal",
            numero,
            exc,
        )
    except Exception as exc:
        api_fallback_motivo = f"Erro inesperado na API Nacional: {exc}"
        logger.warning(
            "Erro inesperado ao consultar API Nacional NFS-e para nota %s: %s - usando fallback",
            numero,
            exc,
        )

    # Portais de consulta por município/sistema (50+ capitais e grandes cidades)
    # Formato: "CIDADE/UF": {"portal": "url", "sistema": "tipo_sistema"}
    portais_conhecidos: dict[str, dict[str, str]] = {
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

    municipio_upper = municipio.upper()

    # Tenta buscar com formato "MUNICIPIO/UF"
    chave = f"{municipio_upper}/{uf_upper}"
    portal_info = portais_conhecidos.get(chave)

    # Se não encontrar, tenta apenas o município
    if not portal_info:
        portal_info = portais_conhecidos.get(municipio_upper)

    # Se ainda não encontrar, usa fallback para portal nacional
    if not portal_info:
        portal_info = portais_conhecidos.get("BRASIL")

    return {
        "numero": numero,
        "municipio": municipio,
        "uf": uf_upper,
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
            "Omie, ContaAzul, NFe.io ou Enotas que suportam múltiplos municípios."
        ),
    }
