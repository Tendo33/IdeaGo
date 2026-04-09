# IdeaGo `saas` Deployment Guide

This document describes how to deploy the hosted `saas` branch.

`saas` is the branch with:

- Supabase-backed auth and profile ownership
- hosted report history and account-bound persistence
- admin APIs and dashboard
- LinuxDo OAuth support
- optional Stripe integration points

It is not the same runtime shape as `main`. If you need the anonymous personal-deployment edition,
switch to `main` and use that branch's deployment docs.

## 1. Current Deployment Reality

The codebase already contains billing integrations, but the public upgrade flow is intentionally
hidden today:

- frontend pricing flag is off
- `/pricing` is not routed
- checkout, portal, and billing-status endpoints intentionally reject public usage for now

That means a production deployment does not require Stripe to boot successfully unless you are
explicitly preparing for future re-enable work.

## 2. Required Services

### Required to boot the hosted app

- OpenAI
- Supabase
- Cloudflare Turnstile
- a domain or stable frontend origin for callbacks and CORS

### Recommended for better production behavior

- Tavily
- Sentry
- GitHub token
- Product Hunt token
- Reddit OAuth credentials

### Optional integrations already wired in code

- LinuxDo OAuth
- Stripe

## 3. Environment Layout

Create both backend and frontend env files:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

### Minimum backend settings

```bash
ENVIRONMENT=production
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://...
AUTH_SESSION_SECRET=change-me-to-a-long-random-secret
FRONTEND_APP_URL=https://your-domain.example
TURNSTILE_SECRET_KEY=your-turnstile-secret
CORS_ALLOW_ORIGINS=https://your-domain.example
```

### Minimum frontend build settings

```bash
VITE_API_BASE_URL=
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_TURNSTILE_SITE_KEY=your-turnstile-site-key
```

Notes:

- `VITE_*` values are build-time inputs for the frontend bundle.
- `FRONTEND_APP_URL` must match the real browser origin used by users.
- `AUTH_SESSION_SECRET` signs backend-managed LinuxDo auth tokens.
- Leave `CORS_ALLOW_ORIGINS=*` only in local development.

### Optional hosted integrations

```bash
LINUXDO_CLIENT_ID=...
LINUXDO_CLIENT_SECRET=...
SENTRY_DSN=...
VITE_SENTRY_DSN=...
TAVILY_API_KEY=...
GITHUB_TOKEN=...
PRODUCTHUNT_DEV_TOKEN=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

### Optional billing preparation

```bash
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRO_PRICE_ID=...
```

Stripe is optional right now because pricing is intentionally hidden.

## 4. Supabase Setup

### Auth and API

You need a Supabase project with:

- project URL
- anon key
- service role key
- direct Postgres URL

The backend validates JWT signing keys through Supabase JWKS and uses the service role key for
admin operations and hosted persistence.

### Database schema

Apply the SQL files in `supabase/migrations/` using your normal Supabase migration workflow.

Important hosted tables and RPCs on `saas` include:

- report persistence
- processing/runtime state
- quota and plan breakdown helpers
- rate-limit helpers

### Provider configuration

Configure only the auth providers you actually want to expose:

- Email/password through Supabase Auth
- GitHub OAuth through Supabase, if desired
- Google OAuth through Supabase, if desired
- LinuxDo through this backend's custom OAuth flow

If you enable LinuxDo, set the callback URL to:

```text
https://your-api-or-app-origin/api/v1/auth/linuxdo/callback
```

Your frontend redirect target must live under `FRONTEND_APP_URL`.

## 5. Local Hosted Run

Terminal 1:

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Terminal 2:

```bash
pnpm --prefix frontend dev
```

This is the fastest way to validate auth, history, profile, and admin changes locally.

## 6. Single-Process Source Run

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

FastAPI serves the built SPA from `frontend/dist`.

## 7. Docker Compose Deployment

The `saas` branch `docker-compose.yml` builds a local image from the current repository instead of
pulling a prebuilt image.

Build and run:

```bash
docker compose build
docker compose up -d
```

The compose build forwards these frontend-related build args:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_TURNSTILE_SITE_KEY`

It also forwards:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

The cache volume persists `CACHE_DIR`.

## 8. Reverse Proxy And HTTPS

For production:

- terminate TLS at a reverse proxy such as Caddy or Nginx
- keep `FRONTEND_APP_URL` aligned with the public HTTPS origin
- set `CORS_ALLOW_ORIGINS` explicitly
- preserve `X-Forwarded-Proto=https` so secure cookie logic behaves correctly

If you deploy frontend and backend under the same origin, you can usually leave `VITE_API_BASE_URL`
empty and rely on same-origin requests.

## 9. Runtime Security Notes

The hosted branch expects these protections in production:

- CSRF enforcement via `X-Requested-With` on mutating API routes
- cookie-backed mutating requests also validate `Origin` / `Referer` against the configured allowlist
- explicit CORS allowlist
- security headers middleware
- rate limiting for analyze and report APIs
- HTTP-only cookie session for LinuxDo auth
- no `SUPABASE_SERVICE_ROLE_KEY` exposure to the browser

## 10. Admin And Operations

Hosted-only operational endpoints:

- `GET /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/quota`
- `GET /api/v1/admin/stats`
- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/health`

To use the admin UI, make sure the authenticated profile has the expected admin role in Supabase.
Admin quota overrides persist in `profiles.plan_limit_override`, while the API and frontend continue
to read and write the effective `plan_limit` contract.

When hosted persistence is unavailable, admin and report routes return `503 DEPENDENCY_UNAVAILABLE`
instead of pretending the dataset is empty.

## 11. Verification Checklist

- backend starts with your hosted env vars
- frontend bundle builds with the correct `VITE_*` values
- `GET /api/v1/health` returns success
- login page renders and Turnstile loads
- Supabase login succeeds
- LinuxDo login succeeds if enabled
- a signed-in user can create an analysis
- SSE progress updates stream correctly
- report history and detail pages load for the owner
- profile editing works
- admin dashboard works for admin users

## 12. Update Strategy

Branch policy:

- shared product work lands on `main`
- `saas` merges `main`
- do not merge hosted-only dependencies back into `main`

When updating a live hosted deployment from source:

```bash
git checkout saas
git pull
docker compose build
docker compose up -d
```

Or for a direct-process deployment:

```bash
git checkout saas
git pull
pnpm --prefix frontend build
uv run python -m ideago
```
