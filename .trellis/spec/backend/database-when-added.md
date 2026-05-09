# Persistence And Hosted Data

The `saas` branch uses both local file cache behavior and Supabase-backed
hosted persistence.

## Current Persistence Boundaries

- `ReportRepository` in `src/ideago/cache/base.py` is the storage contract for
  report CRUD, owner lookup, list/search, status writes, and cleanup.
- File cache supports local/dev behavior.
- Supabase-backed implementations own hosted report persistence and runtime
  status.
- `supabase/migrations/` stores hosted schema/RPC changes.
- Rate limiting can use hosted PostgREST/RPC state when configured.
- Auth/session/profile/quota helpers live under `src/ideago/auth/`.
- Stripe webhook idempotency uses processed-event storage.

## Rules

- Handlers should not know storage details.
- Service/helper code may coordinate business flow, but persistence details
  stay behind repository or Supabase helper boundaries.
- Initial `processing` status persistence for `POST /api/v1/analyze` is a
  critical write; if it fails, the request must fail and quota/reservation
  should be rolled back.
- Terminal report status writes should stay observable even when persistence is
  degraded.
- Account deletion cleanup states are phase-aware; do not collapse every
  failure into one generic rollback.
- Do not log connection strings, credentials, auth tokens, service-role keys, or
  raw sensitive records.

## Migrations

- Add migrations under `supabase/migrations/`.
- Update tests and docs when schema, RPC, quota, admin, billing, or report
  persistence behavior changes.
- Preserve tenant isolation and fail-closed report ownership semantics.

## Verification

Add integration-style tests when behavior depends on real schema constraints,
RPC shape, transactions, owner isolation, or hosted dependency failure handling.
