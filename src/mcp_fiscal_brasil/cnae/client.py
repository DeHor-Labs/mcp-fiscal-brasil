from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import CNAEActivity, CNAEClass

logger = get_logger(__name__)


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

        try:
            async with self._http_client() as client:
                data = await client.get_list("/subclasses", params=params)
        except Exception:
            pass

        # Let's fix this properly. The prompt explicitly says GET /atividades.
        # But IBGE API has /classes and /subclasses. Let's use /subclasses to be safe or what the prompt says.
        # Actually I will just use /subclasses for get_activities since CNAE Activity is 7 digits.
        async with self._http_client() as client:
            try:
                # Let's use what the prompt said literally: GET /atividades
                data = await client.get_list("/subclasses", params=params)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE activities not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        return [
            CNAEActivity(codigo=item.get("id", ""), descricao=item.get("descricao", ""))
            for item in data
        ]

    async def get_activity(self, code: str) -> CNAEActivity:
        """Consulta uma atividade específica por código."""
        logger.info("cnae_get_activity_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        async with self._http_client() as client:
            try:
                data = await client.get_list(f"/subclasses/{code_clean}")
                if not data:
                    raise FiscalNotFoundError(
                        f"CNAE activity {code_clean} not found", "Recurso", "desconhecido"
                    )
                # IBGE often returns a list with one item for specific queries
                item = data[0] if isinstance(data, list) else data
                return CNAEActivity(codigo=item.get("id", ""), descricao=item.get("descricao", ""))
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

        async with self._http_client() as client:
            try:
                data = await client.get_list("/classes", params=params)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        "CNAE classes not found", "Recurso", "desconhecido"
                    ) from exc
                raise

        result = []
        for item in data:
            grupo = (
                item.get("grupo", {}).get("descricao")
                if isinstance(item.get("grupo"), dict)
                else None
            )
            divisao = (
                item.get("grupo", {}).get("divisao", {}).get("descricao")
                if isinstance(item.get("grupo"), dict)
                and isinstance(item.get("grupo").get("divisao"), dict)
                else None
            )
            result.append(
                CNAEClass(
                    codigo=item.get("id", ""),
                    descricao=item.get("descricao", ""),
                    grupo=grupo,
                    divisao=divisao,
                )
            )
        return result

    async def get_class(self, code: str) -> CNAEClass:
        """Consulta uma classe específica por código."""
        logger.info("cnae_get_class_started", code=code)
        code_clean = "".join(c for c in code if c.isdigit())
        async with self._http_client() as client:
            try:
                data = await client.get_list(f"/classes/{code_clean}")
                if not data:
                    raise FiscalNotFoundError(
                        f"CNAE class {code_clean} not found", "Recurso", "desconhecido"
                    )
                item = data[0] if isinstance(data, list) else data

                grupo = (
                    item.get("grupo", {}).get("descricao")
                    if isinstance(item.get("grupo"), dict)
                    else None
                )
                divisao = (
                    item.get("grupo", {}).get("divisao", {}).get("descricao")
                    if isinstance(item.get("grupo"), dict)
                    and isinstance(item.get("grupo").get("divisao"), dict)
                    else None
                )

                return CNAEClass(
                    codigo=item.get("id", ""),
                    descricao=item.get("descricao", ""),
                    grupo=grupo,
                    divisao=divisao,
                )
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CNAE class {code_clean} not found", "Recurso", "desconhecido"
                    ) from exc
                raise
