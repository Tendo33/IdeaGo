# IdeaGo MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered competitor research engine that takes a startup idea in natural language, concurrently searches multiple data sources for real competitors, uses LLM to extract structured insights, and displays an interactive report with real-time progress feedback.

**Architecture:** Plugin-based data source layer + LLM Map-Reduce pipeline + SSE progress streaming + FastAPI backend + React frontend. Each data source is a self-contained plugin implementing a common protocol. The pipeline orchestrator coordinates intent parsing, concurrent fetching, concurrent extraction, and aggregation, pushing progress events via SSE.

**Tech Stack:** Python 3.10+ / FastAPI / httpx / OpenAI SDK / Tavily SDK / Pydantic v2 / loguru / React 18 / TypeScript / Vite / Tailwind CSS

---

## Overview: System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │ SearchBox │→│  SSE Progress UI  │→│   Report Dashboard    │  │
│  └──────────┘  └──────────────────┘  └───────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / SSE
┌───────────────────────────▼─────────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌─────────┐  ┌───────────────┐  ┌───────────────────────────┐  │
│  │ /analyze │→│  Orchestrator  │→│  /reports/{id}            │  │
│  │ /stream  │  │  (Pipeline)   │  │  /reports/{id}/export    │  │
│  └─────────┘  └───────┬───────┘  └───────────────────────────┘  │
│                       │                                          │
│          ┌────────────┼────────────┐                             │
│          ▼            ▼            ▼                              │
│  ┌─────────────┐ ┌─────────┐ ┌──────────┐                       │
│  │IntentParser │ │Extractor│ │Aggregator│   ← LLM Layer         │
│  └─────────────┘ └─────────┘ └──────────┘                       │
│          │            │            │                              │
│          ▼            ▼            ▼                              │
│  ┌─────────────────────────────────────┐                         │
│  │         Source Registry             │   ← Data Source Layer   │
│  │  ┌────────┐ ┌───────┐ ┌─────────┐  │                         │
│  │  │ GitHub │ │Tavily │ │   HN    │  │                         │
│  │  └────────┘ └───────┘ └─────────┘  │                         │
│  └─────────────────────────────────────┘                         │
│                       │                                          │
│              ┌────────▼────────┐                                 │
│              │   Cache Layer   │                                 │
│              │  (JSON files)   │                                 │
│              └─────────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Directory Structure (target state)

```
src/ideago/
├── __init__.py                  # existing
├── config/
│   ├── __init__.py              # existing
│   └── settings.py              # extend: add API keys + cache config
├── contracts/
│   ├── __init__.py              # existing
│   └── protocols.py             # extend: add DataSource + LLMClient protocols
├── models/
│   ├── __init__.py              # existing
│   ├── base.py                  # existing (reuse BaseModel, TimestampMixin)
│   ├── examples.py              # existing
│   └── research.py              # NEW: all research domain models
├── core/
│   ├── __init__.py              # existing
│   └── context.py               # existing
├── sources/                     # NEW: data source plugins
│   ├── __init__.py
│   ├── registry.py              # source registration + discovery
│   ├── github_source.py
│   ├── tavily_source.py
│   └── hackernews_source.py
├── llm/                         # NEW: LLM abstraction layer
│   ├── __init__.py
│   ├── client.py                # async OpenAI wrapper
│   └── prompts/                 # external prompt templates
│       ├── intent_parser.txt
│       ├── extractor.txt
│       └── aggregator.txt
├── pipeline/                    # NEW: orchestration engine
│   ├── __init__.py
│   ├── intent_parser.py
│   ├── extractor.py
│   ├── aggregator.py
│   ├── orchestrator.py          # main pipeline coordinator
│   └── events.py                # SSE event types
├── cache/                       # NEW: local file cache
│   ├── __init__.py
│   └── file_cache.py
├── api/                         # NEW: FastAPI application
│   ├── __init__.py
│   ├── app.py                   # FastAPI app factory
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── analyze.py           # POST /analyze, GET /stream
│   │   ├── reports.py           # GET /reports, GET /reports/{id}
│   │   └── health.py            # GET /health
│   └── schemas.py               # request/response Pydantic models
├── observability/               # existing
│   ├── __init__.py
│   └── log_config.py
└── utils/                       # existing
    ├── __init__.py
    ├── common_utils.py
    ├── date_utils.py
    ├── decorator_utils.py
    ├── file_utils.py
    └── json_utils.py

frontend/                        # NEW: React application
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/                     # API client + SSE hook
│   │   ├── client.ts
│   │   └── useSSE.ts
│   ├── pages/
│   │   ├── HomePage.tsx         # search input
│   │   ├── ReportPage.tsx       # report with SSE progress
│   │   └── HistoryPage.tsx      # cached reports list
│   ├── components/
│   │   ├── SearchBox.tsx
│   │   ├── ProgressTracker.tsx  # real-time pipeline progress
│   │   ├── CompetitorCard.tsx
│   │   ├── SourceStatusBar.tsx  # which sources succeeded/failed
│   │   └── ReportSummary.tsx
│   └── types/
│       └── research.ts          # TypeScript types mirroring backend models
└── design-system/               # generated by ui-ux-pro-max --persist
    ├── MASTER.md
    └── pages/
        ├── home.md
        └── report.md

tests/
├── unit/
│   ├── test_models_research.py
│   ├── test_sources_github.py
│   ├── test_sources_tavily.py
│   ├── test_sources_hackernews.py
│   ├── test_llm_client.py
│   ├── test_pipeline_intent.py
│   ├── test_pipeline_extractor.py
│   ├── test_pipeline_aggregator.py
│   └── test_cache.py
└── integration/
    ├── test_pipeline_e2e.py
    └── test_api_routes.py
```

