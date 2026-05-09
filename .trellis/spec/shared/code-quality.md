# Code Quality

These rules apply to the Python backend/package and the React + Vite frontend.

## Mandatory Rules

- Keep changes small and reviewable.
- Search for existing patterns before adding a new helper, model, hook, or
  component.
- Do not add framework-style abstraction for one call site.
- Do not swallow errors silently.
- Do not log secrets, tokens, passwords, auth headers, or sensitive personal
  data.
- Do not document future layers as current implementation.

## Python

- Use explicit return types on public functions.
- Avoid `Any`; use `unknown`-style validation through Pydantic or explicit
  narrowing when data is dynamic.
- Use Pydantic v2 APIs.
- Keep public imports stable and covered by tests.
- Do not import through `src.<package_name>...`.

## Frontend

- Keep TypeScript strict.
- Do not use `any`, non-null assertions, or ignored TypeScript errors in new
  code.
- Components must preserve accessible names and visible focus states.
- UI text must not overflow or overlap at common mobile and desktop widths.
- Prefer semantic tokens over hard-coded colors.

## Before Handoff

- Run the verification scope that matches the changed surface.
- Include docs changes when behavior, structure, scripts, public APIs, or
  verification commands changed.
