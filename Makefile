.PHONY: dev install test lint format typecheck build serve check check-release-metadata clean

# Instala dependencias de desenvolvimento
dev:
	pip install -e ".[dev]"
	pre-commit install

# Instala apenas dependencias de producao
install:
	pip install -e .

# Roda os testes
test:
	pytest tests/ -v

# Roda testes com cobertura
test-cov:
	pytest tests/ -v --cov=src/mcp_fiscal_brasil --cov-report=html

# Lint com ruff
lint:
	ruff check src/ tests/

# Formata codigo com ruff
format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Checa tipos com mypy
typecheck:
	mypy src/

# Lint + typecheck
check: lint typecheck

# Valida metadados de release/versionamento
check-release-metadata:
	@python scripts/check_release_metadata.py

# Build do pacote
build:
	python -m build

# Inicia o servidor MCP localmente (stdio)
serve:
	python -m mcp_fiscal_brasil.server

# Remove arquivos gerados
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/ *.egg-info/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
