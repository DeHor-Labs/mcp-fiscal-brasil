# CLI

CLI standalone para uso em terminal e scripts shell.

## Instalacao

```bash
pipx install mcp-fiscal-brasil
# binarios: mcp-fiscal, mcp-fiscal-brasil, mcp-fiscal-api
```

## Comandos

| Comando | Descricao |
|---------|-----------|
| `mcp-fiscal cnpj <numero>` | Consulta dados cadastrais de CNPJ |
| `mcp-fiscal cpf <numero>` | Valida CPF (offline) |
| `mcp-fiscal cep <numero>` | Consulta endereco por CEP |
| `mcp-fiscal simples <cnpj>` | Situacao no Simples Nacional |
| `mcp-fiscal municipio <codigo_ibge>` | Dados de municipio por codigo IBGE |
| `mcp-fiscal compliance <cnpj>` | Analise consolidada de compliance |
| `mcp-fiscal supplier <cnpj>` | Score de risco de fornecedor |
| `mcp-fiscal regimes ...` | Comparativo de regimes tributarios |
| `mcp-fiscal version` | Versao do pacote |

## Flag `--json`

Toda saida pode vir como JSON puro para uso programatico:

```bash
mcp-fiscal cnpj 12345678000190 --json | jq '.razao_social'
mcp-fiscal compliance 12345678000190 --json > report.json
```

## Exemplos

### Pipeline shell

```bash
# Validar lista de CNPJs em massa
for cnpj in $(cat cnpjs.txt); do
  mcp-fiscal compliance "$cnpj" --json | jq '{cnpj, risco_geral, score}'
done | jq -s '.'
```

### Planejamento tributario rapido

```bash
mcp-fiscal regimes \
  --faturamento 500000 \
  --setor servicos \
  --folha 180000 \
  --json | jq '.melhor_opcao, .economia_anual_vs_pior'
```

### Due diligence com criterios estritos

```bash
mcp-fiscal supplier 12345678000190 --estrito --json
```
