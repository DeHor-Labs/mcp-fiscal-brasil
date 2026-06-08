# Contribuir

Contribuicoes são bem-vindas! Algumas formas de ajudar:

## Formas de contribuir

- **Issues**: reporte bugs ou peca features em [github.com/DeHor-Labs/mcp-fiscal-brasil/issues](https://github.com/DeHor-Labs/mcp-fiscal-brasil/issues)
- **Pull requests**: fork, branch, PR
- **Documentacao**: melhorias na doc são MUITO bem-vindas
- **Casos de uso**: compartilhe como você usa o `mcp-fiscal-brasil` em projetos reais

## Setup de desenvolvimento

```bash
git clone https://github.com/DeHor-Labs/mcp-fiscal-brasil
cd mcp-fiscal-brasil

# Instalar uv (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup
uv sync --all-extras
```

## Comandos úteis

```bash
# Testes
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy --strict src/

# Build
uv build

# Site de docs local
uv run mkdocs serve
```

## Padroes

- **Estilo**: PEP 8 + ruff format
- **Tipos**: mypy --strict, type hints em todas as funções publicas
- **Testes**: pytest, cobertura mínima 80% em novo código
- **Mensagens de commit**: imperativo curto, sem AI footers (`Co-Authored-By`, `Generated with Claude` etc)
- **Portugues**: pt-BR com acentos corretos em strings/docs user-facing. Codigo e comentários em ingles.

## Estrutura de PR

1. Branch a partir de `main`
2. Commits pequenos e atomicos
3. Testes para mudancas funcionais
4. Atualize CHANGELOG.md
5. PR com descrição clara do que muda e por que

## Codigo de conduta

Seja respeitoso. Foco no código, não na pessoa. Sem toxicidade.
