# Backend Development Standards

This document defines backend expectations for the anonymous `main` branch.

## Current Stack

- Python 3.10+
- FastAPI
- Pydantic v2
- LangGraph + LangChain OpenAI
- local file cache for persisted reports
- SQLite checkpoints for runtime state
- `uv`, `ruff`, `mypy`, `pytest`

## Architecture

Use clear layers:

- `api`: HTTP routes, schemas, errors, middleware
- `pipeline`: LangGraph orchestration and typed event flow
- `cache`: report persistence and runtime status storage
- `models`: domain models
- `config`: `pydantic-settings`
- `observability`: logging and metrics

Rules:

- Keep business logic out of route handlers.
- Use `AppError(status, ErrorCode, message)` for structured API failures.
- Keep report routes explicit and contract-first.
- Keep pipeline state and report assembly typed.
- Keep `pipeline/merger.py` limited to deterministic competitor dedupe.
- Keep whitespace and evidence-backed synthesis in `pipeline/aggregator.py`.

## Public API Shape On `main`

- Versioned prefix: `/api/v1`
- Public routes on `main`: `analyze`, `reports`, `health`
- No auth, billing, profile, or admin routes on `main`
- Analyze, report detail, report status, report export, and history are anonymous on `main`
- Mutating routes require `X-Requested-With`

## Data And Persistence

- `main` persists completed reports through `FileCache`
- `main` persists pipeline checkpoints through local SQLite
- Anonymous reports expire by TTL
- Status files track `processing`, `complete`, `failed`, and `cancelled`
- `main` must not require Supabase or Stripe configuration to boot

## Security Baseline

- CSRF protection on mutating API routes through `X-Requested-With`
- in-memory rate limiting for analyze and reports
- CORS must be explicit in production
- never hardcode secrets
- avoid logging PII or raw secrets

## Source Intelligence V2

- Default report shape is decision-first
- Keep competitor discovery as one section inside the broader validation contract
- Treat report detail and export formats as explicit interfaces
- Ranking stays opportunity-first: pain, commercial, migration, and whitespace evidence should beat raw popularity when signals conflict

## Testing Strategy

- Unit tests for pure logic and edge cases
- Integration tests for file cache and public API flows
- Regression tests for each bug fix
- Prefer deterministic tests over timing-heavy tests

## Done Criteria

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```
