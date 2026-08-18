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

### Frontend configuration (runtime, not build-time)

Public frontend values are **no longer baked into the bundle**. The SPA fetches
them from `GET /api/v1/config` before it mounts, so a single image works for any
deployment. Set them in the root `.env` alongside the rest of the backend config:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
TURNSTILE_SITE_KEY=your-turnstile-site-key
FRONTEND_SENTRY_DSN=            # optional, browser Sentry project
PRICING_ENABLED=false           # optional, exposes /pricing in the SPA
```

`GET /api/v1/config` serves exactly six values through an explicit allowlist:
`supabase_url`, `supabase_anon_key`, `turnstile_site_key`, `sentry_dsn`,
`pricing_enabled`, `environment`. Secrets are never included, and a test asserts
the field set so adding one is a deliberate act.

The only remaining build-time frontend input is `VITE_API_BASE_URL`, because it
is needed to locate that endpoint in the first place:

```bash
VITE_API_BASE_URL=      # leave empty for same-origin (the default for this image)
```

Notes:

- Leave `VITE_API_BASE_URL` empty unless the API lives on a different origin than
  the SPA. The published image serves both from one origin.
- Legacy `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` / `VITE_TURNSTILE_SITE_KEY`
  in `frontend/.env` still work as a local-dev fallback, but runtime values win.
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

### Attack protection (required for the captcha to do anything)

The SPA renders a Turnstile widget and passes the resulting `captchaToken` to
Supabase on sign-in, sign-up and password reset. **Supabase only verifies that
token if CAPTCHA protection is enabled in the project**, otherwise the token is
ignored and the widget is decoration — a bot can call the Supabase auth API
directly with the public anon key, create accounts in bulk and burn LLM quota.

In the Supabase dashboard: *Authentication → Attack Protection → Enable CAPTCHA
protection*, provider **Cloudflare Turnstile**, secret = the same
`TURNSTILE_SECRET_KEY` this backend uses.

The backend verifies Turnstile itself for the LinuxDo flow, so that path is
covered regardless of this setting.

### Scheduled cleanup

Retention RPCs are invoked by the backend's own hourly maintenance task
(`cleanup_stale_processing_slots`, `cleanup_old_webhook_events`,
`cleanup_audit_log`, `cleanup_auth_sessions`, plus `cleanup_expired_reports` and
`cleanup_rate_limit_hits` from their own call sites). No pg_cron configuration is
required — but the corresponding migrations must be applied, or the calls fail
with `PGRST202` and the tables grow unbounded. `tests/test_retention.py` asserts
that every `cleanup_*` function defined in the migrations has a caller.

### Migration order

`supabase/migrations/000_all_migrations.sql` is a **bootstrap snapshot covering
001–012 only**. For a brand-new project either:

- run `000_all_migrations.sql`, then `013` through the highest number, or
- run `001` through the highest number individually

Do not run both `000` and `001`–`012`.

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

The compose build forwards a single frontend build arg:

- `VITE_API_BASE_URL` (empty by default — same-origin)

Everything else the browser needs is served at runtime from `GET /api/v1/config`,
so rebuilding is not required to change Supabase, Turnstile, Sentry, or the
pricing flag. Restart the container and the SPA picks up the new values.

The cache volume persists `CACHE_DIR`.

## 8. Reverse Proxy And HTTPS

For production:

- terminate TLS at a reverse proxy such as Caddy or Nginx
- keep `FRONTEND_APP_URL` aligned with the public HTTPS origin
- set `CORS_ALLOW_ORIGINS` explicitly
- preserve `X-Forwarded-Proto=https` so secure cookie logic behaves correctly
- **set `FORWARDED_ALLOW_IPS` to your proxy's address**

That last point is easy to miss and fails silently. Uvicorn only trusts
`X-Forwarded-*` headers from `127.0.0.1` by default. In Docker the proxy is a
different container with a different address, so the headers are discarded and
`request.client.host` resolves to the proxy for every request. The visible
consequences are that audit-log entries all record the same IP, and the
`remoteip` handed to Turnstile is wrong, weakening its risk scoring.

```bash
FORWARDED_ALLOW_IPS=172.18.0.2     # the proxy container's address
# or, only when the app port cannot be reached from outside the network:
FORWARDED_ALLOW_IPS=*
TRUST_PROXY_HEADERS=true           # default
```

If you deploy frontend and backend under the same origin, you can usually leave `VITE_API_BASE_URL`
empty and rely on same-origin requests.

## 8b. Single Process Only

The image runs one uvicorn process. Some building blocks are already
multi-worker safe (PostgreSQL-backed dedup reservations, the LangGraph Postgres
checkpointer, PostgREST-backed rate limiting), which makes it tempting to scale
out. **Do not add workers or replicas yet.** Three pieces of runtime state are
still per-process:

| State | Consequence of scaling out today |
|---|---|
| In-flight pipeline tasks | Cancel only reaches the worker holding the task. Another worker refunds the quota and marks the report cancelled while the real run keeps going, later flipping the status back to `complete`. |
| SSE run state | A viewer connected to a different worker falls back to polling the status row instead of receiving live progress. |
| In-process metrics | `/admin/metrics` reports one worker's partial view. |

Resolve those before scaling; adding workers is not a configuration-only change.

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
- `GET /api/v1/config` returns your Supabase URL, anon key, and Turnstile site key
- the login page renders a Turnstile widget (proves runtime config reached the browser)
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
