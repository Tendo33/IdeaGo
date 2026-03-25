# AI Tooling Standards

This document defines one shared engineering contract for all AI assistants used in this repository.

**Before starting any task, read the relevant documents in `ai_docs/` first.**

## ai_docs/ Index

| Document | Purpose |
| :--- | :--- |
| `AI_TOOLING_STANDARDS.md` | This file — shared contract for all AI tools |
| `BACKEND_STANDARDS.md` | Backend architecture, layering, API conventions |
| `FRONTEND_STANDARDS.md` | Frontend stack, directory structure, component conventions |
| `SCRIPTS_GUIDE.md` | How to rename the package and update version numbers |
| `MODELS_GUIDE.md` | Pydantic model rules for this project |
| `SETTINGS_GUIDE.md` | Configuration management with pydantic-settings |
| `SDK_USAGE.md` | src-layout import conventions |
| `PRE_COMMIT_GUIDE.md` | Pre-commit hooks setup and usage |

## Tool Configuration Map

- Cursor: `.cursorrules`, `.cursor/rules/*.mdc`, `.cursor/skills/*`
- Codex: `AGENTS.md`, `.codex/skills/*`
- Claude Code: `CLAUDE.md`, `.claude/skills/*`
- Anti-Gravity Agent: `.agent/rules/*.md`, `.agent/skills/*`

## Shared Engineering Contract

1. Plan before coding: restate goal, list assumptions, then implement.
2. Keep edits small and reviewable; avoid broad refactors without explicit request.
3. Prefer existing project conventions over personal preference.
4. Verify before claiming completion.

## Current V2 Contract Boundaries

- Reports are decision-first: recommendation, pain signals, commercial signals, whitespace opportunities, competitors, then evidence and confidence.
- Treat backend report payloads and frontend shared types as explicit contracts that must be updated together when the shape changes.
- Keep LangGraph state, extraction output, and aggregation carriers typed; do not smuggle V2 signal data through anonymous dict side channels.
- Keep `pipeline/merger.py` limited to deterministic competitor dedupe.
- Keep whitespace and entry-wedge synthesis in `pipeline/aggregator.py`, where evidence-backed report assembly is coordinated.
- Source roles are fixed unless a task explicitly changes the source set: Tavily handles broad recall, Reddit pain and switching language, GitHub open-source maturity, Hacker News builder discourse, App Store review-cluster pain, Product Hunt launch positioning.
- Retrieval and ranking changes should stay opportunity-first: corroborated pain, commercial intent, migration signals, and whitespace evidence outrank raw popularity alone.

## Backend Stack (Python)

- Runtime: Python 3.10+
- Dependency management: `uv`
- Lint/format: `ruff`
- Tests: `pytest`
- Style: type hints required, explicit error handling, small pure functions preferred

Current backend stack:

- FastAPI for HTTP API layer
- Pydantic v2 for DTO/schema validation
- Supabase (PostgREST) + local file cache for persistence
- SQL migrations in `supabase/migrations/`
- Stripe SDK for billing
- Structured error codes via `AppError` / `ErrorCode` (`api/errors.py`)

Backend verification:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

For detailed backend engineering rules, see `ai_docs/BACKEND_STANDARDS.md`.

## Frontend Stack

For detailed frontend engineering rules, see `ai_docs/FRONTEND_STANDARDS.md`.

Fixed tech stack — do not change unless explicitly requested:

| Layer | Choice |
| :--- | :--- |
| Package manager | **pnpm** |
| Framework | React |
| Language | TypeScript (strict) |
| Bundler | Vite |
| Styling | Tailwind CSS |
| Component library | **shadcn/ui** |

Preferred layout:

- `frontend/src/app` — app shell and routing
- `frontend/src/features/*` — domain modules
- `frontend/src/components/ui` — shadcn/ui primitives and shared components
- `frontend/src/lib` — utilities and API wrappers

Frontend conventions:

- Use shadcn/ui components as building blocks; customize via Tailwind and CSS variables.
- Prefer semantic HTML, keyboard accessibility, and visible focus states.
- Avoid `any` except for documented edge cases.

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
- edge cases are covered,
- docs/config are updated if behavior or workflow changed.
