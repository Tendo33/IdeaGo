# IdeaGo `main` Deployment Guide

This document describes how to deploy the anonymous `main` branch.

`main` is the personal/open-source deployment line:

- anonymous usage
- local file cache
- local SQLite checkpoints
- no Supabase requirement
- no login
- no billing

If you need the hosted/authenticated runtime, use the `saas` branch instead.

## 1. Current Deployment Model

The `main` branch is designed to boot with a very small environment surface.

You do not need:

- Supabase
- Stripe
- LinuxDo OAuth
- hosted admin infrastructure

You do need:

- OpenAI API access

## 2. Minimum Requirements

- Python 3.10+
- Node.js 20+
- `uv`
- `pnpm`
- `OPENAI_API_KEY`

Recommended for fuller source coverage:

- `TAVILY_API_KEY`
- `GITHUB_TOKEN`
- `PRODUCTHUNT_DEV_TOKEN`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`

## 3. Environment

Create both env files:

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

Frontend settings are intentionally minimal:

```bash
VITE_API_BASE_URL=
VITE_SENTRY_DSN=
```

Important:

- `main` does not need Supabase variables.
- `main` does not need Stripe variables.
- `main` does not need LinuxDo variables.

## 4. Local Development Run

Terminal 1:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Terminal 2:

```bash
pnpm --prefix frontend dev
```

## 5. Single-Process Source Run

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

FastAPI serves the built frontend from `frontend/dist`.

## 6. Docker Deployment

The default `docker-compose.yml` on `main` pulls the published image:

```bash
docker compose pull
docker compose up -d
```

Optional: pin to a specific tag:

```bash
IDEAGO_IMAGE_TAG=0.3.8 docker compose up -d
```

If you prefer to build locally from source, the branch also includes a Dockerfile.

Recommended persistent mounts:

- `CACHE_DIR`
- the parent directory of `LANGGRAPH_CHECKPOINT_DB_PATH`

## 7. Reverse Proxy

For public deployment, put IdeaGo behind a reverse proxy such as:

- Caddy
- Nginx
- Traefik
- Cloudflare Tunnel

Recommendations:

- terminate TLS at the proxy
- keep `CORS_ALLOW_ORIGINS` explicit
- avoid exposing the backend directly without gateway-level controls

## 8. Runtime Behavior

On `main`, the expected flow is:

1. user submits an idea
2. backend creates an analysis job
3. frontend watches SSE progress
4. report is persisted locally
5. report remains visible in history until TTL cleanup removes it

Storage model:

- reports: local file cache
- runtime status: local status files
- pipeline checkpoints: SQLite

## 9. Operational Notes

- Anonymous reports expire based on `ANONYMOUS_CACHE_TTL_HOURS`
- Account-bound persistence is not part of `main`
- Reddit can fall back to public read-only mode if OAuth credentials are not configured
- In production, do not leave `CORS_ALLOW_ORIGINS=*`

## 10. Verification Checklist

- backend starts without Supabase, Stripe, or LinuxDo env vars
- frontend build succeeds
- `/api/v1/health` returns success
- anonymous analyze works
- SSE progress updates render
- report detail opens after completion
- history can reopen the report
- markdown export works

## 11. Update Strategy

Branch policy:

- shared/core product changes land in `main`
- `saas` merges `main`
- do not merge hosted-only runtime dependencies back into `main`

When updating a running `main` deployment:

```bash
git checkout main
git pull
docker compose pull
docker compose up -d
```

Or for a direct-process deployment:

```bash
git checkout main
git pull
pnpm --prefix frontend build
uv run python -m ideago
```
