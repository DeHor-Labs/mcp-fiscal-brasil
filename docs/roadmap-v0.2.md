# Roadmap v0.2.0 - Discovery Fase 0

Este documento consolida a descoberta técnica do estado atual do `mcp-fiscal-brasil` e define um plano de evolução para a versão `v0.2.0`. A análise considerou `src/mcp_fiscal_brasil/`, `pyproject.toml`, `tests/`, `examples/`, `docs/`, `README.md`, `CHANGELOG.md`, Docker, Smithery e workflows do GitHub Actions.

## 1. Estado Atual (v0.1.x)

### Módulos existentes

- `mcp_fiscal_brasil.server`: registra 14 ferramentas FastMCP e expõe transportes `stdio`, `sse`, `http` e `streamable-http`.
  Falta padronizar tratamento de erro por ferramenta, documentar transportes reais no README e adicionar testes dos wrappers FastMCP.

- `mcp_fiscal_brasil.sdk`: oferece a fachada `FiscalBrasil` para uso direto em Python, com CNPJ, CPF, NFe, SEFAZ, Simples, SPED, NFSe portal e eSocial.
  Falta paridade com todas as ferramentas MCP, incluindo certidões, `validar_evento_esocial` e `listar_registros_sped`, além de alinhar nomes dos métodos com os exemplos.

- `mcp_fiscal_brasil.shared`: concentra schemas base, exceções, validadores, constantes, XML seguro, cliente HTTP e rate limiter em memória.
  Falta cache, métricas, jitter, circuit breaker, configuração por ambiente, cliente HTTP reutilizável por domínio e testes diretos de HTTP, XML e rate limit.

- `mcp_fiscal_brasil.cnpj`: consulta dados cadastrais por CNPJ via BrasilAPI e usa ReceitaWS como fallback.
  Falta busca real por nome, filtros por CNAE, UF, porte e situação, enriquecimento por Inscrição Estadual e testes determinísticos dos fluxos HTTP.

- `mcp_fiscal_brasil.cpf`: válida CPF matematicamente de forma offline.
  Falta deixar explícito que não há consulta cadastral pública segura para CPF e que qualquer consulta de situação cadastral exigiria fonte oficial autenticada ou decisão legal.

- `mcp_fiscal_brasil.nfe`: válida chave NFe, consulta BrasilAPI, tenta Portal Nacional NFe e retorna dados parciais extraídos da chave quando as fontes falham.
  Falta integração SOAP SEFAZ com certificado digital, distribuição de DF-e, eventos, cancelamento, validação XSD e testes completos de XML com namespace e protocolo.

- `mcp_fiscal_brasil.nfse`: retorna orientação e portal de consulta para 50 ou mais municípios, com fallback para o Portal Nacional NFSe.
  Falta cliente real por provedor municipal, suporte ABRASF, autenticação, parsing de respostas e normalização de nomes acentuados, por exemplo Goiânia.

- `mcp_fiscal_brasil.simples`: consulta opção pelo Simples Nacional e MEI via BrasilAPI.
  Falta separar semântica de Simples e MEI, lidar com fontes alternativas, expor histórico, explicar defasagem dos dados e remover menção não implementada a cálculo DAS.

- `mcp_fiscal_brasil.sped`: analisa texto SPED pipe-delimitado, identifica registro `0000`, período, empresa, contagem de registros e registros por tipo.
  Falta validação por leiaute, regras por bloco, conferência de encerramentos e totais, análise de EFD-Contribuições, ECD e ECF além da estrutura básica.

- `mcp_fiscal_brasil.esocial`: mantém catálogo hard-coded de eventos e válida XML básico.
  Falta catálogo versionado, validação XSD, assinatura, envio, consulta de recibos, retorno oficial e identificação precisa do código `S-*` a partir do XML.

- `mcp_fiscal_brasil.certidoes`: orienta consulta de CND federal e CRF FGTS com URLs oficiais e válida CPF/CNPJ de entrada.
  Falta automação real de emissão ou verificação, suporte CNDT trabalhista, uso do schema `CertidaoResponse` e definição clara do que depende de CAPTCHA, gov.br ou certificado.

### Cobertura de testes atual

