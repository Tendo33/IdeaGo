# Contributing to IdeaGo (`saas`)

This guide describes how to contribute to the hosted `saas` branch.

## Branch Model

- `main`: personal/open-source deployment line
- `saas`: hosted/commercial line built on top of `main`
- shared product work should land on `main` first whenever possible
- `saas` should only carry hosted-only runtime concerns such as auth, admin, billing integration, and SaaS deployment details

When you touch docs, update the branch-specific docs in the same task. Do not assume `main` and
`saas` share the same setup or runtime behavior.

## Before You Edit

Read the current project standards first:

- `ai_docs/AI_TOOLING_STANDARDS.md`
- `ai_docs/BACKEND_STANDARDS.md`
- `ai_docs/FRONTEND_STANDARDS.md`
- `ai_docs/SETTINGS_GUIDE.md`
- `AGENTS.md`
- `CLAUDE.md`

## Local Setup

```bash
git clone https://github.com/Tendo33/ideago.git
cd ideago
git checkout saas
uv sync --all-extras
pnpm --prefix frontend install
uv run pre-commit install
```

Create env files:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

The hosted branch expects Supabase and Turnstile configuration for normal auth flows.

## Development Workflow

1. Understand whether the change belongs on `main`, `saas`, or both.
2. Read the relevant `ai_docs/` files before editing.
3. Keep changes small and branch-correct.
4. Update docs and env examples if behavior changes.
5. Run verification before asking for review.

## Branch Targeting Rules

Prefer `main` for:

- shared pipeline behavior
- report contract updates
- source orchestration improvements
- anonymous/local deployment behavior

Keep on `saas` for:

- Supabase auth and profile flows
- LinuxDo OAuth
- admin pages and admin APIs
- hosted persistence behavior
- SaaS deployment docs
- billing integration wiring

If a change affects both branches, document both branches explicitly.

## Coding Standards

- Keep functions small, typed, and testable.
- Do not bypass explicit report contracts with ad hoc dict payloads.
- Keep `pipeline/merger.py` limited to deterministic competitor dedupe.
- Keep whitespace and recommendation synthesis in `pipeline/aggregator.py`.
- Preserve the decision-first report ordering.
- Do not expose pricing UI or upgrade CTAs unless the task explicitly restores billing discovery.

## Running The App

Backend:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Frontend:

```bash
pnpm --prefix frontend dev
```

Single-process:

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

## Verification

Run the checks that match your change:

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

If you change docs only, say which checks you skipped and why.

## Pull Request Notes

- Target the correct branch.
- Mention whether the change must be mirrored to the other branch.
- Call out any env var additions or deploy implications.
- Mention if docs were updated alongside behavior changes.

## Documentation Hygiene

Keep these aligned when conventions change:

- `README.md`
- `README_CN.md`
- `DEPLOYMENT.md`
- `frontend/README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `ai_docs/*`
