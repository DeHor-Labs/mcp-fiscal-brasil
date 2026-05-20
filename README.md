<p align="center">
  <img src="assets/banner.svg" width="800" alt="MCP Fiscal Brasil">
</p>

<p align="center">
  <strong>O primeiro servidor MCP para o sistema fiscal brasileiro</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/mcp-fiscal-brasil/"><img src="https://img.shields.io/pypi/v/mcp-fiscal-brasil?color=009c3b&label=PyPI" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-002776?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licenca-MIT-FFDF00?labelColor=002776" alt="License MIT"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatível-7c3aed" alt="MCP Compatible"></a>
  <img src="https://img.shields.io/github/stars/nikolasdehor/mcp-fiscal-brasil?style=flat&color=009c3b" alt="Stars">
  <img src="https://img.shields.io/github/issues/nikolasdehor/mcp-fiscal-brasil?color=FFDF00&labelColor=002776" alt="Issues">
</p>

<p align="center">
  <a href="https://nikolasdehor.github.io/mcp-fiscal-brasil/">📚 Documentação</a> ·
  <a href="#-instalacao">Instalação</a> ·
  <a href="#-ferramentas-disponiveis">Ferramentas</a> ·
  <a href="#-demonstracao">Exemplos</a> ·
  <a href="#-roadmap">Roadmap</a> ·
  <a href="#-contribuindo">Contribuindo</a>
</p>

---

## 🌎 Demo ao vivo

Web UI demo hospedada (Render free tier, pode demorar 30s no primeiro acesso pra acordar):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/nikolasdehor/mcp-fiscal-brasil)

Você pode clicar no botão acima pra hostear sua própria instância em 3 cliques no Render.com.

Veja [docs/getting-started/deploy.md](docs/getting-started/deploy.md) para outras opções (Fly.io, auto-host via Docker).

---

## ✨ Novidades v0.2.0

Versão de evolução com 4 frentes:

- **8 novas fontes de dados**: CNAE, CPF, Simples Nacional, MEI, IBGE, CEP, Empresa consolidada, Certidões
- **Tools agênticas** (alto nível): `analyze_cnpj_compliance`, `compare_tax_regimes`, `risk_score_supplier`, `validate_nfe_full`, `summarize_sped`
- **Múltiplas interfaces**: além do servidor MCP, agora CLI (`mcp-fiscal`), REST API (`mcp-fiscal-api`) com Web UI demo, e pacote npm (`mcp-fiscal-brasil`)
- **Production-grade**: HTTP client com retry exponencial, cache pluggável, rate-limit por host, logs JSON estruturados

```bash
# CLI standalone
mcp-fiscal cnpj 12345678000190
mcp-fiscal compliance 12345678000190
mcp-fiscal regimes --faturamento 500000 --setor servicos --folha 180000

# REST API + Web UI demo
mcp-fiscal-api  # http://localhost:8000

# Node.js
import { analyzeCompliance } from "mcp-fiscal-brasil";
```

Veja [CHANGELOG.md](CHANGELOG.md) para detalhes.

---

## Por que este projeto existe?

O Brasil tem o sistema fiscal mais complexo do mundo. São **27 SEFAZs** estaduais, **NFe + NFSe + SPED + eSocial**, cada município com seu próprio portal de serviços, e mais de **500 mil PMEs** tentando manter conformidade fiscal todos os dias.

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

**14 ferramentas** cobrindo os principais módulos do sistema fiscal brasileiro.

---

### ✅ Ferramentas Funcionais (usáveis agora)

Funcionam 100% sem chaves de API. Instale e use imediatamente.

| Módulo | Ferramenta | Descrição | API |
|--------|-----------|-----------|-----|
| CNPJ | `consultar_cnpj` | Dados completos: razão social, sócios, CNAE, endereço | BrasilAPI (grátis) |
| CNPJ | `consultar_simples_nacional` | Optante Simples/MEI com datas de entrada e exclusão | BrasilAPI (grátis) |
| NFe | `validar_chave_nfe` | Valida dígito + extrai UF, CNPJ, data, número | Offline |
| NFe | `consultar_status_sefaz` | Status do webservice SEFAZ por estado | BrasilAPI (grátis) |
| NFe | `consultar_nfe` | Consulta NFe completa pela chave de 44 dígitos | BrasilAPI (grátis) |
| CPF | `validar_cpf` | Validação de dígito verificador | Offline |
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

