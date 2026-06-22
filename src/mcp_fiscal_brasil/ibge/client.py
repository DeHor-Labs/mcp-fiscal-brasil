from typing import Any

from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import Estado, Municipio

logger = get_logger(__name__)


def _municipio_from_item(item: dict[str, Any]) -> Municipio:
    """Constroi Municipio a partir de um item JSON da API IBGE Localidades."""
    microrregiao_raw = item.get("microrregiao")
    microrregiao_nome: str | None = None
    estado_sigla: str | None = None

    if isinstance(microrregiao_raw, dict):
        microrregiao_nome = microrregiao_raw.get("nome")
        mesorregiao = microrregiao_raw.get("mesorregiao")
        if isinstance(mesorregiao, dict):
            uf = mesorregiao.get("UF")
            if isinstance(uf, dict):
                estado_sigla = uf.get("sigla")

    return Municipio(
        id=item["id"],
        nome=item["nome"],
        microrregiao=microrregiao_nome,
        estado=estado_sigla,
    )


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
                # /estados/{uf} retorna objeto, nao lista
                item = await client.get(f"/estados/{uf}")
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

        return [_municipio_from_item(item) for item in data]

    async def get_municipality(self, code: int) -> Municipio:
        """Consulta um município específico por código."""
        logger.info("ibge_get_municipality_started", code=code)
        async with self._http_client() as client:
            try:
                # /municipios/{code} retorna objeto, nao lista
                item = await client.get(f"/municipios/{code}")
                return _municipio_from_item(item)
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"Município {code} não encontrado", "Recurso", "desconhecido"
                    ) from exc
                raise
