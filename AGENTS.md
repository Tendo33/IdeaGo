# Codex Project Instructions

Use this file as the default project contract for Codex.

## Workflow

1. Understand request and constraints.
2. Propose concise implementation steps.
3. Implement with minimal, targeted edits.
4. Run verification commands before completion claims.

## Engineering Rules

- Follow `doc/AI_TOOLING_STANDARDS.md`.
- Follow `doc/BACKEND_STANDARDS.md` for backend API/service tasks.
- Prefer Python + uv + ruff + pytest for backend work.
- Keep functions small, typed, and testable.
- Handle errors explicitly; avoid silent failures.

## Frontend Default

Unless user specifies otherwise, use React + TypeScript + Vite + Tailwind.

When doing UI/UX work, use:

```bash
python3 .codex/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system -p "<project-name>"
```

Then implement using design tokens and reusable components.

For backend-focused work, use:

```bash
cat .codex/skills/backend-engineering-playbook/SKILL.md
```

## Required Verification

Run what applies to the task:

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