### 🧪 Ferramentas Experimentais

Requerem APIs pagas ou têm cobertura limitada.

| Módulo | Ferramenta | Limitação |
|--------|-----------|-----------|
| CNPJ | `listar_cnpjs_por_nome` | Receita Federal não disponibiliza busca por nome em API pública |

---

## 🚀 Instalação

Três linhas para começar:

```bash
pip install mcp-fiscal-brasil
claude mcp add fiscal-brasil -- mcp-fiscal-brasil
# Pronto! Pergunte ao Claude sobre qualquer empresa brasileira.
```

```python
# Ou use como biblioteca Python:
from mcp_fiscal_brasil import FiscalBrasil
```

### Via uv (recomendado)

```bash
uv add mcp-fiscal-brasil
```

### A partir do código-fonte

```bash
git clone https://github.com/nikolasdehor/mcp-fiscal-brasil.git
cd mcp-fiscal-brasil
pip install -e .
```

---

## ⚙️ Configuração Detalhada

### Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "mcp-fiscal-brasil"
    }
  }
}
```

Reinicie o Claude Desktop. As 14 ferramentas fiscais aparecem automaticamente.

### Claude Code (CLI)

```bash
claude mcp add fiscal-brasil -- mcp-fiscal-brasil
```

### Cursor

Adicione ao `.cursor/mcp.json` do projeto:

```json
{
  "mcpServers": {
    "fiscal-brasil": {
      "command": "mcp-fiscal-brasil"
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
      "command": "mcp-fiscal-brasil"
    }
  }
}
```

### Docker

```bash
docker run --rm -i \
  -e MCP_FISCAL_LOG_LEVEL=INFO \
  ghcr.io/nikolasdehor/mcp-fiscal-brasil:latest
```

---

## 🔑 Variáveis de Ambiente

Todas as variáveis são opcionais. O servidor funciona sem nenhuma configuração.

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `MCP_FISCAL_LOG_LEVEL` | Nível de log: `DEBUG`, `INFO`, `WARNING` | `INFO` |
| `BRASILAPI_BASE_URL` | URL base da BrasilAPI (para ambientes customizados) | `https://brasilapi.com.br/api` |
| `HTTP_TIMEOUT` | Timeout em segundos para chamadas HTTP | `30` |

---

## Dois Modos de Uso

O mcp-fiscal-brasil funciona de **duas formas**:

| Modo | Para quem | Como |
|------|-----------|------|
| **MCP Server** | Usuários de IA (Claude, Cursor, GPT) | Instala e configura no assistente |
| **SDK Python** | Desenvolvedores de apps fiscais/contábeis | Importa e usa no código |

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
    {"doc": doc, "valido": fiscal.validate_cpf(doc) or fiscal.validate_cnpj(doc)}
    for doc in documentos
]
# [{'doc': '529.982.247-25', 'valido': True}, ...]
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

- [x] **v0.1.0** - Consultas CNPJ, CPF, NFe, Simples, SPED (atual)
- [ ] **v0.2.0** - NFSe 50+ municípios, eSocial catálogo completo
- [ ] **v0.3.0** - Emissão NFe/NFSe (requer certificado digital A1)
- [ ] **v1.0.0** - eSocial completo, LGPD audit, compliance suite

---

## 🤝 Contribuindo

Contribuições são bem-vindas!

```bash
# 1. Fork e clone
git clone https://github.com/SEU_USUARIO/mcp-fiscal-brasil.git
cd mcp-fiscal-brasil

# 2. Instale dependências de desenvolvimento
pip install -e ".[dev]"
pre-commit install

# 3. Crie sua branch
git checkout -b feature/meu-recurso

# 4. Implemente, teste e verifique
pytest
ruff check src/
mypy src/

# 5. Abra um Pull Request
```

Veja as [issues abertas](https://github.com/nikolasdehor/mcp-fiscal-brasil/issues) - especialmente as marcadas com `good first issue`.

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
