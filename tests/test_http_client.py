"""Testes para shared/http_client.py (FiscalHTTPClient)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_fiscal_brasil.shared.exceptions import APIError, RateLimitError, TimeoutError
from mcp_fiscal_brasil.shared.http_client import FiscalHTTPClient
from mcp_fiscal_brasil.shared.rate_limiter import SlidingWindowRateLimiter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_transport(handler):
    """Retorna um MockTransport a partir de um handler síncrono."""
    return httpx.MockTransport(handler)


def make_client(handler=None, **kwargs) -> FiscalHTTPClient:
    """Cria um FiscalHTTPClient com transporte mockado."""
    client = FiscalHTTPClient("https://test.fiscal.br", **kwargs)
    if handler is not None:
        transport = make_transport(handler)
        client._client = httpx.AsyncClient(
            base_url="https://test.fiscal.br",
            transport=transport,
            follow_redirects=True,
        )
    return client


# ---------------------------------------------------------------------------
# Inicializacao
# ---------------------------------------------------------------------------


def test_init_default_values():
    client = FiscalHTTPClient("https://api.example.com")
    assert client.base_url == "https://api.example.com"
    assert client.max_retries == 3
    assert client.backoff_factor == 1.5
    assert client.rate_limiter is None
    assert client._client is None


def test_init_strips_trailing_slash():
    client = FiscalHTTPClient("https://api.example.com/")
    assert client.base_url == "https://api.example.com"


def test_init_custom_headers():
    client = FiscalHTTPClient("https://api.example.com", headers={"X-Token": "abc"})
    assert client._default_headers["X-Token"] == "abc"
    assert client._default_headers["Accept"] == "application/json"


def test_init_with_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)
    client = FiscalHTTPClient("https://api.example.com", rate_limiter=limiter)
    assert client.rate_limiter is limiter


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_closes_client():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"ok": True})

    async with FiscalHTTPClient("https://test.fiscal.br") as client:
        transport = make_transport(handler)
        client._client = httpx.AsyncClient(
            base_url="https://test.fiscal.br",
            transport=transport,
        )
        await client.get("/ping")

    # Apos sair do context manager, _client deve estar fechado ou None
    assert client._client is None or client._client.is_closed


# ---------------------------------------------------------------------------
# GET bem-sucedido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_retorna_json_em_sucesso():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"cnpj": "12345678000195"})

    client = make_client(handler)
    result = await client.get("/cnpj/12345678000195")
    assert result == {"cnpj": "12345678000195"}


@pytest.mark.asyncio
async def test_get_retorna_texto_para_xml():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<root><item>1</item></root>",
            headers={"content-type": "application/xml; charset=utf-8"},
        )

    client = make_client(handler)
    result = await client.get("/nfe.xml")
    assert "<root>" in result


@pytest.mark.asyncio
async def test_get_retorna_texto_para_content_type_desconhecido():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"plain text",
            headers={"content-type": "application/octet-stream"},
        )

    client = make_client(handler)
    result = await client.get("/arquivo")
    assert result == "plain text"


# ---------------------------------------------------------------------------
# POST bem-sucedido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_envia_json_e_retorna_resposta():
    received_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        nonlocal received_body
        received_body = json.loads(request.content)
        return httpx.Response(200, json={"criado": True})

    client = make_client(handler)
    result = await client.post("/nfse", json={"numero": "001", "valor": 100.0})
    assert result == {"criado": True}
    assert received_body["numero"] == "001"


@pytest.mark.asyncio
async def test_post_com_data_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"bytes_recebidos": len(request.content)})

    client = make_client(handler)
    result = await client.post("/upload", data=b"payload-binario")
    assert result["bytes_recebidos"] == 15


# ---------------------------------------------------------------------------
# Retry em erros 5xx
# ---------------------------------------------------------------------------


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Cria um HTTPStatusError para simular resposta de erro do servidor."""
    request = httpx.Request("GET", "https://test.fiscal.br/path")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"Server error '{status_code}'", request=request, response=response
    )


