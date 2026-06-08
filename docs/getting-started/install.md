# Instalacao

## Pré-requisitos

- **Python 3.10+** (verifique com `python --version`)
- Conexao com internet (para consultar APIs publicas)

## Metodos suportados

=== "pipx (recomendado para CLI)"

    ```bash
    pipx install mcp-fiscal-brasil
    ```

    Isola o pacote em ambiente próprio. Apos instalar, `mcp-fiscal`, `mcp-fiscal-brasil` e `mcp-fiscal-api` ficam disponíveis no `PATH`.

=== "uv tool (rápido)"

    ```bash
    uv tool install mcp-fiscal-brasil
    ```

    Mesmo resultado que pipx, com [`uv`](https://docs.astral.sh/uv/) (mais rápido).

=== "pip (em um venv)"

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install mcp-fiscal-brasil
    ```

=== "Docker"

    ```bash
    # Servidor MCP via stdio
    docker run --rm -i ghcr.io/dehor-labs/mcp-fiscal-brasil:latest

    # REST API + Web UI demo
    docker run --rm -p 8000:8000 ghcr.io/dehor-labs/mcp-fiscal-brasil:latest mcp-fiscal-api
    ```

=== "Como dependencia"

    Em `pyproject.toml`:

    ```toml
    [project]
    dependencies = [
        "mcp-fiscal-brasil>=0.2.1",
    ]
    ```

    Ou:

    ```bash
    uv add mcp-fiscal-brasil
    pip install mcp-fiscal-brasil
    ```

## Verificar a instalação

```bash
mcp-fiscal version
# mcp-fiscal-brasil 0.2.1
```

```bash
mcp-fiscal cnpj 00000000000191
# (consulta dados publicos da empresa)
```

## Proximos passos

- [Configuracao do cliente MCP](config.md)
- [Quickstart com exemplos](quickstart.md)
