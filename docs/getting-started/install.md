# Instalacao

## Pre-requisitos

- **Python 3.10+** (verifique com `python --version`)
- Conexao com internet (para consultar APIs publicas)

## Metodos suportados

=== "pipx (recomendado para CLI)"

    ```bash
    pipx install mcp-fiscal-brasil
    ```

    Isola o pacote em ambiente proprio. Apos instalar, `mcp-fiscal`, `mcp-fiscal-brasil` e `mcp-fiscal-api` ficam disponiveis no `PATH`.

=== "uv tool (rapido)"

    ```bash
    uv tool install mcp-fiscal-brasil
    ```

    Mesmo resultado que pipx, com [`uv`](https://docs.astral.sh/uv/) (mais rapido).

=== "pip (em um venv)"

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install mcp-fiscal-brasil
    ```

=== "Docker"

    ```bash
    # Servidor MCP via stdio
    docker run --rm -i ghcr.io/nikolasdehor/mcp-fiscal-brasil:0.2.0

    # REST API + Web UI demo
    docker run --rm -p 8000:8000 ghcr.io/nikolasdehor/mcp-fiscal-brasil:0.2.0 mcp-fiscal-api
    ```

=== "Como dependencia"

    Em `pyproject.toml`:

    ```toml
    [project]
    dependencies = [
        "mcp-fiscal-brasil>=0.2.0",
    ]
    ```

    Ou:

    ```bash
    uv add mcp-fiscal-brasil
    pip install mcp-fiscal-brasil
    ```

## Verificar a instalacao

```bash
mcp-fiscal version
# mcp-fiscal-brasil 0.2.0
```

```bash
mcp-fiscal cnpj 00000000000191
# (consulta dados publicos da empresa)
```

## Proximos passos

- [Configuracao do cliente MCP](config.md)
- [Quickstart com exemplos](quickstart.md)
