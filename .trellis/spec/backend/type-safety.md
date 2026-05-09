# Type Safety

## Python Rules

- Keep `py.typed` in `src/ideago`.
- Public functions need explicit return types.
- Prefer Pydantic models for external data shapes, API schemas, and report
  contracts.
- Use Pydantic v2 APIs: `model_config`, `model_dump`, `model_validate`, and
  `field_validator` / `model_validator`.
- Prefer `Protocol` when a behavior contract avoids coupling callers to a
  concrete implementation.
- Avoid `Any`; use explicit models, `TypedDict`, `Protocol`, or `object` plus
  narrowing.

## Report Contract

- Keep backend `ideago.api.schemas`, `ideago.models.research`, and frontend
  `frontend/src/lib/types/research.ts` aligned.
- Treat report detail and export formats as public interfaces.
- Add serialization-sensitive tests for dates, enums, optional fields, source
  result payloads, evidence carriers, and report status responses.

## Frontend Boundary

If the frontend consumes backend JSON:

- centralize calls in `frontend/src/lib/api`
- document or preserve request, success response, and error response shapes
- keep field names stable
- update both Python and TypeScript tests when contract fields change
