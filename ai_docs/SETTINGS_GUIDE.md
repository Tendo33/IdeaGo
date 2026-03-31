# Settings Configuration Guide

This repository uses `pydantic-settings` for runtime configuration.

This file documents the hosted `saas` branch.

## Priority

1. Environment variables
2. `.env`
3. Defaults in `src/ideago/config/settings.py`

## Configuration Model On `saas`

The hosted branch has three buckets of settings:

- core analysis settings
- hosted auth/persistence settings
- optional observability and billing settings

## Required For Normal Hosted Operation

### Core analysis

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

### Hosted auth and persistence

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `AUTH_SESSION_SECRET`
- `FRONTEND_APP_URL`
- `TURNSTILE_SECRET_KEY`

### Frontend build variables

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_TURNSTILE_SITE_KEY`

## Common Optional Settings

- `TAVILY_API_KEY`
- `GITHUB_TOKEN`
- `PRODUCTHUNT_DEV_TOKEN`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `SENTRY_DSN`
- `VITE_SENTRY_DSN`
- `LINUXDO_CLIENT_ID`
- `LINUXDO_CLIENT_SECRET`

## Optional Billing Settings

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRO_PRICE_ID`

These are optional right now because pricing is intentionally hidden in the hosted UI.

## Frontend Build-Time Reminder

`VITE_*` values are compiled into the frontend bundle.

If you deploy with Docker on `saas`, set the `VITE_*` variables before:

```bash
docker compose build
```

or:

```bash
docker compose up --build
```

## Reddit Notes

- `REDDIT_ENABLE_PUBLIC_FALLBACK` should default to `false` in hosted/server environments.
- Use OAuth credentials whenever possible.
- Only enable public fallback if you have confirmed anonymous Reddit access works from your deployment environment.

## Pipeline Result Caps

- `MAX_RESULTS_PER_SOURCE` controls how many raw results each source fetches before pre-ranking.
- `EXTRACTOR_MAX_RESULTS_PER_SOURCE` controls how many ranked results per source enter extraction.
- Keep fetch budget and extractor budget separate.

## Usage

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

```python
from ideago.config.settings import get_settings

settings = get_settings()
print(settings.frontend_app_url)
```

## Maintenance Rule

If you add or rename a setting, update:

- `src/ideago/config/settings.py`
- `.env.example`
- `frontend/.env.example` when applicable
- this guide
- any README or deployment docs that depend on it
