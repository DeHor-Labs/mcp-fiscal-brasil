# Modulo CPF

Validacao **algoritmica offline** do digito verificador do CPF.

A Receita Federal não expoe API publica para consulta de CPF (dados pessoais). Esse módulo so verifica o cálculo matematico do DV.

## Uso

```python
from mcp_fiscal_brasil.cpf.tools import validar_cpf_tool

resultado = await validar_cpf_tool("123.456.789-09")
print(resultado.válido)  # True/False
```

## Tool MCP

- `validar_cpf(cpf: str)` - validação offline do DV
- `consultar_cpf(cpf: str)` - situação cadastral do titular (premium, opt-in)

## Consulta de situação cadastral (premium, opt-in)

Com o provedor premium opcional cpfcnpj.com.br habilitado (`CPFCNPJ_TOKEN`), a tool
`consultar_cpf` confere a situação cadastral do titular na Receita Federal antes de
emitir NF-e, NFC-e ou NFS-e a pessoa física. Não há fonte gratuita de dados de CPF, então
a consulta só ocorre com o token configurado. O dígito verificador é validado localmente
antes de qualquer chamada, para não gastar crédito com CPF malformado.

```python
from mcp_fiscal_brasil.cpf.tools import consultar_cpf_tool

cadastro = await consultar_cpf_tool("123.456.789-09")
# situacao so vem nos pacotes 26 e 8; nos pacotes 1 e 3 fica None.
print(cadastro.situacao.descricao if cadastro.situacao else None)  # ex.: "Regular"
print(cadastro.apto_emissao)        # True apenas quando a situação é Regular
```

O pacote é definido por `CPFCNPJ_CPF_PACKET`: `26` (padrão: nome, nascimento e situação),
`8` (situação com motivo, ano de óbito, número e PDF do comprovante), `3` (nome, nascimento,
gênero e endereço) ou `1` (só o nome). Situações reconhecidas (código oficial da Receita):
`00` Regular, `02` Suspensa, `03` Titular Falecido, `04` Pendente de Regularização, `05`
Cancelada por Multiplicidade, `08` Nula, `09` Cancelada de Ofício.

Privacidade: o CPF é mascarado em todo log (`***.***.***-XX`); o PDF do comprovante nunca
passa por log; campos operacionais do provedor (saldo, consultaID, pacote usado) não são
retornados.

## Limitacoes

A validação offline (`validar_cpf`) não consulta:

- Nome titular
- Situacao cadastral (regular/pendente/cancelada)
- Outras informações pessoais

Esses dados vêm de `consultar_cpf` com o provedor premium opt-in cpfcnpj.com.br.
