# Persistence And Local Data

The `main` branch intentionally uses local persistence, not hosted database
requirements.

## Current Persistence Boundaries

- `cache/` owns local report persistence and status storage.
- Completed reports persist through `FileCache`.
- Anonymous reports expire by TTL.
- Pipeline checkpoints use local SQLite through LangGraph checkpoint settings.
- Status files track `processing`, `complete`, `failed`, and `cancelled`.

## Rules

- `main` must not require Supabase, Stripe, LinuxDo, auth, profile, quota,
  admin, or billing configuration to boot.
- Handlers should not know file-cache storage details.
- Validate external input before persistence.
- Do not log file paths together with sensitive request content when it could
  expose user data.
- Keep cleanup and TTL behavior observable and tested when touched.

## Verification

Add integration-style tests when behavior depends on file cache semantics,
status transitions, cleanup, TTL, or checkpoint path behavior.
