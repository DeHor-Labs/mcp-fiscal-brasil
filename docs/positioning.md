# MCP Fiscal Brasil — Posicionamento

## Visão de produto

Este projeto é a camada de inteligência fiscal de **alto volume** para a rotina brasileira:  
mais rápido que pesquisa manual, mais estruturado que consultas soltas, e com saída pronta para decisão.

## Promessa operacional da vertical fiscal

- **Fornecedores**: `risk_score_supplier`, `consultar_empresas_lote` e `analyze_cnpj_compliance` para risco, aprovação e triagem em volume.
- **Nota fiscal recebida**: `validate_nfe_full` para validar XML, chave e situação cadastral do emissor.
- **Arquivo contábil**: `summarize_sped` para extrair pontos de atenção por período.
- **Planejamento tributário**: `compare_tax_regimes` para escolha preliminar de carga.
- **Conciliação e revisão**: uso combinado de compliance + regimes em fluxos de rotina.

## O que está pronto (agora)

| Área | Entrega | Resultado prático |
|------|---------|------------------|
| Due diligence | `risk_score_supplier` / `consultar_empresas_lote` | Score, risco e recomendação por CNPJ, inclusive em volume |
| NFe | `validate_nfe_full` | Validação estruturada do XML + chave + situação do emissor |
| SPED | `summarize_sped` | Sumário com período, total de registros e inconsistências |
| Regimes | `compare_tax_regimes` | Ranking de MEI / Simples / Lucro Presumido / Lucro Real |
| Compliance | `analyze_cnpj_compliance` | Score + achados + resumo executivo |

## Roadmap e lacunas explícitas

- Não há emissão automática de certidões (`CND`, `CRF`, etc.), apenas orientação com fontes oficiais.
- Validação avançada de NFe (XSD, eventos, cancelamento, distribuições complexas) ainda não cobre todo o ecossistema de cenário real.
- Comparador de regimes é estimado com premissas públicas agregadas; não inclui todos os benefícios, regimes especiais ou regras estaduais.
- SPED atualiza principalmente leitura e inconsistências estruturais básicas, não substituindo uma revisão fiscal completa.
- O projeto já disponibiliza interface MCP/CLI/REST para automação, com foco em decisões assistidas, não parecer legal final.

## Arquitetura de adoção em squads

1. Comece com **um workflow único** por vez (ex.: due diligence).
2. Defina política de risco (`criterios_estritos`/não estritos).
3. Registre decisões e razões em logs estruturados.
4. Expanda para NFe + SPED + comparação de regime apenas após reduzir ruído do fluxo anterior.

## Acesso rápido por cenário

- [Validação em lote de fornecedores](use-cases/due-diligence.md)
- [Aprovação rápida de fornecedor](use-cases/supplier-validation.md)
- [Validação de NFe](agentic/nfe.md)
- [Planejamento de regime](use-cases/tax-planning.md)
- [Relatório de compliance consolidado](use-cases/compliance-report.md)
- [Comparação de SPED](agentic/sped.md)
