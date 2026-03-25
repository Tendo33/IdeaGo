# Claude Code Project Instructions

Use this file as the default project contract for Claude Code.

## Workflow

1. Understand the request and branch target.
2. Read the relevant docs in `ai_docs/` before editing.
3. Keep the change set small and typed.
4. Update docs/config when behavior or structure changes.
5. Run the required verification before claiming completion.

## Branch Model

- `main`: personal/open-source deployment only.
- `saas`: same core product as `main`, plus auth, billing, profile, admin, and SaaS-only env vars.
- Public/core product work flows `main -> saas`.
- Do not add new SaaS runtime dependencies to `main`.

## Current Product Contract

- Product contract is Source Intelligence V2, decision-first.
- Reports must stay ordered as: recommendation / why-now, pain signals, commercial signals, whitespace opportunities, competitors, evidence, confidence.
- `pipeline/merger.py` remains deterministic competitor dedupe only.
- Whitespace and entry-wedge synthesis belong in `pipeline/aggregator.py`.
- Report payloads and frontend shared report types are explicit contracts and must be updated together.

## Current Stack

### Backend

- Python 3.10+
- `uv`, `ruff`, `pytest`, `mypy`
- FastAPI + Pydantic v2
- LangGraph + LangChain OpenAI
- File cache for persisted reports
- SQLite checkpoints for LangGraph runtime state
- Anonymous analyze/history/report/export flow on `main`

### Frontend

- `pnpm` only
- React 19 + TypeScript + Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- `i18next`, `framer-motion`, `recharts`

## Current Project Shape

### Backend package

Main package: `src/ideago`

- `api/`: FastAPI app, dependencies, schemas, errors, `analyze` / `reports` / `health` routes
- `cache/`: cache abstractions and local file cache
- `config/`: runtime settings
- `contracts/`: protocols and interfaces
- `core/`: shared runtime context
- `llm/`: model wrappers and prompt loading
- `models/`: domain models
- `observability/`: logging and metrics
- `pipeline/`: LangGraph engine, nodes, events, merger, extractor, intent parser
- `sources/`: GitHub, Tavily, Hacker News, App Store, Product Hunt, Reddit
- `utils/`: shared helpers

### Frontend layout

- `frontend/src/app`: app shell and routing
- `frontend/src/features/history`: report history
- `frontend/src/features/home`: main search experience
- `frontend/src/features/legal`: legal pages
- `frontend/src/features/reports`: report detail, compare views, charts, progress states
- `frontend/src/components/ui`: shared UI primitives
- `frontend/src/lib/api`: typed API client and SSE hook
- `frontend/src/lib/i18n`: locale setup and translations
- `frontend/src/lib/types`, `frontend/src/lib/utils`: shared types and utilities
- `frontend/src/styles`: global styles

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

- Current user flow is: submit idea -> create analysis job -> stream progress over SSE -> read persisted report/history.
- `main` must boot and run without Supabase, Stripe, or LinuxDo variables.

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

- Keep `AGENTS.md`, `CLAUDE.md`, and `ai_docs/` aligned when conventions change.
- Prefer `ai_docs/` paths, not legacy `doc/` paths.
- Verify commands against `pyproject.toml`, `frontend/package.json`, and the current repo structure before updating docs.
