# Static Fallback vs API Routes

IdeaGo serves the Vite build from FastAPI when `frontend/dist/` exists.

## Rule

API behavior must remain distinct from SPA fallback behavior:

- `/api/v1/*` routes are registered before static fallback.
- Unknown `/api/*` paths return API not-found errors.
- Existing built files are served directly.
- Client-side routes without file extensions may fall back to `index.html`.
- Unknown paths with file extensions return not-found.

## Why It Matters

If static fallback captures API paths, frontend errors become hard to diagnose
because failed API calls receive HTML. If fallback rejects app routes too
aggressively, hosted deep links stop working.

## Verification

When this code changes, run backend tests that cover API not-found behavior and
frontend build/static mount behavior.
