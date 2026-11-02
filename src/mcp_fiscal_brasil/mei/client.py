from datetime import date
from typing import Any

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

    def _optional_bool(self, value: Any) -> bool | None:
        if value is None:
            return None
        return bool(value)

    def _lookup_indicator(
        self, primary: dict[str, Any], primary_key: str, fallback: dict[str, Any], fallback_key: str
    ) -> bool | None:
        if primary_key in primary:
            return self._optional_bool(primary[primary_key])
        if fallback_key in fallback:
            return self._optional_bool(fallback[fallback_key])
        return None

    def _unconfirmed(self, cnpj_clean: str) -> MEIStatus:
        logger.warning("mei_status_nao_confirmado", cnpj=cnpj_clean)
        return MEIStatus(
            cnpj=cnpj_clean,
            mei=None,
            simples_nacional=None,
            fonte_confirmada=False,
        )

    def _status_from_cnpj_payload(self, cnpj_clean: str, data: dict[str, Any]) -> MEIStatus:
        mei = (
            self._optional_bool(data.get("opcao_pelo_mei"))
            if "opcao_pelo_mei" in data
            else None
        )
        simples_nacional = (
            self._optional_bool(data.get("opcao_pelo_simples"))
            if "opcao_pelo_simples" in data
            else None
        )
        return MEIStatus(
            cnpj=cnpj_clean,
            mei=mei,
            data_opcao_mei=self._parse_date(data.get("data_opcao_pelo_mei")),
            data_exclusao_mei=self._parse_date(data.get("data_exclusao_do_mei")),
            simples_nacional=simples_nacional,
            fonte_confirmada=mei is not None and simples_nacional is not None,
        )

    def _status_from_simples_payload(self, cnpj_clean: str, data: dict[str, Any]) -> MEIStatus:
        simples = data.get("simples") if isinstance(data.get("simples"), dict) else data
        simei = data.get("simei") if isinstance(data.get("simei"), dict) else data
        if not isinstance(simples, dict):
            simples = {}
        if not isinstance(simei, dict):
            simei = {}
        mei = self._lookup_indicator(simei, "optante", data, "mei")
        simples_nacional = self._lookup_indicator(simples, "optante", data, "simples_nacional")
        return MEIStatus(
            cnpj=cnpj_clean,
            mei=mei,
            data_opcao_mei=self._parse_date(
                simei.get("data_opcao", data.get("data_opcao_simei"))
            ),
            data_exclusao_mei=self._parse_date(
                simei.get("data_exclusao", data.get("data_exclusao_simei"))
            ),
            simples_nacional=simples_nacional,
            fonte_confirmada=mei is not None and simples_nacional is not None,
        )

    async def _fetch_cnpj_status(self, cnpj_clean: str) -> MEIStatus | None:
        async with self._http_client() as client:
            try:
                data = await client.get(f"/cnpj/v1/{cnpj_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    return None
                raise
        return self._status_from_cnpj_payload(cnpj_clean, data)

    async def _fetch_simples_status(self, cnpj_clean: str) -> MEIStatus | None:
        async with self._http_client() as client:
            try:
                data = await client.get(f"/simples/v1/{cnpj_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    return None
                raise
        return self._status_from_simples_payload(cnpj_clean, data)

    async def get_mei_status(self, cnpj: str) -> MEIStatus:
        """Consulta o status MEI de um CNPJ via BrasilAPI.

        Usa `/cnpj/v1/{cnpj}` (`opcao_pelo_mei` / `opcao_pelo_simples`) e, em 404,
        tenta `/simples/v1/{cnpj}`. Indicadores ausentes ou `null` ficam `None` e
        `fonte_confirmada=False`.
        """
        cnpj_clean = normalizar_cnpj(cnpj)
        if not validate_cnpj_qualquer(cnpj_clean):
            raise FiscalNotFoundError("CNPJ inválido", "CNPJ", cnpj_clean)

        logger.info("mei_status_started", cnpj=cnpj_clean)
        status = await self._fetch_cnpj_status(cnpj_clean)
        if status is not None:
            return status
        status = await self._fetch_simples_status(cnpj_clean)
        if status is not None:
            return status
        return self._unconfirmed(cnpj_clean)
