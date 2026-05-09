# HTTP API

The `saas` branch has a real FastAPI API.

## Route Families

- `POST /api/v1/analyze`: start a report pipeline after auth, quota, and
  processing reservation checks.
- `GET /api/v1/analyze/{report_id}/events`: stream pipeline events over SSE.
- `POST /api/v1/reports/{report_id}/cancel`: cancel a processing report. The
  cancelled terminal status must preserve the report query and owner id even
  when the route handler and background pipeline task both observe cancellation.
- `GET /api/v1/reports`: list authenticated user's reports.
- `GET /api/v1/reports/{report_id}`: return report detail or `202` processing
  status.
- `GET /api/v1/reports/{report_id}/status`: runtime status.
- `DELETE /api/v1/reports/{report_id}` and export endpoints: owner-scoped.
- `auth`: current user, quota/profile/account, Supabase refresh, LinuxDo OAuth.
- `admin`: admin-only user list, quota update, and stats summary.
- `billing`: hidden checkout/portal/status plus active Stripe webhook.
- `health`: deployment health.

## Rules

- Keep handlers thin.
- Validate input at the HTTP boundary.
- Return structured `AppError(status, ErrorCode, message)` for public failures.
- Mutating routes require `X-Requested-With` except Stripe webhook.
- Ownership checks must fail closed.
- Do not return tracebacks, internal config, service-role keys, or raw upstream
  provider payloads in public responses.
- Keep API routes separate from static frontend fallback rules.

## Frontend-Consumed Contract

For every frontend-consumed endpoint, document or preserve:

- HTTP method and path
- request body or query params
- success response
- error response
- auth/session assumptions
- whether SSE, polling, or cache invalidation is involved

## Verification

Add or update tests for valid requests, invalid requests, auth/owner failures,
expected error responses, and frontend/static routing interactions when touched.
