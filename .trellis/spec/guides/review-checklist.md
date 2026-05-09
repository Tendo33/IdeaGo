# Review Checklist

Before handoff, check:

- The change matches the current repository shape.
- No future architecture is documented as already implemented.
- Public imports still work.
- New configuration has safe defaults and does not expose secrets.
- Logs do not include sensitive values.
- Frontend code remains strict, accessible, and responsive.
- Visible frontend work follows the project root `DESIGN.md` when present.
- API/static routing boundaries are clear if the Vite build is mounted.
- Tests cover new behavior or regressions.
- The relevant verification commands were run.
- Docs were updated only where the change made them true and necessary.
