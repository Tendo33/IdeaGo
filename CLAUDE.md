# Claude Code Project Instructions

Use this file as the default project contract for Claude Code.

## Workflow

1. Confirm scope and assumptions.
2. Implement the smallest safe change set.
3. Verify results with project commands.
4. Report changes with file paths and rationale.

## Engineering Rules

- Follow `doc/AI_TOOLING_STANDARDS.md`.
- Follow `doc/BACKEND_STANDARDS.md` for backend API/service tasks.
- Backend baseline: Python, uv, ruff, pytest.
- Keep code typed, readable, and modular.
- Preserve existing project conventions unless asked to change them.

## Frontend Default

Unless explicitly overridden, use React + TypeScript + Vite + Tailwind.

For UI/UX tasks, start with:

```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system -p "<project-name>"
```

For backend-focused work, use:

```bash
cat .claude/skills/backend-engineering-playbook/SKILL.md
```

## Required Verification

Run relevant checks before completion:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```
