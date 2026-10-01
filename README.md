<!-- mcp-name: io.github.DeHor-Labs/mcp-fiscal-brasil -->

<p align="center">
  <img src="https://raw.githubusercontent.com/DeHor-Labs/mcp-fiscal-brasil/main/assets/banner.svg" width="800" alt="MCP Fiscal Brasil">
</p>

<p align="center">
  <strong>O único servidor MCP com suporte nativo a NF-e, NFS-e, SPED, eSocial, Simples Nacional e Reforma Tributária 2026 (IBS/CBS) - sem conta, sem chave e sem configuração.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/mcp-fiscal-brasil/"><img src="https://img.shields.io/pypi/v/mcp-fiscal-brasil?color=009c3b&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/mcp-fiscal-brasil/"><img src="https://img.shields.io/pypi/dm/mcp-fiscal-brasil?color=009c3b&label=downloads%2Fm%C3%AAs" alt="PyPI downloads"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-002776?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://github.com/DeHor-Labs/mcp-fiscal-brasil/actions/workflows/ci.yml"><img src="https://github.com/DeHor-Labs/mcp-fiscal-brasil/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/cobertura-85%25-009c3b?labelColor=002776" alt="Cobertura de testes 85%">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licenca-MIT-FFDF00?labelColor=002776" alt="License MIT"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatível-7c3aed" alt="MCP Compatible"></a>
  <img src="https://img.shields.io/github/stars/DeHor-Labs/mcp-fiscal-brasil?style=flat&color=009c3b" alt="Stars">
  <img src="https://img.shields.io/github/issues/DeHor-Labs/mcp-fiscal-brasil?color=FFDF00&labelColor=002776" alt="Issues">
</p>

<p align="center">
  <a href="https://dehor-labs.github.io/mcp-fiscal-brasil/">📚 Documentação</a> ·
  <a href="#-instalação">Instalação</a> ·
  <a href="#-ferramentas-disponíveis">Ferramentas</a> ·
  <a href="#workflows-que-vendem-sozinho">Workflows</a> ·
  <a href="#-roadmap">Roadmap</a> ·
  <a href="#-contribuindo">Contribuindo</a>
</p>

---

## Início rápido

```bash
uvx mcp-fiscal-brasil
```

