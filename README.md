<div align="center">
  <img src="assets/icon.png" alt="IdeaGo Icon" width="120" />
</div>

# IdeaGo

<p align="center">
  <img src="assets/banner_new.png" alt="IdeaGo Banner" width="100%" />
</p>

IdeaGo is a Source Intelligence V2 system for validating startup ideas. On `main`, it is an anonymous, personal-deployment product: no Supabase, no login, no billing, no account system.

[简体中文](README_CN.md) | English

## Branches

- `main`: personal/open-source deployment. Anonymous analyze, history, report detail, export, local file cache, local SQLite checkpoints.
- `saas`: same core product as `main`, plus auth, payment, profile, admin, and SaaS-only environment variables.

Long-term sync rule:

- shared/core features go `main -> saas`
- commercial-only features stay on `saas`

## What It Does

IdeaGo turns one startup idea into a decision-first report with:

- recommendation and why-now summary
- pain signals
- commercial signals
- whitespace opportunities
- competitors
- evidence and confidence

Core sources:

- Tavily
- Reddit
- GitHub
- Hacker News
- App Store
- Product Hunt

## Main Branch Runtime Model

- backend routes: `/api/v1/analyze`, `/api/v1/reports`, `/api/v1/health`
- report persistence: local `FileCache`
- pipeline checkpoints: local SQLite
- progress updates: SSE
- report flow: anonymous submit -> stream progress -> open report -> revisit from history -> export markdown

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- Node.js 20+
- `pnpm`

### Install

```bash
uv sync --all-extras
pnpm --prefix frontend install
```

### Configure

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Minimum useful config:

- required: `OPENAI_API_KEY`
- recommended: `TAVILY_API_KEY`

### Development

Terminal 1:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Terminal 2:

```bash
pnpm --prefix frontend dev
```

Open:

- frontend: [http://localhost:5173](http://localhost:5173)
- backend health: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Single-process local run

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

Open: [http://localhost:8000](http://localhost:8000)

## Configuration

Important `main` settings:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TAVILY_API_KEY`
- `CACHE_DIR`
- `ANONYMOUS_CACHE_TTL_HOURS`
- `FILE_CACHE_MAX_ENTRIES`
- `LANGGRAPH_CHECKPOINT_DB_PATH`
- `CORS_ALLOW_ORIGINS`

Reddit notes:

- `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` are optional.
- If they are missing, `main` can fall back to public Reddit reads when `REDDIT_ENABLE_PUBLIC_FALLBACK=true`.

## API Overview

- `POST /api/v1/analyze`
- `GET /api/v1/reports`
- `GET /api/v1/reports/{id}`
- `GET /api/v1/reports/{id}/status`
- `GET /api/v1/reports/{id}/stream`
- `GET /api/v1/reports/{id}/export`
- `DELETE /api/v1/reports/{id}`
- `DELETE /api/v1/reports/{id}/cancel`
- `GET /api/v1/health`

`main` does not expose auth, billing, profile, pricing, or admin APIs.

## Development Rules

- Keep the report contract decision-first.
- Treat backend report schemas and frontend shared types as explicit contracts.
- Keep `pipeline/merger.py` deterministic competitor dedupe only.
- Keep whitespace and entry-wedge synthesis in `pipeline/aggregator.py`.
- Do not introduce SaaS runtime dependencies into `main`.

## Verification

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

## Deployment

For personal deployment on `main`, see [DEPLOYMENT.md](DEPLOYMENT.md).

SaaS deployment docs belong on the `saas` branch, not `main`.
