# Node.js (npm wrapper)

Pacote npm `mcp-fiscal-brasil` que envelopa o CLI Python para uso em apps JavaScript/TypeScript.

## Pre-requisito

O CLI Python precisa estar instalado no `PATH`:

```bash
pipx install mcp-fiscal-brasil
mcp-fiscal --help  # deve responder
```

## Instalacao

```bash
npm install mcp-fiscal-brasil
# ou
pnpm add mcp-fiscal-brasil
# ou
yarn add mcp-fiscal-brasil
```

## Uso programatico

```typescript
import {
  lookupCNPJ,
  analyzeCompliance,
  compareRegimes,
  scoreSupplier,
} from "mcp-fiscal-brasil";

// CNPJ lookup
const empresa = await lookupCNPJ("12345678000190");
console.log(empresa.razao_social);

// Compliance
const report = await analyzeCompliance("12345678000190");
console.log(`Risco: ${report.risco_geral} (score ${report.score}/100)`);

// Due diligence
const score = await scoreSupplier("12345678000190", { estrito: true });
console.log(score.recomendacao);  // "aprovar" | "investigar" | etc

// Planejamento tributario
const regimes = await compareRegimes({
  faturamento: 500_000,
  setor: "servicos",
  folha: 180_000,
});
console.log(regimes.melhor_opcao);
```

## CLI passthrough

```bash
npx mcp-fiscal cnpj 12345678000190
npx mcp-fiscal regimes --faturamento 500000 --setor servicos
```

## Trade-offs

Como o wrapper spawna o CLI Python via subprocess:

- **Overhead**: 50-150ms por chamada
- **Pre-requisito**: Python instalado
- **Beneficio**: zero drift entre ecossistemas Python e Node

Para apps Node de alto throughput, considere usar a [REST API](rest-api.md) em vez do wrapper.
