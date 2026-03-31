# IdeaGo Frontend (`saas`)

This document describes the hosted frontend that lives on the `saas` branch.

## What This Frontend Includes

- signed-out landing experience
- login and auth callback flows
- signed-in idea workspace
- report history and report detail pages
- profile management
- admin dashboard
- legal pages
- hidden pricing route and billing integration points

The pricing surface is intentionally disabled right now. `PRICING_ENABLED` is `false`, so do not
document or expose upgrade UI unless the task explicitly restores it.

## Stack

- React 19
- TypeScript
- Vite 7
- Tailwind CSS 4
- React Router 7
- Vitest + Testing Library
- i18next
- Supabase browser client
- Framer Motion
- Recharts

UI is built from project-owned shared primitives in `frontend/src/components/ui`. This branch does
not currently rely on shadcn as a required runtime dependency.

## Commands

```bash
pnpm --prefix frontend install
pnpm --prefix frontend dev
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## Environment Variables

Create `frontend/.env` from `frontend/.env.example`.

Common settings:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_TURNSTILE_SITE_KEY`
- `VITE_SENTRY_DSN`

Notes:

- `VITE_*` values are compiled into the frontend bundle.
- Leave `VITE_API_BASE_URL` empty for same-origin deployments.
- `VITE_TURNSTILE_SITE_KEY` is required for the current auth UI.

## Route Map

### Public routes

- `/`
- `/login`
- `/auth/callback`
- `/terms`
- `/privacy`

### Signed-in routes

- `/reports`
- `/reports/:id`
- `/profile`

### Admin route

- `/admin`

### Hidden route family

- `/pricing` exists in code only when `PRICING_ENABLED` is turned on

## Architecture Notes

### App shell

- `frontend/src/app/App.tsx`
- navbar, theme mode, language switching, error boundary, and route registration

### Auth

- `frontend/src/features/auth`
- `frontend/src/lib/auth`

The hosted frontend supports:

- Supabase session bootstrap
- backend cookie-backed LinuxDo session recovery through `/api/v1/auth/me`
- protected routes
- admin-only route gating

### API and SSE

- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/useSSE.ts`

The API layer centralizes request headers, auth recovery, error parsing, and SSE progress handling.

### Feature areas

- `frontend/src/features/landing`
- `frontend/src/features/home`
- `frontend/src/features/history`
- `frontend/src/features/reports`
- `frontend/src/features/profile`
- `frontend/src/features/admin`
- `frontend/src/features/legal`

## Current Product Rules

- keep the report UI aligned with the decision-first backend contract
- do not add public pricing discovery while billing remains hidden
- preserve signed-in versus signed-out routing behavior
- keep shared report types aligned with backend schemas
- keep auth and admin assumptions out of `main`

## Verification

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
