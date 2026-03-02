# IdeaGo

AI-powered competitor research engine for startup ideas. Input a natural language description of your idea, get a structured report with real competitors, market analysis, and differentiation opportunities — all backed by actual data from GitHub, web search, and Hacker News.

## Features

- **Intent Parsing** — LLM extracts keywords, app type, and generates platform-specific search queries
- **Multi-Source Search** — Concurrent search across GitHub, Tavily (web), and Hacker News
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
