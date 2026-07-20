"""NFe lookup client backed by BrasilAPI and the National NFe Portal."""

from typing import Any, cast

from mcp_fiscal_brasil._core import (
    FiscalHTTPError,
    FiscalRateLimitError,
    HTTPClient,
    get_logger,
    settings,
)

from ..shared.constants import CODIGO_UF
from .schemas import NFeResponse, StatusSEFAZResponse
from .status_sefaz import consultar_status_real
from .xml_parser import parse_nfe_xml

logger = get_logger(__name__)

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
          1. BrasilAPI, with partial state coverage
          2. National NFe Portal, public lookup without authentication
          3. Partial fields extracted from the access key itself
        """
        logger.info("nfe_lookup_started", chave_prefix=chave[:10])

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
