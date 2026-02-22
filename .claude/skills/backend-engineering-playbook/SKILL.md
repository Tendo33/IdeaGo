---
name: backend-engineering-playbook
description: Use when implementing backend API or service tasks that need architecture boundaries, data safety, and verification.
---
# Backend Engineering Playbook

## Goal

Deliver backend changes that are predictable, testable, and production-safe.

## Default Stack (Unless User Overrides)

- Python 3.10+
- FastAPI
- Pydantic v2
- SQLAlchemy + Alembic
- uv + ruff + pytest

## Workflow

1. Confirm scope, API contract, and assumptions.
2. Design by layers: API -> service -> repository -> domain.
3. Keep handlers thin and push business logic into services.
4. Implement explicit validation, error handling, and transaction boundaries.
5. Add or update tests for happy path and edge cases.
6. Run verification before completion claim.

## Quality Checklist

- Uses typed request/response models.
- Avoids secret leakage in logs.
- Includes stable error responses.
- Updates migration/docs if schema or behavior changed.

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
