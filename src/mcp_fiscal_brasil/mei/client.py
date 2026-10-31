from datetime import date

from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError
from mcp_fiscal_brasil.shared.validators import normalizar_cnpj, validate_cnpj_qualquer

from .schemas import MEIStatus

logger = get_logger(__name__)


class MEIClient:
    """Cliente para consulta do MEI via BrasilAPI."""

    def _http_client(self) -> HTTPClient:
        return HTTPClient(
            settings.brasilapi_base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=settings.mcp_fiscal_rate_limit,
        )

    def _parse_date(self, date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str[:10])
        except ValueError:
            return None

    async def get_mei_status(self, cnpj: str) -> MEIStatus:
        """Consulta o status MEI de um CNPJ."""
        cnpj_clean = normalizar_cnpj(cnpj)
        if not validate_cnpj_qualquer(cnpj_clean):
            raise FiscalNotFoundError("CNPJ inválido", "CNPJ", cnpj_clean)

        logger.info("mei_status_started", cnpj=cnpj_clean)
        async with self._http_client() as client:
            try:
                data = await client.get(f"/simples/v1/{cnpj_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    logger.warning("mei_status_nao_confirmado", cnpj=cnpj_clean)
                    return MEIStatus(
                        cnpj=cnpj_clean,
                        mei=False,
                        simples_nacional=False,
                        fonte_confirmada=False,
                    )
                raise

        simples = data.get("simples") if isinstance(data.get("simples"), dict) else data
        simei = data.get("simei") if isinstance(data.get("simei"), dict) else data

        if not isinstance(simples, dict):
            simples = {}
        if not isinstance(simei, dict):
            simei = {}

        return MEIStatus(
            cnpj=cnpj_clean,
            mei=simei.get("optante", data.get("mei", False)),
            data_opcao_mei=self._parse_date(
                simei.get("data_opcao", data.get("data_opcao_simei"))
            ),
            data_exclusao_mei=self._parse_date(
                simei.get("data_exclusao", data.get("data_exclusao_simei"))
            ),
            simples_nacional=simples.get("optante", data.get("simples_nacional", False)),
            fonte_confirmada=True,
        )
