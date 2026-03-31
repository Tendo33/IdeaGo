# Frontend Development Standards

This document defines frontend expectations for the hosted `saas` branch.

## Fixed Stack

| Layer | Choice |
| :--- | :--- |
| Package manager | `pnpm` |
| Framework | React 19 |
| Language | TypeScript |
| Bundler | Vite 7 |
| Styling | Tailwind CSS 4 |
| Routing | React Router 7 |
| Testing | Vitest + Testing Library |

The UI layer is built from project-owned primitives in `frontend/src/components/ui`.

## Current App Shape On `saas`

- signed-out landing experience
- login and auth callback flows
- signed-in home workspace
- report history and report detail
- profile page
- admin page
- legal pages
- hidden pricing route and billing plumbing

Do not expose pricing discovery or upgrade CTAs unless the task explicitly restores billing.

## Directory Structure

```text
frontend/src/
├── app/
├── components/ui/
├── features/admin/
├── features/auth/
├── features/history/
├── features/home/
├── features/landing/
├── features/legal/
├── features/pricing/
├── features/profile/
├── features/reports/
├── lib/api/
├── lib/auth/
├── lib/i18n/
├── lib/supabase/
├── lib/types/
├── lib/utils/
└── styles/
```

Rules:

- Shared primitives live in `components/ui/`
- Feature-specific components stay in their feature folder
- Keep shared API calls in `frontend/src/lib/api/client.ts`
- Keep SSE logic in `frontend/src/lib/api/useSSE.ts`
- Keep auth/session logic in `frontend/src/lib/auth`

## TypeScript Conventions

- Keep strict typing
- Avoid `any`
- Prefer small typed helpers over large untyped components
- Keep shared report types aligned with backend report schemas

## Auth And Session Model

- Supabase session bootstrap lives in `AuthProvider`
- LinuxDo auth recovery relies on backend `/api/v1/auth/me`
- protected routes gate signed-in pages
- admin route gating depends on hosted role hydration

Keep these flows working together when auth changes.

## API Layer

- Centralize HTTP calls in `frontend/src/lib/api/client.ts`
- Use typed wrappers rather than scattered raw `fetch`
- Error parsing must handle both `{"detail": ...}` and `{"error": {"code", "message"}}`
- On 401 responses, auth state should be cleared and users redirected to `/login`
- Preserve the required `X-Requested-With` header behavior for mutating API requests

## Routing

- Keep route-level lazy loading
- Public routes: landing, login, callback, legal
- Protected routes: reports, profile
- Admin route: `/admin`
- `/pricing` remains disabled while `PRICING_ENABLED` is `false`

## UX And Accessibility

- Use semantic HTML
- Keep keyboard access and visible focus states
- Preserve responsive report reading and progress views
- Keep bilingual UI support aligned with `i18next` translations

## Done Criteria

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
