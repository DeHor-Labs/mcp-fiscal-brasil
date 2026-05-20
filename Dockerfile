# Imagem Docker do mcp-fiscal-brasil
# Multi-stage para imagem final enxuta com uv.
#
# Build:
#   docker build -t mcp-fiscal-brasil:0.2.0 .
#
# Run (servidor MCP stdio):
#   docker run --rm -i mcp-fiscal-brasil:0.2.0
#
# Run (REST API + Web UI):
#   docker run --rm -p 8000:8000 mcp-fiscal-brasil:0.2.0 mcp-fiscal-api
#
# Run (MCP HTTP transport):
#   docker run --rm -p 8000:8000 mcp-fiscal-brasil:0.2.0 mcp-fiscal-brasil --transport http
#
# Variaveis de ambiente uteis:
#   MCP_FISCAL_HTTP_TIMEOUT=30
#   MCP_FISCAL_CACHE_TTL=300
#   MCP_FISCAL_RATE_LIMIT=10
#   HOST=0.0.0.0 PORT=8000

# ---- Build stage ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir hatchling build && \
    python -m build --wheel

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

COPY --from=builder /build/dist/*.whl ./

RUN pip install --no-cache-dir *.whl && \
    rm -f *.whl && \
    groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app && \
    chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import mcp_fiscal_brasil; print('ok')" || exit 1

# Comando padrao: servidor MCP via stdio (uso por clientes MCP nativos).
# Sobrescreva para REST API: docker run ... mcp-fiscal-api
CMD ["mcp-fiscal-brasil"]