> **Para manter sempre atualizado:** `uvx` cacheia a versão instalada. Use `uvx mcp-fiscal-brasil@latest` ou `uvx --refresh mcp-fiscal-brasil` para forçar a versão mais recente do [PyPI](https://pypi.org/project/mcp-fiscal-brasil/).

### Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "uvx",
      "args": ["mcp-fiscal-brasil"]
    }
  }
}
```

Reinicie o Claude Desktop. As ferramentas fiscais aparecem automaticamente, sem nenhuma chave de API.

---

## Por que mcp-fiscal-brasil e não outros servidores MCP brasileiros?

| Funcionalidade | mcp-fiscal-brasil | mcp-brasil | brasil-data-mcp |
|---|:---:|:---:|:---:|
| Foco | Vertical fiscal profunda | Dados públicos gerais | Dados públicos gerais |
| NF-e: parse, validação, DANFE, assinatura | Sim | Não | Não |
| SPED/eSocial: análise offline | Sim | Não | Não |
| Tabelas offline (NCM, CFOP, CNAE) | Sim | Não | Não |
| Reforma Tributária 2026 (IBS/CBS) | Sim | Não | Não |
| Simples Nacional/MEI | Sim | Não | Não |
| CPF: validação + situação cadastral (opt-in premium) | Sim | Não | Não |
| Certidão federal/FGTS | Sim (orientação) | Não | Não |
| Certificado A1 (mTLS SEFAZ) | Sim (opt-in) | Não | Não |
| Zero-cadastro, zero chave obrigatória | Sim | Parcial (3 APIs exigem chave) | Sim |
| Tools agênticas de alto nível | Sim (6 tools) | Parcial | Não |
| Linguagem de implementação | Python | Python | Node.js |

**mcp-brasil** (1.6k stars) e **brasil-data-mcp** cobrem dados públicos gerais - CEP, bancos, feriados, economia. Este projeto faz algo diferente: é uma vertical fiscal, com parsing offline de XML, validação XSD, tabelas de referência embutidas e suporte à Reforma 2026. Focos diferentes, públicos distintos.

---

## O que é

`mcp-fiscal-brasil` conecta assistentes de IA, ERPs, CRMs e automações internas ao universo fiscal brasileiro: **CNPJ, CPF, Simples Nacional, NFe, NFSe, SPED, eSocial, certidões e due diligence de fornecedores**.

Ele não tenta ser um catálogo genérico de dados públicos. A proposta é ser uma vertical de produto: transformar consultas fiscais fragmentadas em **tools seguras, composáveis e prontas para agentes**.

### Workflows que vendem sozinho

| Workflow | Tool principal | Resultado |
|----------|----------------|-----------|
| Due diligence de fornecedor | `risk_score_supplier` | Score 0-100, risco, fatores e recomendação de contratação |
| Triagem em lote | `consultar_empresas_lote` | Vários CNPJs em uma chamada, com compliance + score por empresa |
| Compliance de CNPJ | `analyze_cnpj_compliance` | CNPJ + Simples/MEI + CNAE em relatório acionável |
| Validação de NFe | `validate_nfe_full` | XML + chave + emissor, com issues estruturadas |
| Sumário de SPED | `summarize_sped` | Resumo executivo, período, empresa, blocos e inconsistências |
| Planejamento tributário | `compare_tax_regimes` | Comparativo MEI, Simples, Lucro Presumido e Lucro Real |

---

## 🌎 Demo ao vivo

Web UI demo hospedada (Render free tier, pode demorar 30s no primeiro acesso pra acordar):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/DeHor-Labs/mcp-fiscal-brasil)

Você pode clicar no botão acima pra hostear sua própria instância em 3 cliques no Render.com.

Veja [docs/getting-started/deploy.md](docs/getting-started/deploy.md) para outras opções (Fly.io, auto-host via Docker).

---

## ✨ Novidades v0.2.x

Versão de evolução com 4 frentes:

- **8 novas fontes de dados**: CNAE, CPF, Simples Nacional, MEI, IBGE, CEP, Empresa consolidada, Certidões
- **Tools agênticas** (alto nível): `analyze_cnpj_compliance`, `risk_score_supplier`, `consultar_empresas_lote`, `compare_tax_regimes`, `validate_nfe_full`, `summarize_sped`
- **Múltiplas interfaces**: além do servidor MCP, agora CLI (`mcp-fiscal`), REST API (`mcp-fiscal-api`) com Web UI demo, e wrapper Node.js em preview (`npm-wrapper/`)
- **Production-grade**: HTTP client com retry exponencial, cache pluggável, rate-limit por host, logs JSON estruturados

```bash
# CLI standalone
mcp-fiscal cnpj 12345678000190
mcp-fiscal compliance 12345678000190
mcp-fiscal regimes --faturamento 500000 --setor serviços --folha 180000

# REST API + Web UI demo
mcp-fiscal-api  # http://localhost:8000

# Node.js
import { analyzeCompliance } from "mcp-fiscal-brasil";
```

Veja [CHANGELOG.md](CHANGELOG.md) para detalhes.

---

## Por que este projeto existe?

O Brasil tem uma das infraestruturas fiscais mais complexas do mundo. São **27 SEFAZs** estaduais, **NFe + NFSe + SPED + eSocial**, milhares de municípios com portais próprios e milhões de empresas tentando manter conformidade fiscal todos os dias.

Antes deste projeto, integrar IA com qualquer dado fiscal brasileiro exigia desenvolvimento customizado, autenticação em múltiplos portais, e conhecimento profundo de cada API governamental. Cada consulta era um projeto.

**MCP Fiscal Brasil** resolve isso em uma linha: instale o servidor, conecte ao seu assistente de IA, e comece a fazer perguntas em linguagem natural. O servidor cuida de tudo, consultando diretamente Receita Federal, BrasilAPI e SEFAZs estaduais.

---

## 🎬 Demonstração

```
Você:  "Consulte o CNPJ 00.000.000/0001-91 e liste os sócios"

IA:    Empresa: Banco do Brasil S.A.
       Fundada em: 12/10/1808
       Situação: ATIVA
       CNAE principal: 6422100 - Bancos múltiplos com carteira comercial

       Sócios (QSA):
       - União Federal - Sócio-Administrador (60,82%)
       - BNDESPar - Sócio (10,32%)
