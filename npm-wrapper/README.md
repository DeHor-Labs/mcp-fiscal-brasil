# mcp-fiscal-brasil (Node.js wrapper)

Wrapper Node.js/TypeScript para o pacote Python [`mcp-fiscal-brasil`](https://github.com/DeHor-Labs/mcp-fiscal-brasil).

Permite consultar dados fiscais brasileiros (CNPJ, NFe, SPED, Simples Nacional, compliance) em apps JavaScript/TypeScript chamando o CLI Python por baixo.

## Pre-requisitos

O CLI Python precisa estar instalado e disponivel no PATH:

```bash
pipx install mcp-fiscal-brasil
# ou
uv tool install mcp-fiscal-brasil
```

Confirme com `mcp-fiscal --help`.

## Status de distribuição

Este wrapper ainda não está publicado no npm registry. Use localmente a partir deste diretório ou prefira a REST API para apps Node.js em produção.

## Uso local

```bash
npm install
npm run build
```

Antes de usar o CLI abaixo, rode `npm run build` neste diretório (ou execute `npm link` após o build para expor `mcp-fiscal` no `PATH`).

## Uso programatico

```ts
import { lookupCNPJ, analyzeCompliance, compareRegimes } from "mcp-fiscal-brasil";

const empresa = await lookupCNPJ("12345678000190");
console.log(empresa.razao_social);

const compliance = await analyzeCompliance("12345678000190");
console.log(`Risco: ${compliance.risco_geral} (score ${compliance.score}/100)`);

const regimes = await compareRegimes({
  faturamento: 500_000,
  setor: "servicos",
  folha: 180_000,
});
console.log(`Melhor regime: ${regimes.melhor_opcao}`);
```

## Uso via CLI

```bash
node dist/cli.js cnpj 12345678000190
node dist/cli.js compliance 12345678000190
node dist/cli.js regimes --faturamento 500000 --setor servicos

# Ou (após npm link):
mcp-fiscal cnpj 12345678000190
```

## Funcoes disponiveis

| Funcao | Descricao |
|--------|-----------|
| `lookupCNPJ(cnpj)` | Dados cadastrais de empresa |
| `validateCPF(cpf)` | Validacao de CPF (offline) |
| `lookupCEP(cep)` | Endereco por CEP |
| `analyzeCompliance(cnpj)` | Compliance consolidado |
| `scoreSupplier(cnpj, opts)` | Due diligence de fornecedor |
| `compareRegimes(params)` | Comparativo MEI/Simples/LP/LR |

## Por que wrapper e nao reimplementacao

A logica fiscal brasileira muda com frequencia (tabelas Simples, regras CNAE, schemas SPED). Manter UMA implementacao em Python e expor por wrappers leves em outras linguagens reduz drift entre ecossistemas. Tradeoffs: requer Python instalado, overhead de subprocess por chamada (50-150ms).

## Licenca

MIT - Nikolas de Hor
