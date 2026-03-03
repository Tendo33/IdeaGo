# IdeaGo

![IdeaGo Banner](docs/assets/banner.png)

AI-powered competitor research engine for startup ideas. Input a natural language description of your idea, get a structured report with real competitors, market analysis, and differentiation opportunities — all backed by actual data from GitHub, web search, Hacker News, and App Store search.

## Features

- **Intent Parsing** — LLM extracts keywords, app type, and generates platform-specific search queries
- **Multi-Source Search** — Concurrent search across GitHub, Tavily (web), Hacker News, and App Store
- **LLM Fault Tolerance** — Error-classified retries, endpoint failover, and JSON-parse retry recovery
- **LangGraph Pipeline** — State-graph orchestration for intent parsing, source fetch, extraction map, and aggregation reduce
- **Real-Time Progress** — SSE streaming shows each pipeline stage as it happens
- **Source Links** — Every competitor entry includes real, verifiable source URLs
- **Report Transparency** — Every report includes confidence, evidence summary, cost breakdown, and fault-tolerance metadata
- **Markdown Export** — Download reports for sharing
- **Local Cache** — Results cached for 24h to save API calls
- **Checkpoint Resume** — SQLite checkpoints allow same `report_id` thread to resume after interruption
- **Plugin Architecture** — Add new data sources by implementing one interface

## Quick Start (Local Development)

### 1. Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Node.js 18+ and npm

### 2. Install dependencies

```bash
# Backend
uv sync --all-extras

# Frontend
cd frontend && npm install && cd ..
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API keys:
# - OPENAI_API_KEY (required)
# - TAVILY_API_KEY (required)
# - APPSTORE_COUNTRY (optional, default: us)
# - GITHUB_TOKEN (optional, improves rate limits)
# - OPENAI_BASE_URL (optional, for OpenAI-compatible providers)
# - OPENAI_FALLBACK_ENDPOINTS (optional JSON array for failover endpoints)
# - LANGGRAPH_MAX_RETRIES (optional, retryable HTTP/network retries)
# - LANGGRAPH_JSON_PARSE_MAX_RETRIES (optional, invalid JSON recovery retries)
```

### 4. Build frontend

```bash
cd frontend && npm run build && cd ..
```

### 5. Run

```bash
uv run python -m ideago
```

Open http://localhost:8000 in your browser.

### Development Mode (with hot reload)

Terminal 1 — Backend:
```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

Terminal 2 — Frontend:
```bash
cd frontend && npm run dev
```

Frontend dev server at http://localhost:5173 proxies API calls to the backend.

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env with your API keys

docker compose up -d
```

Open http://localhost:8000.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyze` | Start research pipeline |
| `GET` | `/api/v1/reports/{id}/stream` | SSE progress events |
| `GET` | `/api/v1/reports/{id}` | Get completed report |
| `GET` | `/api/v1/reports/{id}/export` | Download as Markdown |
| `GET` | `/api/v1/reports` | List all cached reports |
| `DELETE` | `/api/v1/reports/{id}` | Delete a report |
| `GET` | `/api/v1/health` | Health check |

## Operational Semantics

- `GET /api/v1/health` returns `status: "ok" | "degraded"`.
- SSE `error` events now return a stable `error_code` field (for example `PIPELINE_FAILURE`) and avoid exposing internal exception text.
- CORS is configurable via `CORS_ALLOW_ORIGINS` (comma-separated). Default remains `*` for self-hosted local usage.
- `cost_breakdown.llm_calls` is the total number of real LLM attempts (includes retries and endpoint failovers), not just logical node calls.
- `confidence.freshness_hint` is generated dynamically (for example: `Generated just now`, `Generated 3m ago`, `Generated on 2026-03-01`).

## Report Transparency Fields

`GET /api/v1/reports/{id}` returns `ResearchReport` with the following observability blocks:

- `confidence`: sample size, source coverage/success rate, freshness hint, overall score (`0-100`)
- `evidence_summary`: top evidence lines and linkable evidence items (`title/url/platform/snippet`)
- `cost_breakdown`: LLM attempts/retries/failovers, source call count, pipeline latency, token usage
- `report_meta.llm_fault_tolerance`: `fallback_used`, ordered `endpoints_tried`, and `last_error_class`

## Runtime Data

- Report cache directory is configured by `CACHE_DIR` (default `.cache/ideago`).
- LangGraph checkpoints are stored at `LANGGRAPH_CHECKPOINT_DB_PATH` (default `.cache/ideago/langgraph-checkpoints.db`).
- Per-source internal query parallelism is controlled by `SOURCE_QUERY_CONCURRENCY` (default `2`) to balance throughput and machine load.
- App Store market scope is controlled by `APPSTORE_COUNTRY` (default `us`).
- LLM fault-tolerance knobs:
  - `OPENAI_FALLBACK_ENDPOINTS` for alternate OpenAI-compatible endpoints
  - `LANGGRAPH_MAX_RETRIES` for retryable API/network failures
  - `LANGGRAPH_JSON_PARSE_MAX_RETRIES` for invalid-JSON recovery loops
