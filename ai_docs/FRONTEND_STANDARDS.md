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

- Supabase session bootstrap has priority over cookie-backed recovery
- LinuxDo auth recovery only runs when no Supabase session is present and the route allows `/api/v1/auth/me`
- protected routes gate signed-in pages
- admin route gating depends on hosted role hydration
- `AuthProvider` should keep session bootstrap, cookie recovery, and role hydration in separate helpers so behavior stays testable
- ordinary API calls and SSE should follow the same auth contract: Supabase sessions may send bearer tokens, LinuxDo recovery stays cookie-backed
- on 401, clear local auth state and invalidate history cache before redirecting to `/login`

Keep these flows working together when auth changes.

## API Layer

- Centralize HTTP calls in `frontend/src/lib/api/client.ts`
- Use typed wrappers rather than scattered raw `fetch`
- Error parsing must handle both `{"detail": ...}` and `{"error": {"code", "message"}}`
- On 401 responses, auth state should be cleared and users redirected to `/login`
- Account-deletion cleanup payloads are a typed contract, not ad-hoc strings:
- `rolled_back`
- `restored_access_only`
- `deletion_pending`
- `rollback_failed`
- `deleted`
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
- History cache is only valid for the first page, the current user, and the exact page-size contract; clear it on logout, 401, explicit refresh, deletion, or user switch
- Report detail should keep creation flow and view flow distinct:
- `/reports/new` owns analysis start, start failures, and redirect
- existing `/reports/:id` owns report/status reads, SSE, restart, and cancel
- complete-but-missing reports should retry a few times, then surface a clear restartable error instead of a vague unavailable state
- Admin search should debounce list queries and cancel stale requests; stats should not reload on every keystroke

## Done Criteria

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
