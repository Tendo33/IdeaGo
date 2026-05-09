# Dependencies

Use this when adding or updating dependencies on the `saas` branch.

## Baseline

| Area | Tooling |
| --- | --- |
| Python runtime | Python 3.10+ |
| Python package manager | `uv` |
| Python quality | `ruff`, `mypy`, `pytest` |
| Backend API | FastAPI, Pydantic v2, `pydantic-settings` |
| Pipeline/LLM | LangGraph, LangChain OpenAI, OpenAI-compatible settings |
| Hosted data/auth | Supabase, PostgREST/RPC helpers, JWT/cookie session helpers |
| Billing | Stripe integration code; public pricing stays hidden |
| Observability | `loguru`, audit helpers, metrics, Sentry when configured |
| Frontend package manager | `pnpm` |
| Frontend runtime | React 19, TypeScript strict mode |
| Frontend build | Vite 7 |
| Frontend styling | Tailwind CSS v4, project-owned UI primitives |
| Frontend routing | React Router 7 |
| Frontend testing | Vitest, Testing Library, jsdom |

## Rules

- Check existing dependencies before adding a new one.
- Prefer the standard library or existing project helper when it is enough.
- Keep hosted-only dependencies on `saas` unless the task explicitly targets
  both branches.
- Do not expose backend-only secrets through `VITE_*` variables.
- Docker and CI must use `pnpm` for frontend installs/builds.
- Update docs and verification commands when a dependency changes project
  setup, build, or runtime behavior.

## Search Before Adding

```bash
rg "\"dependency-name\"" pyproject.toml frontend/package.json
rg "from dependency_name|import dependency_name" src tests scripts
rg "dependency-name" frontend/src
```
