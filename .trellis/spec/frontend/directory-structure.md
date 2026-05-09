# Frontend Directory Structure

Use this when adding frontend files under `frontend/`.

```text
frontend/src/
├── app/
├── components/ui/
├── features/history/
├── features/home/
├── features/reports/
├── hooks/
├── lib/api/
├── lib/i18n/
├── lib/types/
├── lib/utils/
└── styles/
```

## Placement Rules

| New thing | Default location |
| --- | --- |
| App shell, router, theme/menu/error boundary | `frontend/src/app/` |
| Reusable UI primitive | `frontend/src/components/ui/` |
| Feature-specific page/component/hook | `frontend/src/features/<feature>/` |
| Shared hook with multiple real users | `frontend/src/hooks/` |
| HTTP client, report API, SSE parser/reducer | `frontend/src/lib/api/` |
| Shared report/domain TS type | `frontend/src/lib/types/` |
| Shared formatting or parsing utility | `frontend/src/lib/utils/` |
| i18n config and locale JSON | `frontend/src/lib/i18n/` |
| Global Tailwind/theme CSS | `frontend/src/styles/` |

## Routing Rules

- Exposed `main` routes should stay limited to home, history, and report detail
  flows.
- `/reports/new` is a transient creation state, not a permanent standalone
  marketing page.
- Do not expose login, pricing, profile, or admin routes on `main`.
