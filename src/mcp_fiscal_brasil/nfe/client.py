"""NFe lookup client backed by BrasilAPI and the National NFe Portal.

Quando o provedor premium opcional cpfcnpj.com.br esta configurado (token via
``CPFCNPJ_TOKEN``), ele e tentado primeiro na consulta por chave, cobrindo NF-e
(modelo 55, pacote 100) e NFC-e (modelo 65, pacote 102) com dados oficiais em
tempo real. As fontes gratuitas seguem como fallback. Sem token, o comportamento
e identico ao anterior.
"""

import re
from datetime import datetime
from typing import Any, cast

from mcp_fiscal_brasil._core import (
    FiscalHTTPError,
    FiscalRateLimitError,
    HTTPClient,
    get_logger,
    settings,
)

from ..shared import cpfcnpj as cpfcnpj_provider
from ..shared.constants import CODIGO_UF
from ..shared.validators import normalizar_cnpj
from .schemas import EnderecoNFe, NFeResponse, StatusSEFAZResponse, TotaisNFe
from .status_sefaz import consultar_status_real
from .xml_parser import parse_nfe_xml

logger = get_logger(__name__)


def _parse_datetime_br(valor: str | None) -> datetime | None:
    """Converte data/hora em formato brasileiro ou ISO em datetime; None se invalido."""
    if not valor:
        return None
    texto = valor.strip()
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _parse_valor_br(valor: str | None) -> float | None:
    """Converte um valor monetario em float.

    Aceita o formato brasileiro (``1.234,56``) e o formato decimal com ponto
    (``1234.56``), este ultimo comum no ``valorTotalDaNotaFiscal`` dos pacotes
    100/102 da cpfcnpj.com.br. Regra: havendo virgula, ela e o separador decimal
    e o ponto e separador de milhar; sem virgula, um unico ponto seguido de 1 ou
    2 digitos e tratado como decimal, e qualquer outra ocorrencia de ponto e
    tratada como separador de milhar.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if "," in texto:
        normalizado = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d+\.\d{1,2}", texto):
        normalizado = texto
    else:
        normalizado = texto.replace(".", "")
    try:
        return float(normalizado)
    except ValueError:
        return None


# National NFe Portal public lookup endpoint, no certificate required.
PORTAL_NFE_BASE = "https://www.nfe.fazenda.gov.br/portal"
PORTAL_NFE_CONSULTA_PATH = "/consultaRecaptcha.aspx"


def _extrair_info_chave(chave: str) -> dict[str, str]:
    """Extract structural fields from a 44 digit NFe access key."""
    cod_uf = int(chave[:2])
    return {
        "uf": CODIGO_UF.get(cod_uf, f"UF {cod_uf}"),
        "ano_mes": f"{chave[4:6]}/{chave[2:4]}",
        "cnpj_emitente": chave[6:20],
        "modelo": chave[20:22],
        "serie": chave[22:25],
        "número": chave[25:34],
    }


class NFEClient:
    """Client for NFe lookup flows."""

    def _http_client(self, base_url: str) -> HTTPClient:
        return HTTPClient(
            base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=settings.mcp_fiscal_rate_limit,
        )

    async def _get_json_or_text(
        self,
        client: HTTPClient,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        response = await client._request("GET", path, params=params)
        content_type = response.headers.get("content-type", "").lower()

        if "json" in content_type:
            data = response.json()
            if isinstance(data, dict):
                return cast(dict[str, Any], data)
            raise FiscalHTTPError(
                "Resposta JSON inválida",
                status_code=response.status_code,
                url=str(response.request.url),
                detail={"response": response.text},
            )

        return response.text

    async def consultar_por_chave(self, chave: str) -> NFeResponse:
        """
        Look up NFe data by its 44 digit access key.

        Fallback chain:
          0. cpfcnpj.com.br premium provider, only when a token is configured
          1. BrasilAPI, with partial state coverage
          2. National NFe Portal, public lookup without authentication
          3. Partial fields extracted from the access key itself
        """
        logger.info("nfe_lookup_started", chave_prefix=chave[:10])

        if cpfcnpj_provider.provedor_configurado():
            try:
                resultado = await self._consultar_cpfcnpj(chave)
                logger.info("nfe_lookup_cpfcnpj_success", chave_prefix=chave[:10])
                return resultado
            except Exception as exc:
                logger.warning(
                    "nfe_lookup_cpfcnpj_failed",
                    chave_prefix=chave[:10],
                    error=str(exc),
                    fallback="brasilapi",
                )

        try:
            resultado = await self._consultar_brasil_api(chave)
            logger.info("nfe_lookup_brasilapi_success", chave_prefix=chave[:10])
            return resultado
        except FiscalRateLimitError as exc:
            logger.warning(
                "nfe_lookup_brasilapi_rate_limited",
                chave_prefix=chave[:10],
                error=str(exc),
                fallback="portal_nfe",
            )
        except FiscalHTTPError as exc:
            logger.warning(
                "nfe_lookup_brasilapi_http_failed",
                chave_prefix=chave[:10],
                status_code=exc.status_code,
                error=str(exc),
                fallback="portal_nfe",
            )
        except Exception as exc:
            logger.warning(
                "nfe_lookup_brasilapi_unexpected_failed",
                chave_prefix=chave[:10],
                error=str(exc),
                fallback="portal_nfe",
            )

        try:
            resultado = await self._consultar_portal_nfe(chave)
            logger.info("nfe_lookup_portal_success", chave_prefix=chave[:10])
            return resultado
        except Exception as exc:
            logger.warning(
                "nfe_lookup_portal_failed",
                chave_prefix=chave[:10],
                error=str(exc),
                fallback="partial_access_key_data",
            )

        logger.info(
            "nfe_lookup_all_sources_failed",
            chave_prefix=chave[:10],
            fallback="partial_access_key_data",
        )
        return self._resposta_parcial_da_chave(chave)

    async def _consultar_brasil_api(self, chave: str) -> NFeResponse:
        """Look up NFe data through BrasilAPI nfe/v1."""
        async with self._http_client(settings.brasilapi_base_url) as client:
            data = await self._get_json_or_text(client, f"/nfe/v1/{chave}")

        if isinstance(data, str):
            return parse_nfe_xml(data, chave)

        return NFeResponse(
            chave_acesso=chave,
            número=str(data.get("número", "")),
            serie=str(data.get("serie", "")),
            situacao=data.get("situacao"),
        )

    def _pacote_cpfcnpj(self, chave: str) -> int | None:
        """Escolhe o pacote da cpfcnpj.com.br pelo modelo embutido na chave.

        Modelo 55 (NF-e) usa o pacote 100; modelo 65 (NFC-e) usa o pacote 102.
        Outros modelos nao sao cobertos e retornam None, pulando o provedor premium.
        """
        modelo = chave[20:22] if len(chave) >= 22 else ""
        if modelo == "55":
            return cpfcnpj_provider.PACOTE_NFE
        if modelo == "65":
            return cpfcnpj_provider.PACOTE_NFCE
        return None

    async def _consultar_cpfcnpj(self, chave: str) -> NFeResponse:
        """Consulta NF-e (pacote 100) ou NFC-e (pacote 102) na cpfcnpj.com.br."""
        pacote = self._pacote_cpfcnpj(chave)
        if pacote is None:
            raise FiscalHTTPError(
                "Modelo de documento nao suportado pelo provedor cpfcnpj.com.br.",
                status_code=0,
                url=settings.cpfcnpj_base_url,
            )
        data = await cpfcnpj_provider.consultar(pacote, chave)
        return self._parse_cpfcnpj(data, chave)

    def _parse_cpfcnpj(self, data: dict[str, Any], chave: str) -> NFeResponse:
        """Transforma a resposta de NF-e/NFC-e da cpfcnpj.com.br em NFeResponse."""
        dados_nfe = ((data.get("nfe") or {}).get("dadosDaNfe")) or {}
        emissao = ((data.get("nfe") or {}).get("emissao")) or {}
        situacao_atual = data.get("situacaoAtual") or {}
        dados_gerais = data.get("dadosGerais") or {}

        emitente = self._endereco_nfe(data.get("emitente"))
        destinatario = self._endereco_nfe(data.get("destinatario"))

        protocolo = None
        data_autorizacao = None
        for evento in data.get("eventosNfe") or []:
            if "autoriza" in str(evento.get("evento", "")).lower():
                protocolo = evento.get("protocolo")
                data_autorizacao = _parse_datetime_br(evento.get("dataAutorizacao"))
                break

        valor_nota = _parse_valor_br(dados_nfe.get("valorTotalDaNotaFiscal"))
        totais = TotaisNFe(valor_nota=valor_nota) if valor_nota is not None else None

        numero = dados_nfe.get("numero") or dados_gerais.get("numero")

        return NFeResponse(
            chave_acesso=chave,
            número=str(numero) if numero else None,
            serie=str(dados_nfe["serie"]) if dados_nfe.get("serie") else None,
            modelo=str(dados_nfe.get("modelo") or chave[20:22] or "55"),
            emitente=emitente,
            destinatario=destinatario,
            data_emissao=_parse_datetime_br(dados_nfe.get("dataDeEmissao")),
            data_saida_entrada=_parse_datetime_br(dados_nfe.get("dataHoraDeSaidaOuDaEntrada")),
            natureza_operacao=emissao.get("naturezaDaOperacao"),
            tipo_operacao=emissao.get("tipoDaOperacao"),
            finalidade=emissao.get("finalidade"),
            totais=totais,
            protocolo_autorizacao=protocolo,
            data_autorizacao=data_autorizacao,
            situacao=situacao_atual.get("situacao"),
            informacoes_adicionais=self._info_ambiente(situacao_atual),
        )

    @staticmethod
    def _endereco_nfe(raw: dict[str, Any] | None) -> EnderecoNFe | None:
        """Monta um EnderecoNFe a partir do bloco emitente/destinatario da cpfcnpj.com.br."""
        if not raw:
            return None

        def _digitos(valor: Any) -> str | None:
            if not valor:
                return None
            somente = "".join(c for c in str(valor) if c.isdigit())
            return somente or None

        def _cnpj(valor: Any) -> str | None:
            # CNPJ pode ser alfanumerico (IN RFB 2.229/2024): remove so a mascara
            # e preserva as letras. CPF segue numerico.
            if not valor:
                return None
            return normalizar_cnpj(str(valor)) or None

        return EnderecoNFe(
            logradouro=raw.get("endereco"),
            bairro=raw.get("bairroDistrito"),
            municipio=raw.get("municipio"),
            uf=raw.get("uf"),
            cep=raw.get("cep"),
            cnpj=_cnpj(raw.get("cnpj")),
            cpf=_digitos(raw.get("cpf")),
            ie=raw.get("inscricaoEstadual"),
            nome=raw.get("nomeRazaoSocial"),
        )

    @staticmethod
    def _info_ambiente(situacao_atual: dict[str, Any]) -> str | None:
        """Descreve o ambiente de autorizacao quando informado."""
        ambiente = situacao_atual.get("ambienteAutorizacao")
        if ambiente:
            return f"Ambiente de autorização: {ambiente}."
        return None

    async def _consultar_portal_nfe(self, chave: str) -> NFeResponse:
        """
        Look up NFe data through the National NFe Portal.

        The portal offers public access key lookup without a digital certificate.
        It returns NFe XML when available.
        """
        async with self._http_client(PORTAL_NFE_BASE) as client:
            data = await self._get_json_or_text(
                client,
                PORTAL_NFE_CONSULTA_PATH,
                params={
                    "tipoConsulta": "completa",
                    "tipoConteudo": "XML",
                    "nfe": chave,
                },
            )

        if isinstance(data, str) and data.strip():
            return parse_nfe_xml(data, chave)

        raise FiscalHTTPError(
            "Portal NFe retornou resposta vazia ou em formato não suportado",
            status_code=200,
            url=PORTAL_NFE_BASE,
        )

    def _resposta_parcial_da_chave(self, chave: str) -> NFeResponse:
        """
        Build an NFeResponse from fields embedded in the access key.

        This gives callers at least UF, issuer CNPJ, number and series when no
        external source can return full details.
        """
        info = _extrair_info_chave(chave)
        from .schemas import EnderecoNFe

        emitente = EnderecoNFe(cnpj=info["cnpj_emitente"])
        return NFeResponse(
            chave_acesso=chave,
            número=info["número"].lstrip("0") or info["número"],
            serie=info["serie"].lstrip("0") or info["serie"],
            modelo=info["modelo"],
            emitente=emitente,
            situacao="Dados parciais - consulta indisponível nas APIs externas",
            informacoes_adicionais=(
                f"UF de emissão: {info['uf']}. "
                f"Emissão: {info['ano_mes']}. "
                "Dados completos indisponíveis: BrasilAPI sem cobertura para este estado "
                "e Portal NFe inacessível no momento."
            ),
        )

    async def consultar_status_servico(
        self, uf: str, ambiente: str | None = None
    ) -> StatusSEFAZResponse:
        """
        Consulta o status real do webservice SEFAZ da UF via NfeStatusServico4 (mTLS).

        Exige certificado digital A1 configurado (NFE_CERTIFICADO_PATH /
        NFE_CERTIFICADO_SENHA) - mTLS é exigência de transporte de todo webservice
        SEFAZ, inclusive consulta de status. Sem certificado, propaga
        FiscalConfigurationError; o chamador decide como tratar (api.py, por
        exemplo, omite a UF da resposta em vez de fabricar um status falso).
        """
        ambiente_efetivo = ambiente or settings.nfe_ambiente
        logger.info("sefaz_status_lookup_started", uf=uf, ambiente=ambiente_efetivo)

        resultado = await consultar_status_real(
            uf.upper(),
            caminho_certificado=settings.nfe_certificado_path,
            senha=settings.nfe_certificado_senha,
            ambiente="homologacao" if ambiente_efetivo == "homologacao" else "producao",
        )

        return StatusSEFAZResponse(
            uf=resultado.uf,
            status=resultado.status,
            descrição=resultado.descricao or "",
            código=resultado.codigo,
            ambiente=ambiente_efetivo,
        )
