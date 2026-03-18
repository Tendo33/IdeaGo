# Claude Code Project Instructions

Use this file as the default project contract for Claude Code.

## Workflow

1. Confirm scope and assumptions.
2. Implement the smallest safe change set.
3. Verify results with project commands.
4. Report changes with file paths and rationale.

## Engineering Rules

- **Read `ai_docs/` for project standards before starting work.**
- Core contract: `ai_docs/AI_TOOLING_STANDARDS.md` (contains full index of all docs).
- Backend rules: `ai_docs/BACKEND_STANDARDS.md`.
- Frontend rules: `ai_docs/FRONTEND_STANDARDS.md`.
- Scripts (rename/version): `ai_docs/SCRIPTS_GUIDE.md`.
- Keep code typed, readable, and modular.
- Preserve existing project conventions unless asked to change them.

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
cat .claude/skills/backend-engineering-playbook/SKILL.md
```

## Required Verification

Run relevant checks before completion:

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
