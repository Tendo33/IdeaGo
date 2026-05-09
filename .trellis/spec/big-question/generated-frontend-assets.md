# Generated Frontend Assets

`frontend/dist/` is generated output from Vite and should not be committed.

## Rule

- Build with `pnpm --prefix frontend build`.
- Docker builds the frontend in a Node stage and copies `dist` into the Python
  runtime image.
- Keep source changes in `frontend/src`, `frontend/public`, or config files.
- Do not patch built files by hand.

## Verification

Run the frontend build after changes to Vite config, Tailwind config/CSS,
frontend dependencies, public assets, Dockerfile frontend stage, or static
mount behavior.