- A suíte possui 50 testes coletáveis; 48 testes offline ou mockados foram reportados como passando, com 2 testes permissivos que podem chamar BrasilAPI ou SEFAZ.
- Estimativa por leitura: cobertura efetiva entre 30% e 40% do pacote, concentrada em validadores, schemas, CPF, parte de CNPJ, parte de NFe e SPED básico.
- Gaps fortes: `sdk.py`, `server.py`, `shared.http_client`, `shared.rate_limiter`, `shared.xml_utils`, `simples`, `nfse`, `certidoes`, `esocial`, fallback ReceitaWS e fluxos de erro HTTP.
- Os exemplos são bons como documentação prática, mas misturam retornos como dict com métodos que hoje retornam modelos Pydantic.

### APIs e fontes externas já integradas

- BrasilAPI: `https://brasilapi.com.br/api/cnpj/v1/{cnpj}`, `https://brasilapi.com.br/api/nfe/v1/{chave}`, `https://brasilapi.com.br/api/nfe/v1/status/{uf}` e `https://brasilapi.com.br/api/simples/v1/{cnpj}`.
- ReceitaWS: `https://receitaws.com.br/v1/cnpj/{cnpj}` como fallback de CNPJ.
- Portal Nacional NFe: `https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx`, usado como tentativa de consulta pública.
- Portais NFSe municipais: tabela estática de URLs, incluindo fallback `https://www.nfse.gov.br/consultapublica`.
- Certidões: URLs informativas da Receita Federal, e-CAC, CAIXA CRF e Conectividade Social, sem automação de emissão.

## 2. Gaps Identificados

### Fontes fiscais e tributárias ausentes

- CNAE oficial do IBGE via `https://servicodados.ibge.gov.br/api/v2/cnae`, útil para busca por código, descrição, classe, subclasse e notas explicativas.
- Municípios e códigos IBGE via `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`, essencial para normalizar NFSe, SPED e endereços de empresas.
- Consulta CNPJ oficial via Conecta Gov/Serpro, como `https://apigateway.conectagov.estaleiro.serpro.gov.br/api-cnpj-empresa/v2/empresa/`, que exige autorização institucional.
- CNPJá API pública `https://open.cnpja.com/office/{cnpj}`, que agrega CNPJ, Simples, SIMEI, SUFRAMA e Cadastro de Contribuintes, com limite público documentado de 5 consultas por minuto por IP.
- Inscrição Estadual via SINTEGRA e portais estaduais, sem API pública nacional padronizada.
- Junta Comercial e Redesim, com portais públicos e fluxos por UF, mas sem API pública aberta e uniforme para contrato social, NIRE ou viabilidade.
- Certidão trabalhista CNDT via TST em `https://cndt-certidao.tst.jus.br/consultarCertidao.faces`, com serviço web público orientado a navegador.
- CND federal via Conecta Gov e portais da Receita/PGFN, com automação condicionada a autorização, CAPTCHA, gov.br ou certificado digital.

### Funcionalidades ausentes em módulos atuais

- CNPJ: busca avançada, lote, enriquecimento por CNAE e município, cache de respostas, fonte secundária com dados de IE e SUFRAMA.
- CPF: validação já existe, mas falta política explícita para não consultar dados pessoais sem fonte legal adequada.
- NFe: validação XSD, consulta com certificado, distribuição de documentos fiscais eletrônicos, eventos, cancelamento e parsing completo.
- NFSe: módulos por provedor, normalização de município por código IBGE, suporte ABRASF e detecção de sistema municipal.
- Simples/MEI: histórico, fonte alternativa, separação de modelo de resposta e indicadores de defasagem.
- SPED: validação por bloco, totais, cruzamentos, severidade de erros e relatórios amigáveis para LLM.
- eSocial: catálogo versionado em dados externos, validação XSD e mapeamento real de evento.
- Certidões: CNDT, verificação de certidão emitida, status normalizado e estratégia de autenticação.

### Gaps de infraestrutura

- Cache: não há cache local, TTL por fonte, armazenamento persistente ou cache stale-while-revalidate.
- Retry: existe retry com backoff, mas sem jitter, sem política por status, sem `Retry-After` e sem circuit breaker.
- Rate limiting: existe janela deslizante em memória, mas não há distribuição entre processos, configuração por fonte ou integração com headers de limite.
- Observabilidade: logs são básicos; faltam métricas, spans, contadores por fonte, latência, taxa de erro e correlação por request.
- Configuração: README cita variáveis não consumidas pelo código, como `MCP_FISCAL_LOG_LEVEL`, `BRASILAPI_BASE_URL` e `HTTP_TIMEOUT`.
- Segurança: falta política de privacidade de dados fiscais, redaction em logs, limites de payload e documentação de fontes sensíveis.