```

```
Você:  "A chave NFe 35240300623904000197550010000012341234567890 é válida?"

IA:    Chave válida!
       Estado de origem: SP (São Paulo)
       Data de emissão: março/2024
       CNPJ emitente: 00.623.904/0001-97
       Número da nota: 000001234
       Dígito verificador: correto (módulo 11)
```

```
Você:  "A empresa 12.345.678/0001-90 é do Simples Nacional?"

IA:    Sim! Empresa optante do Simples Nacional.
       Data de opção: 01/01/2020
       Modalidade: MEI - Microempreendedor Individual
```

```
Você:  "O SEFAZ de São Paulo está online agora?"

IA:    Status SEFAZ SP: OPERACIONAL
       Serviço de autorização de NFe funcionando normalmente.
       Última verificação: agora.
```

---

## 🛠 Ferramentas Disponíveis

Ferramentas de baixo nível para dados fiscais e ferramentas agênticas de alto nível para decisão operacional.

### Tools agênticas

| Ferramenta | Quando usar |
|------------|-------------|
| `analyze_cnpj_compliance` | Relatório consolidado de compliance fiscal de um CNPJ |
| `risk_score_supplier` | Aprovar, investigar ou recusar fornecedor |
| `consultar_empresas_lote` | Triar carteira de fornecedores com score e erro por CNPJ |
| `compare_tax_regimes` | Comparar regimes tributários por cenário |
| `validate_nfe_full` | Validar uma NFe completa a partir do XML |
| `summarize_sped` | Transformar SPED em resumo executivo |

### ✅ Ferramentas Funcionais (usáveis agora)

Funcionam 100% sem chaves de API. Instale e use imediatamente.

| Módulo | Ferramenta | Descrição | API |
|--------|-----------|-----------|-----|
| CNPJ | `consultar_cnpj` | Dados completos: razão social, sócios, CNAE, endereço | BrasilAPI (grátis) + cpfcnpj.com.br (premium, opt-in) |
| CNPJ | `consultar_simples_nacional` | Optante Simples/MEI com datas de entrada e exclusão | BrasilAPI (grátis) |
| NFe | `validar_chave_nfe` | Valida dígito + extrai UF, CNPJ, data, número | Offline |
| NFe | `consultar_nfe` | Consulta NFe completa pela chave de 44 dígitos | BrasilAPI (grátis) + cpfcnpj.com.br (premium, opt-in) |
| NFe | `consultar_nfce` | NFC-e (modelo 65) pela chave de 44 dígitos; consulta completa exige token (pacote 102), senão tenta fontes públicas com dados parciais | cpfcnpj.com.br (pacote 102) + fontes públicas (parcial) |
| NFe | `parse_nfe_xml` | Parseia XML bruto de NF-e/NFC-e e retorna dados estruturados | Offline |
| NFe | `gerar_danfe` | Gera DANFE PDF (A4) a partir do XML de NF-e (mod 55) | Offline |
| NFe | `validar_assinatura_nfe` | Valida assinatura XMLDSig e extrai dados do certificado | Offline |
| NFe | `consultar_status_sefaz` | Status real do webservice SEFAZ por estado via NfeStatusServico4 (requer cert A1) | SEFAZ (mTLS) |
| NFe | `baixar_nfe_distribuicao` | Baixa documentos via NFeDistribuicaoDFe (requer cert A1 local) | SEFAZ (mTLS) |
| NFe | `manifestar_nfe` | Manifesta destinatario em NF-e via NFeRecepcaoEvento (requer cert A1) | SEFAZ (mTLS) |
| CPF | `validar_cpf` | Validação de dígito verificador | Offline |
| CPF | `consultar_cpf` | Situação cadastral do titular (Regular, Suspensa, Titular Falecido, Pendente de Regularização, Cancelada por Multiplicidade, Nula, Cancelada de Ofício) para emissão a pessoa física | cpfcnpj.com.br (premium, opt-in) |
| SPED | `analisar_sped` | Analisa arquivo EFD/ECD/ECF: período, empresa, erros | Offline |
| SPED | `listar_registros_sped` | Filtra registros por tipo (C100, E110, etc.) | Offline |
| eSocial | `listar_eventos_esocial` | Catálogo de eventos filtrável por grupo | Offline |
| eSocial | `validar_evento_esocial` | Validação básica de estrutura XML | Offline |

---

### 🧭 Ferramentas de Orientação

Retornam URLs e instruções - exigem ação manual nos portais governamentais.

| Módulo | Ferramenta | O que retorna |
|--------|-----------|--------------|
| NFSe | `consultar_nfse` | URL do portal NFSe do município + sistema utilizado |
| Certidões | `consultar_certidao_federal` | URL do e-CAC para emissão de CND federal |
| Certidões | `consultar_certidao_fgts` | URL do portal Caixa para consulta do CRF |

---

### 🔐 Ferramentas com Certificado A1 (opt-in)

As tools `baixar_nfe_distribuicao`, `manifestar_nfe` e `consultar_status_sefaz`
requerem um certificado digital A1 (`.pfx`/`.p12`). mTLS é exigência de
transporte de todo webservice SEFAZ, inclusive a consulta de status - não há
como consultar o status real sem certificado.

- O certificado e a senha **nunca são enviados a nenhum servidor externo**.
- A autenticação mTLS e a assinatura XMLDSig são feitas localmente.
- `baixar_nfe_distribuicao` e `manifestar_nfe` recebem o caminho do certificado
  como parâmetro da própria tool (`.pfx`/`.p12` local).
- `consultar_status_sefaz` (via servidor MCP/API REST) usa o certificado
  configurado nas variáveis de ambiente abaixo, e se conecta ao webservice
  próprio da UF consultada ou ao ambiente virtual (SVRS/SVAN) quando a UF não
  tem infraestrutura própria.
- As demais tools (parse, DANFE, assinatura, consultas de CNPJ/NFe via
  BrasilAPI) funcionam sem certificado.

**Configuração** (variáveis em `.env` ou secret do provedor de deploy - ver
`.env.example`):

| Variável | Descrição |
|----------|-----------|
| `NFE_CERTIFICADO_PATH` | Caminho absoluto do `.pfx`/`.p12` montado no container |
| `NFE_CERTIFICADO_SENHA` | Senha do certificado (sempre via gestor de segredos, nunca em `.env` versionado) |
| `NFE_EMITENTE_CNPJ` | CNPJ do titular do certificado (14 dígitos, opcional) |
| `NFE_AMBIENTE` | `producao` ou `homologacao` (padrão `producao`) |

Sem `NFE_CERTIFICADO_PATH`/`NFE_CERTIFICADO_SENHA`, `consultar_status_sefaz`
levanta `FiscalConfigurationError` e o endpoint HTTP `GET /v1/nfe/status-sefaz`
responde 503 - o chamador deve tratar isso como "sem certificado configurado",
não como SEFAZ fora do ar (falha pontual de rede em uma UF especifica, essa
sim, degrada omitindo a UF em vez de derrubar a chamada). `GET
/v1/fiscal/certificado/status` informa apenas se há certificado configurado e
válido (sem titular nem CNPJ - endpoint sem autenticação, não deve permitir
reconhecimento de identidade), sem nunca expor o arquivo ou a senha.

---

### ☁️ Provedor premium opcional: cpfcnpj.com.br (opt-in)

O projeto continua **gratuito, sem cadastro e sem chave de API por padrão**. Para
quem precisa de cobertura e atualidade de nível empresarial, a
[cpfcnpj.com.br](https://www.cpfcnpj.com.br/dev/) pode ser habilitada como uma
fonte premium **opt-in**, sem alterar em nada o comportamento gratuito padrão.

Enquanto o token não é configurado, tudo funciona como antes, usando apenas as
fontes gratuitas (BrasilAPI, ReceitaWS e Portal NFe). Ao definir `CPFCNPJ_TOKEN`,
o provedor passa a ser consultado **primeiro**, e as fontes gratuitas seguem como
fallback automático, de forma transparente.

**O que a fonte premium acrescenta a este projeto fiscal:**

- **Dados oficiais em tempo real (D+0):** cadastro atualizado direto na origem,
  sem depender de janelas de sincronização de bases intermediárias.
- **Sem bases vazadas ou raspadas:** os dados vêm de fontes oficiais, com
  procedência conhecida, e não de dumps de terceiros.
- **Conformidade com certificações internacionais** (ISO/IEC 27001 de segurança
  da informação, ISO/IEC 27701 de privacidade e ISO 37301 de gestão de
  conformidade), reforçando privacidade e tratamento adequado dos dados.
- **Cobre a consulta de NF-e por chave**, que hoje depende de fontes públicas
  instáveis, e adiciona **NFC-e (modelo 65)**, ainda não coberta pelas APIs
  gratuitas.

**Ferramentas cobertas quando o token está ativo:**

| Ferramenta | Fonte premium | Pacote | Documentação |
|-----------|---------------|--------|--------------|
| `consultar_cnpj` | cpfcnpj.com.br | 5 ou 6 | [dev/](https://www.cpfcnpj.com.br/dev/) |
| `consultar_cpf` | cpfcnpj.com.br | 1, 3, 8 ou 26 (padrão 26) | [dev/](https://www.cpfcnpj.com.br/dev/) |
| `consultar_nfe` | cpfcnpj.com.br | 100 (modelo 55) | [#op-get-token-100-chave](https://www.cpfcnpj.com.br/dev/#op-get-token-100-chave) |
| `consultar_nfce` | cpfcnpj.com.br | 102 (modelo 65) | [#op-get-token-102-chave](https://www.cpfcnpj.com.br/dev/#op-get-token-102-chave) |

O `consultar_cpf` confere a situação cadastral do titular antes de emitir NF-e, NFC-e
ou NFS-e a pessoa física (destinatário ou tomador), e deriva `apto_emissao` (verdadeiro
só quando a situação é Regular). Não há fonte gratuita de dados de CPF, então a consulta
só ocorre com o token configurado. O pacote define o que volta:

| Pacote | O que devolve |
|--------|---------------|
| `26` (padrão) | Nome, nascimento e situação cadastral. Suficiente para o caso fiscal e o mais barato com situação. |
| `8` | O do pacote 26 mais motivo da situação, ano de óbito, número e PDF do comprovante da Receita (para arquivar junto da nota). |
| `3` | Nome, nascimento, gênero e endereço completo (preencher o destinatário da NF-e). |
| `1` | Só o nome (conferir se o nome informado bate com o CPF). |

O CPF é mascarado em todo log (`***.***.***-XX`) e os campos operacionais do provedor
(saldo, consultaID, pacote usado) não são retornados.

O `consultar_nfce` retorna a NFC-e completa apenas com o token configurado (pacote
102). Sem token, ele recorre às fontes públicas e pode devolver dados parciais da
chave. A cobertura on-line do pacote 102 está disponível em São Paulo (SP) e Minas
Gerais (MG); as demais UFs exigem habilitação sob demanda e podem retornar o erro
204 (sem consumo de crédito). Detalhes de cobertura em
[cpfcnpj.com.br/dev/](https://www.cpfcnpj.com.br/dev/).

**Configuração** (todas opcionais, ver `.env.example`):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `CPFCNPJ_TOKEN` | Token da conta em cpfcnpj.com.br. **Vazio = fonte premium desligada.** | (vazio) |
| `CPFCNPJ_BASE_URL` | URL base da API premium. Aceita somente `https://` (o token trafega no caminho da URL) | `https://api.cpfcnpj.com.br` |
| `CPFCNPJ_TIMEOUT` | Timeout (segundos) das consultas ao provedor. A documentação recomenda 60 (valor menor pode cortar a requisição após o crédito já ter sido consumido) | `60` |
| `CPFCNPJ_CNPJ_PACKET` | Pacote de CNPJ: `5` (enxuto) ou `6` (completo) | `6` |
| `CPFCNPJ_CPF_PACKET` | Pacote de CPF do `consultar_cpf`: `26` (nome, nascimento, situação), `8` (situação + PDF do comprovante e óbito), `3` (nome, nascimento, gênero, endereço) ou `1` (só nome) | `26` |

