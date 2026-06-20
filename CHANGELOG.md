# Changelog

## [0.4.0] - 2026-06-20

Onda 2: modulo NF-e completo (parse, DANFE, assinatura, distribuicao, manifestacao) e
simulador da transicao tributaria IBS/CBS (Reforma Tributaria 2026-2033). Total de tools
sobe de 36 para 42.

### Added

#### Simulador da Reforma Tributaria IBS/CBS (modulo `agentic.reforma`)

- `simular_transicao_reforma_tributaria` - simula o impacto financeiro da transicao
  tributaria entre 2026 e 2033 para um produto dado. Recebe valor bruto, aliquota atual
  de PIS/COFINS/ISS/ICMS e CNAE, retorna tabela anual com aliquotas IBS/CBS por fase,
  carga tributaria comparada (atual vs. nova) e economia/custo estimado por ano.
  Sem API key, offline. Fonte: LC 214/2025 e Resolucao Comite Gestor CG-IBS n. 1/2025.

#### Normalizacao auxiliar (modulo `agentic.reforma`)

- Helpers internos `normalizar_aliquota_atual` e `normalizar_regime` para canonicalizacao
  de inputs antes do calculo - garantem que entradas em percentual (ex: 12 vs 0.12) e
  strings de regime (simples, lucro_presumido, lucro_real) sejam tratadas uniformemente.

#### Parse e DANFE offline (modulo `nfe`)

- `parse_nfe_xml` - parseia XML bruto de NF-e ou NFC-e e retorna dados estruturados
  (emitente, destinatario, itens, totais, protocolo). Sem API key, offline.
- `gerar_danfe` - gera DANFE PDF (A4, modelo 55) a partir do XML. Retorna base64.
  Sem API key, offline. Requer namespace `http://www.portalfiscal.inf.br/nfe`.
  Modelo 65 (NFC-e) nao suportado na v1.0.0 da lib brazilfiscalreport.
- `validar_assinatura_nfe` - valida assinatura XMLDSig e extrai dados do certificado
  assinante (titular, CNPJ/CPF, validade, AC emissora). Sem API key, offline.
  Suporte opcional a CA bundle PEM para validar cadeia ICP-Brasil.

#### Distribuicao e manifestacao com certificado A1 (opt-in)

- `baixar_nfe_distribuicao` - baixa documentos via NFeDistribuicaoDFe (SEFAZ) usando
  certificado A1 local (.pfx/.p12). Suporta distNSU, consNSU e consChNFe.
  O certificado nunca e enviado a servidores externos - autenticacao mTLS local.
- `manifestar_nfe` - registra manifestacao do destinatario via NFeRecepcaoEvento.
  Eventos: 210200 (Ciencia), 210210 (Confirmacao), 210220 (Desconhecimento),
  210240 (Operacao nao Realizada). Assinatura XMLDSig feita localmente.

#### Novas dependencias

- `brazilfiscalreport==1.0.0` - geracao de DANFE PDF
- `signxml>=4.5.1` - validacao e assinatura XMLDSig
- `cryptography>=48.0.1` - manipulacao de certificados X.509 e PKCS12

### Security

- Toda entrada XML externa e validada via `parse_xml()` (lxml com
  `resolve_entities=False`, `no_network=True`) antes de ser entregue a
  brazilfiscalreport, que usa `xml.etree` sem protecao XXE propria.
- Senhas de certificados A1 nunca aparecem em logs, excecoes ou disco persistente.
- Arquivos PEM temporarios criados com permissao 0600 e removidos no bloco `finally`.

## [0.3.1] - 2026-06-18

### Fixed

- Corrige `mcp-name` no README para `io.github.DeHor-Labs/mcp-fiscal-brasil` (case correto da org no GitHub), necessario para validacao de ownership no registry oficial MCP.
- Corrige namespace no `server.json` para `io.github.DeHor-Labs/mcp-fiscal-brasil`.

## [0.3.0] - 2026-06-17

