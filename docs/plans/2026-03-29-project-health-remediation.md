# IdeaGo Project Health Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the highest-risk product, security, performance, and maintainability gaps identified in the repository health check without breaking the Source Intelligence V2 contract.

**Architecture:** We will execute in three waves. Wave 1 removes user-facing trust and compliance risks. Wave 2 stabilizes the main analysis flow and contract integrity between backend and frontend. Wave 3 pays down structural debt in API/runtime orchestration and oversized frontend modules while preserving existing V2 report boundaries.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/PostgREST, raw SQL migrations, React 19, TypeScript, Vite 7, Tailwind 4, Vitest, pytest.

---

## Delivery Rules

- Follow `ai_docs/AI_TOOLING_STANDARDS.md`, `ai_docs/BACKEND_STANDARDS.md`, and `ai_docs/FRONTEND_STANDARDS.md`.
- Keep report payloads decision-first and contract-explicit.
- Do not move whitespace synthesis into `pipeline/merger.py`.
- Use TDD for backend logic and frontend behavior changes.
- Prefer small commits after each task group.

## Recommended Execution Order

1. Task 1: Fix account deletion contract gap
2. Task 2: Remove PII from audit logging
3. Task 3: Add report query/index performance support
4. Task 4: Make new-analysis flow refresh-safe
5. Task 5: Bound SSE reconnects and expose explicit recovery UX
6. Task 6: Align frontend/backed report contracts
7. Task 7: Consolidate dialog accessibility and page-level UX debt
8. Task 8: Refactor backend runtime composition
9. Task 9: Add regression coverage and operational observability

---

### Task 1: Fix Account Deletion Contract Gap

**Priority:** P0

**Goal:** Make account deletion behavior match the product promise, or narrow the product promise until deletion is truly complete.

**Files:**
- Modify: `src/ideago/auth/supabase_admin.py`
- Modify: `src/ideago/api/routes/auth.py`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `tests/test_api.py`
- Modify: `tests/test_auth.py` if auth deletion tests already live there, otherwise extend `tests/test_api.py`
- Modify: `README.md` if behavior changes are user-visible
- Modify: `README_CN.md` if behavior changes are user-visible

**Implementation notes:**
- Split deletion into explicit phases:
  1. delete app-owned data
  2. revoke or delete auth identity
  3. remove or cancel billing linkage if present
  4. write sanitized audit event
- If auth or billing deletion cannot be completed in this cycle, change frontend copy immediately so it no longer promises full identity/subscription removal.
- Return phase-aware errors instead of generic `"deleted"` when only partial cleanup completes.

**Step 1: Write failing backend tests**

Test cases to add:
- deleting account calls all cleanup phases in order
- partial failure returns structured error
- success path does not log raw email

Run:

```bash
uv run pytest tests/test_api.py -k delete_account -v
```

**Step 2: Implement service split in auth admin helper**

Target shape:

```python
async def delete_user_domain_data(user_id: str) -> dict: ...
async def delete_user_auth_identity(user_id: str) -> dict: ...
async def delete_user_billing_data(user_id: str) -> dict: ...
async def delete_user_account(user_id: str) -> dict: ...
```

**Step 3: Update route behavior**

- Route should call one orchestration function.
- Use `AppError` with structured `ErrorCode`.
- Keep fail-close behavior.

**Step 4: Update frontend danger-zone copy**

- Only promise what the backend now guarantees.
- Show phase-aware failure feedback if deletion fails.

**Step 5: Run verification**

```bash
uv run pytest tests/test_api.py -k delete_account -v
pnpm --prefix frontend test -- ProfilePage --run
pnpm --prefix frontend typecheck
```

**Acceptance criteria:**
- Product copy and backend behavior are aligned.
- No silent partial deletion success.
- Auth identity cleanup path is explicit in code, even if feature-flagged.

---

### Task 2: Remove PII From Audit Logging

**Priority:** P0

**Goal:** Stop storing raw email addresses in the audit trail while preserving enough forensic value for security investigations.

**Files:**
- Modify: `src/ideago/api/routes/auth.py`
- Modify: `src/ideago/observability/audit.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_log_config.py` only if shared logging expectations change

**Implementation notes:**
- Replace raw email with one of:
  - email hash
  - provider + actor_id only
  - domain-only summary if absolutely needed
- Keep audit payload minimal.

**Step 1: Add failing test**

Expected assertion:

```python
assert "email" not in audit_metadata
assert "email_hash" in audit_metadata or audit_metadata == {"provider": "linuxdo"}
```

