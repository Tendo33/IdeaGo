# Backend Development Standards

This document defines default backend practices for this repository and all connected AI tools.

## Default Stack (When Not Specified)

- Language/runtime: Python 3.10+
- API framework: FastAPI
- Data validation: Pydantic v2
- Data access: SQLAlchemy
- Migrations: Alembic
- Package/runtime tooling: uv
- Quality tooling: ruff + pytest

## Architecture

Use a layered design to keep boundaries clear:

- `api` layer: HTTP routes, request/response schemas, auth guards
- `service` layer: business use cases and orchestration
- `repository` layer: persistence and external storage access
- `domain` layer: pure business models and rules

Rules:

- Keep HTTP concerns in `api`; do not put business logic in route handlers.
- Keep SQL/session details in repository layer.
- Service layer should be testable without HTTP or database bootstrapping.

## API Conventions

- Use versioned API prefix, e.g. `/api/v1`.
- Use Pydantic models for all request/response contracts.
- Return structured error payloads with stable error codes.
- Ensure idempotency for retry-safe write operations when applicable.
- Add pagination/filtering/sorting for list endpoints.

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

## Data and Transactions

- Use explicit transaction boundaries for write operations.
- Validate incoming data before persistence.
- Use migrations for schema changes; do not mutate schema manually in production.
- Keep repository methods narrow and purpose-driven.

## Security Baseline

- Validate and sanitize all external input.
- Enforce authN/authZ in API layer and service layer as needed.
- Apply rate limiting for public or high-risk endpoints.
- Use least-privilege credentials for database and infrastructure access.

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