@pytest.mark.asyncio
async def test_retry_em_500_exaure_tentativas():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise _make_http_status_error(500)

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=3)

    with patch("mcp_fiscal_brasil.shared.http_client.asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(APIError) as exc_info:
                await client.get("/falha")

    assert calls == 3
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_retry_em_502_exaure_tentativas():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise _make_http_status_error(502)

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=2)

    with patch("mcp_fiscal_brasil.shared.http_client.asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(APIError) as exc_info:
                await client.get("/gateway")

    assert calls == 2
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_retry_em_503_exaure_tentativas():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise _make_http_status_error(503)

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=2)

    with patch("mcp_fiscal_brasil.shared.http_client.asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(APIError) as exc_info:
                await client.get("/servico")

    assert calls == 2
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_retry_recupera_na_segunda_tentativa():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _make_http_status_error(500)
        # Segunda tentativa: retorna 200
        request = httpx.Request("GET", "https://test.fiscal.br/instavel")
        return httpx.Response(200, json={"ok": True}, request=request)

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=3)

    with patch("mcp_fiscal_brasil.shared.http_client.asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            result = await client.get("/instavel")

    assert result == {"ok": True}
    assert calls == 2


# ---------------------------------------------------------------------------
# Erros 4xx NAO sofrem retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_400_nao_faz_retry():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"erro": "bad request"})

    client = make_client(handler, max_retries=3)

    with pytest.raises(APIError) as exc_info:
        await client.get("/invalido")

    assert calls == 1
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_404_nao_faz_retry():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"erro": "not found"})

    client = make_client(handler, max_retries=3)

    with pytest.raises(APIError) as exc_info:
        await client.get("/recurso")

    assert calls == 1
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_422_nao_faz_retry():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(422, json={"erro": "unprocessable"})

    client = make_client(handler, max_retries=3)

    with pytest.raises(APIError) as exc_info:
        await client.get("/dados-invalidos")

    assert calls == 1
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Mapeamento de status HTTP para mensagens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mapa_401_mensagem_nao_autorizado():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    client = make_client(handler)
    with pytest.raises(APIError) as exc_info:
        await client.get("/protegido")
    assert "autorizado" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_mapa_403_mensagem_acesso_negado():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    client = make_client(handler)
    with pytest.raises(APIError) as exc_info:
        await client.get("/proibido")
    assert "negado" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_mapa_429_mensagem_muitas_requisicoes():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    client = make_client(handler)
    with pytest.raises(APIError) as exc_info:
        await client.get("/limite")
    assert "requisicoes" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_mapa_status_desconhecido():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(418, json={})

    client = make_client(handler)
    with pytest.raises(APIError) as exc_info:
        await client.get("/teapot")
    assert "418" in exc_info.value.message


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_faz_retry_e_levanta_timeout_error():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout simulado", request=MagicMock())

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(TimeoutError) as exc_info:
                await client.get("/lento")

    assert calls == 2
    assert "test.fiscal.br" in exc_info.value.endpoint


# ---------------------------------------------------------------------------
# Erro de rede (RequestError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_erro_de_rede_faz_retry_e_levanta_api_error():
    calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("conexao recusada", request=MagicMock())

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=2)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(APIError) as exc_info:
                await client.get("/offline")

    assert calls == 2
    assert "rede" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# Rate limiter integrado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limiter_chamado_antes_de_cada_tentativa():
    """Verifica que o rate limiter e consultado em cada tentativa."""
    calls_limiter = 0

    class MockLimiter:
        async def acquire(self, key: str) -> None:
            nonlocal calls_limiter
            calls_limiter += 1

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, rate_limiter=MockLimiter())
    await client.get("/com-limiter")
    assert calls_limiter == 1


@pytest.mark.asyncio
async def test_rate_limiter_erro_propagado_sem_retry():
    """RateLimitError do limiter deve ser propagada sem tentar retry HTTP."""
    http_calls = 0

    async def patched_request(*args, **kwargs):
        nonlocal http_calls
        http_calls += 1
        return httpx.Response(200, json={"ok": True})

    class BlockingLimiter:
        async def acquire(self, key: str) -> None:
            raise RateLimitError(endpoint=key, retry_after=5.0)

    client = FiscalHTTPClient("https://test.fiscal.br", rate_limiter=BlockingLimiter())

    with patch("httpx.AsyncClient.request", side_effect=patched_request):
        with pytest.raises(RateLimitError) as exc_info:
            await client.get("/bloqueado")

    assert http_calls == 0, "Nenhuma chamada HTTP deve ocorrer quando o rate limiter bloqueia"
    assert exc_info.value.retry_after == 5.0


# ---------------------------------------------------------------------------
# Backoff entre tentativas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backoff_chama_sleep_entre_tentativas():
    async def patched_request(*args, **kwargs):
        raise _make_http_status_error(500)

    client = FiscalHTTPClient("https://test.fiscal.br", max_retries=3, backoff_factor=2.0)
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("mcp_fiscal_brasil.shared.http_client.asyncio.sleep", side_effect=mock_sleep):
        with patch.object(httpx.AsyncClient, "request", side_effect=patched_request):
            with pytest.raises(APIError):
                await client.get("/instavel")

    # Deve ter chamado sleep 2 vezes (max_retries=3, sleep nas tentativas 1 e 2)
    assert len(sleep_calls) == 2
    # backoff: 2.0^0 = 1.0, 2.0^1 = 2.0
    assert sleep_calls[0] == pytest.approx(1.0)
    assert sleep_calls[1] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# close() e reutilizacao do cliente interno
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_limpa_cliente_interno():
    client = FiscalHTTPClient("https://test.fiscal.br")
    # Força criação do cliente interno
    await client._get_client()
    assert client._client is not None
    await client.close()
    assert client._client is None


@pytest.mark.asyncio
async def test_get_client_cria_novo_apos_close():
    client = FiscalHTTPClient("https://test.fiscal.br")
    first = await client._get_client()
    await client.close()
    second = await client._get_client()
    assert second is not first
    await client.close()


@pytest.mark.asyncio
async def test_close_idempotente():
    """close() pode ser chamado multiplas vezes sem erro."""
    client = FiscalHTTPClient("https://test.fiscal.br")
    await client.close()  # sem cliente criado
    await client.close()  # idem
