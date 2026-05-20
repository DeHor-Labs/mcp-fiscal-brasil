# Tools agenticas

Tools de **alto nivel** desenhadas para uso por agentes de IA (Claude, GPT, Gemini). Cada tool combina multiplos clientes de baixo nivel em uma chamada com saida estruturada e rica em descricoes (otimizada para LLMs).

## Disponiveis (v0.2.0)

| Tool | O que faz |
|------|-----------|
| [`analyze_cnpj_compliance`](compliance.md) | Relatorio consolidado: CNPJ + Simples + MEI + CNAE, score 0-100, risco |
| [`compare_tax_regimes`](regimes.md) | Comparativo MEI/Simples/Lucro Presumido/Lucro Real |
| [`risk_score_supplier`](supplier.md) | Due diligence de fornecedor com recomendacao |
| [`validate_nfe_full`](nfe.md) | NFe: parse XML + chave + situacao do emissor |
| [`summarize_sped`](sped.md) | Sumario executivo de arquivo SPED |

## Por que agentic

Tools de baixo nivel (ex: `consultar_cnpj`, `validar_chave_nfe`) sao uteis, mas exigem que o agente saiba combinar varias chamadas para uma decisao. Tools agenticas resolvem isso:

- Composem multiplos clientes em uma chamada
- Retornam respostas com **score normalizado**, **risco classificado** e **resumo executivo**
- Schema pydantic com `description` em cada campo (auto-explicativo para LLMs)
- Capturam falhas parciais sem bloquear a analise (uma fonte offline nao quebra a tool)

## Exemplo end-to-end

Cenario: agente IA precisa decidir se contratar um fornecedor.

**Sem agentic** (3+ chamadas):
1. `consultar_cnpj(...)` -> dados cadastrais
2. `consultar_simples_nacional(...)` -> regime
3. `consultar_certidao_federal(...)` -> link
4. agente combina manualmente, gera score, decide

**Com agentic** (1 chamada):
```python
score = await risk_score_supplier("12345678000190", criterios_estritos=True)
if score.recomendacao == "recusar":
    return "Bloqueado: " + ", ".join(score.fatores)
```

Em ferramentas como Claude Desktop, o agente IA pode chamar diretamente:

> "Faca due diligence no CNPJ 12.345.678/0001-90 com criterios estritos"

E recebe a resposta consolidada em 1 turno.