### Interfaces ausentes

- CLI humana dedicada para consultas fiscais, separada do comando MCP atual.
- REST API FastAPI com OpenAPI, autenticação opcional e endpoints estáveis.
- Web UI demo para testar ferramentas sem cliente MCP.
- Wrapper npm para instalação e execução em ecossistemas Node.
- Documentação de SDK alinhada aos nomes reais dos métodos e aos tipos Pydantic retornados.

## 3. Roadmap v0.2.0 - 5 Fases

### Fase 1: Infraestrutura Comum

Objetivo: consolidar a base compartilhada antes de expandir fontes. Esta fase deve preservar o padrão atual de `tools.py`, `client.py` e `schemas.py`, mas mover comportamento transversal para `shared`.

Arquivos a criar ou alterar:

- Criar `src/mcp_fiscal_brasil/shared/config.py`: carregar configurações por ambiente com `pydantic-settings` ou `os.environ`; expor `FiscalSettings`, timeouts, base URLs, TTLs, log level e limites por fonte.
- Criar `src/mcp_fiscal_brasil/shared/cache.py`: implementar `AsyncTTLCache`, chaves determinísticas, TTL por fonte, limite de tamanho e modo stale em falhas temporárias.
- Alterar `src/mcp_fiscal_brasil/shared/http_client.py`: aceitar política de retry por fonte, respeitar `Retry-After`, adicionar jitter, headers de request id, cache opcional e métricas por chamada.
- Criar `src/mcp_fiscal_brasil/shared/retry.py`: conter `RetryPolicy`, `RetryDecision`, cálculo de backoff e status retriáveis.
- Criar `src/mcp_fiscal_brasil/shared/metrics.py`: expor `MetricsRecorder`, `NoopMetricsRecorder`, contadores de sucesso, erro, cache hit, cache miss e latência.
- Alterar `src/mcp_fiscal_brasil/shared/rate_limiter.py`: tornar limites configuráveis por fonte e permitir política `wait` ou `raise` quando exceder limite.
- Alterar `src/mcp_fiscal_brasil/shared/exceptions.py`: adicionar `ConfigurationError`, `SourceUnavailableError`, `UnsupportedSourceError`, `ComplianceError` e campos de fonte, endpoint e ação recomendada.
- Criar `tests/test_http_client.py`, `tests/test_cache.py`, `tests/test_retry.py`, `tests/test_metrics.py`, `tests/test_config.py`: cobrir sucesso, erro, cache, rate limit, retry e redaction.

Classes e funções principais:

- `FiscalSettings.from_env()`
- `AsyncTTLCache.get_or_set()`
- `RetryPolicy.should_retry()`
- `FiscalHTTPClient.request_json()`
- `MetricsRecorder.record_http_call()`
- `SourceUnavailableError.from_response()`

### Fase 2: Expansão de Fontes de Dados

Objetivo: adicionar 8 módulos de dados, entre novos pacotes e expansões de pacotes existentes, com fonte, autenticação e risco claramente documentados.

1. `src/mcp_fiscal_brasil/cnae/`
   - Fonte alvo: IBGE CNAE `https://servicodados.ibge.gov.br/api/v2/cnae`.
   - Autenticação: nenhuma documentada.
   - Limite: não publicado; usar limite conservador local de 5 req/s e cache longo, pois a classificação muda pouco.
   - Retorno: seções, divisões, grupos, classes, subclasses, atividades e observações explicativas.
   - Arquivos: `client.py`, `schemas.py`, `tools.py`, `__init__.py`.

2. `src/mcp_fiscal_brasil/cpf/` expandido
   - Fonte alvo: validação matemática offline como padrão; consulta cadastral remota somente após decisão legal e fonte autenticada.
   - Autenticação: nenhuma para validação offline.
   - Limite: não aplicável.
   - Retorno: CPF normalizado, validade, motivo, risco de sequência repetida e avisos de privacidade.
   - Arquivos: alterar `schemas.py` e `tools.py`; adicionar testes de política de privacidade.

3. `src/mcp_fiscal_brasil/simples/` expandido
   - Fonte alvo primária: BrasilAPI `https://brasilapi.com.br/api/simples/v1/{cnpj}`; fonte alternativa: CNPJá `https://open.cnpja.com/office/{cnpj}`.
   - Autenticação: BrasilAPI sem chave; CNPJá público sem chave.
   - Limite: BrasilAPI a confirmar, manter limitador local atual; CNPJá público documenta 5 consultas por minuto por IP.
   - Retorno: opção pelo Simples, datas de opção e exclusão, origem, atualização e confiança.
   - Arquivos: alterar `client.py`, `schemas.py`, `tools.py`; criar providers em `providers.py`.

