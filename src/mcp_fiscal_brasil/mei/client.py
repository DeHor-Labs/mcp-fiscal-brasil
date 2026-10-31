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

    def _status_from_simples_payload(self, cnpj_clean: str, data: dict[str, Any]) -> MEIStatus:
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

    async def _status_from_cnpj_endpoint(self, cnpj_clean: str) -> MEIStatus:
        async with self._http_client() as client:
            try:
                data = await client.get(f"/cnpj/v1/{cnpj_clean}")
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
        opcao_mei = data.get("opcao_pelo_mei")
        opcao_simples = data.get("opcao_pelo_simples")
        indicadores_ok = opcao_mei is not None and opcao_simples is not None
        return MEIStatus(
            cnpj=cnpj_clean,
            mei=bool(opcao_mei) if opcao_mei is not None else False,
            data_opcao_mei=self._parse_date(data.get("data_opcao_pelo_mei")),
            data_exclusao_mei=self._parse_date(data.get("data_exclusao_do_mei")),
            simples_nacional=bool(opcao_simples) if opcao_simples is not None else False,
            fonte_confirmada=indicadores_ok,
        )

    async def get_mei_status(self, cnpj: str) -> MEIStatus:
        """Consulta o status MEI de um CNPJ via BrasilAPI.

        Tenta `/simples/v1/{cnpj}` e, em 404, usa `/cnpj/v1/{cnpj}`
        (`opcao_pelo_mei` / `opcao_pelo_simples`). Se nenhuma fonte confirmar,
        retorna `fonte_confirmada=False`.
        """
        cnpj_clean = normalizar_cnpj(cnpj)
        if not validate_cnpj_qualquer(cnpj_clean):
            raise FiscalNotFoundError("CNPJ inválido", "CNPJ", cnpj_clean)

        logger.info("mei_status_started", cnpj=cnpj_clean)
        async with self._http_client() as client:
            try:
                data = await client.get(f"/simples/v1/{cnpj_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    return await self._status_from_cnpj_endpoint(cnpj_clean)
                raise
        return self._status_from_simples_payload(cnpj_clean, data)