Onda 1: expansao de tabelas fiscais offline, indexadores do Banco Central e exposicao
de seis novos modulos no servidor MCP. Total de tools sobe de 20 para 36.

### Added

#### Tabelas fiscais offline (modulo `tabelas`)
- `consultar_ncm` - lookup de codigo NCM na TIPI (banco SQLite bundled, offline)
- `consultar_cfop` - descricao e natureza de operacao por codigo CFOP
- `validar_cst` - validacao de Codigo de Situacao Tributaria (CST/CSOSN)
- `consultar_cest` - consulta de codigo CEST por produto
- `consultar_aliquota_icms` - aliquota interestadual ICMS/DIFAL por par de UFs
- Script `scripts/build_tabelas_db.py` para popular o banco com a TIPI completa oficial

#### Indexadores BCB (modulo `bcb`)
- `taxa_selic` - taxa Selic vigente via SGS Banco Central
- `ipca_periodo` - acumulado IPCA em intervalo de datas via SGS
- `ptax_data` - cotacao PTAX de compra/venda em data especifica via OData BCB
- `calcular_correcao_monetaria` - correcao monetaria de valor entre duas datas pelo IPCA

#### Novos modulos expostos no servidor MCP
- `cep` - `consultar_cep` via BrasilAPI (ja existia no SDK, agora exposto como tool MCP)
- `cnae` - `consultar_cnae` e `buscar_cnae` via BrasilAPI/IBGE
- `ibge` - `consultar_municipios_ibge` e `consultar_estado_ibge` via IBGE Localidades
- `mei` - `consultar_status_mei` via BrasilAPI
- `empresa` - `consultar_empresa_completa` com dados CNPJ + Simples em paralelo

#### Descriptions Glama aplicadas em todas as 16 tools novas
- Padrao: Purpose, quando usar vs nao usar, comportamento offline/online, Parameter Semantics
- Tools existentes melhoradas: `listar_cnpjs_por_nome`, `analyze_cnpj_compliance`,
  `risk_score_supplier`, `consultar_empresas_lote`

#### Metadata para registries MCP (PR #51)
- `server.json` atualizado com description rica, tags completas e campo `_meta` no
  formato do registry oficial (io.modelcontextprotocol.registry/publisher-provided)
- `pyproject.toml` com keywords expandidos para melhor discoverability no PyPI:
  `brazil`, `icms`, `simples-nacional`, `ncm`, `cfop`, `tax`, `finance`, `government`
- `smithery.yaml` com cabecalho de pitch e descriptions mais claras
- README atualizado com tagline destacando 36 ferramentas e suporte a Reforma Tributaria 2026

#### Empacotamento
- Arquivos `*.db` das tabelas fiscais incluidos no wheel via `hatch.build.targets.wheel`

### Changed

- Total de tools MCP: **36** (era 20 antes da Onda 1)
- Cobertura de testes: **327 testes** passando (era ~117 na v0.2.2)

### Fixed

