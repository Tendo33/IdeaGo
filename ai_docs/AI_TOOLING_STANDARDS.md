# AI Tooling Standards

This document defines the shared engineering contract for AI assistants working on the `main`
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
- `saas` adds hosted runtime features on top of `main`.
- Shared product work lands in `main` first when possible.
- Do not reintroduce Supabase, Stripe, LinuxDo, or account runtime requirements into `main`.

## Shared Engineering Contract

1. Plan before coding.
2. Prefer minimal, reviewable edits.
3. Follow the existing project architecture and typed report contract.
4. Update docs and env examples when behavior changes.
5. Verify before claiming completion.

## Current V2 Contract Boundaries

- Reports are decision-first: recommendation, why-now, pain signals, commercial signals, whitespace opportunities, competitors, evidence, confidence.
- Frontend report sections and anchors must preserve that order one-to-one.
- Backend report payloads and frontend shared report types are explicit contracts.
- Keep LangGraph state, extraction outputs, and aggregation carriers typed.
- `pipeline/merger.py` is deterministic competitor dedupe only.
- Whitespace and opportunity synthesis belongs in `pipeline/aggregator.py`.
- Source roles are fixed unless a task explicitly changes them: Tavily, Reddit, GitHub, Hacker News, App Store, Product Hunt.
- Retrieval and ranking stay opportunity-first rather than popularity-first.

## Main-Branch Runtime Notes

- `main` is anonymous and personal-deployment oriented.
- No auth, profile, admin, or billing runtime should be required.
- Docker Compose on `main` pulls the published image by default.
- The active frontend route surface stays intentionally small.
- Anonymous requests use a stable client-generated `X-Session-Id`; mutating routes still rely on `X-Requested-With`.
- SSE retries are capped and fall back to report status polling rather than retrying forever.

## Backend Stack

- Python 3.10+
- `uv`
- `ruff`
- `pytest`
- `mypy`
- FastAPI
- Pydantic v2
- LangGraph + LangChain OpenAI
- local file cache for reports
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
- do not commit `package-lock.json`
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
- `main` still works without hosted env vars.
