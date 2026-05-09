# Configuration And Logging

## Configuration

- Runtime settings live in `src/ideago/config/settings.py`.
- `Settings` uses `pydantic-settings` and reads environment variables plus
  `.env`.
- Tests that change environment variables must clear/reload cached settings
  explicitly.
- Keep root `.env` as the backend/Docker Compose env file.
- `frontend/.env` is local frontend development only.
- Production deployment should use root `.env` values; do not revive
  `.env.prod` / `.env.production` conventions.

Required hosted settings include OpenAI-compatible model settings, Supabase URL
and keys, Supabase DB URL, auth session secret, frontend app URL, and Turnstile
secret. Tavily, GitHub, Product Hunt, Reddit, Sentry, LinuxDo, and Stripe values
are optional or feature-specific.

## Frontend Build Variables

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_TURNSTILE_SITE_KEY`
- optional `VITE_SENTRY_DSN`

Never expose `SUPABASE_SERVICE_ROLE_KEY`, Stripe secrets, LinuxDo client
secrets, or raw provider API keys through `VITE_*`.

## Logging And Observability

- Use `ideago.observability.log_config.get_logger`.
- Preserve or generate trace/request IDs through middleware.
- Prefer structured fields for report IDs, user IDs when safe, source names,
  provider operation names, and dependency health.
- Never log tokens, passwords, raw auth headers, service-role keys, or sensitive
  personal data.
- Sentry is initialized only when `SENTRY_DSN` is configured.
