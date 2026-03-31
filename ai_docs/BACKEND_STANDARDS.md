# Backend Development Standards

This document defines backend expectations for the hosted `saas` branch.

## Current Stack

- Python 3.10+
- FastAPI
- Pydantic v2
- LangGraph + LangChain OpenAI
- file cache plus Supabase-backed report persistence
- SQLite checkpoints plus hosted runtime state
- `uv`, `ruff`, `mypy`, `pytest`
- Supabase auth/admin helpers
- Stripe integration code

## Architecture

Use clear layers:

- `api`: HTTP routes, schemas, errors, middleware
- `auth`: Supabase auth dependencies, LinuxDo cookie-session helpers, profile/admin helpers
- `billing`: Stripe checkout, portal, webhook plumbing
- `pipeline`: LangGraph orchestration and typed event flow
- `cache`: report persistence, runtime status, repository abstraction
- `models`: domain models and report contracts
- `config`: `pydantic-settings`
- `observability`: logging, audit, metrics, error catalog

Rules:

- Keep business logic out of route handlers.
- Use `AppError(status, ErrorCode, message)` for structured API failures.
- Keep report routes explicit and contract-first.
- Keep pipeline state and report assembly typed.
- Keep `pipeline/merger.py` limited to deterministic competitor dedupe.
- Keep whitespace and evidence-backed synthesis in `pipeline/aggregator.py`.

## API Shape On `saas`

- Versioned prefix: `/api/v1`
- Route families on `saas`: `analyze`, `reports`, `auth`, `admin`, `billing`, `health`
- Auth routes support Supabase-backed access and LinuxDo custom OAuth
- Admin routes assume hosted user ownership and admin role checks
- Billing routes exist, but checkout, portal, and status are intentionally hidden from users right now
- Mutating API routes require `X-Requested-With` except Stripe webhook

## Persistence And Ownership

- Use the `ReportRepository` abstraction for report storage.
- Hosted deployments can use Supabase-backed persistence in addition to local file cache behavior.
- User-owned reports persist indefinitely.
- Anonymous reports still use TTL semantics until claimed.
- Runtime state and rate-limit helpers may depend on hosted PostgREST/Supabase RPCs.

## Security Baseline

- CSRF protection through `X-Requested-With`
- explicit CORS allowlist in production
- security headers middleware enabled for all responses
- rate limiting per user or per IP, with hosted PostgREST-backed enforcement when configured
- HTTP-only cookie session for LinuxDo auth
- never expose `SUPABASE_SERVICE_ROLE_KEY` to the browser
- avoid logging PII or raw secrets

## Hosted Auth Notes

- `/auth/linuxdo/start` is a `POST`, not a `GET`
- LinuxDo callback completes in the backend and redirects back to the frontend callback route
- Supabase session bootstrap and backend cookie recovery both need to keep the current user model aligned
- Profile and quota operations are part of the hosted contract

## Billing Notes

- Stripe integration code should remain testable and isolated from route wiring
- user-facing pricing flows are intentionally hidden until a task explicitly restores them
- webhook signature verification is still required whenever Stripe is configured

## Source Intelligence V2

- Default report shape is decision-first
- Keep competitor discovery as one section inside the broader validation contract
- Treat report detail and export formats as explicit interfaces
- Ranking stays opportunity-first: pain, commercial, migration, and whitespace evidence should beat raw popularity when signals conflict

## Testing Strategy

- Unit tests for pure logic and edge cases
- Integration tests for hosted persistence and key API flows
- Regression tests for each bug fix
- Prefer deterministic tests over timing-heavy tests

## Done Criteria

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```
