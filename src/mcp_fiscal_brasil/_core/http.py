"""Async HTTP client with retries, rate limiting and short lived GET caching."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from inspect import Parameter, signature
from typing import Any, cast

import httpx
from aiolimiter import AsyncLimiter
from cachetools import TTLCache
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

__all__ = ["HTTPClient"]

_CacheKey = tuple[str, str, tuple[tuple[str, Any], ...]]


class _ReadableQuery(bytes):
    def __str__(self) -> str:
        return self.decode("ascii")


class _ReadableQueryURL(httpx.URL):
    @property
    def query(self) -> bytes:
        return _ReadableQuery(super().query)


class HTTPClient:
    """Small async JSON client for external fiscal services."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        cache_ttl: int = 300,
        rate_limit_per_second: int = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.cache_ttl = max(0, cache_ttl)
        self.rate_limit_per_second = max(1, rate_limit_per_second)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            event_hooks={"request": [self._prepare_request]},
        )
        self._cache: TTLCache[_CacheKey, dict[str, Any] | list[Any]] = TTLCache(
            maxsize=1024,
            ttl=self.cache_ttl,
        )
        self._limiter = AsyncLimiter(
            self.rate_limit_per_second,
            self.rate_limit_per_second,
        )

    async def __aenter__(self) -> HTTPClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _prepare_request(self, request: httpx.Request) -> None:
        # Preserve bytes semantics while keeping stringified queries readable for callers.
        if request.url.query:
            request.url = _ReadableQueryURL(str(request.url))

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a GET request and return the JSON object response."""
        url = self._absolute_url(path)
        cache_key = self._cache_key("GET", url, params)

        if self.cache_ttl > 0 and cache_key in self._cache:
            return cast(dict[str, Any], self._cache[cache_key])

        response = await self._request("GET", path, params=params, headers=headers)
        data = self._json_object(response)

        if self.cache_ttl > 0 and 200 <= response.status_code < 300:
            self._cache[cache_key] = data

        return data

    async def get_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> list[Any]:
        """Run a GET request and return the JSON list response."""
        url = self._absolute_url(path)
        cache_key = self._cache_key("GET_LIST", url, params)

        if self.cache_ttl > 0 and cache_key in self._cache:
            return cast(list[Any], self._cache[cache_key])

        response = await self._request("GET", path, params=params, headers=headers)
        data = self._json_list(response)

        if self.cache_ttl > 0 and 200 <= response.status_code < 300:
            self._cache[cache_key] = data

        return data

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a POST request and return the JSON object response."""
        response = await self._request("POST", path, json=json, headers=headers)
        return self._json_object(response)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            await self._limiter.acquire()
        except ValueError as exc:
            raise self._rate_limit_error(
                "Limite de requisições excedido",
                retry_after=float(self.rate_limit_per_second),
            ) from exc

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(self._is_retryable_error),
                wait=wait_exponential(min=1, max=60),
                stop=stop_after_attempt(self.max_retries),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.request(
                        method,
                        path.lstrip("/"),
                        params=self._sorted_params(params),
                        json=json,
                        headers=headers,
                    )
                    if not 200 <= response.status_code < 300:
                        if self._is_retryable_status(response.status_code):
                            response.raise_for_status()
                        raise self._http_error(method, response)
                    return response
        except httpx.HTTPStatusError as exc:
            raise self._http_error(method, exc.response) from exc
        except httpx.RequestError as exc:
            raise self._request_error(method, exc) from exc

        raise self._http_error(method, None)

    def _absolute_url(self, path: str) -> str:
        return str(httpx.URL(self.base_url).join(path.lstrip("/")))

    def _cache_key(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
    ) -> _CacheKey:
        sorted_params = tuple(
            sorted((str(key), self._freeze(value)) for key, value in (params or {}).items())
        )
        return (method.upper(), url, sorted_params)

    def _sorted_params(self, params: dict[str, Any] | None) -> list[tuple[str, Any]] | None:
        if params is None:
            return None
        return sorted((str(key), value) for key, value in params.items())

    def _freeze(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(sorted((str(key), self._freeze(item)) for key, item in value.items()))
        if isinstance(value, list | tuple):
            return tuple(self._freeze(item) for item in value)
        if isinstance(value, set | frozenset):
            return tuple(sorted(self._freeze(item) for item in value))
        return value

    def _json_object(self, response: httpx.Response) -> dict[str, Any]:
        data = response.json()
        if isinstance(data, dict):
            return cast(dict[str, Any], data)
        raise self._http_error(
            response.request.method,
            response,
            "A resposta não é um objeto JSON válido.",
        )

    def _json_list(self, response: httpx.Response) -> list[Any]:
        data = response.json()
        if isinstance(data, list):
            return data
        raise self._http_error(
            response.request.method,
            response,
            "A resposta não é uma lista JSON válida.",
        )

    def _is_retryable_error(self, exc: BaseException) -> bool:
        if isinstance(exc, httpx.RequestError):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return self._is_retryable_status(exc.response.status_code)
        return False

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599

    def _request_error(self, method: str, exc: httpx.RequestError) -> Exception:
        request = exc.request
        url = str(request.url) if request is not None else self.base_url
        return self._make_core_error(
            "FiscalHTTPError",
            "Falha de comunicação com serviço externo",
            method=method.upper(),
            url=url,
            endpoint=url,
            status_code=None,
            details={"error": str(exc)},
        )

    def _http_error(
        self,
        method: str,
        response: httpx.Response | None,
        message: str | None = None,
    ) -> Exception:
        status_code = response.status_code if response is not None else None
        url = str(response.request.url) if response is not None else self.base_url
        response_text = response.text if response is not None else None
        return self._make_core_error(
            "FiscalHTTPError",
            message or self._status_message(status_code),
            method=method.upper(),
            url=url,
            endpoint=url,
            status_code=status_code,
            response_text=response_text,
            response_body=response_text,
            details={"response": response_text},
        )

    def _rate_limit_error(self, message: str, retry_after: float | None = None) -> Exception:
        return self._make_core_error(
            "FiscalRateLimitError",
            message,
            retry_after=retry_after,
            rate_limit_per_second=self.rate_limit_per_second,
        )

    def _status_message(self, status_code: int | None) -> str:
        messages = {
            400: "Requisição inválida",
            401: "Não autorizado",
            403: "Acesso negado",
            404: "Recurso não encontrado",
            422: "Dados inválidos",
            429: "Limite de requisições excedido",
            500: "Erro interno do servidor",
            502: "Gateway inválido",
            503: "Serviço indisponível",
            504: "Tempo limite do gateway",
        }
        if status_code is None:
            return "Falha na requisição HTTP"
        return messages.get(status_code, f"Erro HTTP {status_code}")

    def _make_core_error(self, error_name: str, message: str, **kwargs: Any) -> Exception:
        errors_module = import_module("mcp_fiscal_brasil._core.errors")
        error_cls = getattr(errors_module, error_name)
        accepted_kwargs = self._accepted_kwargs(error_cls, kwargs)

        try:
            return cast(Exception, error_cls(message=message, **accepted_kwargs))
        except TypeError:
            return cast(Exception, error_cls(message, **accepted_kwargs))

    def _accepted_kwargs(
        self, error_cls: type[Exception], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            parameters = signature(error_cls).parameters
        except (TypeError, ValueError):
            return kwargs

        if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters.values()):
            return kwargs

        return {key: value for key, value in kwargs.items() if key in parameters}
