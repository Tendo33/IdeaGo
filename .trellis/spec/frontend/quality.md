# Frontend Quality

## Mandatory Rules

- TypeScript remains strict.
- No `any`, non-null assertions, or ignored TypeScript errors in new code.
- Components must be responsive and accessible.
- Visible focus styles must remain visible.
- Styling should use semantic tokens.
- Preserve i18n coverage for English and Chinese locale files.
- Keep API calls centralized in `frontend/src/lib/api`.
- Keep shared report contracts centralized in `frontend/src/lib/types`.

## Anonymous Flow Rules

- `main` uses anonymous API requests; do not assume auth redirects or session
  tokens.
- Anonymous report reads, export, status, and stream calls send a stable
  client-generated `X-Session-Id`.
- Query validation in the UI must mirror backend normalization rules: collapse
  whitespace, require at least one letter, require at least 4 meaningful
  alphanumeric characters, and reject symbol-heavy input.
- SSE reconnects must be capped and fall back to runtime status polling instead
  of reconnecting forever.
- Preserve `ApiError` detail through fallback paths so 429/runtime CTAs can stay
  specific.
- `SectionNav` anchors should map one-to-one to rendered report sections.

## Testing

- Use Vitest + Testing Library.
- Prefer `userEvent` for interactions.
- Test visible behavior, accessible names, and state changes.
- Contract-sensitive types live in `frontend/src/lib/types` and should stay
  aligned with backend schemas.

## Visual Checks

For visible UI changes, check at least one mobile and one desktop viewport and
record the design source used.
