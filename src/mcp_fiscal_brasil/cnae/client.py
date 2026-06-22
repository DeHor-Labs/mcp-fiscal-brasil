from typing import Any

from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import CNAEActivity, CNAEClass

logger = get_logger(__name__)


def _cnae_class_from_item(item: dict[str, Any]) -> CNAEClass:
    """Constroi CNAEClass a partir de um item JSON da API IBGE CNAE."""
    grupo_raw = item.get("grupo")
    grupo: str | None = None
    divisao: str | None = None

    if isinstance(grupo_raw, dict):
        grupo = grupo_raw.get("descricao")
        divisao_raw = grupo_raw.get("divisao")
        if isinstance(divisao_raw, dict):
            divisao = divisao_raw.get("descricao")

    return CNAEClass(
        código=str(item.get("id", "")),
        descrição=item.get("descricao", ""),
        grupo=grupo,
        divisao=divisao,
    )


class CNAEClient:
    """Cliente para consulta da API IBGE CNAE v2."""

    def _http_client(self) -> HTTPClient:
        return HTTPClient(
            settings.ibge_cnae_base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=5,
        )

    async def get_activities(self, search: str | None = None) -> list[CNAEActivity]:
        """Consulta subclasses (atividades) do CNAE."""
        logger.info("cnae_get_activities_started", search=search)
        params = {}
        if search:
            params["busca"] = search

        # /subclasses (sem codigo) retorna lista
        async with self._http_client() as client:
            try:
                data = await client.get_list("/subclasses", params=params)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE activities not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        return [
            CNAEActivity(código=str(item.get("id", "")), descrição=item.get("descricao", ""))
            for item in data
        ]

    async def get_activity(self, code: str) -> CNAEActivity:
        """Consulta uma atividade específica por código."""
        logger.info("cnae_get_activity_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        async with self._http_client() as client:
            try:
                # /subclasses/{code} retorna objeto, nao lista
                item = await client.get(f"/subclasses/{code_clean}")
                return CNAEActivity(
                    código=str(item.get("id", "")),
                    descrição=item.get("descricao", ""),
                )
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CNAE activity {code_clean} not found", "Recurso", "desconhecido"
                    ) from exc
                raise

    async def get_classes(self, search: str | None = None) -> list[CNAEClass]:
        """Consulta classes do CNAE."""
        logger.info("cnae_get_classes_started", search=search)
        params = {}
        if search:
            params["busca"] = search

        # /classes (sem codigo) retorna lista
        async with self._http_client() as client:
            try:
                data = await client.get_list("/classes", params=params)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE classes not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        return [_cnae_class_from_item(item) for item in data]

    async def get_class(self, code: str) -> CNAEClass:
        """Consulta uma classe específica por código."""
        logger.info("cnae_get_class_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        async with self._http_client() as client:
            try:
                # /classes/{code} retorna objeto, nao lista
                item = await client.get(f"/classes/{code_clean}")
                return _cnae_class_from_item(item)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CNAE class {code_clean} not found", "Recurso", "desconhecido"
                    ) from exc
                raise