Run:

```bash
uv run pytest tests/test_api.py -k audit -v
```

**Step 2: Update login and delete-account audit payloads**

Current hotspots:
- `src/ideago/api/routes/auth.py`

**Step 3: Add helper if needed**

If hashing is chosen, centralize it in observability/auth helper instead of duplicating route logic.

**Step 4: Run verification**

```bash
uv run pytest tests/test_api.py -k "audit or auth" -v
uv run mypy src
```

**Acceptance criteria:**
- No raw email in `metadata`.
- Audit table contract still works without schema change.

---

### Task 3: Add Report Search Performance Support

**Priority:** P0

**Goal:** Prevent history search and report listing from degrading into costly scans as user report volume grows.

**Files:**
- Modify: `supabase/migrations/003_create_reports.sql` only if using squashed local setup
- Create: `supabase/migrations/014_reports_search_indexes.sql`
- Modify: `src/ideago/cache/supabase_cache.py`
- Modify: `tests/test_cache.py`
- Modify: `README.md` or deployment docs if migration rollout steps need to be documented

**Implementation notes:**
- Add `(user_id, created_at desc)` index.
- Add trigram GIN index on `query` if fuzzy search remains `ilike`.
- Keep current API shape unchanged.
- Sanitize search input further if wildcard-heavy queries create pathological scans.

**Step 1: Add migration test coverage or repository regression coverage**

Add repository-level tests for:
- listing by `user_id`
- listing by `user_id + q`
- correct pagination after search

Run:

```bash
uv run pytest tests/test_cache.py -k list_reports -v
```

**Step 2: Write migration**

Target SQL:

```sql
create extension if not exists pg_trgm;

create index if not exists idx_reports_user_created_at
  on public.reports (user_id, created_at desc);

create index if not exists idx_reports_query_trgm
  on public.reports using gin (query gin_trgm_ops);
```

**Step 3: Review repository query**

- Keep query generation in `src/ideago/cache/supabase_cache.py`
- Strip unnecessary wildcard characters
- Keep exact `user_id` filter mandatory

**Step 4: Run verification**

```bash
uv run pytest tests/test_cache.py -k list_reports -v
uv run pytest
```

**Acceptance criteria:**
- History endpoint behavior unchanged.
- Schema now supports the observed query pattern.

---

### Task 4: Make New Analysis Flow Refresh-Safe

**Priority:** P1

**Goal:** Remove the drop-off where `/reports/new` loses the query after refresh or direct open.

**Files:**
- Modify: `frontend/src/features/home/HomePage.tsx`
- Modify: `frontend/src/features/reports/ReportPage.tsx`
- Modify: `frontend/src/features/home/components/SearchBox.tsx` only if submission contract changes
- Modify: `frontend/src/app/App.tsx` if route parsing helpers belong there
- Modify: `frontend/src/features/reports/ReportPage.test.tsx` or nearest report tests
- Modify: `frontend/src/features/home/HomePage.test.tsx`

**Implementation notes:**
- Preferred source of truth: URL query param `?q=...`
- Fallback: `location.state`
- Optional backup: short-lived session draft
- Redirect to `/` only after all sources are empty

**Step 1: Write failing frontend tests**

Test cases:
- navigating to `/reports/new?q=test` starts analysis
- refreshing `/reports/new?q=test` does not bounce home
- `/reports/new` without query redirects home

Run:

```bash
pnpm --prefix frontend test ReportPage --run
```

**Step 2: Update submit path from home**

- `HomePage` should navigate to `/reports/new?q=<encoded>`
- Keep state fallback only for compatibility

**Step 3: Update report boot logic**

- Read `searchParams`
- Normalize once
- Avoid double-triggering analysis

**Step 4: Run verification**

```bash
pnpm --prefix frontend test ReportPage HomePage --run
pnpm --prefix frontend typecheck
pnpm --prefix frontend build
```

**Acceptance criteria:**
- Refresh-safe
- Shareable
- No duplicate start requests

---

### Task 5: Bound SSE Reconnects And Expose Explicit Recovery UX

**Priority:** P1

**Goal:** Replace infinite reconnect ambiguity with a user-understandable recovery flow.

**Files:**
- Modify: `frontend/src/lib/api/useSSE.ts`
- Modify: `frontend/src/features/reports/components/useReportLifecycle.ts`
- Modify: `frontend/src/features/reports/ReportPage.tsx`
- Modify: `frontend/src/features/reports/components/ReportStatusStates.tsx` if status UI lives there
- Modify: `frontend/src/lib/api/useSSE.test.ts` if present, otherwise add nearest frontend tests

