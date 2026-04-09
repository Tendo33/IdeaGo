# Health Check Remediation Todo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the highest-value gaps from the April 2026 comprehensive health check without breaking the Source Intelligence V2 product contract.

**Architecture:** This plan keeps the existing FastAPI + Supabase + React architecture and focuses on contract integrity, fail-closed error handling, admin reliability, and targeted frontend maintainability improvements. We will fix data-contract drift first, then repair operational truthfulness in backend responses, then harden security and performance, and only then pay down large-component debt.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, Supabase/PostgREST, SQL migrations, pytest, React 19, TypeScript, Vite 7, Tailwind CSS 4, Vitest, Testing Library

---

## Delivery Rules

- Follow `AGENTS.md`, `CLAUDE.md`, `ai_docs/BACKEND_STANDARDS.md`, and `ai_docs/FRONTEND_STANDARDS.md`.
- Preserve the Source Intelligence V2 decision-first report contract and section order.
- Do not move whitespace synthesis into `pipeline/merger.py`.
- Use TDD for all behavior changes.
- Prefer one focused commit per task.
- Update docs when runtime behavior or operator workflows change.

## Recommended Execution Order

1. Task 1: Repair admin quota schema drift
2. Task 2: Stop masking repository failures as empty business states
3. Task 3: Add admin/profile query performance support
4. Task 4: Harden cookie-backed CSRF defenses
5. Task 5: Improve quota-exceeded and degraded-state UX
6. Task 6: Refactor oversized report lifecycle and API client seams
7. Task 7: Refactor oversized auth/report UI components
8. Task 8: Reduce report-page performance overhead
9. Task 9: Close docs and config hygiene gaps

---

### Task 1: Repair Admin Quota Schema Drift

**Files:**
- Modify: `supabase/migrations/001_create_profiles.sql`
- Modify: `supabase/migrations/002_quota_functions.sql`
- Create: `supabase/migrations/015_admin_quota_contract.sql`
- Modify: `src/ideago/auth/supabase_admin.py`
- Modify: `src/ideago/api/routes/admin.py`
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/src/features/admin/AdminPage.tsx`
- Test: `tests/test_api.py`
- Test: `frontend/src/features/admin/__tests__/AdminPage.test.tsx` or create if missing

**Step 1: Write the failing backend tests**

- Add a test proving `list_profiles()` returns a stable `plan_limit` field even when quota is derived by RPC or view logic.
- Add a test proving `set_user_quota()` updates the supported storage field instead of patching a non-existent `profiles.plan_limit` column.
- Add a route test proving `PATCH /api/v1/admin/users/{user_id}/quota` returns a valid updated payload.

Run:

```bash
uv run pytest tests/test_api.py -k "admin and quota" -v
```

Expected: new admin quota tests fail against the current implementation.

**Step 2: Write the failing frontend test**

- Add a test proving the admin quota editor loads a numeric limit and saves it through the admin API without crashing on refreshed data.

Run:

```bash
pnpm --prefix frontend test -- AdminPage --run
```

Expected: the new admin quota contract case fails.

**Step 3: Add the database contract**

- Create `supabase/migrations/015_admin_quota_contract.sql`.
- Add `plan_limit_override` to `profiles` if that is the chosen design.
- Add a stable admin-facing projection that exposes `plan_limit` as:

```sql
coalesce(plan_limit_override, public.get_plan_limit('daily'))
```

- Do not change the public Source Intelligence report contract.

**Step 4: Update backend admin data access**

- Replace direct `plan_limit` column reads in `src/ideago/auth/supabase_admin.py`.
- Read from the admin projection or compute `plan_limit` explicitly.
- Write only to the supported override field.
- Keep `usage_count` updates intact.

**Step 5: Update frontend admin types and rendering**

- Keep `AdminUser.plan_limit` as the display field.
- Do not leak storage-specific names like `plan_limit_override` into the UI.
- Keep row editing behavior unchanged from the operator perspective.

**Step 6: Re-run targeted tests**

```bash
uv run pytest tests/test_api.py -k "admin and quota" -v
pnpm --prefix frontend test -- AdminPage --run
```

Expected: targeted backend and frontend tests pass.

**Step 7: Commit**

```bash
git add supabase/migrations/015_admin_quota_contract.sql supabase/migrations/001_create_profiles.sql supabase/migrations/002_quota_functions.sql src/ideago/auth/supabase_admin.py src/ideago/api/routes/admin.py frontend/src/lib/api/client.ts frontend/src/features/admin/AdminPage.tsx tests/test_api.py frontend/src/features/admin
git commit -m "fix: align admin quota contract with database schema"
```

---

### Task 2: Stop Masking Repository Failures As Empty Business States

**Files:**
- Modify: `src/ideago/cache/supabase_cache.py`
- Modify: `src/ideago/auth/supabase_admin.py`
- Modify: `src/ideago/api/routes/reports.py`
- Modify: `src/ideago/api/routes/admin.py`
- Modify: `src/ideago/api/errors.py`
- Modify: `tests/test_cache.py`
- Modify: `tests/test_api.py`
- Test: `frontend/src/features/history/__tests__/HistoryPage.test.tsx`
- Test: `frontend/src/features/admin/__tests__/AdminPage.test.tsx`

**Step 1: Write the failing backend tests**

- Add a cache test proving `list_reports()` raises an infrastructure error when Supabase returns non-200.
- Add a route test proving `GET /api/v1/reports` returns a structured `503` instead of `[]` on repository failure.
- Add an admin test proving `GET /api/v1/admin/users` returns `503` instead of silently returning an empty list when profile fetch fails.

Run:

```bash
uv run pytest tests/test_cache.py -k list_reports -v
uv run pytest tests/test_api.py -k "admin_list_users or list_reports" -v
```

Expected: new failure-semantics tests fail.

**Step 2: Add explicit repository-level exceptions**

- Introduce a small typed error such as:

```python
class RepositoryUnavailable(RuntimeError):
    ...
