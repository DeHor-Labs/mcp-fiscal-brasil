"""Tests for the shared async HTTP client."""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mcp_fiscal_brasil._core import http as core_http
from mcp_fiscal_brasil._core.errors import FiscalHTTPError
from mcp_fiscal_brasil._core.http import HTTPClient

Handler = Callable[[httpx.Request], httpx.Response]


def patch_async_client(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    original_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(core_http.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_get_retries_500_and_fails_before_fourth_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 3:
            return httpx.Response(500, json={"erro": "temporário"})
        return httpx.Response(200, json={"ok": True})

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", max_retries=3, cache_ttl=0)

    with pytest.raises(FiscalHTTPError) as exc_info:
        await client.get("/unstable")

    assert calls == 3
    assert exc_info.value.status_code == 500
    assert exc_info.value.url == "https://example.test/unstable"


@pytest.mark.asyncio
async def test_get_retries_429_then_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"erro": "limite"})
        return httpx.Response(200, json={"ok": True})

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", max_retries=3, cache_ttl=0)

    result = await client.get("/rate-limited")

    assert result == {"ok": True}
    assert calls == 2


@pytest.mark.asyncio
async def test_get_cache_hit_returns_same_object_for_same_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"call": calls, "query": str(request.url.query)})

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", cache_ttl=300)

    first = await client.get("/cached", params={"b": "2", "a": "1"})
    second = await client.get("/cached", params={"a": "1", "b": "2"})

    assert first is second
    assert first == {"call": 1, "query": "a=1&b=2"}
    assert calls == 1


@pytest.mark.asyncio
async def test_post_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"call": calls})

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", cache_ttl=300)

    first = await client.post("/submit", json={"a": 1})
    second = await client.post("/submit", json={"a": 1})

    assert first == {"call": 1}
    assert second == {"call": 2}
    assert calls == 2


@pytest.mark.asyncio
async def test_rate_limit_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"call": calls})

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", cache_ttl=0, rate_limit_per_second=1)

    start = time.monotonic()
    first, second = await asyncio.gather(client.get("/one"), client.get("/two"))
    elapsed = time.monotonic() - start

    assert first == {"call": 1}
    assert second == {"call": 2}
    assert elapsed >= 0.9
    assert calls == 2


@pytest.mark.asyncio
async def test_get_raises_fiscal_error_on_non_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um 200 com corpo que nao e JSON valido (HTML, texto truncado etc.) deve
    virar FiscalHTTPError, nunca um json.JSONDecodeError cru."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html/>")

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", max_retries=1, cache_ttl=0)

    with pytest.raises(FiscalHTTPError) as exc_info:
        await client.get("/broken")

    assert exc_info.value.status_code == 200


@pytest.mark.asyncio
async def test_get_list_raises_fiscal_error_on_non_json_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", max_retries=1, cache_ttl=0)

    with pytest.raises(FiscalHTTPError):
        await client.get_list("/broken-list")


@pytest.mark.asyncio
async def test_get_raises_fiscal_error_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    patch_async_client(monkeypatch, handler)
    client = HTTPClient("https://example.test", max_retries=1, cache_ttl=0)

    with pytest.raises(FiscalHTTPError) as exc_info:
        await client.get("/slow")

    assert exc_info.value.status_code is None