**Implementation notes:**
- Add `MAX_RECONNECT_ATTEMPTS` or `MAX_RECONNECT_DURATION_MS`
- Transition to explicit terminal error state after limit
- Offer `Retry stream`, `Check status`, `Restart analysis`
- Log last failure reason for observability

**Step 1: Write failing tests**

Test cases:
- repeated disconnects stop after threshold
- terminal error is surfaced to UI
- manual retry resets counters

Run:

```bash
pnpm --prefix frontend test useSSE --run
```

**Step 2: Update hook contract**

Suggested additions:

```ts
isTerminalError: boolean
reconnectAttempts: number
lastFailureReason: string | null
```

**Step 3: Update report lifecycle/UI**

- Distinguish:
  - processing
  - reconnecting
  - connection lost but report may still be processing
  - terminal failure

**Step 4: Run verification**

```bash
pnpm --prefix frontend test ReportPage useSSE --run
pnpm --prefix frontend build
```

**Acceptance criteria:**
- No infinite reconnect loop.
- User always sees a deterministic next action.

---

### Task 6: Align Frontend And Backend Report Contracts

**Priority:** P1

**Goal:** Eliminate drift between backend V2 report schemas and frontend shared types.

**Files:**
- Modify: `frontend/src/lib/types/research.ts`
- Modify: `src/ideago/models/research.py` only if backend contract is intentionally revised
- Modify: `src/ideago/api/schemas.py` only if backend contract is intentionally revised
- Modify: `frontend/src/features/reports/components/LandscapeChart.tsx`
- Modify: `frontend/src/features/reports/components/ReportCompetitorSection.tsx`
- Modify: `frontend/src/features/reports/components/ComparePanel.tsx`
- Modify: `frontend/src/features/reports/*.test.tsx` where needed

**Implementation notes:**
- Add missing frontend fields:
  - `Intent.exact_entities`
  - `Intent.comparison_anchors`
  - `Intent.search_goal`
  - `Competitor.relevance_kind`
- Remove `any` from chart interaction code.
- Audit downstream rendering assumptions after type expansion.

**Step 1: Write failing type-level checks or tests**

Run:

```bash
pnpm --prefix frontend typecheck
```

Expected: current changes should expose consumer mismatches once types are corrected.

**Step 2: Update shared TS types**

- Match backend names exactly.
- Preserve strictness.

**Step 3: Fix consumers**

- Chart click payload typing
- compare UI
- competitor filter/sort views

**Step 4: Run verification**

```bash
pnpm --prefix frontend typecheck
pnpm --prefix frontend test -- --run
```

**Acceptance criteria:**
- Frontend types reflect backend V2 payload.
- No `any` remains in the chart interaction path.

---

### Task 7: Consolidate Dialog Accessibility And Page-Level UX Debt

**Priority:** P2

**Goal:** Remove brittle custom dialog behavior and improve keyboard accessibility across history/report/profile flows.

**Files:**
- Modify: `frontend/src/features/history/HistoryPage.tsx`
- Modify: `frontend/src/features/reports/components/ComparePanel.tsx`
- Create: `frontend/src/components/ui/Dialog.tsx` only if a shared dialog primitive does not already exist
- Modify: `frontend/src/features/profile/ProfilePage.tsx`
- Modify: relevant frontend tests

**Implementation notes:**
- Prefer one shared dialog primitive over multiple custom implementations.
- Ensure:
  - focus trap
  - restore focus
  - Escape close
  - backdrop click semantics
  - ARIA labels
- If using an existing shadcn/Radix-compatible primitive, keep styling local.

**Step 1: Introduce or adopt dialog primitive**

Run:

```bash
pnpm --prefix frontend test ComparePanel HistoryPage ProfilePage --run
```

**Step 2: Migrate delete-confirm dialog**

- History delete modal
- Profile dangerous action confirmation

**Step 3: Migrate compare panel**

- Keep existing layout
- Replace manual document-level keydown trap

**Step 4: Run verification**

```bash
pnpm --prefix frontend test ComparePanel HistoryPage ProfilePage --run
pnpm --prefix frontend lint
```

**Acceptance criteria:**
- Dialog behavior is consistent.
- Keyboard users can traverse and exit all modal flows reliably.

---

### Task 8: Refactor Backend Runtime Composition

**Priority:** P2

**Goal:** Reduce monolithic API bootstrapping and separate middleware/runtime responsibilities without changing external API behavior.

