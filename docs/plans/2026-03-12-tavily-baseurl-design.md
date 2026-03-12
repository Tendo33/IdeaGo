# Tavily Base URL Design

## Goal
Add a configurable `TAVILY_BASE_URL` that allows the Tavily client to target a
non-official endpoint while preserving the official default when unset.

## Scope
- Add a new settings field: `tavily_base_url`.
- Wire the value into `TavilySource` and the Tavily SDK client.
- Update `.env.example` to document the new variable.

Out of scope:
- Replacing the Tavily SDK with a custom HTTP client.
- Changing existing search behavior or result parsing.

## Architecture
Configuration remains centralized in `Settings`. The base URL is injected into
`TavilySource` via `dependencies.get_orchestrator()`. `TavilySource` passes the
value to `AsyncTavilyClient` only when provided, otherwise SDK defaults apply.

## Data Flow
`TAVILY_BASE_URL` -> `Settings.tavily_base_url` -> `dependencies.TavilySource`
-> `AsyncTavilyClient(base_url=...)` (only if non-empty).

## Error Handling
No new error types. Existing timeout and `SourceSearchError` behavior remains
unchanged. Invalid or unreachable endpoints will surface through existing
exceptions and logs.

## Testing
- Baseline behavior with empty `TAVILY_BASE_URL` should remain unchanged.
- When `TAVILY_BASE_URL` is set, verify `AsyncTavilyClient` receives it (unit
  test or targeted smoke check).

## Backward Compatibility
Default behavior is preserved because the base URL is optional and only applied
when configured.
