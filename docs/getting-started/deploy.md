# Hospedagem

Quer rodar o `mcp-fiscal-brasil` como servico publico ou interno? Tres opcoes pre-configuradas no repo.

## Render.com (recomendado para demo)

Free tier com 750h/mes. Servico dorme apos 15min de inatividade (cold start de ~30s ao acordar).

### Setup

1. Crie conta em [render.com](https://render.com)
2. Em **Dashboard -> New -> Blueprint**
3. Aponte para `https://github.com/nikolasdehor/mcp-fiscal-brasil`
4. Render le `render.yaml` e configura tudo automaticamente
5. Apos ~3min, voce tem URL tipo `mcp-fiscal-brasil.onrender.com`

### URL publica

- Web UI: `https://mcp-fiscal-brasil.onrender.com/`
- OpenAPI: `https://mcp-fiscal-brasil.onrender.com/docs`
- Endpoints: `https://mcp-fiscal-brasil.onrender.com/v1/...`

## Fly.io (recomendado para producao)

Free allowance pequeno mas estavel. Latencia minima do BR (region `gru` = Sao Paulo). Sempre ativo (sem cold start).

### Setup

```bash
# Instalar flyctl
brew install flyctl  # ou: curl -L https://fly.io/install.sh | sh

flyctl auth signup
flyctl launch --copy-config --no-deploy --name mcp-fiscal-brasil --region gru
flyctl deploy
```

`fly.toml` ja vem configurado no repo.

### URL publica

- `https://mcp-fiscal-brasil.fly.dev/`

## Auto-host via Docker

Em qualquer VPS com Docker:

```bash
docker run -d \
  --name mcp-fiscal \
  --restart=always \
  -p 80:8000 \
  -e MCP_FISCAL_CACHE_TTL=600 \
  -e MCP_FISCAL_RATE_LIMIT=10 \
  ghcr.io/nikolasdehor/mcp-fiscal-brasil:0.2.0 \
  mcp-fiscal-api
```

Ou via docker-compose (`docker-compose.yml` do repo):

```bash
docker compose up -d api
```

## Configuracao recomendada para producao

Independente da plataforma, em producao real:

- **`MCP_FISCAL_CACHE_BACKEND=redis`** + Redis externo (Render/Fly oferecem add-ons)
- **`MCP_FISCAL_RATE_LIMIT=20`** ou mais (ajustar pela taxa de erros das APIs publicas)
- **`MCP_FISCAL_LOG_LEVEL=INFO`** (debug so em troubleshooting)
- **Proxy reverso com auth** (Nginx + basic auth, Cloudflare Access, etc) se exposto publicamente
- **HTTPS obrigatorio** (todas as plataformas acima cobrem isso automaticamente)

## Custos esperados

| Plataforma | Plano | Custo/mes | Always-on |
|------------|-------|-----------|-----------|
| Render | Free | $0 | Nao (sleep 15min) |
| Render | Starter | US$ 7 | Sim |
| Fly.io | Free allowance | $0 | Sim (256MB) |
| Fly.io | Shared CPU | ~US$ 3 | Sim (256MB) |
| AWS EC2 t4g.nano | spot | ~US$ 2 | Sim |
| Hostinger VPS | KVM 1 | R$ 12 | Sim |
