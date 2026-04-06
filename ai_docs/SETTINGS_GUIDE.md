# Settings Configuration Guide

This repository uses `pydantic-settings` for runtime configuration.

This file documents the anonymous `main` branch.

## Priority

1. Environment variables
2. `.env`
3. Defaults in `src/ideago/config/settings.py`

## Main Branch Configuration Model

`main` is the personal deployment branch.

Required for real analysis:

- `OPENAI_API_KEY`

Common optional settings:

- `TAVILY_API_KEY`
- `GITHUB_TOKEN`
- `PRODUCTHUNT_DEV_TOKEN`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `SENTRY_DSN`

Personal deployment storage/runtime settings:

- `CACHE_DIR`
- `ANONYMOUS_CACHE_TTL_HOURS`
- `FILE_CACHE_MAX_ENTRIES`
- `LANGGRAPH_CHECKPOINT_DB_PATH`

Advanced orchestration knobs:

- `MAX_RESULTS_PER_SOURCE`
- `EXTRACTOR_MAX_RESULTS_PER_SOURCE`
- `AGGREGATION_TIMEOUT_SECONDS`
- `SOURCE_QUERY_CAPS`
- `QUERY_FAMILY_DEFAULT_WEIGHTS`
- `APP_TYPE_ORCHESTRATION_PROFILES`

## Frontend Settings

- `VITE_API_BASE_URL`
- `VITE_SENTRY_DSN`

## Reddit Notes

- `main` can use public Reddit fallback when OAuth credentials are missing
- control that behavior with `REDDIT_ENABLE_PUBLIC_FALLBACK`
- use OAuth credentials when you need more reliable Reddit access

## Usage

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

```python
from ideago.config.settings import get_settings

settings = get_settings()
print(settings.cache_dir)
```

## Maintenance Rule

If you add or rename a setting, update:

- `src/ideago/config/settings.py`
- `.env.example`
- `frontend/.env.example` when applicable
- this guide
- any README or deployment docs that depend on it
