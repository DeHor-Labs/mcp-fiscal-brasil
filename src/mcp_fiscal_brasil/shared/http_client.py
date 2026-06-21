"""Cliente HTTP assincrono com retry, backoff e integracao com rate limiter."""

import asyncio
import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from .exceptions import APIError, RateLimitError, TimeoutError
from .rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)
_PACKAGE_NAME = "mcp-fiscal-brasil"

# Timeout padrao (segundos): connect=5, read=30, write=10
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


def _default_user_agent() -> str:
    try:
        package_version = version(_PACKAGE_NAME)
    except PackageNotFoundError:
        package_version = "0.0.0"
    return f"{_PACKAGE_NAME}/{package_version}"


class FiscalHTTPClient:
    """
    Cliente HTTP assincrono com:
    - Retry automático com backoff exponencial
    - Integracao com SlidingWindowRateLimiter
    - Mapeamento de erros HTTP para excecoes fiscais
    - Logging estruturado
    """

    def __init__(
        self,
        base_url: str,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.rate_limiter = rate_limiter
        self._default_headers = {
            "Accept": "application/json",
            "User-Agent": _default_user_agent(),
            **(headers or {}),
        }
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._default_headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Fecha a conexao HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "FiscalHTTPClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        rate_limit_key: str | None = None,
    ) -> dict[str, Any] | list[Any] | str:
        """Executa GET com retry e rate limiting."""
        return await self._request(
            "GET", path, params=params, headers=headers, rate_limit_key=rate_limit_key
        )

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        data: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        rate_limit_key: str | None = None,
    ) -> dict[str, Any] | list[Any] | str:
        """Executa POST com retry e rate limiting."""
        return await self._request(
            "POST", path, json=json, data=data, headers=headers, rate_limit_key=rate_limit_key
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        rate_limit_key: str | None = None,
    ) -> dict[str, Any] | list[Any] | str:
        """Executa uma requisicao HTTP com retry e backoff exponencial."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        key = rate_limit_key or path

        last_error: Exception | None = None

        for tentativa in range(self.max_retries):
            # Rate limiting antes de cada tentativa
            if self.rate_limiter is not None:
                try:
                    await self.rate_limiter.acquire(key)
                except RateLimitError:
                    raise

            try:
                client = await self._get_client()
                # Remove leading slash so httpx preserves the base_url path component.
                # httpx treats paths starting with "/" as absolute (drops base_url path).
                response = await client.request(
                    method,
                    path.lstrip("/"),
                    params=params,
                    json=json,
                    content=data,
                    headers=headers,
                )

                logger.debug(
                    "HTTP %s %s -> %d (tentativa %d/%d)",
                    method,
                    url,
                    response.status_code,
                    tentativa + 1,
                    self.max_retries,
                )

                return self._handle_response(response, url)

            except httpx.TimeoutException as e:
                last_error = TimeoutError(endpoint=url, timeout_seconds=self.timeout.read or 30.0)
                logger.warning(
                    "Timeout em %s (tentativa %d/%d): %s", url, tentativa + 1, self.max_retries, e
                )

            except httpx.HTTPStatusError as e:
                # Erros 5xx são retriaveis; 4xx não
                if e.response.status_code < 500:
                    raise self._map_http_error(e, url) from e
                last_error = self._map_http_error(e, url)
                logger.warning(
                    "HTTP %d em %s (tentativa %d/%d)",
                    e.response.status_code,
                    url,
                    tentativa + 1,
                    self.max_retries,
                )

            except httpx.RequestError as e:
                last_error = APIError(message=f"Erro de rede: {e}", endpoint=url)
                logger.warning(
                    "Erro de rede em %s (tentativa %d/%d): %s",
                    url,
                    tentativa + 1,
                    self.max_retries,
                    e,
                )

            # Backoff exponencial antes da proxima tentativa
            if tentativa < self.max_retries - 1:
                sleep_time = self.backoff_factor**tentativa
                logger.debug("Aguardando %.1fs antes de retentar...", sleep_time)
                await asyncio.sleep(sleep_time)

        raise last_error or APIError(message="Numero maximo de tentativas excedido", endpoint=url)

    def _handle_response(
        self, response: httpx.Response, url: str
    ) -> dict[str, Any] | list[Any] | str:
        """Processa a resposta HTTP e lanca excecoes para erros."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise self._map_http_error(e, url) from e

        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()  # type: ignore[no-any-return]
        if "xml" in content_type or "text" in content_type:
            return response.text
        return response.text

    def _map_http_error(self, exc: httpx.HTTPStatusError, url: str) -> APIError:
        """Mapeia erros HTTP para APIError com mensagens em português."""
        status = exc.response.status_code
        messages = {
            400: "Requisicao invalida",
            401: "Não autorizado",
            403: "Acesso negado",
            404: "Recurso não encontrado",
            422: "Dados invalidos",
            429: "Muitas requisicoes - tente novamente mais tarde",
            500: "Erro interno do servidor",
            502: "Gateway invalido",
            503: "Servico indisponivel",
            504: "Timeout do gateway",
        }
        message = messages.get(status, f"Erro HTTP {status}")
        return APIError(message=message, status_code=status, endpoint=url)
