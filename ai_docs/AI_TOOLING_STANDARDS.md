# AI Tooling Standards

This document defines the shared engineering contract for AI assistants working on the `saas`
branch.

## Read Order

Before editing, read the relevant docs in `ai_docs/`:

- `AI_TOOLING_STANDARDS.md`
- `BACKEND_STANDARDS.md`
- `FRONTEND_STANDARDS.md`
- `MODELS_GUIDE.md`
- `SETTINGS_GUIDE.md`
- `SDK_USAGE.md`
- `SCRIPTS_GUIDE.md`
- `PRE_COMMIT_GUIDE.md`

## Branch Model

- `main` is the anonymous/personal deployment line.
- `saas` is the hosted/commercial line.
- Shared product changes should land in `main` first when possible.
- Hosted-only runtime dependencies must stay on `saas`.

## Shared Engineering Contract

1. Plan before coding.
2. Prefer minimal, reviewable edits.
3. Follow the existing typed report contract.
4. Update docs and env examples when behavior changes.
5. Verify before claiming completion.

## Current V2 Contract Boundaries

- Reports are decision-first: recommendation, why-now, pain signals, commercial signals, whitespace opportunities, competitors, evidence, confidence.
- Backend report payloads and frontend shared report types are explicit contracts.
- Keep LangGraph state, extraction outputs, and aggregation carriers typed.
- `pipeline/merger.py` is deterministic competitor dedupe only.
- Whitespace and opportunity synthesis belongs in `pipeline/aggregator.py`.
- Source roles stay fixed unless a task explicitly changes them: Tavily, Reddit, GitHub, Hacker News, App Store, Product Hunt.
- Retrieval and ranking stay opportunity-first rather than popularity-first.

## Hosted Runtime Notes

- `saas` adds auth, profile ownership, admin APIs, hosted persistence, and LinuxDo OAuth on top of `main`.
- Billing code is present, but pricing discovery is intentionally hidden right now.
- Frontend auth relies on Supabase sessions plus backend cookie recovery for LinuxDo sessions.
- Docker Compose on `saas` builds the app from source instead of pulling the published `main` image.

## Backend Stack

- Python 3.10+
- `uv`
- `ruff`
- `pytest`
- `mypy`
- FastAPI
- Pydantic v2
- LangGraph + LangChain OpenAI
- file cache plus Supabase-backed persistence
- SQLite checkpoints plus hosted runtime state
- Stripe integration plumbing

Backend verification:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

## Frontend Stack

- `pnpm`
- React 19
- TypeScript
- Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- project-owned shared UI primitives in `frontend/src/components/ui`

Frontend verification:

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Definition Of Done

A task is done only when:

- requested behavior is implemented,
- relevant checks pass,
- docs/config/examples are updated if needed,
- branch-specific differences remain documented correctly.
