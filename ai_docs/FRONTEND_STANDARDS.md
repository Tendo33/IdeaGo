# Frontend Development Standards

This document defines default frontend practices for this repository and all connected AI tools.

## Fixed Stack

| Layer | Choice |
| :--- | :--- |
| Package manager | **pnpm** |
| Framework | React |
| Language | TypeScript (strict mode) |
| Bundler | Vite |
| Styling | Tailwind CSS |
| Component library | **shadcn/ui** |

> This stack is non-negotiable unless the user explicitly requests a change.

## Directory Structure

```text
frontend/
├── src/
│   ├── app/                # App shell, routing, providers
│   ├── features/           # Domain modules (one folder per feature)
│   │   └── <feature>/
│   │       ├── components/ # Feature-scoped components
│   │       ├── hooks/      # Feature-scoped hooks
│   │       ├── lib/        # Feature-scoped utilities
│   │       └── index.ts    # Public API barrel
│   ├── components/
│   │   └── ui/             # shadcn/ui primitives + shared components
│   ├── hooks/              # Global reusable hooks
│   ├── lib/                # Utilities, API client, constants
│   └── styles/             # Global CSS, Tailwind config extensions
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

Rules:

- Feature modules export through a barrel `index.ts`; imports between features go through the barrel.
- Shared UI primitives live in `components/ui/`; feature-specific components stay in their feature folder.
- Never import from another feature's internal files directly.

## shadcn/ui Usage

- Use shadcn/ui components as the baseline building blocks.
- Customize appearance via Tailwind classes and CSS variables (theme tokens), not by forking component source.
- When a shadcn/ui component doesn't exist for the need, build a custom component following the same patterns (Radix primitives + Tailwind + `cn()` utility).
- Keep the `components.json` config committed so `pnpm dlx shadcn@latest add <component>` works for all contributors.

## TypeScript Conventions

- Enable `strict: true` in `tsconfig.json`.
- Avoid `any`; use `unknown` + type narrowing when the type is genuinely dynamic.
- Prefer `interface` for object shapes that may be extended; use `type` for unions, intersections, and computed types.
- Export component props as named interfaces (e.g. `export interface ButtonProps`).

## Styling Conventions

- Tailwind utility classes are the primary styling mechanism.
- Use CSS variables (defined in `styles/globals.css`) for theme tokens: colors, radius, spacing scale.
- Avoid inline `style={}` except for truly dynamic values (e.g. percentage widths from data).
- Use the `cn()` helper (from `lib/utils.ts`) to merge conditional class names.

## State Management

- Start with React built-ins: `useState`, `useReducer`, `useContext`.
- For cross-feature or complex client state, prefer a lightweight store (e.g. Zustand) if needed.
- Server state is currently managed via custom hooks with `useEffect` + `useState`.

## API Layer

- Centralize HTTP calls in `lib/api/client.ts`.
- Use the typed `fetchWithTimeout` wrapper; do not scatter raw `fetch()` calls across components.
- Return typed response objects; throw typed errors.
- Error parsing uses `extractErrorDetail` to handle both `{"detail": ...}` and `{"error": {"code", "message"}}` formats.
- On 401 responses, both `client.ts` and `useSSE.ts` clear auth state via `clearCustomAuthSession()` and redirect to `/login`.

## Routing

- Use React Router (or TanStack Router) for client-side routing.
- Route definitions live in `app/` directory.
- Use lazy loading (`React.lazy` + `Suspense`) for feature-level route splits.

## Testing Strategy

- Unit tests: utility functions, hooks, pure logic.
- Component tests: use Vitest + Testing Library for interactive behavior.
- Prefer `userEvent` over `fireEvent` for realistic interaction simulation.
- Co-locate test files next to the code they test (`Button.test.tsx` beside `Button.tsx`).

## Accessibility Baseline

- Use semantic HTML elements (`button`, `nav`, `main`, `section`, etc.).
- All interactive elements must be keyboard-accessible with visible focus states.
- Images require `alt` text; decorative images use `alt=""`.
- Use ARIA attributes only when semantic HTML is insufficient.

## Performance Basics

- Memoize expensive computations with `useMemo`; memoize callbacks with `useCallback` only when passed to optimized children.
- Use `React.lazy` for code-splitting at the route level.
- Optimize images: use modern formats (WebP/AVIF), provide explicit `width`/`height`.
- Avoid barrel re-exports that defeat tree-shaking.

## Done Criteria (Frontend)

A frontend task is complete only if:

- behavior is implemented as requested,
- components render correctly and are keyboard-accessible,
- relevant tests pass,
- lint and type checks pass,
- no `any` types added without documented justification.

Recommended checks:

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```
