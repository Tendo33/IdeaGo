# HTTP API

The `main` branch has a real anonymous FastAPI API.

## Route Families

- `POST /api/v1/analyze`: start a report pipeline.
- `GET /api/v1/analyze/{report_id}/events`: stream pipeline events over SSE.
- `POST /api/v1/reports/{report_id}/cancel`: cancel a processing report.
- `GET /api/v1/reports`: list local anonymous report history.
- `GET /api/v1/reports/{report_id}`: return report detail or processing status.
- `GET /api/v1/reports/{report_id}/status`: runtime status.
- report export endpoints: anonymous markdown export.
- `health`: deployment health.

## Rules

- Keep handlers thin.
- Validate input at the HTTP boundary.
- Return structured `AppError(status, ErrorCode, message)` for public failures.
- Mutating routes require `X-Requested-With`.
- Preserve stable anonymous `X-Session-Id` behavior for report reads, status,
  export, and streaming calls.
- Do not return tracebacks, internal config, or raw upstream provider payloads in
  public responses.
- Keep API routes separate from static frontend fallback rules.

## Frontend-Consumed Contract

For every frontend-consumed endpoint, document or preserve:

- HTTP method and path
- request body or query params
- success response
- error response
- anonymous session/rate-limit assumptions
- whether SSE, polling, or cache invalidation is involved

## Verification

Add or update tests for valid requests, invalid requests, rate-limit/session
behavior, expected error responses, and frontend/static routing interactions
when touched.
