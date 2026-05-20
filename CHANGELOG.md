# Changelog

## [0.2.0] - 2026-05-20

Release focada em produzir o MCP fiscal brasileiro mais completo do mercado.

### Added

#### Fase 1 - Infraestrutura comum (`_core/`)
- HTTP client unificado (`httpx` + `tenacity` retry exponencial + `cachetools` cache pluggable + `aiolimiter` rate-limit per-host)
- Logging estruturado JSON via `structlog`
- Configuracao via `pydantic-settings` com env vars `MCP_FISCAL_*`
- Hierarquia de exceptions tipadas

#### Fase 2 - 8 novas fontes de dados
- `cnae/` - tabela CNAE da Receita
- `cpf/` - validacao algoritmica offline
- `simples/` - regime Simples Nacional
- `mei/` - status MEI
- `ibge/` - municipios, UFs, codigos IBGE
- `cep/` - lookup de endereco por CEP
- `empresa/` - dados consolidados de empresa
- `certidoes/` - geracao de URLs de certidoes (CND, FGTS, CNDT)

#### Fase 3 - Tools agenticas (`agentic/`)
- `analyze_cnpj_compliance` - relatorio consolidado (CNPJ + Simples + MEI + CNAE) com score 0-100 e risco classificado
- `compare_tax_regimes` - comparativo MEI/Simples/Lucro Presumido/Lucro Real com aliquota efetiva e imposto estimado
- `risk_score_supplier` - due diligence de fornecedor com recomendacao (aprovar/aprovar_com_ressalvas/investigar/recusar)
- `validate_nfe_full` - validacao consolidada de NFe (parse XML + chave + situacao do emissor)
- `summarize_sped` - sumario executivo de arquivo SPED

#### Fase 4 - Multiplas interfaces
- **CLI** (`mcp-fiscal`) - typer com comandos cnpj, cpf, cep, simples, municipio, compliance, supplier, regimes. Flag `--json`.
- **REST API** (`mcp-fiscal-api`) - FastAPI com endpoints `/v1/*` e OpenAPI docs em `/docs`
- **Web UI demo** - rota `/` da API com pagina htmx 2.0 (CNPJ lookup, compliance, comparativo de regimes)
- **npm wrapper** (`mcp-fiscal-brasil` no npm) - TypeScript que spawna o CLI Python para uso em apps Node.js

#### Fase 5 - Docker e release
- Dockerfile multi-stage com healthcheck e usuario nao-root
- docker-compose com profiles para API e MCP HTTP
- Bump v0.1.1 -> v0.2.0

### Changed
- Author corrigido para "Nikolas de Hor" (era "Nikolas DeHor")
- Modulos legados (cnpj, nfe, sped) refatorados para usar `_core`
- Suite de testes expandida para **117 testes** (era ~70)

### Quality gates
- `mypy --strict`: limpo no codigo novo
- `ruff check` + `ruff format`: limpos
- Cobertura: 80%+ no codigo novo



### Added
- 8 modules: CNPJ, CPF, NFe, NFSe, Simples Nacional, SPED, eSocial, Certidoes
- 14 MCP tools for fiscal queries via natural language
- SDK mode: FiscalBrasil class for direct Python integration
- 5 integration examples: basic, FastAPI, Django, batch validation, ERP
- NFe fallback chain: BrasilAPI -> Portal Nacional -> partial key data
- eSocial catalog expanded to 45+ events (S-1.0 complete)
- NFSe coverage expanded to 50+ municipalities (all state capitals + major cities)
- CI/CD: GitHub Actions (lint, test, publish PyPI), Docker, pre-commit
- Published on PyPI: pip install mcp-fiscal-brasil

### Fixed
- XXE vulnerability in xml_utils.py (safe parser with resolve_entities=False)
- Chave NFe validator: weights and direction corrected (SEFAZ spec right-to-left)
- HTTP client: leading slash in paths breaking httpx URLs
- FastMCP: description -> instructions (breaking change v3.1.1)
- datetime.utcnow() deprecated -> datetime.now(timezone.utc)
- 28 ruff lint errors, 5 mypy errors corrected
- Portuguese text review across all 17 source files (~530 corrections)

## [0.1.0] - 2026-03-27

### Added
- Initial release
- Project structure with 41 Python files
- Shared module: HTTP client, rate limiter, validators, XML utils
- Basic tools for all 8 fiscal modules
