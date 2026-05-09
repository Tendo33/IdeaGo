# Hosted Operations Runbook

Use this when touching auth, reports, billing, hosted persistence, or production
deployment behavior on `saas`.

## Stripe Webhook Troubleshooting

Symptoms:

- Stripe dashboard shows repeated delivery failures.
- `POST /api/v1/billing/webhook` returns `404`, `400`, or `503`.
- Billing state does not update after customer or subscription events.

Checks:

1. Confirm `/api/v1/billing/webhook` is mounted in the running app.
2. Confirm the route is exempt from CSRF checks.
3. Verify Stripe secret key and webhook signing secret are configured.
4. Check logs for `BILLING_INVALID_SIGNATURE`, webhook construction errors, or
   event-claim failures.
5. Inspect processed webhook event storage before replaying deliveries.

## `analysis_status_persist_failed`

Symptoms:

- `POST /api/v1/analyze` returns `503 DEPENDENCY_UNAVAILABLE`.
- Users do not receive a `report_id`.
- Metrics or logs include `analysis_status_persist_failed`.

Checks:

1. Verify Supabase report-status writes from the current backend environment.
2. Confirm hosted credentials point at the intended Supabase project.
3. Determine whether failures happen for initial `processing` writes or terminal
   status updates.
4. Inspect quota state and processing reservations to confirm rollback happened.

If the initial `processing` write failed, do not fabricate a report entry
manually. Retry after persistence is healthy.

## Account Deletion Cleanup States

- `rolled_back`: delete failed early and `deletion_pending` was cleared.
- `restored_access_only`: access markers were restored but downstream cleanup
  may already have removed data.
- `deletion_pending`: cleanup reached a later phase and intentionally kept the
  account marked for deletion.
- `rollback_failed`: compensation also failed; inspect and repair profile flags
  manually.

Do not treat every cleanup failure as a full rollback.

## Smoke Checks After Hosted Deploys

1. `GET /api/v1/health`
2. `GET /api/v1/auth/me` with a known-good cookie-backed session
3. `POST /api/v1/analyze` in a hosted environment with healthy persistence
4. `POST /api/v1/billing/webhook` using a signed test event
5. `DELETE /api/v1/auth/account` in staging with a disposable account