```

- Use it in `src/ideago/cache/supabase_cache.py` and `src/ideago/auth/supabase_admin.py` when upstream Supabase calls fail.
- Do not silently return `[]`, `0`, `""`, or `None` for infrastructure faults.

**Step 3: Map repository failures in API routes**

- Convert repository exceptions to `AppError(503, ...)`.
- Keep `404` for real missing resources.
- Keep `403` for authorization failures.

**Step 4: Write the failing frontend tests**

- Add a history-page test proving a repository outage shows an error alert, not the empty-state CTA.
- Add an admin-page test proving a repository outage shows the warning alert, not the “no users” state.

Run:

```bash
pnpm --prefix frontend test -- HistoryPage --run
pnpm --prefix frontend test -- AdminPage --run
```

Expected: new degraded-state tests fail.

**Step 5: Update frontend error rendering only if needed**

- Keep current alert components.
- Ensure empty states are gated behind successful loads, not merely `reports.length === 0`.

**Step 6: Re-run targeted tests**

```bash
uv run pytest tests/test_cache.py -k list_reports -v
uv run pytest tests/test_api.py -k "admin_list_users or list_reports" -v
pnpm --prefix frontend test -- HistoryPage --run
pnpm --prefix frontend test -- AdminPage --run
```

Expected: targeted tests pass with explicit degraded behavior.

**Step 7: Commit**

```bash
git add src/ideago/cache/supabase_cache.py src/ideago/auth/supabase_admin.py src/ideago/api/routes/reports.py src/ideago/api/routes/admin.py src/ideago/api/errors.py tests/test_cache.py tests/test_api.py frontend/src/features/history frontend/src/features/admin
git commit -m "fix: expose repository failures as degraded states"
```

---

### Task 3: Add Admin/Profile Query Performance Support

**Files:**
- Create: `supabase/migrations/016_admin_query_indexes.sql`
- Modify: `src/ideago/auth/supabase_admin.py`
- Modify: `src/ideago/api/routes/admin.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`
- Modify: `README_CN.md`

**Step 1: Write the failing regression tests**

- Add a backend test proving admin user listing continues to sort by `created_at desc` after the query refactor.
- Add a backend test proving admin stats still return valid counts when plan breakdown is present.

Run:

```bash
uv run pytest tests/test_api.py -k "admin and stats" -v
```

Expected: either current tests need extension or new ones fail while refactoring.

**Step 2: Add the migration**

- Create `supabase/migrations/016_admin_query_indexes.sql`.
- Add:

```sql
create index if not exists idx_profiles_created_at_desc
  on public.profiles (created_at desc);
