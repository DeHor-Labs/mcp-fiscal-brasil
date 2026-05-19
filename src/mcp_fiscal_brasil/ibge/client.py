from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import Estado, Municipio

logger = get_logger(__name__)


class IBGEClient:
    """Cliente para a API de Localidades do IBGE."""

    def _http_client(self) -> HTTPClient:
        return HTTPClient(
            settings.ibge_localidades_base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=settings.mcp_fiscal_rate_limit,
        )

    async def get_states(self) -> list[Estado]:
        """Consulta todos os estados (Unidades da Federação)."""
        logger.info("ibge_get_states_started")
        async with self._http_client() as client:
            data = await client.get_list("/estados")

        return [
            Estado(
                id=item["id"],
                sigla=item["sigla"],
                nome=item["nome"],
                regiao=item.get("regiao", {}).get("nome")
                if isinstance(item.get("regiao"), dict)
                else None,
            )
            for item in data
        ]

    async def get_state(self, uf: str) -> Estado:
        """Consulta um estado específico pela sua sigla (UF)."""
        logger.info("ibge_get_state_started", uf=uf)
        async with self._http_client() as client:
            try:
                data = await client.get_list(f"/estados/{uf}")
                if not data:
                    raise FiscalNotFoundError(
                        f"Estado {uf} não encontrado", "Recurso", "desconhecido"
                    )
                item = data[0] if isinstance(data, list) else data
                return Estado(
                    id=item["id"],
                    sigla=item["sigla"],
                    nome=item["nome"],
                    regiao=item.get("regiao", {}).get("nome")
                    if isinstance(item.get("regiao"), dict)
                    else None,
                )
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"Estado {uf} não encontrado", "Recurso", "desconhecido"
                    ) from exc
                raise

    async def get_municipalities(self, uf: str | None = None) -> list[Municipio]:
        """Consulta todos os municípios, opcionalmente filtrados por UF."""
        logger.info("ibge_get_municipalities_started", uf=uf)
        path = f"/estados/{uf}/municipios" if uf else "/municipios"
        async with self._http_client() as client:
            data = await client.get_list(path)

        return [
            Municipio(
                id=item["id"],
                nome=item["nome"],
                microrregiao=item.get("microrregiao", {}).get("nome")
                if isinstance(item.get("microrregiao"), dict)
                else None,
                estado=item.get("microrregiao", {})
                .get("mesorregiao", {})
                .get("UF", {})
                .get("sigla")
                if isinstance(item.get("microrregiao"), dict)
                and isinstance(item.get("microrregiao").get("mesorregiao"), dict)
                and isinstance(item.get("microrregiao").get("mesorregiao").get("UF"), dict)
                else None,
            )
            for item in data
        ]

    async def get_municipality(self, code: int) -> Municipio:
        """Consulta um município específico por código."""
        logger.info("ibge_get_municipality_started", code=code)
        async with self._http_client() as client:
            try:
                data = await client.get_list(f"/municipios/{code}")
                if not data:
                    raise FiscalNotFoundError(
                        f"Município {code} não encontrado", "Recurso", "desconhecido"
                    )
                item = data[0] if isinstance(data, list) else data
                return Municipio(
                    id=item["id"],
                    nome=item["nome"],
                    microrregiao=item.get("microrregiao", {}).get("nome")
                    if isinstance(item.get("microrregiao"), dict)
                    else None,
                    estado=item.get("microrregiao", {})
                    .get("mesorregiao", {})
                    .get("UF", {})
                    .get("sigla")
                    if isinstance(item.get("microrregiao"), dict)
                    and isinstance(item.get("microrregiao").get("mesorregiao"), dict)
                    and isinstance(item.get("microrregiao").get("mesorregiao").get("UF"), dict)
                    else None,
                )
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"Município {code} não encontrado", "Recurso", "desconhecido"
                    ) from exc
                raise