---

## Data Models (Complete Specification)

### Platform Enum

```python
class Platform(str, Enum):
    GITHUB = "github"
    TAVILY = "tavily"
    HACKERNEWS = "hackernews"
    PRODUCT_HUNT = "producthunt"    # reserved for future
    GOOGLE_TRENDS = "google_trends" # reserved for future
```

### RawResult

```python
class RawResult(BaseModel):
    title: str = Field(description="Result title / 结果标题")
    description: str = Field(default="", description="Result description / 结果描述")
    url: str = Field(description="Source URL (mandatory) / 来源链接（必填）")
    platform: Platform = Field(description="Source platform / 来源平台")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw API response preserved for debugging")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Intent

```python
class SearchQuery(BaseModel):
    platform: Platform
    queries: list[str] = Field(min_length=1, description="Platform-specific search queries")

class Intent(BaseModel):
    keywords_en: list[str] = Field(min_length=1, description="English keywords extracted from user input")
    keywords_zh: list[str] = Field(default_factory=list, description="Chinese keywords if applicable")
    app_type: str = Field(description="Application form: web / mobile / browser-extension / cli / api / desktop")
    target_scenario: str = Field(description="One-sentence target scenario description")
    search_queries: list[SearchQuery] = Field(description="Per-platform tailored search queries")
    cache_key: str = Field(default="", description="Normalized cache key derived from sorted keywords + app_type")
```

### Competitor

```python
class Competitor(BaseModel):
    name: str = Field(description="Product/project name")
    links: list[str] = Field(min_length=1, description="At least 1 URL required — no link = not recorded")
    one_liner: str = Field(description="One-sentence positioning")
    features: list[str] = Field(default_factory=list, description="Key features list")
    pricing: Optional[str] = Field(default=None, description="Pricing info if available")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="0-1 relevance score, higher = more relevant")
    source_platforms: list[Platform] = Field(description="Which platforms this competitor was found on")
    source_urls: list[str] = Field(description="Original pages where competitor info was extracted from")
```

### SourceResult

```python
class SourceStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    CACHED = "cached"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"  # LLM extraction failed, showing raw results

class SourceResult(BaseModel):
    platform: Platform
    status: SourceStatus
    raw_count: int = Field(default=0, description="Number of raw results fetched")
    competitors: list[Competitor] = Field(default_factory=list)
    error_msg: Optional[str] = Field(default=None)
    duration_ms: int = Field(default=0, description="Time taken for this source in milliseconds")