**Files:**
- Modify: `src/ideago/api/app.py`
- Create: `src/ideago/api/middleware/security.py`
- Create: `src/ideago/api/middleware/rate_limit.py`
- Create: `src/ideago/api/exception_handlers.py`
- Modify: `src/ideago/api/dependencies.py`
- Modify: `tests/test_api.py`

**Implementation notes:**
- `create_app()` should become composition-only.
- Separate:
  - trace/metrics middleware
  - csrf middleware
  - security headers middleware
  - rate limiting
  - exception handlers
- In `dependencies.py`, split runtime task registry from distributed dedup behavior.

**Step 1: Add regression tests first**

Cover:
- CSRF header rejection
- rate limit rejection
- security headers present
- app error envelope unchanged

Run:

```bash
uv run pytest tests/test_api.py -k "csrf or rate_limit or headers or error" -v
```

**Step 2: Extract middleware modules**

- Move one middleware at a time.
- Keep route registration unchanged.

**Step 3: Separate runtime registries**

Suggested boundary:

```python
class ProcessingDedupStore: ...
class PipelineTaskRegistry: ...
```

**Step 4: Run verification**

```bash
uv run pytest tests/test_api.py -k "csrf or rate_limit or headers or error" -v
uv run mypy src
uv run pytest
```

**Acceptance criteria:**
- Behavior unchanged externally.
- `app.py` shrinks materially.
- Runtime responsibilities are easier to reason about.

---

### Task 9: Add Regression Coverage And Operational Observability

**Priority:** P2

**Goal:** Convert the health check’s highest-risk findings into durable tests and lightweight metrics.

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_cache.py`
- Modify: `frontend/src/features/reports/*.test.tsx`
- Modify: `frontend/src/features/history/*.test.tsx`
- Modify: `src/ideago/observability/audit.py`
- Modify: `src/ideago/observability/metrics.py` if adding counters
- Modify: `README.md` or ops docs if new metrics are exposed

**Implementation notes:**
- Add metrics/counters for:
  - start analysis failure
  - SSE terminal reconnect failure
  - report status `not_found`
  - account deletion phase failure
- Add at least one regression test per issue fixed in Tasks 1-8.

**Step 1: Build regression checklist**

- Each completed fix must add a direct test reference in commit message or PR notes.

**Step 2: Add backend counters/logs where cheap**

- Do not introduce heavy telemetry dependencies.
- Reuse existing observability patterns.

**Step 3: Add frontend behavior tests**

- report new-flow recovery
- terminal SSE state
- dialog keyboard behavior

**Step 4: Run final verification**

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test -- --run
pnpm --prefix frontend build
```

**Acceptance criteria:**
- Each health-check finding is either fixed or captured as deferred debt with a regression guard.
- Team has enough observability to detect recurrence.

---

## Suggested Milestone Breakdown

### Milestone A: Risk Closure

- Complete Tasks 1-3
- Ship behind no new feature flags unless deletion cleanup needs staged rollout
- Recommended commit cadence:
  - `fix: align account deletion contract`
  - `fix: remove pii from audit logs`
  - `perf: add report search indexes`

### Milestone B: Core Flow Stability

- Complete Tasks 4-6
- Focus on report creation, SSE resilience, and contract alignment
- Recommended commit cadence:
  - `fix: persist report creation query in url`
  - `fix: cap sse reconnect loop`
  - `refactor: align frontend report types with backend`

### Milestone C: Structural Cleanup

- Complete Tasks 7-9
- Focus on maintainability and regression durability
- Recommended commit cadence:
  - `refactor: unify modal accessibility behavior`
  - `refactor: extract api middleware modules`
  - `test: add regression coverage for health-check fixes`

---

## Rollout Notes

- Apply SQL migration before deploying the backend code that depends on search/index assumptions.
- Treat account deletion changes as a release note item.
- If auth identity deletion depends on unavailable admin APIs, ship copy correction first and full deletion second.
- Keep frontend and backend contract updates in the same PR whenever `ReportDetailV2`-related fields change.

## Final Verification Gate

Do not mark complete until all of the following pass:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test -- --run
pnpm --prefix frontend build
```

## Handoff

Plan complete and saved to `docs/plans/2026-03-29-project-health-remediation.md`.

Two execution options:

**1. Subagent-Driven (this session)** - implement task-by-task here, with tight review after each milestone.

**2. Parallel Session (separate)** - open a fresh execution session and follow this plan as the source of truth.
