# Analytical Chat Queries Context

**Gathered:** 2026-10-31
**Spec:** `.specs/features/analytical-chat-queries/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Improve the chat's analytical correctness for sales questions, present useful
summaries, and make validated read-only queries execute automatically in the
React frontend. The existing broad LLM fallback, safety boundary, and Streamlit
coexistence remain in scope only as compatibility constraints.

---

## Implementation Decisions

### Result behavior

- The default answer is a concise executive summary followed by the detailed
  result table.
- The SQL remains available in a collapsed details control.

### Execution behavior

- The normal React chat path uses automatic execution for validated read-only
  queries.
- Explicit API callers can continue to request review mode.

### Business semantics

- Completed sales are the default (`status = 'concluida'`).
- Receipt-level revenue uses `vendas.valor_total`.
- Product-level value uses `itens_venda.subtotal`.
- Product questions aggregate by product rather than returning raw item rows.

### Agent's Discretion

- The exact deterministic recognition strategy for the supported Portuguese
  sales intents.
- The exact summary wording, provided it is derived from returned data.
- The exact UI element used for collapsed SQL details, provided it remains
  accessible and does not duplicate the result.

---

## Specific References

- The user explicitly selected “Resumo executivo + tabela detalhada”.
- The user explicitly selected “Executar automaticamente e mostrar SQL
  recolhido”.
- The database inspection showed `vendas`, `itens_venda`, and `produtos` are
  the relevant tables.

---

## Deferred Ideas

- Automatic reconciliation of `vendas.valor_total` against item subtotals.
- A user settings screen for choosing review versus automatic execution.
- A general semantic planner for every domain and table in the database.
