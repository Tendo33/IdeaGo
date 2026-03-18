# project-development-playbook

Apply one consistent delivery workflow across backend and frontend tasks.

**Reference:** Read `ai_docs/AI_TOOLING_STANDARDS.md` for the full docs index before starting.

## Workflow

1. Confirm scope and assumptions.
2. Choose implementation path (backend, frontend, full stack).
3. Implement minimal changes aligned with project conventions.
4. Run relevant verification commands.
5. Report what changed and what was verified.

## Backend Defaults

- Python 3.10+
- `uv` for dependencies and execution
- `ruff` for lint/format
- `pytest` for tests

For deeper backend architecture rules, use `backend-engineering-playbook`.

## Frontend Defaults

Fixed stack: pnpm + React + TypeScript + Vite + Tailwind CSS + shadcn/ui.

- Use shadcn/ui as the component library; customise via Tailwind and CSS variables.
- UI primitives go in `frontend/src/components/ui`.
- Domain modules go in `frontend/src/features/*`.

## Verification Checklist

Run what applies:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