```

- If the new admin projection from Task 1 needs support, add the smallest necessary supporting index set only.

**Step 3: Keep backend queries minimal**

- Avoid broad `select=*` patterns.
- Keep exact operator-facing fields only.
- Keep `HEAD + count=exact` stats code for now unless a simpler improvement is obviously safe.

**Step 4: Update operator docs**

- Note the new migration in `README.md` and `README_CN.md` if deployment sequencing matters.

**Step 5: Re-run targeted tests**

```bash
uv run pytest tests/test_api.py -k "admin and stats" -v
```

Expected: admin query tests pass.

**Step 6: Commit**

```bash
git add supabase/migrations/016_admin_query_indexes.sql src/ideago/auth/supabase_admin.py src/ideago/api/routes/admin.py tests/test_api.py README.md README_CN.md
git commit -m "perf: add admin query indexes and docs"
```

---

### Task 4: Harden Cookie-Backed CSRF Defenses

**Files:**
- Modify: `src/ideago/api/http_middleware.py`
- Modify: `src/ideago/config/settings.py`
- Modify: `src/ideago/api/app.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`
- Modify: `README_CN.md`

**Step 1: Write the failing tests**

- Add a test proving a mutating cookie-backed API request with a bad `Origin` is rejected even if `X-Requested-With` is present.
- Add a test proving same-origin SPA requests still succeed.
- Add a test proving the Stripe webhook exemption still works.

Run:

```bash
uv run pytest tests/test_api.py -k "csrf or webhook" -v
```

Expected: new origin-validation cases fail on current middleware.

**Step 2: Add explicit allowed-origin checking**

- Reuse configured CORS origins.
- Validate `Origin` or `Referer` for mutating `/api/` requests that rely on cookies.
- Preserve the existing `X-Requested-With` requirement.
- Keep `/api/v1/billing/webhook` exempt.

**Step 3: Add any minimal settings helper needed**

- If origin normalization is needed, add a tiny helper in `src/ideago/config/settings.py`.
- Do not over-engineer a full CSRF token system in this batch.

**Step 4: Update docs**

- Document the stricter mutating-request requirements for local and deployed SPA clients.

**Step 5: Re-run targeted tests**

```bash
uv run pytest tests/test_api.py -k "csrf or webhook" -v
```

Expected: CSRF tests pass and webhook behavior remains unchanged.

**Step 6: Commit**

```bash
git add src/ideago/api/http_middleware.py src/ideago/config/settings.py src/ideago/api/app.py tests/test_api.py README.md README_CN.md
git commit -m "security: validate origin for cookie-backed mutating requests"
```

---

### Task 5: Improve Quota-Exceeded And Degraded-State UX

**Files:**
- Modify: `frontend/src/features/reports/ReportPage.tsx`
- Modify: `frontend/src/features/profile/ProfilePage.tsx`
- Modify: `frontend/src/features/history/HistoryPage.tsx`
- Modify: `frontend/src/lib/api/client.ts`
- Modify: `frontend/src/lib/i18n` translation files as needed
- Test: `frontend/src/features/reports/__tests__/ReportPage.test.tsx`
- Test: `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` or create if missing
- Test: `frontend/src/features/history/__tests__/HistoryPage.test.tsx`

**Step 1: Write the failing tests**

- Add a report-page test proving quota-exceeded state shows actionable recovery text and does not collapse into a generic error banner.
- Add a profile-page test proving quota load failure shows an unavailable state instead of rendering misleading zeroed usage.
- Add a history-page test proving infrastructure errors do not render the normal empty state.

Run:

```bash
pnpm --prefix frontend test -- ReportPage --run
pnpm --prefix frontend test -- ProfilePage --run
pnpm --prefix frontend test -- HistoryPage --run
```

Expected: new UX-state cases fail.

**Step 2: Implement the minimal UI changes**

- In `ReportPage`, show reset timing or a clear “try later / go to history” recovery path.
- In `ProfilePage`, add a small unavailable panel inside the usage card when quota cannot be loaded.
- In `HistoryPage`, keep the error alert dominant over empty-state CTAs.

**Step 3: Update copy**

- Add translations for the new degraded/quota messages.
- Keep pricing and upgrade entry points hidden per project contract.

**Step 4: Re-run targeted tests**

```bash
pnpm --prefix frontend test -- ReportPage --run
pnpm --prefix frontend test -- ProfilePage --run
pnpm --prefix frontend test -- HistoryPage --run
```

Expected: targeted UI behavior passes.

**Step 5: Commit**

```bash
git add frontend/src/features/reports/ReportPage.tsx frontend/src/features/profile/ProfilePage.tsx frontend/src/features/history/HistoryPage.tsx frontend/src/lib/api/client.ts frontend/src/lib/i18n frontend/src/features/reports frontend/src/features/profile frontend/src/features/history
git commit -m "feat: improve quota and degraded-state recovery UX"
```

---

### Task 6: Refactor Oversized Report Lifecycle And API Client Seams

**Files:**
- Modify: `frontend/src/features/reports/components/useReportLifecycle.ts`
- Create: `frontend/src/features/reports/components/reportLifecycleReducer.ts`
- Create: `frontend/src/features/reports/components/reportLifecycleActions.ts`
- Modify: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/authClient.ts`
- Create: `frontend/src/lib/api/reportsClient.ts`
- Create: `frontend/src/lib/api/adminClient.ts`
- Modify: existing imports across report/auth/admin pages
- Test: `frontend/src/features/reports/__tests__/ReportPage.test.tsx`
- Test: `frontend/src/lib/api/__tests__/*` if needed

