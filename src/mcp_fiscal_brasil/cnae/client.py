from typing import Any

from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import CNAEActivity, CNAEClass

logger = get_logger(__name__)

_MAX_BUSCA_RESULTADOS = 50


def _texto_campo(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _cnae_activity_from_item(item: dict[str, Any]) -> CNAEActivity:
    return CNAEActivity(
        código=str(item.get("id", item.get("codigo", ""))),
        descrição=_texto_campo(item, "descricao", "descrição", "description"),
    )


def _cnae_class_from_item(item: dict[str, Any]) -> CNAEClass:
    grupo_raw = item.get("grupo")
    grupo: str | None = None
    divisao: str | None = None

    if isinstance(grupo_raw, dict):
        grupo = _texto_campo(grupo_raw, "descricao", "descrição") or None
        divisao_raw = grupo_raw.get("divisao")
        if isinstance(divisao_raw, dict):
            divisao = _texto_campo(divisao_raw, "descricao", "descrição") or None

    return CNAEClass(
        código=str(item.get("id", "")),
        descrição=_texto_campo(item, "descricao", "descrição", "description"),
        grupo=grupo,
        divisao=divisao,
    )


def _as_dict_payload(data: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    raise FiscalNotFoundError("CNAE payload inválido", "Recurso", "desconhecido")


def _match_busca(activity: CNAEActivity, search: str) -> bool:
    termo = search.casefold()
    haystack = f"{activity.código} {activity.descrição}".casefold()
    return termo in haystack


class CNAEClient:
    def _http_client(self) -> HTTPClient:
        return HTTPClient(
            settings.ibge_cnae_base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=5,
        )

    async def _fetch_subclasse(self, code_clean: str) -> dict[str, Any]:
        async with self._http_client() as client:
            try:
                return await client.get(f"/subclasses/{code_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CNAE activity {code_clean} not found", "Recurso", "desconhecido"
                    ) from exc
                msg = str(exc).lower()
                if "objeto json" not in msg and "lista json" not in msg:
                    raise
                try:
                    data = await client.get_list(f"/subclasses/{code_clean}")
                except FiscalHTTPError as list_exc:
                    if list_exc.status_code == 200:
                        raise FiscalNotFoundError(
                            f"CNAE activity {code_clean} not found",
                            "Recurso",
                            code_clean,
                        ) from list_exc
                    raise
                return _as_dict_payload(data)

    async def get_activities(self, search: str | None = None) -> list[CNAEActivity]:
        logger.info("cnae_get_activities_started", search=search)
        params: dict[str, Any] = {}
        if search:
            params["busca"] = search

        async with self._http_client() as client:
            try:
                data = await client.get_list("/subclasses", params=params or None)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE activities not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        activities = [_cnae_activity_from_item(item) for item in data if isinstance(item, dict)]
        if search is None:
            return activities
        filtrados = [item for item in activities if _match_busca(item, search)]
        return filtrados[:_MAX_BUSCA_RESULTADOS]

    async def get_activity(self, code: str) -> CNAEActivity:
        logger.info("cnae_get_activity_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        item = _as_dict_payload(await self._fetch_subclasse(code_clean))
        activity = _cnae_activity_from_item(item)
        if not activity.descrição:
            raise FiscalNotFoundError(
                f"CNAE activity {code_clean} sem descrição", "Recurso", code_clean
            )
        return activity

    async def get_classes(self, search: str | None = None) -> list[CNAEClass]:
        logger.info("cnae_get_classes_started", search=search)
        params: dict[str, Any] = {}
        if search:
            params["busca"] = search

        async with self._http_client() as client:
            try:
                data = await client.get_list("/classes", params=params or None)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE classes not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        classes = [_cnae_class_from_item(item) for item in data if isinstance(item, dict)]
        if search is None:
            return classes
        termo = search.casefold()
        filtrados = [
            item
            for item in classes
            if termo in f"{item.código} {item.descrição}".casefold()
        ]
        return filtrados[:_MAX_BUSCA_RESULTADOS]

    async def get_class(self, code: str) -> CNAEClass:
        logger.info("cnae_get_class_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        async with self._http_client() as client:
            try:
                raw = await client.get(f"/classes/{code_clean}")
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CNAE class {code_clean} not found", "Recurso", "desconhecido"
                    ) from exc
                raise
        return _cnae_class_from_item(_as_dict_payload(raw))
