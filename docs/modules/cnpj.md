# Modulo CNPJ

Consulta de dados cadastrais de empresas via BrasilAPI (preferencial) com fallback para ReceitaWS.

## API publica

```python
from mcp_fiscal_brasil.cnpj.client import CNPJClient

client = CNPJClient()
empresa = await client.consultar("12345678000190")
print(empresa.razao_social)
```

## Schema

```python
class CNPJResponse(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    situacao_cadastral: str
    natureza_juridica: str
    porte: str | None
    capital_social: float | None
    data_abertura: date | None
    atividade_principal: AtividadeCNAE | None
    atividades_secundarias: list[AtividadeCNAE]
    endereco: Endereco
    telefone: str | None
    email: str | None
    qsa: list[QSASocio]
    origem: str  # "BrasilAPI" ou "ReceitaWS"
```

## Tools MCP

- `consultar_cnpj(cnpj: str)` - dados completos
- `listar_cnpjs_por_nome(nome, uf?)` - busca por nome (limitada)

## Fontes

- **BrasilAPI**: https://brasilapi.com.br/ (preferencial)
- **ReceitaWS**: https://receitaws.com.br/ (fallback)
- Rate limit publico: 3 req/min por IP em ambos (~)

Habilite cache em producao para nao bater no rate limit.
