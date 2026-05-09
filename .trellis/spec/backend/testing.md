# Backend Testing

## Defaults

- Use `pytest`.
- Use `ruff` and `mypy` as gates, not optional polish.
- New behavior needs tests.
- Bug fixes need at least one regression test.

## Test Shape

- Pure logic gets unit tests.
- API behavior gets route tests for success, validation, anonymous session
  headers, rate limiting, and structured errors.
- Configuration behavior gets environment-isolated tests.
- Pipeline behavior should test typed state/event/report contracts rather than
  sleeping on timing-sensitive behavior.
- External provider and source integrations should be mocked at stable
  boundaries unless a task explicitly asks for live integration.

## Main Regression Areas

- query validation and normalization
- anonymous `X-Session-Id` behavior
- SSE retry cap and `/status` fallback semantics
- report status transitions: processing, complete, failed, cancelled
- file-cache TTL and cleanup
- static fallback vs `/api/*` error behavior
- source concurrency override restoration

## Before Completion

Run the smallest relevant check first while working, then the full required
backend or full-stack gate before claiming the task is complete.
