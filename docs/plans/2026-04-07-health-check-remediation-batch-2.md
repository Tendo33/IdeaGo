# Health Check Remediation Batch 2 Implementation Plan

**Goal:** Continue closing high-impact UX and resiliency gaps from the health check with small, verifiable changes.

**Architecture:** This batch keeps the current FastAPI + React contract intact. It focuses on report-readiness recovery when SSE fails and on clearer user actions during long-running analysis recovery paths.

**Tech Stack:** Python 3.10+, FastAPI, pytest, React 19, TypeScript, React Router 7, Vitest, Testing Library

---

### Task 1: Expose deterministic recovery actions after SSE reconnect exhaustion

**Files:**
- Modify: `frontend/src/lib/api/useSSE.ts`
- Modify: `frontend/src/features/reports/components/useReportLifecycle.ts`
- Modify: `frontend/src/features/reports/ReportPage.tsx`
- Modify: `frontend/src/features/reports/components/ReportErrorBanner.tsx`
- Modify: `frontend/src/lib/i18n/locales/en/translation.json`
- Modify: `frontend/src/lib/i18n/locales/zh/translation.json`
- Test: `frontend/src/features/reports/__tests__/ReportPage.test.tsx`
- Test: `frontend/src/features/reports/components/__tests__/useReportLifecycle.test.tsx`

**Step 1: Write failing tests**

- Add a page-level test proving a terminal SSE error on a processing report shows explicit actions for `Retry stream` and `Check status`.
- Add a lifecycle test proving manual `Check status` can recover into the ready report state without forcing a restart.

**Step 2: Implement minimal recovery contract**

- Surface stream diagnostics already available from `useSSE` to the report lifecycle.
- Add a dedicated `checkCurrentStatus()` path that fetches report/status once and updates lifecycle state without restarting analysis.
- Allow the error banner to render multiple explicit actions instead of a single ambiguous retry button.

**Step 3: Verify**

```bash
pnpm --prefix frontend test -- ReportPage useReportLifecycle --run
pnpm --prefix frontend typecheck
pnpm --prefix frontend build
```

**Acceptance criteria:**
- Stream failure no longer leaves users with a vague single retry path.
- Users can explicitly retry the stream, check persisted status, or restart analysis when recoverable.

### Task 2: Capture any remaining high-signal recovery gaps from the report flow

**Files:**
- Re-evaluate after Task 1

**Step 1: Reassess**

- Run the targeted report-flow tests and inspect remaining rough edges in the report lifecycle.
- Pick the next smallest fix with clear user value.

**Step 2: Implement and verify**

- Keep changes batch-sized and fully verified before moving on.
