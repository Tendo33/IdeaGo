# Codex Project Instructions

Use this file as the default project contract for Codex.

## Workflow

1. Understand the request and constraints.
2. Read the relevant docs in `ai_docs/` before editing.
3. Propose concise implementation steps.
4. Implement with minimal, targeted changes.
5. Run verification commands before claiming completion.

## Engineering Rules

- **Read `ai_docs/` for project standards before starting work.**
- Core contract: `ai_docs/AI_TOOLING_STANDARDS.md`.
- Backend rules: `ai_docs/BACKEND_STANDARDS.md`.
- Frontend rules: `ai_docs/FRONTEND_STANDARDS.md`.
- Models: `ai_docs/MODELS_GUIDE.md`.
- Settings: `ai_docs/SETTINGS_GUIDE.md`.
- SDK/import conventions: `ai_docs/SDK_USAGE.md`.
- Scripts and versioning: `ai_docs/SCRIPTS_GUIDE.md`.
- Pre-commit: `ai_docs/PRE_COMMIT_GUIDE.md`.
- Keep functions small, typed, and testable.
- Handle errors explicitly; avoid silent failures.
- Prefer updating existing files over creating new files.
- If behavior, workflow, or structure changes, update docs in the same task.

## Current Stack

### Backend

- Python 3.10+
- `uv`, `ruff`, `pytest`, `mypy`
- FastAPI + Pydantic v2
- LangGraph + LangChain OpenAI
- File cache + Supabase cache + SQLite checkpoints
- Supabase-backed authentication/session support
- Stripe SDK for billing integration

### Frontend

- `pnpm` only
- React 19 + TypeScript + Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- `i18next`, `@supabase/supabase-js`, `framer-motion`, `recharts`

## Current Project Shape

### Source Intelligence V2

- The product is now an idea-validation system, not just a competitor lookup flow.
- Persisted reports are decision-first: recommendation / why-now, pain signals, commercial signals, whitespace opportunities, competitors, then evidence and confidence.
- Competitor discovery remains required, but it is only one section inside the report contract.
- `/api/v1/reports/{report_id}` and report exports should be treated as explicit contracts, not implicit `model_dump()` surfaces.
- Pipeline state and evidence handoff should stay typed; do not introduce anonymous dict side channels for signal-rich report data.
- `pipeline/merger.py` remains deterministic competitor dedupe only; whitespace and entry-wedge synthesis belong in `pipeline/aggregator.py`.
- Fixed source roles: Tavily for broad recall, Reddit for pain/migration language, GitHub for open-source and ecosystem maturity, Hacker News for builder sentiment, App Store for review-cluster pain, Product Hunt for launch positioning.
- Ranking direction is opportunity-first: pain, commercial, migration, and corroborated whitespace evidence should outrank simple popularity or SEO visibility.

### Backend package

Main package: `src/ideago`

- `api/`: FastAPI app, dependencies, schemas, errors, `auth` / `analyze` / `reports` / `billing` / `health` routes
- `auth/`: auth dependencies, Supabase admin helpers, auth models
- `billing/`: Stripe checkout, portal, webhook processing
- `cache/`: cache abstractions (ReportRepository protocol), file cache, Supabase cache
- `config/`: runtime settings (Pydantic)
- `contracts/`: protocols and interfaces
- `core/`: shared runtime context
- `llm/`: model wrappers, prompt loader, prompt templates
- `models/`: domain models
- `observability/`: logging setup
- `pipeline/`: LangGraph engine, nodes, events, merger, extractor, intent parser
  - Query flow is now `intent_parser -> query_planning_rewriting -> platform_adaptation -> sources -> extractor -> aggregator`
  - `nodes.py` keeps graph-node orchestration entry points
  - `nodes_orchestration.py` / `nodes_extraction.py` / `nodes_confidence.py` / `nodes_report_assembly.py` hold split helper logic
  - `query_planning.py` owns typed query planning/rewrite plus LLM-first planner fallback
- `sources/`: GitHub, Tavily, Hacker News, App Store, Product Hunt, Reddit sources
- `utils/`: shared helper utilities

### Frontend layout

- `frontend/src/app`: app shell and routing
- `frontend/src/features/auth`: login and auth callback flow
- `frontend/src/features/history`: report history
- `frontend/src/features/home`: main search experience
- `frontend/src/features/landing`: landing page
- `frontend/src/features/pricing`: plan selection and Stripe checkout
- `frontend/src/features/profile`: user profile and subscription management
- `frontend/src/features/reports`: report details, compare views, charts, progress states
- `frontend/src/components/ui`: shared UI primitives
- `frontend/src/lib/api`: typed API client (incl. billing endpoints) and SSE hook
- `frontend/src/lib/auth`: auth context, token helpers, protected route
- `frontend/src/lib/i18n`: locale setup and translations (en, zh)
- `frontend/src/lib/supabase`: Supabase client
- `frontend/src/lib/types`, `frontend/src/lib/utils`: shared types and utilities
- `frontend/src/styles`: global styles
- Pricing and upgrade UI entry points are intentionally hidden until billing is re-enabled; avoid exposing `/pricing` or upgrade CTAs unless the task explicitly restores them.

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

- Docker Compose uses the prebuilt image `simonsun3/ideago:latest`.
- Current user flow is: submit idea -> create analysis job -> stream progress over SSE -> read persisted report/history.
- Report detail and export consumers should expect the decision-first V2 shape, not a competitor-first payload.
- Auth-related env already includes Supabase and LinuxDo OAuth settings.

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
