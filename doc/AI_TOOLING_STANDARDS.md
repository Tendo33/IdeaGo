# AI Tooling Standards

This document defines one shared engineering contract for all AI assistants used in this repository.

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

## Backend Baseline (Python)

- Runtime: Python 3.10+
- Dependency management: `uv`
- Lint/format: `ruff`
- Tests: `pytest`
- Style: type hints required, explicit error handling, small pure functions preferred

If a backend API/service is needed and no framework is specified, default to:

- FastAPI for HTTP API layer
- Pydantic v2 for DTO/schema validation
- SQLAlchemy + Alembic for persistence and migrations
- Redis for cache/short-lived state when required

Recommended verification sequence:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

For detailed backend engineering rules, see `doc/BACKEND_STANDARDS.md`.

## Frontend Baseline (Default Stack)

When frontend work is needed and no other stack is specified, use:

- React
- TypeScript
- Vite
- Tailwind CSS

Preferred layout:

- `frontend/src/app` for app shell and routing
- `frontend/src/features/*` for domain modules
- `frontend/src/components/ui` for shared visual primitives
- `frontend/src/lib` for utilities and API wrappers

Quality gates:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

## UI/UX Workflow (ui-ux-pro-max)

For page/component design tasks:

1. Run `ui-ux-pro-max` with `--design-system` first.
2. Start from accessibility, responsiveness, and visual hierarchy.
3. Convert output into reusable design tokens (color, spacing, typography, radius, shadow).
4. Implement in Tailwind with consistent naming and component variants.

## Definition of Done

A task is done only when:

- requested behavior is implemented,
- relevant checks pass,
- edge cases are covered,
- docs/config are updated if behavior or workflow changed.
