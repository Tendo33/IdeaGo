# Verification

Run checks that match the changed surface. Cross-boundary or docs/platform
changes should run the full stack gate unless a failure is clearly unrelated and
documented.

## Backend

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

## Frontend

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Full Stack

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Docs And Platform Checks

```bash
find . -maxdepth 2 -type d -name "ai_*" -print
git diff --check
```

Legacy AI-doc directories should not reappear as current docs entrypoints.
