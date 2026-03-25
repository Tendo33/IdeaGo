# Backend Development Standards

This document defines default backend practices for this repository and all connected AI tools.

## Current Stack

- Language/runtime: Python 3.10+
- API framework: FastAPI
- Data validation: Pydantic v2
- Data access: Supabase (PostgREST) + local file cache
- Migrations: Raw SQL in `supabase/migrations/`
- Pipeline: LangGraph + LangChain OpenAI
- Billing: Stripe SDK (async via `run_in_executor`)
- Package/runtime tooling: uv
- Quality tooling: ruff + mypy + pytest

## Architecture

Use a layered design to keep boundaries clear:

- `api` layer: HTTP routes, request/response schemas, auth guards, structured error codes (`api/errors.py`)
- `billing` layer: Stripe checkout, portal, webhook processing
- `pipeline` layer: LangGraph engine, nodes, events — orchestrates AI research
- `cache` layer: `ReportRepository` protocol, Supabase + file cache implementations
- `models` layer: pure domain models (research reports, competitors, intents)
- `auth` layer: Supabase auth, JWT verification, LinuxDo OAuth
- `config` layer: Pydantic settings, environment loading

Rules:

- Keep HTTP concerns in `api`; do not put business logic in route handlers.
- Keep Supabase/file I/O details in cache layer.
- Use `AppError(status, ErrorCode, message)` for all API errors — returns `{"error": {"code": "...", "message": "..."}}`.
- Billing service should be testable without HTTP bootstrapping.
- Keep `pipeline/merger.py` limited to deterministic competitor dedupe.
- Keep whitespace, entry-wedge, and trust synthesis in `pipeline/aggregator.py`.
- Keep V2 pipeline state and aggregation carriers typed; do not add anonymous dict side channels for extracted signals or evidence.

## API Conventions

- Use versioned API prefix `/api/v1`.
- Use Pydantic models for all request/response contracts.
- Treat report detail and export payloads as explicit contracts; do not rely on implicit `model_dump()` drift at route boundaries.
- Keep backend report schemas aligned with frontend shared report types when the decision-first V2 payload changes.
- Return structured error payloads via `AppError` with `ErrorCode` enum (see `api/errors.py`).
- All list endpoints return paginated responses (`PaginatedReportList` pattern: `items`, `total`, `limit`, `offset`).
- CSRF protection via `X-Requested-With` header on state-changing requests (webhook endpoints are exempt).
- Rate limiting is configurable per-endpoint (analyze and reports).

## Source Intelligence V2

- Default report structure is decision-first: recommendation, pain signals, commercial signals, whitespace opportunities, competitors, then evidence and confidence.
- Confidence and evidence-summary fields should be assembled from deterministic trust inputs such as source diversity, evidence density, recency, degradation, and explicit uncertainty/conflict signals.
- Competitor discovery remains important, but it is one section of a broader idea-validation contract.
- Keep the six-source role split explicit in backend orchestration and docs: Tavily for broad recall, Reddit for pain/migration language, GitHub for open-source maturity, Hacker News for builder sentiment, App Store for review-cluster pain, Product Hunt for launch positioning.
- Ranking and pre-filtering should be opportunity-first: stronger pain, commercial, migration, and whitespace evidence should beat simple popularity when the signals conflict.

## Configuration and Secrets

- Use `pydantic-settings` for config.
- Read secrets from environment variables, never hardcode.
- Keep `.env` local-only; do not commit sensitive values.
- Define environment-specific behavior explicitly (dev/stage/prod).

## Logging and Observability

- Use `loguru` for structured logs.
- Include request or trace identifiers in logs.
- Log failures with actionable context (operation, entity id, reason).
- Avoid logging PII, tokens, passwords, or raw secrets.

## Data and Persistence

- Supabase (PostgREST) for production persistence; local file cache for dev/single-process.
- Schema migrations live in `supabase/migrations/` as numbered SQL files.
- `ReportRepository` protocol defines the storage contract; implementations in `cache/`.
- Anonymous reports expire (`expires_at`); user-owned reports persist indefinitely.
- `update_report_user_id` must clear `expires_at` when claiming a report.

## Security Baseline

- Fail-close IDOR protection: unknown owner → 404, wrong owner → 403.
- `get_by_id` enforces `user_id` filter at the repository level.
- CSRF protection on all mutating API endpoints (webhooks exempt via `_CSRF_EXEMPT_PATHS`).
- Rate limiting is per-user (authenticated) or per-IP (anonymous), configurable via settings.
- Stripe webhook endpoints verify signatures instead of CSRF tokens.
- Use least-privilege credentials; never expose `service_role_key` to frontend.

## Testing Strategy

- Unit tests: domain/service logic and edge cases.
- Integration tests: repository behavior and key API flows.
- Regression tests for every bug fix.
- Prefer deterministic tests; avoid timing-based flakes.

## Done Criteria (Backend)

A backend task is complete only if:

- behavior is implemented as requested,
- relevant tests pass,
- lint/format checks pass,
- migrations/docs are updated when behavior or schema changes.

Recommended checks:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```
