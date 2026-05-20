# Modulo CPF

Validacao **algoritmica offline** do digito verificador do CPF.

A Receita Federal nao expoe API publica para consulta de CPF (dados pessoais). Esse modulo so verifica o calculo matematico do DV.

## Uso

```python
from mcp_fiscal_brasil.cpf.tools import validar_cpf_tool

resultado = await validar_cpf_tool("123.456.789-09")
print(resultado.valido)  # True/False
```

## Tool MCP

- `validar_cpf(cpf: str)` - validacao offline do DV

## Limitacoes

Nao consulta:

- Nome titular
- Situacao cadastral (regular/pendente/cancelada)
- Outras informacoes pessoais

Para esses dados, e necessario contrato com SERPRO Datavalid ou Caixa.
