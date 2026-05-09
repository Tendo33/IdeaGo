# Frontend Index

Read this before frontend work on IdeaGo `main`.

## Current Frontend

The frontend is an anonymous product SPA under `frontend/`:

- React 19
- TypeScript strict mode
- Vite 7
- Tailwind CSS 4
- React Router 7
- `pnpm`
- Vitest + Testing Library
- `i18next`
- `framer-motion`, `recharts`, `lucide-react`, `sonner`

## Product Surface

- anonymous home flow
- anonymous history flow
- `/reports/new` creation handoff
- report detail, progress, compare, export, and evidence UI
- SSE progress tracking with capped reconnects and status fallback
- legal page files may exist, but active `main` route surface stays small

Do not add login, pricing, profile, admin, Supabase, Stripe, LinuxDo, or hosted
runtime dependencies back into `main`.

## Rules

- Use `pnpm` only.
- Keep TypeScript strict.
- Do not use `any` by default.
- Shared UI primitives live in `frontend/src/components/ui`.
- API calls and SSE helpers live in `frontend/src/lib/api`.
- Shared report types live in `frontend/src/lib/types`.
- Keep route-level lazy loading in `frontend/src/app/App.tsx`.
- Preserve bilingual UI support through `i18next` locale files.
- Read `design-md.md` before visible UI work.

## More Specific Guides

- `directory-structure.md`
- `design-md.md`
- `vite-static-mount.md`
- `components.md`
- `quality.md`
