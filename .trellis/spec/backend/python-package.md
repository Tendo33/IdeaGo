# Python Package Rules

## Package Shape

Use `src/ideago/` for importable Python code and `tests/` for backend tests.
Do not import modules through `src.ideago`.

Important stable surfaces:

- `ideago.api.app:create_app`
- `ideago.api.schemas`
- `ideago.models.research`
- `ideago.cache.base`
- `ideago.config.settings.get_settings`

## Typing

- Keep `src/ideago/py.typed`.
- Public functions need explicit return types.
- Use the project `BaseModel` from `ideago.models.base` for reusable Pydantic
  models.
- Prefer `Protocol` when behavior contracts avoid coupling callers to a
  concrete implementation.
- Avoid `Any` unless the boundary is genuinely dynamic and narrowed promptly.

## Public API Changes

When adding or moving public symbols:

1. Update the relevant `__init__.py` export.
2. Update or add tests that import from the public surface.
3. Update docs that mention stable imports.
4. Run backend verification.
