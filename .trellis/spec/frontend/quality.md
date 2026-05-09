# Frontend Quality

## Mandatory Rules

- TypeScript remains strict.
- No `any`, non-null assertions, or ignored TypeScript errors in new code.
- Components must be responsive and accessible.
- Visible focus styles must remain visible.
- Styling should use semantic tokens.
- Preserve i18n coverage for English and Chinese locale files.
- Keep API calls centralized in `frontend/src/lib/api`.
- Keep Supabase/session/bootstrap behavior centralized in `frontend/src/lib/auth`
  and `frontend/src/lib/supabase`.

## Hosted Flow Rules

- Supabase session bootstrap has priority over cookie-backed recovery.
- LinuxDo auth recovery only runs when no Supabase session is present and the
  route allows `/api/v1/auth/me`.
- On 401 responses, clear local auth state and invalidate history cache before
  redirecting to `/login`.
- Report creation (`/reports/new`) owns start failures and redirect.
- Existing report detail (`/reports/:id`) owns status reads, SSE, restart, and
  cancel behavior.
- SSE disconnects should leave users with a recoverable status path.
- Admin search should debounce list queries and cancel stale requests; stats
  should not reload on every keystroke.

## Testing

- Use Vitest + Testing Library.
- Prefer `userEvent` for interactions.
- Test visible behavior, accessible names, and state changes.
- Contract-sensitive types live in `frontend/src/lib/types` and should stay
  aligned with backend schemas.

## Visual Checks

For visible UI changes, check at least one mobile and one desktop viewport and
record the design source used.
