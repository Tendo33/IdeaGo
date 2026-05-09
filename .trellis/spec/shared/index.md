# Shared Index

These rules apply to the `saas` branch of IdeaGo.

## Source Of Truth

- `.trellis/spec/` is the detailed AI collaboration source of truth.
- `AGENTS.md` and `CLAUDE.md` are thin platform entrypoints that point here.
- Product docs such as `README.md`, `README_CN.md`, `DEPLOYMENT.md`, and
  `frontend/README.md` remain user-facing docs and should stay consistent with
  this spec.

## Documentation Files

| File | Description | When to Read |
| --- | --- | --- |
| [code-quality.md](./code-quality.md) | Mandatory quality rules | Always |
| [dependencies.md](./dependencies.md) | Stack and dependency constraints | Adding or updating dependencies |
| [project-docs.md](./project-docs.md) | Trellis documentation conventions | Changing docs or project structure |
| [scripts.md](./scripts.md) | Maintenance scripts and pre-commit notes | Script or release work |
| [verification.md](./verification.md) | Baseline verification commands | Before completion |

## Core Rules

- Use `uv` for Python and `pnpm` for the frontend.
- No untyped public Python APIs.
- No frontend `any` in new TypeScript code.
- No secrets in logs or Vite public environment variables.
- Keep frontend and backend contracts explicit.
- Preserve the branch model: `saas` owns hosted auth, billing, quota, admin,
  Supabase persistence, and LinuxDo cookie-session recovery.
- Do not describe pricing as public-facing while `PRICING_ENABLED` is `false`
  and billing route handlers intentionally return not-found for users.
