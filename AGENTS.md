# Codex Project Instructions

Use this file as the Codex entrypoint for IdeaGo on the `saas` branch.

## Read Order

1. Start with [.trellis/spec/README.md](.trellis/spec/README.md).
2. Read [.trellis/spec/shared/index.md](.trellis/spec/shared/index.md) and [.trellis/spec/shared/verification.md](.trellis/spec/shared/verification.md).
3. For backend work, read [.trellis/spec/backend/index.md](.trellis/spec/backend/index.md).
4. For frontend work, read [.trellis/spec/frontend/index.md](.trellis/spec/frontend/index.md).
5. For non-trivial changes, read [.trellis/spec/guides/pre-implementation-checklist.md](.trellis/spec/guides/pre-implementation-checklist.md).

## Branch Guardrails

- `main` is the anonymous/personal deployment edition.
- `saas` is the hosted/commercial edition.
- Shared product work should land on `main` first when practical.
- Do not move hosted-only auth, billing, Supabase, quota, or admin runtime dependencies back into `main`.

## Working Rules

- Treat `.trellis/spec/` as the only detailed AI collaboration source of truth.
- Keep changes small, typed, and branch-correct.
- Update `.trellis/spec/` whenever behavior, structure, scripts, adapters, public APIs, verification commands, or stack choices change.
- Use `pnpm` for the frontend and `uv` for Python.
- Do not claim completion without running the checks that match the changed surface.
