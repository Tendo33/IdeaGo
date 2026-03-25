# Settings Configuration Guide

This repository uses `pydantic-settings` for runtime configuration.

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

## Usage

```bash
cp .env.example .env
```

```python
from ideago.config.settings import get_settings

settings = get_settings()
print(settings.cache_dir)
```

## Notes

- `main` must start without Supabase, Stripe, or LinuxDo variables.
- Reddit can fall back to public read-only access when OAuth credentials are missing.
- If you add a new setting, update both `src/ideago/config/settings.py` and `.env.example`.
