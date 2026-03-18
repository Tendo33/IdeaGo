# Codex Project Instructions

Use this file as the default project contract for Codex.

## Workflow

1. Understand request and constraints.
2. Propose concise implementation steps.
3. Implement with minimal, targeted edits.
4. Run verification commands before completion claims.

## Engineering Rules

- **Read `ai_docs/` for project standards before starting work.**
- Core contract: `ai_docs/AI_TOOLING_STANDARDS.md` (contains full index of all docs).
- Backend rules: `ai_docs/BACKEND_STANDARDS.md`.
- Frontend rules: `ai_docs/FRONTEND_STANDARDS.md`.
- Scripts (rename/version): `ai_docs/SCRIPTS_GUIDE.md`.
- Keep functions small, typed, and testable.
- Handle errors explicitly; avoid silent failures.

## Tech Stack

### Backend

- Python 3.10+ / uv / ruff / pytest
- FastAPI + Pydantic v2 (when API is needed)
- SQLAlchemy + Alembic (when persistence is needed)

### Frontend

- **pnpm** (package manager)
- React + TypeScript + Vite
- Tailwind CSS + **shadcn/ui** (component library)

Layout convention:

- `frontend/src/app` — app shell and routing
- `frontend/src/features/*` — domain modules
- `frontend/src/components/ui` — shadcn/ui primitives and shared components
- `frontend/src/lib` — utilities and API wrappers

For backend-focused work, use:

```bash
cat .codex/skills/backend-engineering-playbook/SKILL.md
```

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
