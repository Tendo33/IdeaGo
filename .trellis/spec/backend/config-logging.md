# Configuration And Logging

## Configuration

- Runtime settings live in `src/ideago/config/settings.py`.
- `Settings` uses `pydantic-settings` and reads environment variables plus
  `.env`.
- Tests that change environment variables must clear/reload cached settings
  explicitly.
- `main` should be useful with only `OPENAI_API_KEY` for real analysis.
- Optional provider settings include Tavily, GitHub, Product Hunt, Reddit, and
  Sentry.
- Local runtime settings include cache directory, anonymous cache TTL, file
  cache max entries, checkpoint DB path, rate limits, and CORS origins.

## Frontend Build Variables

- `VITE_API_BASE_URL`
- optional `VITE_SENTRY_DSN`

No frontend env var is required for anonymous session identity or SSE recovery.
Never expose raw provider API keys through `VITE_*`.

## Logging And Observability

- Use `ideago.observability.log_config.get_logger`.
- Preserve or generate request/trace IDs through middleware.
- Prefer structured fields for report IDs, source names, provider operation
  names, and dependency health.
- Never log tokens, passwords, raw auth headers, API keys, or sensitive personal
  data.
- Production logging should keep verbose exception `backtrace` and `diagnose`
  off by default.
