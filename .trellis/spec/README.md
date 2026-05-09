# IdeaGo SaaS Trellis Spec

This spec is the AI collaboration source of truth for the `saas` branch of
IdeaGo. The branch is the hosted/commercial edition of the product: it keeps the
Source Intelligence V2 analysis core and adds Supabase auth, hosted report
persistence, quota/account management, admin APIs, LinuxDo session recovery, and
Stripe billing plumbing.

Use the `main` branch for the anonymous/personal deployment edition. Do not copy
hosted-only dependencies or contracts from `saas` into `main` unless the task
explicitly says both branches should change.

## Product Contract

IdeaGo turns a rough startup idea into a decision-first validation report backed
by live evidence from Tavily, Reddit, GitHub, Hacker News, App Store, and Product
Hunt. Reports stay ordered as:

1. recommendation and why-now
2. pain signals
3. commercial signals
4. whitespace opportunities
5. competitors
6. evidence
7. confidence

`/api/v1/reports/{report_id}` and export payloads are explicit contracts.
`pipeline/merger.py` remains deterministic competitor dedupe only. Whitespace,
entry-wedge, and opportunity synthesis belong in `pipeline/aggregator.py`.

## Structure

### [Backend](./backend/index.md)

FastAPI, LangGraph, Supabase, auth/session, billing, persistence, and Source
Intelligence V2 backend rules.

### [Frontend](./frontend/index.md)

React 19 + Vite 7 + Tailwind 4 hosted product UI rules.

### [Shared](./shared/index.md)

Cross-cutting stack, docs, dependencies, quality, and verification rules.

### [Guides](./guides/index.md)

Task flow, pre-implementation, cross-layer thinking, and review checklists.

### [Common Issues / Pitfalls](./big-question/index.md)

Known production-sensitive traps for the hosted branch.

## Read Order

1. `shared/index.md`
2. `backend/index.md` before backend work
3. `frontend/index.md` before frontend work
4. `guides/pre-implementation-checklist.md` before non-trivial changes
5. `shared/verification.md` before claiming completion
6. `guides/review-checklist.md` before handoff

## Baseline Stack

- Python 3.10+
- `uv`
- FastAPI + Pydantic v2 + `pydantic-settings`
- LangGraph + LangChain OpenAI
- Supabase auth, PostgREST/RPC persistence, and hosted runtime state
- Stripe integration code with user-facing pricing intentionally hidden
- React 19
- TypeScript strict mode
- Vite 7
- Tailwind CSS v4
- React Router 7
- `pnpm`
- Vitest + Testing Library + jsdom

## Project Bias

- Keep changes small, typed, and explicit.
- Preserve branch-specific behavior: hosted-only SaaS functionality belongs on
  `saas`; anonymous/personal behavior belongs on `main`.
- Update this spec when behavior, structure, scripts, adapters, public APIs,
  verification commands, or stack choices change.
