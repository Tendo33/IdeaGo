# AI Tooling Standards

This document defines the shared engineering contract for AI assistants working in this repository.

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

- `main` is the personal/open-source deployment line.
- `saas` adds commercial runtime features on top of `main`.
- Shared product work lands in `main` first, then merges into `saas`.
- Do not reintroduce Supabase, Stripe, LinuxDo, or account runtime requirements into `main`.

## Shared Engineering Contract

1. Plan before coding.
2. Prefer minimal, reviewable edits.
3. Follow the existing project architecture.
4. Update docs and env examples when behavior changes.
5. Verify before claiming completion.

## Current V2 Contract Boundaries

- Reports are decision-first: recommendation, why-now, pain signals, commercial signals, whitespace opportunities, competitors, then evidence and confidence.
- Backend report payloads and frontend shared types are explicit contracts.
- Keep LangGraph state, extraction outputs, and aggregation carriers typed.
- `pipeline/merger.py` is deterministic competitor dedupe only.
- Whitespace and opportunity synthesis belongs in `pipeline/aggregator.py`.
- Source roles are fixed unless the task explicitly changes them: Tavily, Reddit, GitHub, Hacker News, App Store, Product Hunt.
- Retrieval and ranking stay opportunity-first rather than popularity-first.

## Backend Stack

- Python 3.10+
- `uv`
- `ruff`
- `pytest`
- `mypy`
- FastAPI
- Pydantic v2
- LangGraph + LangChain OpenAI
- Local file cache for reports
- SQLite checkpoints for pipeline state

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

Frontend verification:

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Definition of Done

A task is done only when:

- requested behavior is implemented,
- relevant checks pass,
- docs/config/examples are updated if needed,
- `main` still works without SaaS env vars.