- To reset checkpoints only, remove the checkpoint DB file without deleting report cache JSON files.

## Architecture

```
User Input
  -> LangGraph StateGraph
  -> IntentParser (LLM)
  -> Concurrent Source Search
  -> Concurrent Extraction (LLM Map)
  -> Aggregation (LLM Reduce)
  -> Cache Persist + SSE Terminal Event
```

## Execution Flow (End-to-End)

This section documents the actual runtime flow from the first API call to final report rendering.

### 1) Analysis kickoff (`POST /api/v1/analyze`)

1. Client sends idea text to `POST /api/v1/analyze`.
2. Backend normalizes and hashes the query for de-duplication.
3. If the same normalized query is already processing, backend returns the existing `report_id` (no duplicate pipeline run).
4. Otherwise backend:
   - Creates in-memory runtime state for this `report_id`
   - Starts a background task (`_run_pipeline`)
   - Returns `report_id` immediately

### 2) Runtime status + SSE channel

1. Background task writes a lightweight status file as `processing`.
2. Frontend opens `GET /api/v1/reports/{id}/stream` (SSE).
3. SSE behavior:
   - Replays historical events for reconnect clients
   - Streams live pipeline events
   - Sends ping heartbeats on long idle periods
   - Stops on terminal events: `report_ready`, `error`, `cancelled`
4. If no active run state exists, stream endpoint falls back to status-file-derived terminal event.

### 3) LangGraph pipeline execution (backend core)

Pipeline graph order:

1. `parse_intent`
   - LLM parses keywords, app type, scenario, and per-platform queries.
2. `cache_lookup`
   - Uses deterministic `intent.cache_key`.
   - Cache hit: emits `report_ready` from cache and exits early.
   - Cache miss: continue.
3. `fetch_sources` (concurrent)
   - Runs all available source plugins in parallel:
     - `github`
     - `tavily`
     - `hackernews`
     - `appstore` (iTunes Search API, `APPSTORE_COUNTRY` scoped)
   - Emits `source_started` / `source_completed` / `source_failed`.
   - Source timeout and failures are isolated per source (partial progress is preserved).
4. `extract_map` (concurrent per source)
   - LLM extraction converts `RawResult` into structured competitors.
   - If extraction fails for a source, pipeline degrades to raw-to-competitor fallback entries (status becomes `degraded`) instead of aborting the full run.
5. `aggregate`
   - LLM deduplicates and merges cross-source competitors.
   - Generates market summary, recommendation type, recommendation text, and differentiation angles.
   - On aggregation failure, pipeline falls back to unprocessed competitors.
6. `assemble_report`
   - Builds final `ResearchReport` including:
     - `source_results`
     - `confidence`
     - `evidence_summary`
     - `cost_breakdown`
     - `report_meta.llm_fault_tolerance`
7. `persist_report`
   - Writes report JSON to cache + updates index.
   - Emits terminal `report_ready`.

### 4) Failure / cancellation semantics

1. Any unhandled pipeline exception:
   - Writes status as `failed`
   - Emits terminal `error` with stable `error_code` (for example `PIPELINE_FAILURE`)
   - Avoids leaking internal stack details to clients
2. `DELETE /api/v1/reports/{id}/cancel`:
   - Cancels running task if active
   - Writes `cancelled` status
   - Emits terminal `cancelled`

### 5) Frontend lifecycle behavior

1. Report page first calls report fetch API:
   - If report exists: render directly (`ready`)
   - If processing: enter live-progress mode and attach SSE
   - If missing: query runtime status endpoint to distinguish `processing` / `failed` / `cancelled` / `not_found`
2. While processing:
   - Horizontal stepper updates from SSE event stream
   - Source preview cards aggregate per-source result counts
3. On terminal SSE:
   - `report_ready`: refetch full report JSON and render
   - `error` / `cancelled`: show runtime error state + retry actions
4. SSE auto-reconnect:
   - Exponential backoff
   - Event de-duplication by `(type, stage, timestamp)`
   - Max reconnect attempts with user-visible connection error

### 6) Cache and persistence model

1. Report cache:
   - One JSON file per report: `{report_id}.json`
   - Central index file: `_index.json`
   - TTL-based expiration (`CACHE_TTL_HOURS`)
2. Runtime status cache:
   - One status file per run: `{report_id}.status.json`
   - States: `processing | complete | failed | cancelled`
3. LangGraph checkpoint store:
   - SQLite DB (`LANGGRAPH_CHECKPOINT_DB_PATH`)
   - Enables resume for the same `report_id` thread if interrupted

See [docs/plans/2026-02-22-ideago-mvp-design.md](docs/plans/2026-02-22-ideago-mvp-design.md) for full architecture documentation.

## Quality Checks

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

## Tech Stack

- **Backend:** Python 3.10+ / FastAPI / LangGraph / LangChain OpenAI / httpx / Tavily SDK / Pydantic v2 / loguru
- **Frontend:** React 18 / TypeScript / Vite / Tailwind CSS v4 / Lucide Icons
- **Design System:** Generated via ui-ux-pro-max (Space Grotesk + DM Sans, dark theme)

## License

MIT
