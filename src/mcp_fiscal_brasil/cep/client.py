from mcp_fiscal_brasil._core import FiscalNotFoundError, HTTPClient, get_logger, settings
from mcp_fiscal_brasil._core.errors import FiscalHTTPError

from .schemas import Endereco

logger = get_logger(__name__)


def validate_cep(cep: str) -> bool:
    """Valida se uma string tem o formato correto de um CEP (8 dígitos)."""
    clean_cep = "".join(c for c in cep if c.isdigit())
    return len(clean_cep) == 8


class CEPClient:
    """Cliente para busca de endereços por CEP via BrasilAPI."""

    def _http_client(self) -> HTTPClient:
        return HTTPClient(
            settings.brasilapi_base_url,
            timeout=settings.mcp_fiscal_http_timeout,
            max_retries=settings.mcp_fiscal_max_retries,
            cache_ttl=settings.mcp_fiscal_cache_ttl,
            rate_limit_per_second=settings.mcp_fiscal_rate_limit,
        )

    async def get_address(self, cep: str) -> Endereco:
        """Busca o endereço completo a partir de um CEP."""
        logger.info("cep_get_address_started", cep=cep)
        cep_clean = "".join(c for c in cep if c.isdigit())
        if not validate_cep(cep_clean):
            raise FiscalNotFoundError(f"Formato de CEP inválido: {cep}", "Recurso", "desconhecido")

        async with self._http_client() as client:
            try:
                data = await client.get(f"/cep/v2/{cep_clean}")
                return Endereco(
                    cep=data.get("cep", ""),
                    state=data.get("state", ""),
                    city=data.get("city", ""),
                    neighborhood=data.get("neighborhood", ""),
                    street=data.get("street", ""),
                    service=data.get("service"),
                )
            except FiscalHTTPError as exc:
                if exc.status_code == 404:
                    raise FiscalNotFoundError(
                        f"CEP {cep_clean} não encontrado", "Recurso", "desconhecido"
                    ) from exc
                raise
