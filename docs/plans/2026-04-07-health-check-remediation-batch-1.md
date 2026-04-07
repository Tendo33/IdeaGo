# Health Check Remediation Batch 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the highest-risk security and UX gaps found in the health check without changing the project contract.

**Architecture:** This batch keeps the existing FastAPI + React structure intact and focuses on hardening existing seams. Backend work tightens session validity and dedup failure handling; frontend work repairs broken flows in history and admin gating with minimal surface-area changes.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, pytest, React 19, TypeScript, React Router 7, Vitest, Testing Library

---

### Task 1: Revoke deleted custom sessions

**Files:**
- Modify: `src/ideago/auth/dependencies.py`
- Modify: `src/ideago/api/routes/auth.py`
- Modify: `src/ideago/auth/supabase_admin.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing tests**

- Add a test proving `refresh_token()` rejects a backend-issued token when the user profile is gone or marked unavailable.
- Add a test proving `get_optional_user()` rejects a backend-issued custom token when profile lookup says the user no longer exists.
- Add a test proving `delete_account()` clears the backend-managed auth cookie on success.

**Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
uv run pytest tests/test_api.py -k "refresh_token or get_optional_user or delete_account"
```

Expected: at least the new cases fail for the current implementation.

**Step 3: Write the minimal implementation**

- Add a small helper that validates a custom-session user is still active before accepting or refreshing the token.
- Call that helper from custom-token auth and refresh flows.
- Clear the auth cookie inside `DELETE /api/v1/auth/account` after successful deletion.

**Step 4: Re-run the targeted backend tests**

Run:

```bash
uv run pytest tests/test_api.py -k "refresh_token or get_optional_user or delete_account"
```

Expected: all targeted tests pass.

### Task 2: Fail closed when distributed dedup store is unavailable

**Files:**
- Modify: `src/ideago/api/dependencies.py`
- Modify: `src/ideago/api/routes/analyze.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing tests**

- Add a test proving `reserve_processing_report()` surfaces an infrastructure error when Supabase dedup is configured but RPC reservation fails.
- Add a route-level test proving `POST /api/v1/analyze` returns a structured 503 instead of silently starting duplicate work in that case.

**Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
uv run pytest tests/test_api.py -k "reserve_processing_report or start_analysis"
```

Expected: new dedup failure cases fail.

**Step 3: Write the minimal implementation**

- Replace the ambiguous `None means both success and error` behavior with an explicit failure signal.
- Keep the in-memory assignment only for true reservation success.
- Map the failure to a structured `AppError`.

**Step 4: Re-run the targeted backend tests**

Run:

```bash
uv run pytest tests/test_api.py -k "reserve_processing_report or start_analysis"
```

Expected: all targeted tests pass.

### Task 3: Keep history search usable when result count is zero

**Files:**
- Modify: `frontend/src/features/history/HistoryPage.tsx`
- Test: `frontend/src/features/history/__tests__/HistoryPage.test.tsx`

**Step 1: Write the failing test**

- Add a test proving the search input remains visible after a query returns zero reports.

**Step 2: Run the targeted frontend test to verify it fails**

Run:

```bash
pnpm --prefix frontend test -- HistoryPage
```

Expected: the new case fails because the input disappears.

**Step 3: Write the minimal implementation**

- Decouple search-input rendering from `reports.length > 0`.
- Keep the input visible whenever the page is loaded or there is an active query.
- Add an accessible label for the input while preserving the existing placeholder.

**Step 4: Re-run the targeted frontend test**

Run:

```bash
pnpm --prefix frontend test -- HistoryPage
```

Expected: targeted history tests pass.

### Task 4: Remove admin-route role hydration flicker

**Files:**
- Modify: `frontend/src/lib/auth/AuthProvider.tsx`
- Modify: `frontend/src/lib/auth/ProtectedRoute.tsx`
- Test: `frontend/src/app/App.test.tsx` or a new focused auth-route test file

**Step 1: Write the failing test**

- Add a test proving an authenticated admin is not shown the forbidden state while role hydration is still in flight.

**Step 2: Run the targeted frontend test to verify it fails**

Run:

```bash
pnpm --prefix frontend test -- App
```

Expected: the new admin hydration case fails against current behavior.

**Step 3: Write the minimal implementation**

- Track role hydration separately from base session loading.
- Keep `AdminRoute` in loading state until role resolution completes for an authenticated user.

**Step 4: Re-run the targeted frontend test**

Run:

```bash
pnpm --prefix frontend test -- App
```

Expected: targeted app/auth tests pass.

### Task 5: Final verification

**Files:**
- Verify only

**Step 1: Run backend verification**

```bash
uv run ruff check src tests scripts
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

**Step 3: Summarize**

- Record which risks were closed.
- Call out any deferred items from the original health check that remain for batch 2.
