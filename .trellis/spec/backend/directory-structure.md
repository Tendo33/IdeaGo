# Backend Directory Structure

Use this when adding files under `src/ideago`.

```text
src/ideago/
├── api/
├── auth/
├── billing/
├── cache/
├── config/
├── contracts/
├── core/
├── llm/
├── models/
├── notifications/
├── observability/
├── pipeline/
├── sources/
└── utils/
```

## Placement Rules

| New thing | Default location |
| --- | --- |
| FastAPI app, route, middleware, schema, or API error | `src/ideago/api/` |
| Supabase user/profile/session/auth dependency | `src/ideago/auth/` |
| Stripe checkout, portal, customer, subscription, webhook | `src/ideago/billing/` |
| Report persistence or status repository behavior | `src/ideago/cache/` |
| Runtime settings field or settings helper | `src/ideago/config/` |
| Protocol/interface shared across modules | `src/ideago/contracts/` |
| LLM model invocation or prompt-loading behavior | `src/ideago/llm/` |
| Reusable Pydantic domain/report model | `src/ideago/models/` |
| Pipeline orchestration, nodes, extraction, aggregation, events | `src/ideago/pipeline/` |
| External source adapter | `src/ideago/sources/` |
| Cross-cutting helper with 2+ real users | `src/ideago/utils/` |

## Rules

- Keep route handlers thin and push pipeline/business behavior into the modules
  that own it.
- Keep repository details behind `ReportRepository`.
- Do not mix API response models with persistence payload quirks unless they
  are intentionally the same contract.
- Add tests beside the behavior being changed; do not rely only on snapshots or
  manual API checks.