```

### ResearchReport

```python
class ResearchReport(TimestampMixin):
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique report ID")
    query: str = Field(description="User's original natural language input")
    intent: Intent
    source_results: list[SourceResult] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list, description="Globally deduplicated competitor list")
    market_summary: str = Field(default="", description="LLM-generated market analysis paragraph")
    go_no_go: str = Field(default="", description="Go/No-Go recommendation with reasoning")
    differentiation_angles: list[str] = Field(default_factory=list, description="Suggested differentiation points")
```

---

## Protocol Definitions (extend existing contracts/protocols.py)

```python
@runtime_checkable
class DataSource(Protocol):
    """Interface that all data source plugins must implement."""

    @property
    def platform(self) -> Platform: ...

    def is_available(self) -> bool:
        """Check if this source has required credentials configured."""
        ...

    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        """Execute search and return raw results."""
        ...

@runtime_checkable
class ProgressCallback(Protocol):
    """Callback interface for pipeline progress events."""

    async def on_event(self, event: "PipelineEvent") -> None: ...
```

---

## SSE Event Types

```python
class EventType(str, Enum):
    INTENT_PARSED = "intent_parsed"
    SOURCE_STARTED = "source_started"
    SOURCE_COMPLETED = "source_completed"
    SOURCE_FAILED = "source_failed"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    AGGREGATION_STARTED = "aggregation_started"
    AGGREGATION_COMPLETED = "aggregation_completed"
    REPORT_READY = "report_ready"
    ERROR = "error"

class PipelineEvent(BaseModel):
    type: EventType
    stage: str
    message: str                     # human-readable, e.g. "Searching GitHub..."
    data: dict[str, Any] = {}        # e.g. {"platform": "github", "count": 8}
    timestamp: datetime
```

Frontend receives these events via SSE and renders a step-by-step progress tracker showing which stage is active, which sources are being searched, and counts.

---

## Pipeline Orchestrator Flow (detailed)

```
Orchestrator.run(query: str, callback: ProgressCallback):

1. CHECK CACHE
   - IntentParser.build_cache_key(query) → tentative cache_key
   - If cache hit (within TTL): emit REPORT_READY, return cached report

2. INTENT PARSING
   - emit INTENT_PARSED event
   - IntentParser.parse(query) → Intent
   - Compute final cache_key = hash(sorted(keywords_en) + app_type)
   - Second cache check with final key (in case different input same intent)

3. CONCURRENT FETCHING
   - For each available source in SourceRegistry:
     - emit SOURCE_STARTED { platform }
     - source.search(intent.search_queries[platform], limit=MAX_RESULTS)
     - On success: emit SOURCE_COMPLETED { platform, count }
     - On failure: emit SOURCE_FAILED { platform, error }
     - Timeout: per-source timeout from config (default 30s)
   - Collect all SourceResult objects (partial OK)

4. CONCURRENT EXTRACTION (Map)
   - For each SourceResult where status == OK:
     - emit EXTRACTION_STARTED { platform }
     - Extractor.extract(raw_results) → list[Competitor]
     - On LLM failure: DEGRADE → convert RawResult to minimal Competitor (name + url only)
     - emit EXTRACTION_COMPLETED { platform, competitor_count }
   - Timeout: per-extraction timeout (default 60s)

5. AGGREGATION (Reduce)
   - emit AGGREGATION_STARTED
   - Aggregator.aggregate(all_competitors) → deduplicated list + summary + go_no_go
   - Deduplication rules:
     a. Same domain in links → must merge
     b. Name similarity > 80% + feature overlap → LLM decides merge
     c. Merged entries keep all links from all sources
   - Sort by relevance_score descending
   - emit AGGREGATION_COMPLETED

6. ASSEMBLE REPORT
   - Build ResearchReport with all data
   - Write to cache
   - emit REPORT_READY { report_id }
