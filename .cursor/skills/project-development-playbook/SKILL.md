# project-development-playbook

Apply one consistent delivery workflow across backend and frontend tasks.

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

Unless user specifies otherwise, use React + TypeScript + Vite + Tailwind.

For UI/UX work, start with:

```bash
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system -p "<project-name>"
```

## Verification Checklist

Run what applies:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```