4. `src/mcp_fiscal_brasil/mei/`
   - Fonte alvo: BrasilAPI e CNPJá para indicadores de SIMEI/MEI por CNPJ.
   - Autenticação: sem chave nas fontes públicas atuais.
   - Limite: mesmo limite de CNPJ/Simples da fonte usada.
   - Retorno: optante SIMEI, datas, situação, observação sobre defasagem e vínculo com Simples.
   - Arquivos: `client.py`, `schemas.py`, `tools.py`, `__init__.py`.

5. `src/mcp_fiscal_brasil/ibge/`
   - Fonte alvo: IBGE Localidades `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`.
   - Autenticação: nenhuma documentada.
   - Limite: não publicado; cache local por 30 dias e limitador conservador.
   - Retorno: código IBGE, município, UF, região, região imediata e intermediária.
   - Arquivos: `client.py`, `schemas.py`, `tools.py`, `normalization.py`, `__init__.py`.

6. `src/mcp_fiscal_brasil/junta_comercial/`
   - Fonte alvo: Redesim `https://www.gov.br/empresas-e-negócios/pt-br/redesim` e portais estaduais por UF.
   - Autenticação: varia por estado; muitos fluxos exigem gov.br, certificado, pagamento ou sessão web.
   - Limite: não padronizado.
   - Retorno: orientação por UF, URLs de consulta, campos necessários, riscos e status de automação suportada.
   - Arquivos: `catalog.py`, `schemas.py`, `tools.py`, `__init__.py`; cliente HTTP real somente para fontes com API pública permitida.

7. `src/mcp_fiscal_brasil/inscricao_estadual/`
   - Fonte alvo: SINTEGRA `https://www.sintegra.gov.br/` e alternativa CNPJá `https://open.cnpja.com/office/{cnpj}` para Cadastro de Contribuintes.
   - Autenticação: SINTEGRA por portal web; CNPJá público sem chave.
   - Limite: CNPJá público 5 consultas por minuto por IP; SINTEGRA não padronizado.
   - Retorno: número da IE, UF, situação, regime, fonte, data de atualização e aviso quando a fonte exigir consulta manual.
   - Arquivos: `client.py`, `schemas.py`, `tools.py`, `validators.py`, `__init__.py`.

8. `src/mcp_fiscal_brasil/certidoes/` expandido
   - Fonte alvo CND federal: Receita/PGFN e Conecta Gov CND `https://www.gov.br/conecta/catalogo/apis/consultar-certidao-negativa-de-debito`.
   - Fonte alvo FGTS: CAIXA CRF `https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf`.
   - Fonte alvo trabalhista: TST CNDT `https://cndt-certidao.tst.jus.br/consultarCertidao.faces`.
   - Autenticação: Conecta Gov exige autorização; portais podem exigir CAPTCHA, sessão, certificado ou interação humana.
   - Limite: não padronizado, tratar como portal sensível e usar limite muito conservador.
   - Retorno: tipo, documento, status normalizado, validade, URL de emissão/verificação, fonte e nível de automação.
   - Arquivos: alterar `client.py`, `schemas.py`, `tools.py`; criar `providers.py`.

### Fase 3: AI-Friendly Tools

Objetivo: tornar o MCP mais útil para Claude e outros clientes de LLM do que uma simples camada de consulta bruta.

Ferramentas propostas:

- `enriquecer_empresa`: recebe CNPJ e retorna CNPJ, Simples, MEI, CNAE, município IBGE, IE quando disponível, certidões orientativas e resumo de riscos.
- `consultar_empresas_lote`: aceita lista de CNPJs, aplica cache, rate limit e retorna resultados parciais com erros por item.
- `resumir_situacao_fiscal`: transforma dados estruturados em resumo curto em pt-BR, com fonte, data, confiança e próximos passos.
- `comparar_empresas`: compara duas ou mais empresas por situação, CNAE, porte, UF, Simples/MEI e regularidade disponível.
- `explicar_cnae`: recebe código ou texto e explica hierarquia, atividades incluídas, atividades excluídas e relação com o CNPJ consultado.
- `avaliar_fornecedor`: combina CNPJ, Simples/MEI, certidões orientativas, IE, NFSe municipal e sinais de risco para compra, cadastro ou pagamento.