```

---

## LLM Prompt Strategy

All prompts stored in `src/ideago/llm/prompts/` as plain text files with `{variable}` placeholders.

### intent_parser.txt
- Input: user's natural language query
- Output: strict JSON matching Intent model schema
- Key instruction: generate **platform-specific** search queries
  - GitHub: `"markdown notes extension" stars:>50`
  - Tavily: `"markdown note-taking browser extension" competitor alternative`
  - HN: `Show HN markdown notes extension`

### extractor.txt
- Input: list of RawResult (title + description + url) from ONE platform
- Output: strict JSON list of Competitor objects
- Key constraints:
  - ONLY extract information present in the provided data
  - NEVER fabricate URLs — every link must come from the input
  - If a result is irrelevant to the query context, skip it
  - Assign relevance_score based on: keyword match strength, feature completeness, popularity signals

### aggregator.txt
- Input: all Competitor objects from all platforms
- Output: deduplicated Competitor list + market_summary + go_no_go + differentiation_angles
- Key constraints:
  - Merge duplicates (same product from different sources) — keep all links
  - Recalculate relevance_score based on cross-platform presence (appearing on 3 sources > 1 source)
  - market_summary: 2-3 paragraphs based on actual data patterns
  - go_no_go: explicit recommendation with reasoning tied to data
  - differentiation_angles: gaps found in existing competitors' weaknesses

---

## Cache Design

```python
# Cache key: normalized from Intent
# Storage: .cache/ideago/{cache_key}.json
# Content: full ResearchReport JSON
# TTL: configurable, default 24 hours
# Index: .cache/ideago/_index.json
#   → list of {report_id, query, cache_key, created_at}
#   → used by /reports history endpoint

class FileCache:
    async def get(self, cache_key: str) -> Optional[ResearchReport]
    async def put(self, cache_key: str, report: ResearchReport) -> None
    async def list_reports(self) -> list[ReportSummary]
    async def delete(self, report_id: str) -> bool
    async def cleanup_expired(self) -> int
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyze` | Start research pipeline. Body: `{"query": "..."}`. Returns `{"report_id": "uuid"}`. If identical query is already processing, returns existing ID. |
| `GET` | `/api/v1/reports/{id}/stream` | SSE endpoint. Streams `PipelineEvent` objects in real-time until `REPORT_READY` or `ERROR`. |
| `GET` | `/api/v1/reports/{id}` | Get completed report JSON. Returns 202 if still processing, 200 when done. |
| `GET` | `/api/v1/reports/{id}/export` | Download report as Markdown file. |
| `GET` | `/api/v1/reports` | List all cached reports (for history page). Returns `[{id, query, created_at, competitor_count}]`. |
| `DELETE` | `/api/v1/reports/{id}` | Delete a cached report. |
| `GET` | `/api/v1/health` | Health check with source availability. Returns `{"status": "ok", "sources": {"github": true, ...}}`. |

---

## Frontend Pages

### / (HomePage)

- Centered search box with placeholder: "Describe your startup idea..."
- Submit button
- Below: recent report cards (from history) for quick re-access
- On submit: POST /analyze → navigate to /reports/{id}

### /reports/{id} (ReportPage)

**Phase 1: SSE Progress View (while pipeline is running)**
- Step-by-step progress tracker (vertical timeline):
  - "Analyzing your idea..." (intent parsing)
  - "Searching GitHub..." with spinner → "Found 8 results" with checkmark
  - "Searching web with Tavily..." → "Found 12 results"
  - "Searching Hacker News..." → "Found 5 results"
  - "Extracting competitor insights..." → "Identified 15 competitors"
  - "Analyzing and deduplicating..." → "6 unique competitors"
  - "Generating report..."
- Animated transitions between stages

**Phase 2: Report View (when pipeline completes)**
- **Header**: user's original query + generation time
- **Go/No-Go Banner**: colored banner (green/yellow/red) with recommendation
- **Source Status Bar**: which sources succeeded/failed/cached
- **Market Summary**: 2-3 paragraph overview
- **Competitor Cards**: sorted by relevance_score
  - Each card: name, one-liner, features (tags), pricing, strengths (green), weaknesses (red), links (clickable)
- **Differentiation Angles**: bullet list of opportunities
- **Export Button**: download as Markdown

### /reports (HistoryPage)

- List of past reports, sorted by date descending
- Each row: query text + date + competitor count + link to full report
- Delete button per report

---

## Configuration (.env)

```env
# Required
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...

