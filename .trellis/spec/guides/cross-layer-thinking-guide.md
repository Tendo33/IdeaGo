# Cross-Layer Thinking Guide

Use this when a change touches both Python and the Vite frontend, or when the
backend serves built frontend assets.

## Layers

```text
React UI
  -> frontend API helper or relative URL
  -> Python HTTP boundary when present
  -> service/domain logic when present
  -> persistence when present
```

For static serving:

```text
Browser route
  -> backend API route check
  -> static asset check
  -> client app fallback
```

## Questions

- What layer owns validation?
- What layer owns the user-facing error message?
- Are date, enum, nullable, and optional fields represented the same way on both
  sides?
- Can unknown API routes accidentally return the frontend shell?
- Does the frontend need same-origin relative paths or an explicit API base URL?
- What test proves the full contract still works?

## Prevention

- Keep request/response examples in docs when endpoints are added.
- Add regression tests for routing precedence and serialization-sensitive data.
- Keep generated build output out of version control unless the project has a
  documented reason.