O que torna essas ferramentas mais úteis para LLM:

- Saídas com `summary`, `facts`, `sources`, `confidence`, `warnings` e `next_actions`.
- Mensagens de erro acionáveis, sem stack trace e com sugestão de alternativa.
- Proveniência explícita por campo, distinguindo dado oficial, dado de agregador público, cálculo offline e orientação manual.
- Suporte a lote com resultados parciais, para o modelo continuar o raciocínio mesmo quando uma fonte falha.
- Resumos naturais sem esconder o JSON original, permitindo resposta conversacional e auditoria.

Arquivos a criar:

- `src/mcp_fiscal_brasil/intelligence/schemas.py`
- `src/mcp_fiscal_brasil/intelligence/enrichment.py`
- `src/mcp_fiscal_brasil/intelligence/summaries.py`
- `src/mcp_fiscal_brasil/intelligence/tools.py`
- `tests/test_intelligence_enrichment.py`
- `tests/test_intelligence_summaries.py`

### Fase 4: Múltiplas Interfaces

Objetivo: manter o MCP como interface principal, mas abrir caminhos de uso para terminal, REST, navegador e Node.

CLI com Typer:

- Dependências: `typer>=0.12`, `rich>=13`.
- Novo script: `fiscal-brasil = "mcp_fiscal_brasil.cli:app"`, preservando `mcp-fiscal-brasil` para MCP.
- Arquivos: `src/mcp_fiscal_brasil/cli.py`, `src/mcp_fiscal_brasil/cli_format.py`, `tests/test_cli.py`.
- Comandos: `cnpj consultar`, `cpf validar`, `nfe validar-chave`, `sefaz status`, `cnae buscar`, `empresa enriquecer`, `certidao orientar`.

FastAPI REST:

- Dependências: `fastapi>=0.115`, `uvicorn[standard]>=0.30`.
- Arquivos: `src/mcp_fiscal_brasil/api/app.py`, `api/routes_cnpj.py`, `api/routes_nfe.py`, `api/routes_enrichment.py`, `api/errors.py`, `tests/test_api.py`.
- Endpoints iniciais: `GET /health`, `GET /cnpj/{cnpj}`, `GET /cpf/{cpf}/validação`, `GET /nfe/{chave}/validação`, `GET /sefaz/{uf}/status`, `GET /cnae/{código}`, `POST /empresas/enriquecer-lote`.
- OpenAPI deve expor exemplos reais, erros padronizados e cabeçalhos de rate limit quando aplicável.

Web UI demo:

- Escolha técnica: Vite + React + TypeScript, consumindo a REST API local.
- Arquivos: `web/package.json`, `web/src/App.tsx`, `web/src/api.ts`, `web/src/styles.css`, `web/README.md`.
- Escopo: formulário de CNPJ, validação de CPF, status SEFAZ, busca CNAE e enriquecimento de fornecedor.
- Empacotamento: manter fora do wheel na v0.2.0 ou servir build estático somente se houver decisão de distribuição.

Wrapper npm:

- Abordagem: pacote Node fino que executa o comando Python instalado ou usa `uvx mcp-fiscal-brasil`.
- Arquivos: `npm/package.json`, `npm/bin/mcp-fiscal-brasil.js`, `npm/README.md`, `npm/test/smoke.test.js`.
- Estratégia: não reimplementar regras fiscais em TypeScript na v0.2.0; apenas facilitar instalação por clientes MCP do ecossistema Node.

### Fase 5: Docker, Docs, Release v0.2.0

Objetivo: deixar a entrega reproduzível, publicável e bem documentada.

Docker:

- Alterar `Dockerfile` para suportar `stdio` e `http` por variável, com usuário não root e healthcheck real.
- Alterar `docker-compose.yml` para usar apenas variáveis consumidas pelo código ou documentar claramente chaves futuras.
- Criar `.dockerignore` para reduzir build context.
- Criar `.github/workflows/docker.yml` para publicar `ghcr.io/dehor-labs/mcp-fiscal-brasil`.

GitHub Actions e publicação:

- Manter `.github/workflows/ci.yml` com Python 3.10 a 3.13.
- Adicionar teste de pacote instalado por wheel.
- Manter `.github/workflows/publish.yml` para PyPI via Trusted Publishing.
- Criar `.github/workflows/npm-publish.yml` se o wrapper npm for aprovado.
- Sincronizar versão em `pyproject.toml`, `src/mcp_fiscal_brasil/__init__.py` e `CHANGELOG.md`.

