# Claude Code Project Instructions

Use this file as the default project contract for Claude Code on the `saas` branch.

## Workflow

1. Understand the request and whether it affects `saas`, `main`, or both.
2. Read the relevant docs in `ai_docs/` before editing.
3. Keep changes small, typed, and branch-correct.
4. Update docs and env examples when behavior or workflow changes.
5. Run the applicable verification commands before claiming completion.

## Branch Model

- `main`: anonymous/personal deployment edition
- `saas`: hosted/commercial edition built on top of `main`
- shared product work should land on `main` first when practical
- do not move hosted-only runtime dependencies back into `main`

## Current Product Contract

- Product contract is Source Intelligence V2 and decision-first.
- Reports stay ordered as: recommendation / why-now, pain signals, commercial signals, whitespace opportunities, competitors, evidence, confidence.
- `/api/v1/reports/{report_id}` and export payloads are explicit contracts.
- `pipeline/merger.py` remains deterministic competitor dedupe only.
- Whitespace and entry-wedge synthesis belongs in `pipeline/aggregator.py`.
- Keep typed state and typed evidence carriers across orchestration, extraction, and report assembly.

## Current Stack

### Backend

- Python 3.10+
- `uv`, `ruff`, `pytest`, `mypy`
- FastAPI + Pydantic v2
- LangGraph + LangChain OpenAI
- file cache plus Supabase-backed report persistence
- SQLite checkpoints plus hosted runtime state
- Supabase-backed auth/session support
- Stripe integration code, with public pricing flow intentionally hidden

### Frontend

- `pnpm` only
- React 19 + TypeScript + Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- `i18next`, `@supabase/supabase-js`, `framer-motion`, `recharts`
- project-owned shared UI primitives in `frontend/src/components/ui`

## Current Project Shape

### Backend package

Main package: `src/ideago`

- `api/`: FastAPI app, middleware, schemas, errors, `auth` / `analyze` / `reports` / `billing` / `admin` / `health`
- `auth/`: auth dependencies, cookie session helpers, Supabase admin helpers
- `billing/`: Stripe checkout, portal, webhook plumbing
- `cache/`: report repository abstraction with file and Supabase implementations
- `config/`: runtime settings
- `contracts/`: protocols and interfaces
- `core/`: shared runtime context
- `llm/`: model wrappers and prompt loading
- `models/`: domain models
- `observability/`: logging, audit, metrics, error catalog
- `pipeline/`: orchestration, extraction, aggregation, typed report assembly
- `sources/`: GitHub, Tavily, Hacker News, App Store, Product Hunt, Reddit

### Frontend layout

- `frontend/src/app`: router, shell, navbar, error boundary
- `frontend/src/features/auth`: login and auth callback flow
- `frontend/src/features/history`: report history
- `frontend/src/features/home`: signed-in workspace
- `frontend/src/features/landing`: signed-out marketing page
- `frontend/src/features/legal`: terms and privacy pages
- `frontend/src/features/profile`: user profile and account settings
- `frontend/src/features/reports`: report detail and progress views
- `frontend/src/features/admin`: admin dashboard
- `frontend/src/components/ui`: shared UI primitives
- `frontend/src/lib/api`: typed API client and SSE hook
- `frontend/src/lib/auth`: auth context, redirect helpers, token handling
- `frontend/src/lib/i18n`: locale setup and translations

## Runtime Notes

- Backend dev server:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

- Frontend dev server:

```bash
pnpm --prefix frontend dev
```

- Single-process local run:

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

- `docker-compose.yml` builds a local image from the current repo.
- Current user flow is: landing/login -> authenticated workspace -> analysis -> SSE progress -> persisted history/detail.
- Frontend auth currently supports Supabase sessions plus LinuxDo cookie-backed recovery.
- Pricing and upgrade entry points are intentionally hidden until a task explicitly restores them.

## Required Verification

Run what applies to the task:

```bash
# Backend
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest

# Frontend
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Documentation Hygiene

- Keep `README.md`, `README_CN.md`, `DEPLOYMENT.md`, `frontend/README.md`, `AGENTS.md`, `CLAUDE.md`, and `ai_docs/` aligned when conventions change.
- Prefer `ai_docs/` paths, not legacy `doc/` paths.
- Verify commands against `pyproject.toml`, `frontend/package.json`, and the current repo structure before updating docs.
