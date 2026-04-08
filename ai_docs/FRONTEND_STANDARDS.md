# Frontend Development Standards

This document defines frontend expectations for the anonymous `main` branch.

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

## Current App Shape On `main`

- anonymous home flow
- anonymous history flow
- anonymous report detail flow
- SSE progress tracking
- report compare/export/evidence UI

Do not add login, pricing, profile, admin, or Supabase runtime dependencies back into `main`.

## Directory Structure

```text
frontend/src/
├── app/
├── components/ui/
├── features/history/
├── features/home/
├── features/reports/
├── lib/api/
├── lib/i18n/
├── lib/types/
├── lib/utils/
└── styles/
```

Rules:

- Shared primitives live in `components/ui/`
- Feature-specific components stay in their feature folder
- Keep shared API calls in `frontend/src/lib/api/client.ts`
- Keep SSE logic in `frontend/src/lib/api/useSSE.ts`
- Keep reducer/parser helpers for SSE in `frontend/src/lib/api/sseState.ts`
- Do not introduce `package-lock.json`

## TypeScript Conventions

- Keep strict typing
- Avoid `any`
- Prefer small typed helpers over large untyped components
- Keep shared report types aligned with backend report schemas

## API Layer

- Centralize HTTP calls in `frontend/src/lib/api/client.ts`
- Use typed wrappers rather than scattered raw `fetch`
- Error parsing must handle both `{"detail": ...}` and `{"error": {"code", "message"}}`
- `main` uses anonymous API requests; do not assume auth redirects or session tokens
- Anonymous report reads, export, status, and stream calls send a stable client-generated `X-Session-Id`
- Query validation in the UI must mirror backend normalization rules: collapse whitespace, require at least one letter, require at least 4 meaningful alphanumeric characters, and reject symbol-heavy input
- SSE reconnects must be capped and fall back to runtime status polling instead of reconnecting forever
- Preserve `ApiError` detail through fallback paths so 429/runtime CTAs can stay specific

## Routing

- Keep route-level lazy loading
- On `main`, exposed routes should stay limited to home, history, and report detail
- Do not expose login, pricing, profile, or admin routes on `main`

## Accessibility And UX

- Use semantic HTML
- Keep keyboard access and visible focus states
- Preserve responsive report reading and progress views
- Keep report section order aligned with the decision-first contract:
  `recommendation -> why-now -> pain -> commercial -> whitespace -> competitors -> evidence -> confidence`
- `SectionNav` anchors should map one-to-one to rendered report sections

## Done Criteria

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
