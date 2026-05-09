# Project Docs

IdeaGo uses Trellis spec files for AI-facing engineering documentation.

## Documentation Rules

- `.trellis/spec/` stores current implementation facts, coding conventions,
  branch guardrails, and verification commands.
- `AGENTS.md` and `CLAUDE.md` should stay short and link into `.trellis/spec/`.
- User-facing docs stay in `README.md`, `README_CN.md`, `DEPLOYMENT.md`, and
  `CHANGELOG.md`.
- If behavior, structure, scripts, adapters, public APIs, stack choices, or
  verification commands change, update the related spec and public docs in the
  same change.
- Future plans must be labeled as future or not implemented; do not present
  hosted-only SaaS features as active on `main`.

## Branch Documentation

- This branch is `main`.
- Keep anonymous/personal deployment details here: local file cache, SQLite
  checkpoints, anonymous report/session behavior, and local Docker defaults.
- `saas` has a separate Trellis adaptation and must not be treated as the source
  of truth for `main`.