Trate o token como segredo: use o gestor de segredos do seu provedor de deploy,
nunca um `.env` versionado em produção.

---

### 🧪 Ferramentas Experimentais

Requerem APIs pagas ou têm cobertura limitada.

| Módulo | Ferramenta | Limitação |
|--------|-----------|-----------|
| CNPJ | `listar_cnpjs_por_nome` | Receita Federal não disponibiliza busca por nome em API pública |

---

## 🚀 Instalação

A forma mais simples, sem instalar nada permanentemente:

```bash
uvx mcp-fiscal-brasil
```

> **O que é `uvx`?** É o gerenciador de ferramentas do [uv](https://docs.astral.sh/uv/), que baixa e executa pacotes Python em ambiente isolado, sem poluir seu sistema. Se ainda não tem o uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

> **Mantendo atualizado via PyPI:** use `uvx mcp-fiscal-brasil@latest` ou `uvx --refresh mcp-fiscal-brasil` para forçar a versão mais recente. O `uvx` cacheia localmente, então sem `@latest` você pode continuar numa versão antiga.

---

## ⚙️ Configuração por Cliente MCP

Cole o trecho abaixo no arquivo de configuração do seu cliente. **Nenhuma chave de API é necessária.**

### Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "uvx",
      "args": ["mcp-fiscal-brasil"]
    }
  }
}
```

Reinicie o Claude Desktop. As ferramentas fiscais e agênticas aparecem automaticamente.

### Claude Code (CLI)

```bash
claude mcp add fiscal-brasil -- uvx mcp-fiscal-brasil
```

### Cursor / `.mcp.json`

Crie ou edite `.cursor/mcp.json` (ou `.mcp.json` na raiz do projeto):

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "uvx",
      "args": ["mcp-fiscal-brasil"]
    }
  }
}
```