**Step 1: Write the failing tests**

- Add a reducer-level test proving the report lifecycle transitions correctly on:
  - initial load
  - processing
  - complete-but-missing retry
  - cancelled
  - restart
- Add a light API module smoke test proving report/auth/admin imports still expose the expected functions.

Run:

```bash
pnpm --prefix frontend test -- ReportPage --run
```

Expected: new transition coverage fails because reducer/modules do not exist yet.

**Step 2: Extract lifecycle state transitions**

- Move state transitions into `reportLifecycleReducer.ts`.
- Keep network side effects in the hook.
- Keep current visible behavior unchanged.

**Step 3: Split `client.ts` by domain**

- Leave `fetchWithTimeout`, `ApiError`, and shared helpers in the base module.
- Move auth-specific functions into `authClient.ts`.
- Move report functions into `reportsClient.ts`.
- Move admin functions into `adminClient.ts`.
- Re-export from `client.ts` only if needed for compatibility.

**Step 4: Re-run targeted tests**

```bash
pnpm --prefix frontend test -- ReportPage --run
pnpm --prefix frontend typecheck
```

Expected: behavior is unchanged and imports still typecheck.

**Step 5: Commit**

```bash
git add frontend/src/features/reports/components/useReportLifecycle.ts frontend/src/features/reports/components/reportLifecycleReducer.ts frontend/src/features/reports/components/reportLifecycleActions.ts frontend/src/lib/api/client.ts frontend/src/lib/api/authClient.ts frontend/src/lib/api/reportsClient.ts frontend/src/lib/api/adminClient.ts frontend/src/features/reports frontend/src/lib/api
git commit -m "refactor: split report lifecycle state and api clients"
```

---

### Task 7: Refactor Oversized Auth And Report UI Components

