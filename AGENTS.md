# Codex Project Instructions

Use this file as the Codex entrypoint for IdeaGo on the `saas` branch.

## Branch Guardrails

- `main` is the anonymous/personal deployment edition.
- `saas` is the hosted/commercial edition.
- Shared product work should land on `main` first when practical.
- Do not move hosted-only auth, billing, Supabase, quota, or admin runtime dependencies back into `main`.

## Working Rules

- Keep changes small, typed, and branch-correct.
- Use `pnpm` for the frontend and `uv` for Python.
- Do not claim completion without running the checks that match the changed surface.
