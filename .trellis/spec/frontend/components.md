# Components

## Component Rules

- Components use TypeScript and explicit props.
- Shared primitives live under `frontend/src/components/ui`.
- Feature-specific components stay with the feature under
  `frontend/src/features/<feature>/`.
- UI primitives should be small, composable, accessible, and tested when
  behavior is not trivial.
- Do not introduce a third-party UI kit unless a task explicitly approves the
  dependency and migration.

## Styling

- Use Tailwind CSS v4.
- Keep global CSS focused on theme tokens, reset-level rules, and app-wide
  primitives.
- Avoid one-off hard-coded colors unless matching an existing token or visual
  contract.
- Preserve visible focus styles and keyboard access.
- Text must not overflow or overlap on common mobile and desktop widths.

## Interaction Testing

- Use Vitest + Testing Library.
- Prefer `userEvent` for user interactions.
- Test visible behavior and accessible state, not private component internals.
- For auth, report creation, history cache, SSE, and admin behavior, test the
  state transitions users actually see.