**Files:**
- Modify: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/components/AuthModeShell.tsx`
- Create: `frontend/src/features/auth/components/OAuthButtons.tsx`
- Create: `frontend/src/features/auth/components/PasswordAuthForm.tsx`
- Create: `frontend/src/features/auth/components/ResetPasswordForm.tsx`
- Create: `frontend/src/features/auth/components/TurnstilePanel.tsx`
- Modify: `frontend/src/features/reports/components/ReportHeader.tsx`
- Create: `frontend/src/features/reports/components/ReportActionsMenu.tsx`
- Create: `frontend/src/features/reports/components/ReportDecisionHero.tsx`
- Test: `frontend/src/features/auth/__tests__/LoginPage.test.tsx`
- Test: `frontend/src/features/reports/__tests__/ReportHeader.test.tsx`

**Step 1: Write the failing tests**

- Add a login-page test proving each auth mode still renders and submits through the same callbacks after extraction.
- Add a report-header test proving share/export/print actions still work after menu extraction.

Run:

```bash
pnpm --prefix frontend test -- LoginPage --run
pnpm --prefix frontend test -- ReportHeader --run
```

Expected: new extraction-safety cases fail until the components exist.

**Step 2: Extract auth page subcomponents**

- Move Turnstile rendering into its own file.
- Move provider buttons into a dedicated component.
- Move password login/register and reset form markup into separate components.
- Keep route behavior and copy unchanged.

**Step 3: Extract report header subcomponents**

- Move dropdown/action logic into `ReportActionsMenu.tsx`.
- Move decision summary hero layout into `ReportDecisionHero.tsx`.
- Keep keyboard accessibility behavior unchanged.

**Step 4: Re-run targeted tests**

```bash
pnpm --prefix frontend test -- LoginPage --run
pnpm --prefix frontend test -- ReportHeader --run
pnpm --prefix frontend typecheck
```

Expected: extracted components preserve behavior.

**Step 5: Commit**

```bash
git add frontend/src/features/auth/LoginPage.tsx frontend/src/features/auth/components frontend/src/features/reports/components/ReportHeader.tsx frontend/src/features/reports/components/ReportActionsMenu.tsx frontend/src/features/reports/components/ReportDecisionHero.tsx frontend/src/features/auth/__tests__/LoginPage.test.tsx frontend/src/features/reports/__tests__/ReportHeader.test.tsx
git commit -m "refactor: split oversized auth and report header components"
```

---

### Task 8: Reduce Report-Page Performance Overhead

**Files:**
- Modify: `frontend/src/features/reports/components/ReportContentPane.tsx`
- Modify: `frontend/src/features/reports/components/LandscapeChart.tsx`
- Modify: `frontend/src/features/reports/components/VirtualizedCompetitorList.tsx`
- Modify: `frontend/src/features/reports/components/ReportCompetitorSection.tsx`
- Test: `frontend/src/features/reports/__tests__/LandscapeChart.test.tsx`
- Test: `frontend/src/features/reports/__tests__/VirtualizedCompetitorList.test.tsx`

**Step 1: Write the failing tests**

- Add a chart-loading test proving `LandscapeChart` is not mounted until the chart region is actually needed.
- Add a virtualization test proving list mode can render with a simpler fixed-row path.

Run:

```bash
pnpm --prefix frontend test -- LandscapeChart --run
pnpm --prefix frontend test -- VirtualizedCompetitorList --run
```

Expected: new deferred-mount / fixed-row tests fail.

**Step 2: Implement the smallest safe perf wins**

- Gate chart mount behind viewport intent or explicit section visibility.
- Keep the current lazy import in `ReportContentPane`.
- Simplify list-mode virtualization to use fixed row heights where possible.
- Keep grid-mode measuring only if still necessary.

**Step 3: Re-run targeted tests and build**

```bash
pnpm --prefix frontend test -- LandscapeChart --run
pnpm --prefix frontend test -- VirtualizedCompetitorList --run
pnpm --prefix frontend build
```

Expected: tests pass and the build still succeeds.

**Step 4: Commit**

```bash
git add frontend/src/features/reports/components/ReportContentPane.tsx frontend/src/features/reports/components/LandscapeChart.tsx frontend/src/features/reports/components/VirtualizedCompetitorList.tsx frontend/src/features/reports/components/ReportCompetitorSection.tsx frontend/src/features/reports/__tests__/LandscapeChart.test.tsx frontend/src/features/reports/__tests__/VirtualizedCompetitorList.test.tsx
git commit -m "perf: defer report chart work and simplify virtualization"
```

---

### Task 9: Close Docs And Config Hygiene Gaps

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DEPLOYMENT.md`
- Modify: `frontend/README.md`
- Create or modify: `.cursorrules` if the team still expects it

**Step 1: Write the failing docs checklist**

- Create a small manual checklist in the PR description or local notes:
  - admin quota contract documented
  - degraded-state behavior documented
  - CSRF expectations documented
  - `.cursorrules` decision documented

Expected: at least one item is currently missing.

**Step 2: Align the docs**

- Document the admin quota contract and required migrations.
- Document degraded-state semantics so operators know that `503` means dependency failure, not empty business data.
- Document stricter mutating-request CSRF requirements.

**Step 3: Resolve `.cursorrules`**

- If the repo still relies on it, add a minimal version that points to `AGENTS.md` and `ai_docs`.
- If the team intentionally deprecated it, add that decision to `README.md` or `CLAUDE.md` so the absence is not accidental.

**Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md README.md README_CN.md DEPLOYMENT.md frontend/README.md .cursorrules
git commit -m "docs: align health remediation guidance and repo config"
```

---

### Task 10: Final Verification

**Files:**
- Verify only

**Step 1: Run backend verification**

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

**Step 2: Run frontend verification**

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

**Step 3: Review contract alignment**

- Confirm report payload order remains:
  - recommendation / why-now
  - pain signals
  - commercial signals
  - whitespace opportunities
  - competitors
  - evidence
  - confidence
- Confirm `pipeline/merger.py` remains deterministic dedupe only.
- Confirm whitespace synthesis still lives in `pipeline/aggregator.py`.

**Step 4: Summarize residual risk**

- List any deferred refactors not completed in this batch.
- Call out any migrations that require production rollout sequencing.
