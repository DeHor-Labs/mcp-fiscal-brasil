# Modulos

Cada fonte de dado fiscal e um modulo Python em `src/mcp_fiscal_brasil/`.

## Disponiveis (v0.2.0)

| Modulo | Fonte | Tipo |
|--------|-------|------|
| [cnpj](cnpj.md) | BrasilAPI, ReceitaWS | Dados cadastrais |
| [cpf](cpf.md) | Algoritmico | Validacao offline |
| [cep](cep.md) | BrasilAPI, ViaCEP | Enderecos |
| [nfe](nfe.md) | SEFAZ, parse XML | Notas fiscais eletronicas |
| [nfse](#) | Portais municipais | Servicos eletronicos |
| [sped](sped.md) | Parse local | Escrituracao digital |
| [esocial](#) | Validacao | Eventos eSocial |
| [simples](simples.md) | API Receita | Regime Simples Nacional |
| [mei](#) | API Receita | Microempreendedor |
| [cnae](cnae.md) | Tabela local + API | Atividades economicas |
| [ibge](ibge.md) | API IBGE | Municipios, UFs |
| [empresa](#) | Consolidado | Dados unificados |
| [certidoes](#) | URLs portais | Certidoes negativas |

## Convencao

Cada modulo segue o mesmo padrao:

```
src/mcp_fiscal_brasil/<modulo>/
├── __init__.py    # exports publicos
├── client.py      # cliente assincrono
├── schemas.py     # modelos pydantic
└── tools.py       # tools MCP (quando aplicavel)
```

Para detalhes da arquitetura interna, veja o codigo no [GitHub](https://github.com/nikolasdehor/mcp-fiscal-brasil/tree/main/src/mcp_fiscal_brasil).
