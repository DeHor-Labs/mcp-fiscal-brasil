# Node.js wrapper preview

Wrapper Node.js/TypeScript que envelopa o CLI Python para uso em apps JavaScript/TypeScript.

!!! warning "Preview de distribuição"

    O código do wrapper está em `npm-wrapper/`, mas o pacote ainda não foi publicado no npm registry.
    Para produção hoje, prefira a [REST API](rest-api.md) ou o SDK Python. Esta página documenta o contrato planejado e o uso local do wrapper.

## Pré-requisito

O CLI Python precisa estar instalado no `PATH`:

```bash
pipx install mcp-fiscal-brasil
mcp-fiscal --help  # deve responder
```

## Uso local

```bash
cd npm-wrapper
npm install
npm run build
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

// Planejamento tributário
const regimes = await compareRegimes({
  faturamento: 500_000,
  setor: "serviços",
  folha: 180_000,
});
console.log(regimes.melhor_opcao);
```

## CLI passthrough local

```bash
node dist/cli.js cnpj 12345678000190
node dist/cli.js regimes --faturamento 500000 --setor serviços
```

## Trade-offs

Como o wrapper spawna o CLI Python via subprocess:

- **Overhead**: 50-150ms por chamada
- **Pré-requisito**: Python instalado
- **Beneficio**: zero drift entre ecossistemas Python e Node

Para apps Node de alto throughput, considere usar a [REST API](rest-api.md) em vez do wrapper.
