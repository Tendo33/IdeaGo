# Project Docs

IdeaGo uses Trellis spec files for AI-facing engineering documentation.

## Documentation Rules

- `.trellis/spec/` stores current implementation facts, coding conventions,
  branch guardrails, and verification commands.
- `AGENTS.md` and `CLAUDE.md` should stay short and link into `.trellis/spec/`.
- User-facing docs stay in `README.md`, `README_CN.md`, `DEPLOYMENT.md`,
  `CONTRIBUTING.md`, and `frontend/README.md`.
- If behavior, structure, scripts, adapters, public APIs, stack choices, or
  verification commands change, update the related spec and public docs in the
  same change.
- Future plans must be labeled as future or not implemented; do not present
  disabled pricing flows or hidden routes as active UI.

## Branch Documentation

- This branch is `saas`.
- Keep hosted branch details here: Supabase auth/persistence, quotas, admin
  APIs, LinuxDo session recovery, Stripe plumbing, and hosted operations.
- `main` has a separate Trellis adaptation and must not inherit `saas`-only
  docs by accident.