Documentação:

- Atualizar `README.md` com estado real de cada ferramenta, transportes reais, variáveis de ambiente reais e exemplos do SDK com nomes corretos.
- Atualizar `CHANGELOG.md` com entrada `0.2.0`.
- Criar `docs/migration-v0.2.md` com mudanças de SDK, CLI, REST e Docker.
- Criar `docs/sources.md` com fonte, autenticação, limite conhecido, risco legal e status de automação.
- Criar `docs/interfaces.md` para MCP, SDK, CLI, REST, Web UI e npm.
- Criar `docs/security-and-privacy.md` para CPF, CNPJ, logs, cache e fontes com CAPTCHA.

## 4. Riscos Técnicos

- BrasilAPI é útil e gratuita, mas é agregadora comunitária. Pode mudar cobertura, formato, disponibilidade ou política de uso.
- ReceitaWS é fallback público de terceiros e pode sofrer instabilidade, limite baixo ou mudança comercial.
- CNPJá público tem limite documentado de 5 consultas por minuto por IP e defasagem de dados, apesar de cobrir campos importantes como Simples, SIMEI e Cadastro de Contribuintes.
- IBGE CNAE e Localidades são fontes oficiais e estáveis, mas não devem ser chamadas sem cache em massa.
- Portal Nacional NFe e portais NFSe são orientados a navegador e podem usar CAPTCHA, JavaScript, sessão ou bloqueios automatizados.
- SINTEGRA e Inscrição Estadual não têm API nacional JSON padronizada, variam por UF e podem exigir scraping frágil.
- Junta Comercial e Redesim variam por estado e por tipo de consulta. Contrato social e NIRE podem envolver taxas, autenticação ou restrições.
- CND federal via Conecta Gov é oficial, mas não é uma API aberta para qualquer consumidor; depende de habilitação e contrato institucional.
- FGTS CRF e TST CNDT são consultas públicas de portal, mas automação pode conflitar com termos de uso, CAPTCHA ou limites não documentados.
- CPF é dado pessoal. A v0.2.0 deve limitar CPF a validação matemática, salvo decisão formal sobre fonte, finalidade, base legal e retenção.

## 5. Estimativas por Fase

| Fase | Linhas de código estimadas | Testes estimados | Prazo estimado |
|------|----------------------------|------------------|----------------|
| Fase 1: Infraestrutura Comum | 700 a 1.000 LOC | 35 a 50 testes | 2 a 3 dias |
| Fase 2: Expansão de Fontes de Dados | 1.600 a 2.400 LOC | 80 a 120 testes | 4 a 6 dias |
| Fase 3: AI-Friendly Tools | 700 a 1.100 LOC | 35 a 55 testes | 2 a 3 dias |
| Fase 4: Múltiplas Interfaces | 1.400 a 2.100 LOC | 60 a 90 testes | 4 a 5 dias |
| Fase 5: Docker, Docs, Release v0.2.0 | 500 a 900 LOC ou linhas de configuração/docs | 20 a 35 testes e smoke tests | 2 a 3 dias |

Total estimado: 4.900 a 7.500 linhas entre código, testes, configuração e documentação. Em desenvolvimento full-auto com revisão humana nos pontos de arquitetura, a janela realista é de 14 a 20 dias corridos, assumindo que fontes oficiais com autenticação sejam tratadas como orientação ou stubs quando o acesso não estiver disponível.

## 6. Decisões Arquiteturais para Validar

1. O `v0.2.0` deve ser uma release de consolidação e expansão de consultas, ou deve corrigir primeiro a divergência entre README, CHANGELOG e versão real `0.1.0`?

2. Para fontes sem API pública oficial, como SINTEGRA, Junta Comercial, FGTS e CNDT, o projeto deve oferecer apenas orientação segura ou aceitar integrações por scraping com risco documentado?

3. O cache deve ser apenas em memória na v0.2.0 ou deve incluir backend persistente opcional, como SQLite, para reduzir chamadas a fontes públicas?

4. O pacote npm deve ser um wrapper que invoca Python ou deve ser adiado até haver API REST estável e SDK TypeScript real?

5. As ferramentas de alto nível devem retornar resumo em linguagem natural junto com dados estruturados, ou devem retornar apenas JSON enriquecido para o cliente LLM resumir?
