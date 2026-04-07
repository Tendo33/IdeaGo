# Dead Code Cleanup Batch 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove a first batch of low-risk dead code from the `saas` branch without changing business logic, UI behavior, or frontend/backend contracts.

**Architecture:** Limit this pass to structural cleanups that are proven unused by static analysis or direct reference checks. Do not delete API routes, response fields, auth flows, or hidden billing/plans plumbing unless a separate contract review confirms they are unused.

**Tech Stack:** Python 3.10+, FastAPI, React 19, TypeScript, Vite 7, pnpm, uv, Ruff, Vitest

---

### Task 1: Capture Safe Cleanup Scope

**Files:**
- Modify: `frontend/src/components/ui/Skeleton.tsx`
- Modify: `frontend/src/features/history/HistoryPage.tsx`
- Modify: `frontend/src/features/history/historyCache.ts`
- Modify: `frontend/src/lib/telemetry/clientMetrics.ts`
- Modify: `frontend/src/lib/utils/dateLocale.ts`
- Modify: `src/ideago/api/app.py`
- Modify: `src/ideago/notifications/service.py`

**Step 1: Remove unused frontend exports and props**

- Delete the unused `ReportCardSkeleton` export from `frontend/src/components/ui/Skeleton.tsx`.
- Remove the dead `onNavigate` prop and dead `handleNavigate` callback from `frontend/src/features/history/HistoryPage.tsx`.
- Collapse file-local constants/types that are not referenced outside their defining modules back to internal symbols.

**Step 2: Remove backend comment residue and dead parameter usage**

- Delete commented-out billing import/router residue from `src/ideago/api/app.py`.
- Make `LogNotificationSender.send()` consume `body_text` and `body_html` in structured logging so its declared keyword-only parameters are not dead.
- Keep notification method signatures intact to avoid keyword-argument contract drift.

**Step 3: Verify no logic or contract changes**

Run:

```bash
uv run python scripts/run_vulture.py --min-confidence 80
uv run ruff check src tests scripts
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
```

Expected:
- No new lint/type/test failures introduced by this cleanup batch.
- Vulture no longer reports dead variables from the log-only notification sender implementation.

**Step 4: Record follow-up risks**

- Do not delete hidden pricing/billing code in this batch.
- Do not delete backend route contracts or report payload fields without confirming frontend/runtime usage.
- Summarize high-risk candidates separately for manual review.
