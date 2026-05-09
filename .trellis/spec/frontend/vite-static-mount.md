# Vite Static Mount

The backend serves the built Vite SPA when `frontend/dist/` exists.

## Build Boundary

- Source lives in `frontend/src`.
- Production assets are produced by `pnpm --prefix frontend build`.
- Docker builds the frontend with `corepack enable && pnpm install --frozen-lockfile`.
- Python code must not import frontend source files.
- Frontend code must not depend on backend internals.

## Routing

- API routes must win before static fallback.
- `/assets/*` serves built static assets directly.
- Client-side app routes may fall back to `index.html`.
- Unknown `/api/*` paths must return API errors, not the frontend shell.
- Requests with file extensions that are not real built files should return
  not-found instead of the SPA shell.

## Configuration

- Prefer same-origin relative API paths for local/personal deployments.
- Use `VITE_*` only for browser-safe build-time values.
- Never expose raw provider API keys through Vite variables.

## Verification

For static mount changes, run both frontend build and backend tests that cover
fallback/API separation.
