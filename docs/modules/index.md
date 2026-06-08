# Modulos

Cada fonte de dado fiscal e um módulo Python em `src/mcp_fiscal_brasil/`.

## Disponiveis (v0.2.x)

| Modulo | Fonte | Tipo |
|--------|-------|------|
| [cnpj](cnpj.md) | BrasilAPI, ReceitaWS | Dados cadastrais |
| [cpf](cpf.md) | Algoritmico | Validacao offline |
| [cep](cep.md) | BrasilAPI, ViaCEP | Enderecos |
| [nfe](nfe.md) | SEFAZ, parse XML | Notas fiscais eletrônicas |
| [nfse](#) | Portais municipais | Servicos eletrônicos |
| [sped](sped.md) | Parse local | Escrituracao digital |
| [esocial](#) | Validacao | Eventos eSocial |
| [simples](simples.md) | API Receita | Regime Simples Nacional |
| [mei](#) | API Receita | Microempreendedor |
| [cnae](cnae.md) | Tabela local + API | Atividades economicas |
| [ibge](ibge.md) | API IBGE | Municipios, UFs |
| [empresa](#) | Consolidado | Dados unificados |
| [certidoes](#) | URLs portais | Certidoes negativas |

## Convencao

Cada módulo segue o mesmo padrao:

```
src/mcp_fiscal_brasil/<módulo>/
├── __init__.py    # exports publicos
├── client.py      # cliente assincrono
├── schemas.py     # modelos pydantic
└── tools.py       # tools MCP (quando aplicável)
```

Para detalhes da arquitetura interna, veja o código no [GitHub](https://github.com/DeHor-Labs/mcp-fiscal-brasil/tree/main/src/mcp_fiscal_brasil).
