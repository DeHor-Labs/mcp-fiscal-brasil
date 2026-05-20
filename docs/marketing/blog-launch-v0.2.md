---
title: "mcp-fiscal-brasil v0.2.0: o sistema fiscal brasileiro inteiro acessivel por IA em uma linha de codigo"
author: Nikolas de Hor
date: 2026-05-20
tags: [python, mcp, fiscal, brasil, ia, claude]
---

# mcp-fiscal-brasil v0.2.0: o sistema fiscal brasileiro inteiro acessivel por IA em uma linha de codigo

> CNPJ, NFe, SPED, Simples Nacional, compliance, planejamento tributario. Tudo via MCP, CLI, REST API ou SDK Python. Sem captcha, sem login, sem dependencias pagas.

Sou desenvolvedor em Goiania e ha alguns meses lancei o `mcp-fiscal-brasil`, um servidor [Model Context Protocol](https://modelcontextprotocol.io) que permite a agentes de IA (Claude, Cursor, GPT) consultarem dados fiscais brasileiros em linguagem natural. Acabei de publicar a **v0.2.0**, um salto grande em relacao a primeira versao, e quero compartilhar o que mudou, por que mudou e como pode te ajudar.

Spoiler: no final do post, voce consegue fazer isso aqui em 5 minutos:

```python
from mcp_fiscal_brasil.agentic import risk_score_supplier

score = await risk_score_supplier("12.345.678/0001-90", criterios_estritos=True)
if score.recomendacao == "recusar":
    print(f"Bloqueado: {', '.join(score.fatores)}")
```

Ou, se voce conversa com Claude:

> "Faz a due diligence completa do CNPJ 12.345.678/0001-90 com criterios estritos"

E recebe um relatorio consolidado em um turno.

---

## O problema que ninguem queria resolver

O Brasil tem 27 SEFAZs estaduais, NFe + NFSe + SPED + eSocial, mais de 5.500 municipios cada um com seu portal proprio de NFSe, **e mais de 500 mil PMEs** tentando manter conformidade fiscal todo dia.

Antes do `mcp-fiscal-brasil`, integrar IA com qualquer dado fiscal brasileiro exigia:

- Aprender APIs e schemas de cada fonte (BrasilAPI, ReceitaWS, IBGE, portais municipais)
- Lidar com rate limits diferentes, formatos diferentes (JSON, XML, TXT pipe-delimited)
- Cuidar de retry, cache, parsing XML de NFe, validacao algoritmica de DV
- Compor varias chamadas para responder uma pergunta simples como "essa empresa esta apta a contratar?"

Resultado: cada projeto que precisava disso virava semanas de codigo de cola. E quando virava, era uma bola de neve de manutencao porque APIs mudam, regimes tributarios sao atualizados, novos eventos do eSocial sao adicionados.

O `mcp-fiscal-brasil` resolve isso em uma instalacao:

```bash
pipx install mcp-fiscal-brasil
mcp-fiscal cnpj 12345678000190
```

E pronto. CNPJ consultado via BrasilAPI (com fallback automatico pra ReceitaWS), formatado em pydantic, com retry exponencial e cache embutido.

---

## O que mudou na v0.2.0

A v0.1.x tinha o basico: CNPJ, CPF, NFe, NFSe, SPED, eSocial via servidor MCP. Util, mas limitado. A v0.2.0 foca em transformar isso no MCP fiscal brasileiro mais completo do mercado. Cinco fases:

### Fase 1: Infraestrutura production-grade

Antes, cada modulo tinha seu proprio cliente HTTP. Acoplado, dificil de testar, sem cache uniforme. Refatorei tudo para usar uma **infra comum** em `src/mcp_fiscal_brasil/_core/`:

- HTTP client com `httpx` + `tenacity` (retry exponencial)
- Cache pluggavel: memory (default), SQLite, Redis
- Rate-limit per-host via `aiolimiter`
- Logs estruturados JSON via `structlog`
- Config via `pydantic-settings` (env vars `MCP_FISCAL_*`)
- Hierarquia tipada de excecoes

Resultado: cada modulo agora e magro, com toda a complexidade infraestrutural compartilhada e testada.

### Fase 2: 8 novas fontes de dados

Adicionei modulos completos para:

- **CNAE** (Classificacao Nacional de Atividades Economicas)
- **CPF** (validacao algoritmica)
- **CEP** (BrasilAPI + ViaCEP fallback)
- **Simples Nacional** (consulta de regime)
- **MEI** (status de microempreendedor)
- **IBGE** (municipios, UFs, codigos)
- **Empresa consolidada** (dados unificados)
- **Certidoes** (URLs para CND, FGTS, CNDT)

Cada um com `client.py`, `schemas.py` (pydantic), tools MCP e testes.

### Fase 3: Tools agenticas (esse foi o pulo do gato)

Tools de baixo nivel sao uteis, mas exigem que o agente IA saiba combinar varias chamadas. Eu queria que o agente pudesse responder perguntas como "essa empresa e segura pra contratar?" em UMA chamada, nao em cinco.

Por isso criei o modulo `agentic/`:

| Tool | O que faz |
|------|-----------|
| `analyze_cnpj_compliance` | Consolida CNPJ + Simples + MEI + CNAE, retorna score 0-100 e risco classificado |
| `compare_tax_regimes` | Compara MEI/Simples/Lucro Presumido/Lucro Real com aliquota efetiva estimada |
| `risk_score_supplier` | Due diligence de fornecedor com recomendacao (aprovar/investigar/recusar) |
| `validate_nfe_full` | NFe: parse XML + valida chave + verifica situacao do emissor |
| `summarize_sped` | Sumario executivo de arquivo SPED |

Cada tool retorna um schema pydantic com `description` rica em cada campo. O agente IA entende imediatamente o que cada output significa, sem precisar consultar docs externas.

Exemplo real do `analyze_cnpj_compliance`:

```python
report = await analyze_cnpj_compliance("12345678000190")
# ComplianceReport(
#     cnpj="12345678000190",
#     razao_social="EMPRESA EXEMPLO LTDA",
#     risco_geral="medio",
#     score=65,
#     achados=[
#         ComplianceFinding(
#             categoria="endereco",
#             severidade="medio",
#             titulo="Endereco incompleto",
#             detalhe="Endereco cadastral incompleto ou nao retornado pela fonte.",
#             recomendacao="Solicitar comprovante de endereco atualizado.",
#         )
#     ],
#     resumo_executivo="CNPJ 12345678000190 (EMPRESA EXEMPLO LTDA) apresenta risco medio (score 65/100)...",
#     fontes_consultadas=["BrasilAPI", "Simples Nacional"],
# )
```

Detalhe importante: a tool **tolera falhas parciais**. Se a API do Simples estiver offline, ela ainda retorna o relatorio com os dados do CNPJ. Verifique `fontes_consultadas` pra saber o que respondeu.

### Fase 4: Multiplas interfaces

O servidor MCP atende agentes IA, mas tem gente que precisa usar isso em outros contextos: scripts shell, frontends, microservicos legados. Por isso adicionei tres interfaces alternativas:

**CLI standalone:**

```bash
mcp-fiscal cnpj 12345678000190
mcp-fiscal compliance 12345678000190
mcp-fiscal regimes --faturamento 500000 --setor servicos --folha 180000
mcp-fiscal supplier 12345678000190 --estrito --json
```

Toda saida tem `--json` para uso programatico. Roda no terminal, em pipelines shell, em scripts de batch.

**REST API:**

```bash
mcp-fiscal-api
# http://localhost:8000
```

FastAPI com OpenAPI docs em `/docs`, endpoints `/v1/cnpj/`, `/v1/agentic/compliance/`, etc.

**Web UI demo:**

A rota `/` da REST API serve uma pagina demo com tres formularios htmx 2.0:

- Consulta de CNPJ
- Compliance consolidado
- Comparativo de regimes tributarios

Sem build step. Dark mode. Pronta pra demos.

**npm wrapper:**

Para apps Node.js/TypeScript, publiquei um pacote npm que envelopa o CLI Python:

```typescript
import { lookupCNPJ, analyzeCompliance } from "mcp-fiscal-brasil";

const empresa = await lookupCNPJ("12345678000190");
const report = await analyzeCompliance(empresa.cnpj);
```

### Fase 5: Docker e release

Dockerfile multi-stage com usuario nao-root, healthcheck e cache de pip. Compose com profile para REST API e MCP HTTP transport.

Mais: site de documentacao com mkdocs-material em **[nikolasdehor.github.io/mcp-fiscal-brasil/](https://nikolasdehor.github.io/mcp-fiscal-brasil/)**, com guia de instalacao, configuracao para Claude Desktop/Cursor, casos de uso reais e referencia completa.

---

## Casos de uso reais

### 1. Due diligence automatizada de fornecedores

Cenario: empresa cadastra 100+ fornecedores por mes. Cada cadastro exigia 30 minutos manuais (consultar CNPJ, verificar regime, conferir certidoes, decidir).

Com o `mcp-fiscal-brasil`:

```python
async def cadastrar_fornecedor(cnpj: str) -> dict:
    score = await risk_score_supplier(cnpj, criterios_estritos=True)

    if score.recomendacao == "recusar":
        return {"status": "bloqueado", "motivos": score.fatores}
    if score.recomendacao == "investigar":
        await fila_compliance.enqueue(cnpj, score)

    return {"status": "aprovado"}
```

100 fornecedores em **paralelo** com `asyncio.gather` e um semaforo de 10 chamadas concorrentes: 10-15 segundos. Antes: 50 horas-pessoa.

### 2. Planejamento tributario instantaneo

Empresa pergunta ao contador: "qual o melhor regime pro meu cenario?". Tradicionalmente: planilha, calculo manual, comparacao. 30-60 minutos.

```python
plano = compare_tax_regimes(
    faturamento_anual=500_000,
    setor="servicos",
    folha_pagamento_anual=180_000,
)
# Em milissegundos:
# melhor_opcao = "simples_nacional" (Anexo III pelo Fator R)
# economia_anual_vs_pior = R$ 23.000
```

Plus: o assistente de IA pode fazer essa pergunta direto para o cliente em linguagem natural ("quanto voce fatura e quanto e folha?") e responder com a recomendacao.

### 3. Validacao pre-emissao de NFe

Antes de emitir NFe contra um destinatario:

```python
async def pre_emissao(cnpj_destinatario: str):
    report = await analyze_cnpj_compliance(cnpj_destinatario)
    if report.risco_geral == "critico":
        raise BloqueioFiscal(report.resumo_executivo)
```

Evita emitir nota contra CNPJ baixado / inapto, que daria rejeicao SEFAZ depois.

---

## Stack e decisoes tecnicas

Algumas escolhas que valem destacar:

- **uv** como gerenciador de dependencias. Mais rapido que pip + venv + pip-tools combinados.
- **httpx + tenacity** ao inves de `requests`. Async-first, retry decorator declarativo.
- **structlog** com renderizador JSON em producao. Logs prontos pra Loki/CloudWatch/Datadog sem regex.
- **pydantic v2** em tudo. Schemas auto-documentados, validacao na fronteira, serializacao pra LLM em uma linha.
- **mypy --strict** no codigo novo. Cada PR roda type checking sem exception.
- **Sem dependencias pagas**. Tudo via APIs publicas: BrasilAPI, ReceitaWS, IBGE, portais SEFAZ.

Quem entendeu Brasil sabe: tem que ser robusto a rate limit, a sites que caem, a respostas com encoding errado, a XML com namespace as vezes presente as vezes nao. A v0.2.0 trata todos esses casos com fallback chain e captura de excecoes individuais.

---

## Como comecar agora

Tres formas, do mais rapido pro mais customizavel:

### 1. CLI (1 minuto)

```bash
pipx install mcp-fiscal-brasil
mcp-fiscal cnpj 00000000000191
```

### 2. Claude Desktop

Adicione em `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "mcp-fiscal-brasil"
    }
  }
}
```

Reinicie o Claude Desktop. Pergunte em linguagem natural:

> "Consulte o CNPJ 12.345.678/0001-90 e me da um relatorio de compliance"

### 3. SDK Python

```bash
uv add mcp-fiscal-brasil
```

```python
import asyncio
from mcp_fiscal_brasil.agentic import analyze_cnpj_compliance

asyncio.run(analyze_cnpj_compliance("12345678000190"))
```

---

## Roadmap

V0.2.0 entregou o nucleo. Olhando pra frente:

- **v0.3.0**: integracoes nativas com frameworks BR (Django ContaPRO, Laravel Saas-Fiscal)
- **v0.3.0**: cliente SOAP para webservices SEFAZ que exigem certificado A1/A3
- **v0.3.0**: tools agenticas para folha (eSocial S-1.0 completo)
- **v0.4.0**: SDK em outras linguagens (Go, Rust) ao inves de wrappers

---

## Por que open source

Eu mantenho esse projeto sozinho. Trabalho de outra coisa pra pagar as contas. Faco isso porque acredito que **automacao fiscal nao deveria ser refem de SaaS caros**. PMEs brasileiras pagam fortunas por sistemas que so consultam CNPJ. Com o `mcp-fiscal-brasil`, qualquer dev junior pode integrar consultas fiscais em qualquer app, gratuitamente.

Se voce usa, **deixa uma estrela no GitHub**: [github.com/nikolasdehor/mcp-fiscal-brasil](https://github.com/nikolasdehor/mcp-fiscal-brasil). Isso ajuda outras pessoas a descobrirem o projeto.

Se voce quer contribuir, abra uma issue ou PR. Casos de uso reais sao especialmente bem-vindos: conta como voce usa, que pode entrar como tutorial na doc.

Se voce e empresa e quer feature especifica, posso fazer consultoria. Mando contato via [LinkedIn](https://www.linkedin.com/in/nikolasdehor).

---

## Links

- **GitHub**: https://github.com/nikolasdehor/mcp-fiscal-brasil
- **Documentacao**: https://nikolasdehor.github.io/mcp-fiscal-brasil/
- **PyPI**: https://pypi.org/project/mcp-fiscal-brasil/
- **Changelog**: https://github.com/nikolasdehor/mcp-fiscal-brasil/blob/main/CHANGELOG.md
- **MCP Spec**: https://modelcontextprotocol.io

Se voce chegou ate aqui, valeu pela paciencia. Espero que o projeto seja util. Qualquer feedback, abra issue ou me chama no LinkedIn.

Abraco de Goiania.

— Nikolas de Hor
