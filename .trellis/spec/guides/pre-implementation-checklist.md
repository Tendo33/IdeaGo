# Pre-Implementation Checklist

Use this before non-trivial Python + Vite changes.

## Scope

- [ ] Is this backend-only, frontend-only, static-mount, scripts, docs, or full
  stack?
- [ ] Which current docs describe the existing behavior?
- [ ] Is the requested layer already present, or would this introduce a new
  layer?

## Patterns

- [ ] Search for existing models, helpers, hooks, and components first.
- [ ] If adding config, will it be used in tests or frontend build settings?
- [ ] If adding a type/model, is there already a Pydantic model or TypeScript
  type that should be the source of truth?
- [ ] If adding a utility, is there a second real caller?

## Frontend/Backend Boundary

- [ ] Is the request/response shape documented?
- [ ] Are errors finite and testable?
- [ ] If serving static files, do API routes still win before fallback?
- [ ] Are secrets kept out of frontend public variables?

## Verification

- [ ] What is the smallest command that proves the local change?
- [ ] What full gate is required before handoff?
