# Frontend Directory Structure

Use this when adding frontend files under `frontend/`.

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
├── hooks/
├── lib/api/
├── lib/auth/
├── lib/i18n/
├── lib/supabase/
├── lib/types/
├── lib/utils/
└── styles/
```

## Placement Rules

| New thing | Default location |
| --- | --- |
| App shell, router, theme menu, error boundary | `frontend/src/app/` |
| Reusable UI primitive | `frontend/src/components/ui/` |
| Feature-specific page/component/hook | `frontend/src/features/<feature>/` |
| Shared hook with multiple real users | `frontend/src/hooks/` |
| HTTP client, reports/auth/admin API, SSE parser/reducer | `frontend/src/lib/api/` |
| Supabase/session/protected route/auth state | `frontend/src/lib/auth/` or `frontend/src/lib/supabase/` |
| Shared report/domain TS type | `frontend/src/lib/types/` |
| Shared formatting or parsing utility | `frontend/src/lib/utils/` |
| i18n config and locale JSON | `frontend/src/lib/i18n/` |
| Global Tailwind/theme CSS | `frontend/src/styles/` |

## Routing Rules

- Public routes: landing, login, auth callback, legal.
- Protected routes: home workspace, reports, history, profile.
- Admin route: `/admin`.
- `/pricing` remains disabled while `PRICING_ENABLED` is `false`.