- Corrige inversão das alíquotas de ICMS interestadual (Resolução do Senado Federal
  n. 22/1989): operações com origem em Sul/Sudeste exceto ES (SP, RJ, MG, PR, RS, SC)
  para destinos N/NE/CO/ES retornam 7%, e as demais retornam 12%, conforme a norma.
  O bug afetava `consultar_aliquota_icms` e o cálculo de DIFAL. (#54)
- Workflow `welcome.yml`: inputs da `actions/first-interaction@v3` corrigidos de hifens
  (`repo-token`, `issue-message`, `pr-message`) para underscores (`repo_token`,
  `issue_message`, `pr_message`), que e o padrao exigido pela v3 da action

## [0.2.2] - 2026-06-08

Release de consolidação dos fluxos agenticos fiscais e da publicação do pacote.

### Added
- `consultar_empresas_lote` para triagem em lote de fornecedores com compliance, score e erros por CNPJ.
- Documentação de posicionamento, casos de uso e catálogo agentico v0.2.x.
- Cobertura de testes para validação de NFSe, sandbox de arquivos da API e path traversal relativo.

### Changed
- Repositório, docs e metadados migrados para `DeHor-Labs/mcp-fiscal-brasil`.
- Workflows do GitHub Actions atualizados para versões mais novas de `checkout`, `setup-python`, `cache`, `first-interaction` e `dependabot/fetch-metadata`.
- Exemplos de Docker e instalação atualizados para a versão `0.2.2`.

### Fixed
- Validação de CNPJ nos endpoints REST antes de chamar serviços externos.
- Restrição de caminhos de NFe/SPED a um diretório base configurável com permissão restritiva.
- Validação de entradas NFSe e padronização do campo `numero`.
- Processamento em lote com concorrência controlada, limite de lote e logs estruturados de falha.

## [0.2.1] - 2026-05-29

### Changed

- Ajuste de consistência de release metadata entre `pyproject.toml`, `server.json` e `npm-wrapper/package.json` (todos com versão `0.2.1`).
- Corrigida a documentação de histórico de releases para incluir uma entrada de `0.2.1` com foco em alinhamento de versionamento e integridade de artefatos.

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
- `cpf/` - validação algoritmica offline
- `simples/` - regime Simples Nacional
- `mei/` - status MEI
- `ibge/` - municipios, UFs, códigos IBGE
- `cep/` - lookup de endereço por CEP
- `empresa/` - dados consolidados de empresa
- `certidoes/` - geracao de URLs de certidoes (CND, FGTS, CNDT)

#### Fase 3 - Tools agenticas (`agentic/`)
- `analyze_cnpj_compliance` - relatório consolidado (CNPJ + Simples + MEI + CNAE) com score 0-100 e risco classificado
- `compare_tax_regimes` - comparativo MEI/Simples/Lucro Presumido/Lucro Real com alíquota efetiva e imposto estimado
- `risk_score_supplier` - due diligence de fornecedor com recomendação (aprovar/aprovar_com_ressalvas/investigar/recusar)
- `validate_nfe_full` - validação consolidada de NFe (parse XML + chave + situação do emissor)
- `summarize_sped` - sumário executivo de arquivo SPED

#### Fase 4 - Multiplas interfaces
- **CLI** (`mcp-fiscal`) - typer com comandos cnpj, cpf, cep, simples, municipio, compliance, supplier, regimes. Flag `--json`.
- **REST API** (`mcp-fiscal-api`) - FastAPI com endpoints `/v1/*` e OpenAPI docs em `/docs`
- **Web UI demo** - rota `/` da API com pagina htmx 2.0 (CNPJ lookup, compliance, comparativo de regimes)
- **npm wrapper** (`mcp-fiscal-brasil` no npm) - TypeScript que spawna o CLI Python para uso em apps Node.js

#### Fase 5 - Docker e release
- Dockerfile multi-stage com healthcheck e usuário não-root
- docker-compose com profiles para API e MCP HTTP
- Bump v0.1.1 -> v0.2.0

### Changed
- Author corrigido para "Nikolas de Hor" (era "Nikolas DeHor")
- Modulos legados (cnpj, nfe, sped) refatorados para usar `_core`
- Suite de testes expandida para **117 testes** (era ~70)

### Quality gates
- `mypy --strict`: limpo no código novo
- `ruff check` + `ruff format`: limpos
- Cobertura: 80%+ no código novo



### Added
- 8 modules: CNPJ, CPF, NFe, NFSe, Simples Nacional, SPED, eSocial, Certidoes
- 14 MCP tools for fiscal queries via natural language
- SDK mode: FiscalBrasil class for direct Python integration
- 5 integration examples: basic, FastAPI, Django, batch validation, ERP
- NFe fallback chain: BrasilAPI -> Portal Nacional -> partial key data
- eSocial catalog expanded to 45+ events (S-1.0 complete)
- NFSe coverage expanded to 50+ municipalities (all state capitals + major cities)
- CI/CD: GitHub Actions (lint, test, publish PyPI), Docker, pré-commit
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
