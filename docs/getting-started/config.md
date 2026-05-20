# Configuracao

## Variaveis de ambiente

Todas opcionais, com defaults razoaveis.

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `MCP_FISCAL_HTTP_TIMEOUT` | `30` | Timeout HTTP em segundos |
| `MCP_FISCAL_MAX_RETRIES` | `3` | Maximo de retries por requisicao |
| `MCP_FISCAL_CACHE_TTL` | `300` | TTL do cache em segundos |
| `MCP_FISCAL_RATE_LIMIT` | `10` | Requests por segundo (por host) |
| `MCP_FISCAL_CACHE_BACKEND` | `memory` | `memory`, `sqlite` ou `redis` |
| `MCP_FISCAL_REDIS_URL` | - | URL do Redis (se `cache_backend=redis`) |
| `MCP_FISCAL_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Exemplo `.env`:

```bash
MCP_FISCAL_HTTP_TIMEOUT=60
MCP_FISCAL_CACHE_TTL=3600
MCP_FISCAL_RATE_LIMIT=5
MCP_FISCAL_LOG_LEVEL=DEBUG
```

## Cliente MCP

### Claude Desktop

Adicione em `claude_desktop_config.json`:

=== "macOS / Linux"

    Arquivo: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `~/.config/Claude/claude_desktop_config.json` (Linux).

    ```json
    {
      "mcpServers": {
        "fiscal-brasil": {
          "command": "mcp-fiscal-brasil",
          "args": []
        }
      }
    }
    ```

=== "Windows"

    Arquivo: `%APPDATA%\Claude\claude_desktop_config.json`.

    ```json
    {
      "mcpServers": {
        "fiscal-brasil": {
          "command": "mcp-fiscal-brasil.exe",
          "args": []
        }
      }
    }
    ```

Reinicie o Claude Desktop. O servidor aparece como `fiscal-brasil` com 20+ ferramentas.

### Claude Code (CLI)

```bash
claude mcp add fiscal-brasil mcp-fiscal-brasil
```

### Cursor

Adicione em Settings -> MCP Servers:

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "mcp-fiscal-brasil"
    }
  }
}
```

### Outros clientes MCP

Qualquer cliente compativel com MCP funciona. O servidor expoe via stdio por padrao. Para HTTP transport:

```bash
mcp-fiscal-brasil --transport http --port 8000
```

## Cache em producao

Em producao, prefira `sqlite` ou `redis`:

```bash
MCP_FISCAL_CACHE_BACKEND=sqlite
# armazena em ~/.cache/mcp-fiscal-brasil.db

MCP_FISCAL_CACHE_BACKEND=redis
MCP_FISCAL_REDIS_URL=redis://localhost:6379/0
```

## Logs estruturados

Em producao, logs sao emitidos como JSON via `structlog`:

```json
{
  "event": "cnpj_lookup_started",
  "cnpj": "12345678000190",
  "timestamp": "2026-05-20T10:30:00Z",
  "level": "info"
}
```

Ideal para parsing em Loki, Datadog, CloudWatch, etc.