### VS Code + Continue

Adicione ao `settings.json`:

```json
{
  "continue.mcpServers": {
    "fiscal-brasil": {
      "command": "uvx",
      "args": ["mcp-fiscal-brasil"]
    }
  }
}
```

### Docker

```bash
docker run --rm -i \
  -e MCP_FISCAL_LOG_LEVEL=INFO \
  ghcr.io/dehor-labs/mcp-fiscal-brasil:latest
```

---

## 🛠 Instalação permanente (alternativa)

Prefere instalar uma vez e manter no PATH?

```bash
# via pip
pip install mcp-fiscal-brasil

# via uv (recomendado para projetos Python)
uv add mcp-fiscal-brasil
```

Após a instalação, os snippets JSON acima funcionam com `"command": "mcp-fiscal-brasil"` (sem o `uvx`).

### A partir do código-fonte

```bash
git clone https://github.com/DeHor-Labs/mcp-fiscal-brasil.git
cd mcp-fiscal-brasil
pip install -e .
```

---

## 🔑 Variáveis de Ambiente

Todas as variáveis são opcionais. O servidor funciona sem nenhuma configuração.

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `MCP_FISCAL_LOG_LEVEL` | Nível de log: `DEBUG`, `INFO`, `WARNING` | `INFO` |
| `BRASILAPI_BASE_URL` | URL base da BrasilAPI (para ambientes customizados) | `https://brasilapi.com.br/api` |
| `HTTP_TIMEOUT` | Timeout em segundos para chamadas HTTP | `30` |
| `CPFCNPJ_TOKEN` | Token do provedor premium opt-in [cpfcnpj.com.br](https://www.cpfcnpj.com.br/dev/). Vazio = desligado (padrão gratuito intacto) | (vazio) |
| `CPFCNPJ_BASE_URL` | URL base da API premium cpfcnpj.com.br. Aceita somente `https://` | `https://api.cpfcnpj.com.br` |
| `CPFCNPJ_TIMEOUT` | Timeout (segundos) das consultas à cpfcnpj.com.br (recomendado 60 pela documentação) | `60` |
| `CPFCNPJ_CNPJ_PACKET` | Pacote de CNPJ na cpfcnpj.com.br: `5` ou `6` | `6` |
| `CPFCNPJ_CPF_PACKET` | Pacote de CPF na cpfcnpj.com.br: `1`, `3`, `8` ou `26` | `26` |

---

## Modos de Uso

O `mcp-fiscal-brasil` funciona de quatro formas:

| Modo | Para quem | Como |
|------|-----------|------|
| **MCP Server** | Usuários de IA (Claude, Cursor, GPT) | Instala e configura no assistente |
| **SDK Python** | Desenvolvedores de apps fiscais/contábeis | Importa e usa no código |
| **CLI** | Operação, scripts e automações locais | Usa `mcp-fiscal ...` |
| **REST API + Web UI** | Integração HTTP e demo pública | Usa `mcp-fiscal-api` |

---

## 🐍 Uso como Biblioteca Python (SDK)

Além de funcionar como servidor MCP, você pode importar e usar diretamente no seu código Python - sem servidor, sem configuração extra.

### Início Rápido

```python
import asyncio
from mcp_fiscal_brasil import FiscalBrasil

async def main():
    async with FiscalBrasil() as fiscal:
        empresa = await fiscal.consultar_cnpj("00.000.000/0001-91")
        print(empresa["razao_social"])  # Banco do Brasil S.A.
        print(empresa["situacao_cadastral"])  # ATIVA

asyncio.run(main())
```

### Validações Offline (sem API, instantâneo)

```python
from mcp_fiscal_brasil import FiscalBrasil

fiscal = FiscalBrasil()

# Validações locais - sem chamada de rede
print(fiscal.validate_cpf("529.982.247-25"))       # True
print(fiscal.validate_cnpj("11.222.333/0001-81"))  # True / False
print(fiscal.validate_chave_nfe("3524...44 digitos..."))  # dict com detalhes
```

### Integração com FastAPI

```python
from fastapi import FastAPI
from mcp_fiscal_brasil import FiscalBrasil

app = FastAPI()
fiscal = FiscalBrasil()

@app.get("/cnpj/{cnpj}")
async def consultar(cnpj: str):
    async with fiscal:
        return await fiscal.consultar_cnpj(cnpj)
```

### Integração com Django

```python
# views.py
import asyncio
from mcp_fiscal_brasil import FiscalBrasil
from django.http import JsonResponse

def consulta_cnpj(request, cnpj):
    async def buscar():
        async with FiscalBrasil() as fiscal:
            return await fiscal.consultar_cnpj(cnpj)
    dados = asyncio.run(buscar())
    return JsonResponse(dados)
```

### Cadastro Automático de Fornecedor (exemplo ERP)

```python
import asyncio
from mcp_fiscal_brasil import FiscalBrasil

async def cadastrar_fornecedor(cnpj: str, db_session):
    async with FiscalBrasil() as fiscal:
        if not fiscal.validate_cnpj(cnpj):
            raise ValueError("CNPJ inválido")

        dados = await fiscal.consultar_cnpj(cnpj)
        simples = await fiscal.consultar_simples_nacional(cnpj)

        await db_session.execute(
            "INSERT INTO fornecedores (cnpj, razao_social, simples) VALUES (?, ?, ?)",
            [cnpj, dados["razao_social"], simples["optante"]]
        )
```

### Validação em Lote

```python
import asyncio
from mcp_fiscal_brasil import FiscalBrasil

fiscal = FiscalBrasil()

documentos = ["529.982.247-25", "000.000.000-00", "11.222.333/0001-81"]

resultados = [
    {"doc": doc, "válido": fiscal.validate_cpf(doc) or fiscal.validate_cnpj(doc)}
    for doc in documentos
]
# [{'doc': '529.982.247-25', 'válido': True}, ...]
```

---

## 🏗 Arquitetura

```
Claude / GPT / Cursor / qualquer cliente MCP
           |
           | Model Context Protocol (stdio)
           v
    mcp-fiscal-brasil
           |
    +------+-------+--------+--------+--------+-------+--------+
    |      |       |        |        |        |       |        |
   CNPJ   CPF    NFe      NFSe   Simples    SPED  eSocial Certidões
    |      |       |        |        |        |       |        |
    v      v       v        v        v        v       v        v
BrasilAPI  --   SEFAZ   Portais   Receita  Parser  Catálogo  URLs
ReceitaWS       estaduais municipais Federal  local   local  governamentais
```

**Fontes de dados:**
- [BrasilAPI](https://brasilapi.com.br) - CNPJ, CEP, bancos (open source, sem autenticação)
- [ReceitaWS](https://www.receitaws.com.br) - CNPJ (fallback)
- SEFAZs estaduais - Status de serviço e consulta de NFe
- Receita Federal - Simples Nacional e certidões (orientação de acesso)

---

## 📍 Roadmap

- [x] **v0.1.x** - Consultas CNPJ, CPF, NFe, Simples Nacional e SPED; ~14 tools MCP
- [x] **v0.2.x** - Infra production-grade (_core), CLI, REST API, Web UI demo, wrapper npm/Node.js e tools agênticas (compliance, due diligence, comparativo de regimes); ~20 tools MCP
- [x] **v0.3.x** - Tabelas fiscais offline (NCM/TIPI, CFOP, CST, CEST, ICMS interestadual) e indexadores BCB (Selic, IPCA, PTAX, correção monetária); ~36 tools MCP
- [x] **v0.4.x** - Módulo NF-e completo (parse, DANFE, assinatura XMLDSig, distribuição mTLS, manifestação do destinatário) e simulador da Reforma Tributária IBS/CBS (LC 214/2025); ~42 tools MCP
- [x] **v0.5.x** - Módulo de importação (II, IPI, PIS/COFINS-importação, ICMS grossed-up, AFRMM, Siscomex) por NCM; circuit breaker NFS-e; correções SPED e path injection; automação de release; ~44 tools MCP
- [ ] **v0.6.x** - NFC-e modelo 65 (DANFE cupom, autorizacao e cancelamento); NFS-e por provedor/municipio; validação XSD completa NF-e e SPED
- [ ] **v0.7.x** - eSocial versionado (S-1.1); cache persistente entre sessões; LGPD audit trail
- [ ] **v1.0.0** - Suíte fiscal com contratos de API estáveis, cobertura operacional ampliada e SLA de manutenção documentado

---

## Como acompanhar

[![GitHub Discussions](https://img.shields.io/github/discussions/DeHor-Labs/mcp-fiscal-brasil)](https://github.com/DeHor-Labs/mcp-fiscal-brasil/discussions)
[![GitHub Stars](https://img.shields.io/github/stars/DeHor-Labs/mcp-fiscal-brasil)](https://github.com/DeHor-Labs/mcp-fiscal-brasil/stargazers)

<a href="https://star-history.com/#DeHor-Labs/mcp-fiscal-brasil&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=DeHor-Labs/mcp-fiscal-brasil&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=DeHor-Labs/mcp-fiscal-brasil&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=DeHor-Labs/mcp-fiscal-brasil&type=Date" />
 </picture>
</a>

- **Releases**: clique em **Watch -> Releases** no topo do repositório para ser notificado a cada versão nova
- **Discussions**: [github.com/DeHor-Labs/mcp-fiscal-brasil/discussions](https://github.com/DeHor-Labs/mcp-fiscal-brasil/discussions) - canal para sugestões de feature, dúvidas fiscais e técnicas, e casos de uso. Sugestões feitas aqui entram no roadmap de verdade
- **Newsletter**: acompanhe os releases comentados na [LinkedIn Newsletter MCP Fiscal Brasil](https://www.linkedin.com/newsletters/7474668338875494400/) - cada edição explica o que chegou, o que foi corrigido e o que vem por ai. [Assinar agora](https://www.linkedin.com/build-relation/newsletter-follow?entityUrn=7474668338875494400)
- **Issues**: bugs com contexto completo (versão, XML de exemplo sem dados reais, comportamento esperado vs. obtido)

---

## 🤝 Contribuindo

Contribuições são bem-vindas!

```bash
# 1. Clone o repo ou seu fork
git clone https://github.com/DeHor-Labs/mcp-fiscal-brasil.git
cd mcp-fiscal-brasil

# 2. Instale dependências de desenvolvimento
pip install -e ".[dev]"
pre-commit install

# 3. Crie sua branch
git checkout -b feature/meu-recurso

# 4. Implemente, teste e verifique
python scripts/check_release_metadata.py
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest

# 5. Abra um Pull Request
```

Veja as [issues abertas](https://github.com/DeHor-Labs/mcp-fiscal-brasil/issues) - especialmente as marcadas com `good first issue`.

Cada módulo segue o padrão `client.py` + `schemas.py` + `tools.py`, o que torna simples adicionar novos módulos fiscais.

---

## 📄 Licença

MIT - veja [LICENSE](LICENSE) para detalhes.

---

<p align="center">
  Feito com 💚💛 para o Brasil
  <br>
  <sub>Conectando inteligência artificial ao sistema fiscal mais complexo do mundo</sub>
</p>
