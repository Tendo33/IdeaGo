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
- File cache + SQLite checkpoints
- Supabase-backed authentication/session support already exists

### Frontend

- `pnpm` only
- React 19 + TypeScript + Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- `i18next`, `@supabase/supabase-js`, `framer-motion`, `recharts`

## Current Project Shape

### Backend package

Main package: `src/ideago`

- `api/`: FastAPI app, dependencies, schemas, `auth` / `analyze` / `reports` / `health` routes
- `auth/`: auth dependencies, Supabase admin helpers, auth models
- `cache/`: cache abstractions, file cache, Supabase cache
- `config/`: runtime settings
- `contracts/`: protocols and interfaces
- `core/`: shared runtime context
- `llm/`: model wrappers, prompt loader, prompt templates
- `models/`: domain models
- `observability/`: logging setup
- `pipeline/`: LangGraph engine, nodes, events, merger, extractor, intent parser
- `sources/`: GitHub, Tavily, Hacker News, App Store, Product Hunt, Reddit sources
- `utils/`: shared helper utilities

### Frontend layout

- `frontend/src/app`: app shell and routing
- `frontend/src/features/auth`: login and auth callback flow
- `frontend/src/features/history`: report history
- `frontend/src/features/home`: main search experience
- `frontend/src/features/landing`: landing page
- `frontend/src/features/profile`: user profile
- `frontend/src/features/reports`: report details, compare views, charts, progress states
- `frontend/src/components/ui`: shared UI primitives
- `frontend/src/lib/api`: typed API client and SSE hook
- `frontend/src/lib/auth`: auth context, token helpers, protected route
- `frontend/src/lib/i18n`: locale setup and translations
- `frontend/src/lib/supabase`: Supabase client
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

- Docker Compose uses the prebuilt image `simonsun3/ideago:latest`.
- Current user flow is: submit idea -> create analysis job -> stream progress over SSE -> read persisted report/history.
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
