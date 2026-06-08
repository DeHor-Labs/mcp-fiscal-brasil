# REST API

API HTTP via FastAPI. Util para integrações que não falam MCP (frontends, no-code, microservicos legados).

## Executar

```bash
mcp-fiscal-api
# http://localhost:8000
```

Por padrao escuta em `127.0.0.1:8000`. Para produção:

```bash
HOST=0.0.0.0 PORT=8080 mcp-fiscal-api
```

Ou direto via uvicorn:

```bash
uvicorn mcp_fiscal_brasil.api:app --host 0.0.0.0 --port 8080 --workers 4
```

## OpenAPI docs

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- JSON spec: `http://localhost:8000/openapi.json`

## Endpoints

### Meta

- `GET /health` - status do serviço

### Modulos

- `GET /v1/cnpj/{cnpj}` - dados cadastrais
- `GET /v1/cpf/{cpf}` - validação de CPF
- `GET /v1/cep/{cep}` - endereço por CEP
- `GET /v1/simples/{cnpj}` - Simples Nacional
- `GET /v1/ibge/municipio/{código}` - municipio IBGE
- `GET /v1/nfe/chave/{chave}` - válida chave NFe

### Agentic

- `GET /v1/agentic/compliance/{cnpj}` - relatório consolidado
- `GET /v1/agentic/supplier/{cnpj}` - due diligence
- `GET /v1/agentic/regimes` - comparativo de regimes
- `POST /v1/nfe/validate` - validação consolidada NFe (XML)
- `POST /v1/sped/summarize` - sumário executivo SPED

## Web UI

A rota `/` serve uma pagina htmx 2.0 com três demos interativas (CNPJ lookup, compliance, comparativo de regimes). Veja [Web UI](web-ui.md).

## Producao

### Docker

```bash
docker run --rm -p 8000:8000 \
  -e MCP_FISCAL_CACHE_BACKEND=sqlite \
  -e MCP_FISCAL_RATE_LIMIT=20 \
  ghcr.io/dehor-labs/mcp-fiscal-brasil:latest \
  mcp-fiscal-api
```

### Compose com Redis

Veja `docker-compose.yml` no repo. Para habilitar Redis, descomente o serviço `redis` e mude:

```yaml
environment:
  MCP_FISCAL_CACHE_BACKEND: redis
  MCP_FISCAL_REDIS_URL: redis://redis:6379/0
```

### Atras de proxy reverso (Nginx)

```nginx
location /api/fiscal/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

## Autenticacao

A v0.2.x não implementa autenticação na API. **Não exponha publicamente sem layer de auth** (proxy com auth básica, OAuth, ou API gateway). Para uso interno na sua rede, esta seguro.
