# IdeaGo Deployment Guide

This document describes how to deploy the `main` branch.

`main` is the personal/open-source deployment line:

- anonymous usage
- local file cache
- local SQLite checkpoints
- no Supabase
- no login
- no billing

If you need the commercial/authenticated deployment, use the `saas` branch instead. SaaS-specific deployment docs belong there.

## 1. Minimum Requirements

- VPS or local machine with Docker, or a local workstation for direct run
- Python 3.10+
- Node.js 20+
- `uv`
- `pnpm`
- `OPENAI_API_KEY`

Recommended:

- `TAVILY_API_KEY`
- `GITHUB_TOKEN`
- `PRODUCTHUNT_DEV_TOKEN`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`

## 2. Environment

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Minimum `.env` for `main`:

```bash
ENVIRONMENT=production
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
CACHE_DIR=.cache/ideago
ANONYMOUS_CACHE_TTL_HOURS=24
FILE_CACHE_MAX_ENTRIES=500
LANGGRAPH_CHECKPOINT_DB_PATH=.cache/ideago/langgraph-checkpoints.db
CORS_ALLOW_ORIGINS=https://your-domain.example
```

Important:

- `main` does not need Supabase variables.
- `main` does not need Stripe variables.
- `main` does not need LinuxDo variables.

## 3. Local Development Run

Terminal 1:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Terminal 2:

```bash
pnpm --prefix frontend dev
```

## 4. Single-Process Local Deployment

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

This serves the built frontend from the FastAPI app.

## 5. Docker Deployment

Build and run:

```bash
docker compose up --build -d
```

Recommended persistent mounts:

- cache directory for reports
- SQLite checkpoint file directory

If you manage Docker yourself, make sure these paths survive container restarts:

- `CACHE_DIR`
- parent directory of `LANGGRAPH_CHECKPOINT_DB_PATH`

## 6. Reverse Proxy

For public deployment, put IdeaGo behind a reverse proxy such as:

- Caddy
- Nginx
- Traefik
- Cloudflare Tunnel

Recommendations:

- terminate TLS at the proxy
- keep `CORS_ALLOW_ORIGINS` explicit
- avoid exposing the backend directly without rate limiting or gateway controls

## 7. Runtime Behavior

On `main`, the expected flow is:

1. user submits idea
2. backend creates analysis job
3. frontend watches SSE progress
4. report is persisted locally
5. report remains visible in history until TTL cleanup removes anonymous entries

Storage model:

- reports: local file cache
- runtime status: local status files
- pipeline checkpoints: SQLite

## 8. Operational Notes

- Anonymous reports expire based on `ANONYMOUS_CACHE_TTL_HOURS`
- Owned/account-based persistence is not part of `main`
- Reddit can fall back to public read-only mode if OAuth credentials are not configured
- In production, do not leave `CORS_ALLOW_ORIGINS=*`

## 9. Update Strategy

Long-term branch policy:

- shared/core product changes land in `main`
- `saas` merges `main`
- do not merge the entire `saas` branch back into `main`

When updating a running `main` deployment:

```bash
git checkout main
git pull
pnpm --prefix frontend build
docker compose up --build -d
```

Or for a direct-process deployment:

```bash
git checkout main
git pull
pnpm --prefix frontend build
uv run python -m ideago
```

## 10. Verification Checklist

- backend starts without Supabase, Stripe, or LinuxDo env vars
- frontend build succeeds
- `/api/v1/health` returns `{"status":"ok"}`
- anonymous analyze works
- SSE progress updates render
- report detail opens after completion
- history can reopen the report
- markdown export works