# Optional (enhances GitHub rate limit from 10/hr to 5000/hr)
GITHUB_TOKEN=ghp_...

# LLM settings
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=60

# Pipeline settings
MAX_RESULTS_PER_SOURCE=10
SOURCE_TIMEOUT_SECONDS=30
EXTRACTION_TIMEOUT_SECONDS=60

# Cache settings
CACHE_DIR=.cache/ideago
CACHE_TTL_HOURS=24

# Server
HOST=0.0.0.0
PORT=8000
```

---

## New Dependencies

### Backend (add to pyproject.toml)

```toml
dependencies = [
    # existing
    "loguru>=0.7.0",
    "pydantic>=2.10.6",
    "pydantic-settings>=2.0.0",
    "aiofiles>=23.0.0",
    # new
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.0",
    "openai>=1.60.0",
    "tavily-python>=0.5.0",
    "sse-starlette>=2.0.0",
    "jinja2>=3.1.0",
]
```

### Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "react-router-dom": "^7"
  },
  "devDependencies": {
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "vite": "^6",
    "tailwindcss": "^4",
    "@vitejs/plugin-react": "^4"
  }
}
```

---

## Timeouts & Error Handling

| Stage | Timeout | On Failure |
|-------|---------|------------|
| Intent Parsing | 30s | Abort entire pipeline, return error |
| GitHub Search | 30s | Mark source TIMEOUT, continue with other sources |
| Tavily Search | 30s | Mark source TIMEOUT, continue |
| HN Search | 30s | Mark source TIMEOUT, continue |
| LLM Extraction (per source) | 60s | Mark source DEGRADED, show raw results without analysis |
| LLM Aggregation | 60s | Skip aggregation, return un-deduplicated list with warning |
| All sources failed | - | Return error report with "no data could be fetched" message |

---

## Implementation Phases

### Phase 1: Foundation (models + config + protocols)
- Extend `config/settings.py` with new fields
- Create `models/research.py` with all domain models
- Extend `contracts/protocols.py` with DataSource + ProgressCallback
- Tests for all models (validation, serialization)

### Phase 2: Data Sources
- Create `sources/registry.py`
- Implement `GitHubSource` (uses httpx + GitHub Search API)
- Implement `TavilySource` (uses tavily-python SDK)
- Implement `HackerNewsSource` (uses httpx + Algolia HN API)
- Tests with mocked HTTP responses (no real API calls)

### Phase 3: LLM Layer
- Create `llm/client.py` (async OpenAI wrapper with timeout + retry)
- Write prompt templates in `llm/prompts/`
- Implement `IntentParser`
- Implement `Extractor`
- Implement `Aggregator`
- Tests with mocked LLM responses

### Phase 4: Pipeline + Cache
- Create `cache/file_cache.py`
- Create `pipeline/events.py` (SSE event types)
- Create `pipeline/orchestrator.py` (full pipeline coordination)
- Integration tests with mocked sources + LLM

### Phase 5: API Layer
- Create FastAPI app factory in `api/app.py`
- Implement routes: analyze, reports, health
- SSE streaming endpoint
- Request/response schemas
- Integration tests with TestClient

### Phase 6: Frontend
- Run `ui-ux-pro-max --design-system --persist` for design tokens
- Scaffold React + Vite + Tailwind project
- Implement pages: Home, Report (with SSE progress), History
- Build components: SearchBox, ProgressTracker, CompetitorCard, SourceStatusBar

### Phase 7: Integration
- Docker + docker-compose (backend + frontend)
- E2E testing with real APIs (manual)
- README update with setup instructions

---

## Testing Strategy

- **Unit tests**: models, sources (mocked HTTP), LLM layer (mocked OpenAI), cache, pipeline stages
- **Integration tests**: full pipeline with mocked externals, API routes with TestClient
- **No real API calls in CI**: all external dependencies mocked via `pytest-mock` / `respx`
- **Manual E2E**: with real API keys, run full pipeline and verify report quality
- **Coverage target**: 80% (as configured in existing pyproject.toml)
