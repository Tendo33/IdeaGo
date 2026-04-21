# Hosted Operations Runbook

This runbook covers the hosted `saas` branch paths that are easy to break and painful to debug in production.

## Stripe Webhook Troubleshooting

Symptoms:

- Stripe dashboard shows repeated delivery failures
- `POST /api/v1/billing/webhook` returns `404`, `400`, or `503`
- billing state does not update after customer or subscription events

Checks:

1. Confirm `/api/v1/billing/webhook` is mounted in the running app.
2. Confirm the route is still exempt from CSRF checks.
3. Verify Stripe secret key and webhook signing secret are configured for the current environment.
4. Check application logs for `BILLING_INVALID_SIGNATURE`, webhook construction errors, or event-claim failures.
5. Inspect the `processed_webhook_events` store before replaying a delivery to avoid misreading idempotent skips as failures.

Recovery guidance:

- `404`: deployment is likely missing the billing router or is serving the wrong build.
- `400` with invalid signature: verify endpoint secret and raw-body forwarding, then replay from Stripe.
- `503`: inspect hosted dependency health and Supabase availability before replaying queued events.

## `analysis_status_persist_failed`

Symptoms:

- `POST /api/v1/analyze` returns `503 DEPENDENCY_UNAVAILABLE`
- users do not receive a `report_id`
- metrics or logs include `analysis_status_persist_failed`

Checks:

1. Verify Supabase `report_status` writes are succeeding from the current backend environment.
2. Confirm hosted credentials point at the intended Supabase project.
3. Check whether failures happen only for initial `processing` writes or also for terminal status updates.
4. Inspect quota state and processing reservations for the affected user to confirm rollback happened.

Recovery guidance:

- If the initial `processing` write failed, do not manually fabricate a report entry; the request should be retried after persistence is healthy.
- If terminal status writes failed, inspect logs for the `report_id`, verify whether the report body exists, then repair status rows manually if needed.
- Repeated failures usually point to hosted persistence credentials, table permissions, or a broken migration.

## Account Deletion Cleanup States

The hosted delete-account flow now returns phase-aware cleanup states. Do not treat every failure as a full rollback.

### `rolled_back`

Meaning:

- the delete attempt failed early enough that `deletion_pending` was cleared
- the user should be able to continue using the account and retry later

Operator action:

- verify profile flags were cleared
- confirm the user can access profile, quota, and refresh endpoints again

### `restored_access_only`

Meaning:

- access markers were restored, but some downstream cleanup may already have removed data

Operator action:

- tell the user access has been restored but data loss may already have occurred
- inspect reports, billing state, and auth identity before advising a retry

### `deletion_pending`

Meaning:

- deletion reached a later phase and the system intentionally kept the account marked for deletion
- the current session should already be revoked

Operator action:

1. inspect which phase failed
2. verify whether the auth identity, billing data, or profile row still exists
3. complete cleanup manually or restore the account explicitly before letting the user retry

### `rollback_failed`

Meaning:

- the system attempted compensation and could not restore the profile flags cleanly

Operator action:

1. inspect the `profiles` row for `deletion_pending` and `deleted_at`
2. determine whether the account should be restored or fully deleted
3. repair the profile flags manually before asking the user to sign in again

## Recommended Smoke Checks After Hosted Deploys

Run these after deployments that touch auth, reports, billing, or hosted persistence:

1. `GET /api/v1/health`
2. `GET /api/v1/auth/me` with a known-good cookie-backed session
3. `POST /api/v1/analyze` in a hosted environment with healthy persistence
4. `POST /api/v1/billing/webhook` using a signed test event
5. `DELETE /api/v1/auth/account` in staging with a disposable account
