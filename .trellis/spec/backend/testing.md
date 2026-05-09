# Backend Testing

## Defaults

- Use `pytest`.
- Use `ruff` and `mypy` as gates, not optional polish.
- New behavior needs tests.
- Bug fixes need at least one regression test.

## Test Shape

- Pure logic gets unit tests.
- API behavior gets route tests for success, validation, auth, owner isolation,
  and structured errors.
- Configuration behavior gets environment-isolated tests.
- Pipeline behavior should test typed state/event/report contracts rather than
  sleeping on timing-sensitive behavior.
- Supabase, Stripe, provider, and external source integrations should be mocked
  at stable boundaries unless a task explicitly asks for live integration.

## Hosted Regression Areas

- quota charge/refund and processing reservation rollback
- initial and terminal report status persistence
- SSE terminal event semantics
- LinuxDo cookie-session recovery
- account deletion cleanup states
- admin role gating and stats cache behavior
- billing webhook signature and idempotency
- static fallback vs `/api/*` error behavior

## Before Completion

Run the smallest relevant check first while working, then the full required
backend or full-stack gate before claiming the task is complete.
