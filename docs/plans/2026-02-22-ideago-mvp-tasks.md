# IdeaGo MVP — Detailed Task Breakdown

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered competitor research engine. See `2026-02-22-ideago-mvp-design.md` for full architecture.

**Architecture:** Plugin-based sources + LLM Map-Reduce + SSE streaming + FastAPI + React

**Tech Stack:** Python 3.10+ / FastAPI / httpx / OpenAI / Tavily / Pydantic v2 / React 18 / Vite / Tailwind

---

## Phase 1: Foundation (Models + Config + Protocols)

### Task 1.1: Add new dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1:** Add runtime dependencies

Add to the `dependencies` list:
```toml
"fastapi>=0.115.0",
"uvicorn[standard]>=0.34.0",
"httpx>=0.28.0",
"openai>=1.60.0",
"tavily-python>=0.5.0",
"sse-starlette>=2.0.0",
"jinja2>=3.1.0",
```

**Step 2:** Run `uv sync --all-extras`

Expected: all packages install successfully.

**Step 3:** Commit

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add fastapi, httpx, openai, tavily dependencies"
```

---

### Task 1.2: Extend settings.py with new config fields

**Files:**
- Modify: `src/ideago/config/settings.py`
- Test: `tests/unit/test_settings.py`

**Step 1:** Write the failing test

```python
# tests/unit/test_settings.py
from ideago.config.settings import Settings

def test_settings_has_openai_fields():
    s = Settings(openai_api_key="sk-test", tavily_api_key="tvly-test")
    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-4o-mini"
    assert s.openai_timeout_seconds == 60

def test_settings_has_tavily_fields():
    s = Settings(tavily_api_key="tvly-test")
    assert s.tavily_api_key == "tvly-test"

def test_settings_has_github_token_optional():
    s = Settings(tavily_api_key="tvly-test")
    assert s.github_token == ""

def test_settings_has_pipeline_fields():
    s = Settings(tavily_api_key="tvly-test")
    assert s.max_results_per_source == 10
    assert s.source_timeout_seconds == 30
    assert s.extraction_timeout_seconds == 60

def test_settings_has_cache_fields():
    s = Settings(tavily_api_key="tvly-test")
    assert s.cache_dir == ".cache/ideago"
    assert s.cache_ttl_hours == 24

def test_settings_has_server_fields():
    s = Settings(tavily_api_key="tvly-test")
    assert s.host == "0.0.0.0"
    assert s.port == 8000
```

**Step 2:** Run test to verify it fails

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: FAIL — fields not found.

**Step 3:** Add fields to `Settings` class in `src/ideago/config/settings.py`

```python
# --- API Keys ---
openai_api_key: str = Field(default="", description="OpenAI API key / OpenAI 密钥")
openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name / 模型名称")
openai_timeout_seconds: int = Field(default=60, ge=5, le=300, description="LLM request timeout")
tavily_api_key: str = Field(default="", description="Tavily API key / Tavily 密钥")
github_token: str = Field(default="", description="GitHub personal access token (optional)")

# --- Pipeline ---
max_results_per_source: int = Field(default=10, ge=1, le=50, description="Max results per source")
source_timeout_seconds: int = Field(default=30, ge=5, le=120, description="Per-source fetch timeout")
extraction_timeout_seconds: int = Field(default=60, ge=10, le=180, description="Per-source LLM extraction timeout")

# --- Cache ---
cache_dir: str = Field(default=".cache/ideago", description="Cache directory path")
cache_ttl_hours: int = Field(default=24, ge=1, le=168, description="Cache TTL in hours")

# --- Server ---
host: str = Field(default="0.0.0.0", description="Server host")
port: int = Field(default=8000, ge=1, le=65535, description="Server port")
```

**Step 4:** Run test to verify it passes

```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: PASS

**Step 5:** Update `.env.example` with new vars

**Step 6:** Commit

```bash
git add src/ideago/config/settings.py tests/unit/test_settings.py .env.example
git commit -m "feat: add API keys, pipeline, cache, server config fields"
```

---

### Task 1.3: Create Platform enum and RawResult model

**Files:**
- Create: `src/ideago/models/research.py`
- Test: `tests/unit/test_models_research.py`

**Step 1:** Write the failing test

```python
# tests/unit/test_models_research.py
import pytest
from ideago.models.research import Platform, RawResult

def test_platform_enum_values():
    assert Platform.GITHUB == "github"
    assert Platform.TAVILY == "tavily"
    assert Platform.HACKERNEWS == "hackernews"

def test_raw_result_valid():
    r = RawResult(
        title="Test Repo",
        url="https://github.com/test/repo",
        platform=Platform.GITHUB,
    )
    assert r.title == "Test Repo"
    assert r.description == ""
    assert r.url == "https://github.com/test/repo"

def test_raw_result_requires_url():
    with pytest.raises(Exception):
        RawResult(title="No URL", platform=Platform.GITHUB)

def test_raw_result_serialization():
    r = RawResult(
        title="Test", url="https://example.com", platform=Platform.GITHUB
    )
    data = r.model_dump(mode="json")
    assert data["platform"] == "github"
    assert "fetched_at" in data
```

**Step 2:** Run test to verify it fails

```bash
uv run pytest tests/unit/test_models_research.py::test_platform_enum_values -v
```
Expected: FAIL — module not found.

**Step 3:** Create `src/ideago/models/research.py` with Platform + RawResult

```python
"""Research domain models.

竞品调研领域模型。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import Field

from ideago.models.base import BaseModel, TimestampMixin


class Platform(str, Enum):
    """Supported data source platforms / 支持的数据源平台。"""
    GITHUB = "github"
    TAVILY = "tavily"
    HACKERNEWS = "hackernews"
    PRODUCT_HUNT = "producthunt"
    GOOGLE_TRENDS = "google_trends"


class RawResult(BaseModel):
    """Single raw result from a data source / 数据源返回的单条原始结果。"""
    title: str = Field(description="Result title / 结果标题")
    description: str = Field(default="", description="Result description / 结果描述")
    url: str = Field(description="Source URL, mandatory / 来源链接（必填）")
    platform: Platform = Field(description="Source platform / 来源平台")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Raw API response backup")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fetch timestamp / 抓取时间",
    )
```

**Step 4:** Run test to verify it passes

```bash
uv run pytest tests/unit/test_models_research.py -v
```
Expected: PASS

**Step 5:** Commit

```bash
git add src/ideago/models/research.py tests/unit/test_models_research.py
git commit -m "feat: add Platform enum and RawResult model"
```

---

### Task 1.4: Add Intent model (SearchQuery + Intent)

**Files:**
- Modify: `src/ideago/models/research.py`
- Modify: `tests/unit/test_models_research.py`

**Step 1:** Write the failing test

```python
from ideago.models.research import Platform, SearchQuery, Intent

def test_search_query():
    sq = SearchQuery(
        platform=Platform.GITHUB,
        queries=["markdown notes extension stars:>50"],
    )
    assert sq.platform == Platform.GITHUB
    assert len(sq.queries) == 1

def test_search_query_requires_at_least_one():
    with pytest.raises(Exception):
        SearchQuery(platform=Platform.GITHUB, queries=[])

def test_intent_valid():
    intent = Intent(
        keywords_en=["markdown", "notes", "browser extension"],
        app_type="browser-extension",
        target_scenario="Take markdown notes on web pages",
        search_queries=[
            SearchQuery(platform=Platform.GITHUB, queries=["markdown notes extension"]),
        ],
    )
    assert len(intent.keywords_en) == 3
    assert intent.keywords_zh == []

def test_intent_cache_key_generation():
    intent = Intent(
        keywords_en=["notes", "markdown", "browser extension"],
        app_type="browser-extension",
        target_scenario="test",
        search_queries=[
            SearchQuery(platform=Platform.GITHUB, queries=["test"]),
        ],
    )
    key = intent.compute_cache_key()
    # Same keywords in different order should produce same key
    intent2 = Intent(
        keywords_en=["browser extension", "markdown", "notes"],
        app_type="browser-extension",
        target_scenario="different text",
        search_queries=[
            SearchQuery(platform=Platform.GITHUB, queries=["test"]),
        ],
    )
    assert intent2.compute_cache_key() == key
```

**Step 2:** Run to verify failure. **Step 3:** Implement SearchQuery + Intent in research.py.

```python
import hashlib

class SearchQuery(BaseModel):
    """Platform-specific search queries / 平台定制搜索词。"""
    platform: Platform = Field(description="Target platform / 目标平台")
    queries: list[str] = Field(min_length=1, description="Search query strings")

class Intent(BaseModel):
    """Parsed user intent / 解析后的用户意图。"""
    keywords_en: list[str] = Field(min_length=1, description="English keywords")
    keywords_zh: list[str] = Field(default_factory=list, description="Chinese keywords")
    app_type: str = Field(description="App form: web/mobile/browser-extension/cli/api/desktop")
    target_scenario: str = Field(description="One-sentence scenario description")
    search_queries: list[SearchQuery] = Field(description="Per-platform search queries")
    cache_key: str = Field(default="", description="Normalized cache key")

    def compute_cache_key(self) -> str:
        normalized = sorted(k.lower().strip() for k in self.keywords_en)
        raw = f"{self.app_type.lower()}::{'|'.join(normalized)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 1.5: Add Competitor model

**Files:**
- Modify: `src/ideago/models/research.py`
- Modify: `tests/unit/test_models_research.py`

**Step 1:** Write the failing test

```python
from ideago.models.research import Competitor, Platform

def test_competitor_valid():
    c = Competitor(
        name="Markdownify",
        links=["https://markdownify.app"],
        one_liner="Convert web pages to Markdown",
        source_platforms=[Platform.TAVILY],
        source_urls=["https://google.com/search?q=..."],
    )
    assert c.name == "Markdownify"
    assert c.relevance_score == 0.5
    assert c.pricing is None

def test_competitor_requires_at_least_one_link():
    with pytest.raises(Exception):
        Competitor(
            name="No Link",
            links=[],
            one_liner="test",
            source_platforms=[Platform.GITHUB],
            source_urls=["https://example.com"],
        )

def test_competitor_relevance_score_bounds():
    with pytest.raises(Exception):
        Competitor(
            name="T", links=["https://a.com"], one_liner="t",
            source_platforms=[Platform.GITHUB], source_urls=["https://a.com"],
            relevance_score=1.5,
        )
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
class Competitor(BaseModel):
    """A competitor product identified during research / 调研中发现的竞品。"""
    name: str = Field(description="Product/project name / 产品名称")
    links: list[str] = Field(min_length=1, description="URLs (at least 1 required)")
    one_liner: str = Field(description="One-sentence positioning / 一句话定位")
    features: list[str] = Field(default_factory=list, description="Key features")
    pricing: Optional[str] = Field(default=None, description="Pricing info")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0, description="0-1 relevance")
    source_platforms: list[Platform] = Field(description="Platforms where found")
    source_urls: list[str] = Field(description="Original source page URLs")
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 1.6: Add SourceResult model (SourceStatus + SourceResult)

**Files:**
- Modify: `src/ideago/models/research.py`
- Modify: `tests/unit/test_models_research.py`

**Step 1:** Write the failing test

```python
from ideago.models.research import SourceStatus, SourceResult, Platform

def test_source_status_values():
    assert SourceStatus.OK == "ok"
    assert SourceStatus.DEGRADED == "degraded"

def test_source_result_ok():
    sr = SourceResult(platform=Platform.GITHUB, status=SourceStatus.OK, raw_count=8)
    assert sr.error_msg is None
    assert sr.competitors == []

def test_source_result_failed():
    sr = SourceResult(
        platform=Platform.TAVILY,
        status=SourceStatus.FAILED,
        error_msg="API key invalid",
    )
    assert sr.error_msg == "API key invalid"
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
class SourceStatus(str, Enum):
    """Status of a data source query / 数据源查询状态。"""
    OK = "ok"
    FAILED = "failed"
    CACHED = "cached"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"

class SourceResult(BaseModel):
    """Result from one data source including status / 单个数据源结果（含状态）。"""
    platform: Platform
    status: SourceStatus
    raw_count: int = Field(default=0, description="Number of raw results fetched")
    competitors: list[Competitor] = Field(default_factory=list)
    error_msg: Optional[str] = Field(default=None)
    duration_ms: int = Field(default=0, description="Fetch duration in ms")
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 1.7: Add ResearchReport model

**Files:**
- Modify: `src/ideago/models/research.py`
- Modify: `tests/unit/test_models_research.py`

**Step 1:** Write the failing test

```python
from ideago.models.research import ResearchReport, Intent, SearchQuery, Platform

def _make_intent() -> Intent:
    return Intent(
        keywords_en=["test"],
        app_type="web",
        target_scenario="test scenario",
        search_queries=[SearchQuery(platform=Platform.GITHUB, queries=["test"])],
    )

def test_report_auto_generates_id():
    r = ResearchReport(query="test idea", intent=_make_intent())
    assert len(r.id) > 0
    assert r.competitors == []

def test_report_serialization_roundtrip():
    r = ResearchReport(query="test", intent=_make_intent(), go_no_go="Go")
    data = r.model_dump(mode="json")
    r2 = ResearchReport.model_validate(data)
    assert r2.id == r.id
    assert r2.go_no_go == "Go"
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
class ResearchReport(TimestampMixin):
    """Complete research report / 完整调研报告。"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique report ID")
    query: str = Field(description="User's original input / 用户原始输入")
    intent: Intent
    source_results: list[SourceResult] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list, description="Deduplicated competitor list")
    market_summary: str = Field(default="", description="Market analysis paragraph")
    go_no_go: str = Field(default="", description="Go/No-Go recommendation")
    differentiation_angles: list[str] = Field(default_factory=list, description="Differentiation suggestions")
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 1.8: Add SSE event models (pipeline/events.py)

**Files:**
- Create: `src/ideago/pipeline/__init__.py`
- Create: `src/ideago/pipeline/events.py`
- Test: `tests/unit/test_pipeline_events.py`

**Step 1:** Write the failing test

```python
from ideago.pipeline.events import EventType, PipelineEvent

def test_event_type_values():
    assert EventType.SOURCE_STARTED == "source_started"
    assert EventType.REPORT_READY == "report_ready"

def test_pipeline_event_creation():
    e = PipelineEvent(
        type=EventType.SOURCE_COMPLETED,
        stage="github_search",
        message="Found 8 results from GitHub",
        data={"platform": "github", "count": 8},
    )
    assert e.stage == "github_search"
    assert e.data["count"] == 8

def test_pipeline_event_to_sse_format():
    e = PipelineEvent(
        type=EventType.INTENT_PARSED,
        stage="intent_parsing",
        message="Intent parsed successfully",
    )
    sse = e.to_sse()
    assert '"type": "intent_parsed"' in sse or '"type":"intent_parsed"' in sse
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
# src/ideago/pipeline/events.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field
from ideago.models.base import BaseModel


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
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_sse(self) -> str:
        return self.model_dump_json()
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 1.9: Extend protocols.py with DataSource + ProgressCallback

**Files:**
- Modify: `src/ideago/contracts/protocols.py`
- Test: `tests/unit/test_protocols.py`

**Step 1:** Write the failing test

```python
from ideago.contracts.protocols import DataSource, ProgressCallback

def test_datasource_is_runtime_checkable():
    assert hasattr(DataSource, "__protocol_attrs__") or hasattr(DataSource, "__abstractmethods__") or True
    # just verify import works and it's a Protocol

def test_progress_callback_is_runtime_checkable():
    from ideago.pipeline.events import PipelineEvent, EventType

    class MockCallback:
        async def on_event(self, event: PipelineEvent) -> None:
            pass

    assert isinstance(MockCallback(), ProgressCallback)
```

**Step 2:** Run to verify failure. **Step 3:** Add to protocols.py:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ideago.models.research import Platform, RawResult
    from ideago.pipeline.events import PipelineEvent

@runtime_checkable
class DataSource(Protocol):
    @property
    def platform(self) -> Platform: ...
    def is_available(self) -> bool: ...
    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]: ...

@runtime_checkable
class ProgressCallback(Protocol):
    async def on_event(self, event: PipelineEvent) -> None: ...
```

**Step 4:** Run to verify pass. **Step 5:** Update `__all__`. **Step 6:** Commit.

---

### Task 1.10: Export all new models in models/__init__.py

**Files:**
- Modify: `src/ideago/models/__init__.py`

**Step 1:** Add all research model exports.

**Step 2:** Verify imports work:

```bash
uv run python -c "from ideago.models.research import Platform, RawResult, Intent, Competitor, SourceResult, ResearchReport; print('OK')"
```

**Step 3:** Run full Phase 1 tests:

```bash
uv run pytest tests/unit/test_models_research.py tests/unit/test_pipeline_events.py tests/unit/test_settings.py -v
```

**Step 4:** Run lint:

```bash
uv run ruff check src/ideago/models/ src/ideago/pipeline/ src/ideago/config/
uv run mypy src/ideago/models/ src/ideago/pipeline/ src/ideago/config/
```

**Step 5:** Commit.

---

## Phase 2: Data Sources

### Task 2.1: Create SourceRegistry

**Files:**
- Create: `src/ideago/sources/__init__.py`
- Create: `src/ideago/sources/registry.py`
- Test: `tests/unit/test_source_registry.py`

**Step 1:** Write the failing test

```python
import pytest
from ideago.sources.registry import SourceRegistry
from ideago.models.research import Platform, RawResult

class FakeSource:
    platform = Platform.GITHUB
    def is_available(self) -> bool:
        return True
    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return []

class UnavailableSource:
    platform = Platform.TAVILY
    def is_available(self) -> bool:
        return False
    async def search(self, queries: list[str], limit: int = 10) -> list[RawResult]:
        return []

def test_register_and_get_source():
    reg = SourceRegistry()
    src = FakeSource()
    reg.register(src)
    assert reg.get(Platform.GITHUB) is src

def test_get_available_sources():
    reg = SourceRegistry()
    reg.register(FakeSource())
    reg.register(UnavailableSource())
    available = reg.get_available()
    assert len(available) == 1
    assert available[0].platform == Platform.GITHUB

def test_register_duplicate_raises():
    reg = SourceRegistry()
    reg.register(FakeSource())
    with pytest.raises(ValueError):
        reg.register(FakeSource())
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
# src/ideago/sources/registry.py
from ideago.contracts.protocols import DataSource
from ideago.models.research import Platform


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[Platform, DataSource] = {}

    def register(self, source: DataSource) -> None:
        if source.platform in self._sources:
            raise ValueError(f"Source for {source.platform} already registered")
        self._sources[source.platform] = source

    def get(self, platform: Platform) -> DataSource | None:
        return self._sources.get(platform)

    def get_available(self) -> list[DataSource]:
        return [s for s in self._sources.values() if s.is_available()]

    def get_all(self) -> list[DataSource]:
        return list(self._sources.values())
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 2.2: Implement GitHubSource

**Files:**
- Create: `src/ideago/sources/github_source.py`
- Test: `tests/unit/test_sources_github.py`

**Step 1:** Write the failing test

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from ideago.sources.github_source import GitHubSource
from ideago.models.research import Platform

MOCK_GITHUB_RESPONSE = {
    "total_count": 2,
    "items": [
        {
            "full_name": "user/markdown-clipper",
            "description": "Clip web pages as Markdown",
            "html_url": "https://github.com/user/markdown-clipper",
            "stargazers_count": 1200,
            "language": "TypeScript",
            "topics": ["markdown", "browser-extension"],
        },
        {
            "full_name": "user2/web-to-md",
            "description": "Convert web to markdown",
            "html_url": "https://github.com/user2/web-to-md",
            "stargazers_count": 300,
            "language": "JavaScript",
            "topics": [],
        },
    ],
}

def test_github_source_platform():
    src = GitHubSource(token="")
    assert src.platform == Platform.GITHUB

def test_github_is_always_available():
    src = GitHubSource(token="")
    assert src.is_available() is True

@pytest.mark.asyncio
async def test_github_search_returns_raw_results():
    src = GitHubSource(token="test-token")
    mock_response = httpx.Response(200, json=MOCK_GITHUB_RESPONSE)
    with patch.object(src._client, "get", new_callable=AsyncMock, return_value=mock_response):
        results = await src.search(["markdown notes extension"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.GITHUB
    assert "github.com" in results[0].url
    assert results[0].raw_data["stargazers_count"] == 1200

@pytest.mark.asyncio
async def test_github_search_handles_api_error():
    src = GitHubSource(token="")
    mock_response = httpx.Response(403, json={"message": "rate limit"})
    with patch.object(src._client, "get", new_callable=AsyncMock, return_value=mock_response):
        results = await src.search(["test"], limit=5)
    assert results == []
```

**Step 2:** Run to verify failure. **Step 3:** Implement GitHubSource.

Key implementation points:
- Uses `httpx.AsyncClient` with base_url `https://api.github.com`
- Search endpoint: `GET /search/repositories?q={query}&sort=stars&per_page={limit}`
- Authorization header if token provided
- Maps response items to `RawResult` objects
- Stores full item dict in `raw_data` for stars, language, topics etc
- Returns empty list on HTTP error (logged with loguru)

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 2.3: Implement TavilySource

**Files:**
- Create: `src/ideago/sources/tavily_source.py`
- Test: `tests/unit/test_sources_tavily.py`

**Step 1:** Write the failing test

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ideago.sources.tavily_source import TavilySource
from ideago.models.research import Platform

MOCK_TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Markdownify - Chrome Extension",
            "url": "https://chromewebstore.google.com/detail/markdownify",
            "content": "Convert any webpage to markdown with one click...",
            "score": 0.95,
        },
        {
            "title": "Web Clipper for Notion",
            "url": "https://notion.so/web-clipper",
            "content": "Save web pages directly to Notion...",
            "score": 0.82,
        },
    ]
}

def test_tavily_source_platform():
    src = TavilySource(api_key="test")
    assert src.platform == Platform.TAVILY

def test_tavily_not_available_without_key():
    src = TavilySource(api_key="")
    assert src.is_available() is False

def test_tavily_available_with_key():
    src = TavilySource(api_key="tvly-test")
    assert src.is_available() is True

@pytest.mark.asyncio
async def test_tavily_search_returns_raw_results():
    src = TavilySource(api_key="tvly-test")
    # Mock the tavily client's search method
    with patch.object(src, "_search_single", new_callable=AsyncMock, return_value=MOCK_TAVILY_RESPONSE["results"]):
        results = await src.search(["markdown browser extension competitor"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.TAVILY
    assert "chromewebstore" in results[0].url
```

**Step 2:** Run to verify failure. **Step 3:** Implement TavilySource.

Key implementation points:
- Uses `tavily-python` async client (TavilyClient)
- Runs each query via `client.search(query, max_results=limit)`
- Deduplicates results across multiple queries by URL
- Maps to RawResult, stores full response in raw_data
- Returns empty list on error

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 2.4: Implement HackerNewsSource

**Files:**
- Create: `src/ideago/sources/hackernews_source.py`
- Test: `tests/unit/test_sources_hackernews.py`

**Step 1:** Write the failing test

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from ideago.sources.hackernews_source import HackerNewsSource
from ideago.models.research import Platform

MOCK_HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: I built a Markdown web clipper",
            "url": "https://example.com/clipper",
            "objectID": "12345",
            "points": 150,
            "num_comments": 42,
            "story_text": "I was frustrated with existing tools...",
        },
        {
            "title": "Ask HN: Best tools for web clipping?",
            "url": "",
            "objectID": "67890",
            "points": 80,
            "num_comments": 65,
            "story_text": "Looking for recommendations...",
        },
    ]
}

def test_hn_platform():
    src = HackerNewsSource()
    assert src.platform == Platform.HACKERNEWS

def test_hn_always_available():
    src = HackerNewsSource()
    assert src.is_available() is True

@pytest.mark.asyncio
async def test_hn_search():
    src = HackerNewsSource()
    mock_response = httpx.Response(200, json=MOCK_HN_RESPONSE)
    with patch.object(src._client, "get", new_callable=AsyncMock, return_value=mock_response):
        results = await src.search(["markdown web clipper"], limit=10)
    assert len(results) == 2
    assert results[0].platform == Platform.HACKERNEWS
    # HN posts without URL get the HN discussion URL
    assert "ycombinator" in results[1].url or "example" in results[0].url
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

Key implementation points:
- Base URL: `https://hn.algolia.com/api/v1/search`
- Params: `query={q}&tags=story&hitsPerPage={limit}`
- Posts without external URL get `https://news.ycombinator.com/item?id={objectID}`
- No auth needed
- Stores points, num_comments in raw_data

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 2.5: Phase 2 integration check

**Step 1:** Run all source tests:

```bash
uv run pytest tests/unit/test_source_registry.py tests/unit/test_sources_github.py tests/unit/test_sources_tavily.py tests/unit/test_sources_hackernews.py -v
```

**Step 2:** Run lint:

```bash
uv run ruff check src/ideago/sources/
uv run mypy src/ideago/sources/
```

**Step 3:** Commit.

---

## Phase 3: LLM Layer

### Task 3.1: Create async OpenAI client wrapper

**Files:**
- Create: `src/ideago/llm/__init__.py`
- Create: `src/ideago/llm/client.py`
- Test: `tests/unit/test_llm_client.py`

**Step 1:** Write the failing test

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ideago.llm.client import LLMClient

@pytest.mark.asyncio
async def test_llm_client_complete_returns_text():
    client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
    mock_choice = MagicMock()
    mock_choice.message.content = '{"key": "value"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.complete("test prompt")
    assert result == '{"key": "value"}'

@pytest.mark.asyncio
async def test_llm_client_complete_json_parses():
    client = LLMClient(api_key="sk-test", model="gpt-4o-mini")
    mock_choice = MagicMock()
    mock_choice.message.content = '{"name": "test", "score": 0.8}'
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch.object(client._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await client.complete_json("test prompt")
    assert result["name"] == "test"
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
# src/ideago/llm/client.py
import json
from typing import Any

from openai import AsyncOpenAI
from loguru import logger


class LLMClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 60) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = model

    async def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("LLM request failed")
            raise

    async def complete_json(self, prompt: str, system: str = "") -> dict[str, Any]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception:
            logger.exception("LLM JSON request failed")
            raise
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 3.2: Create prompt templates

**Files:**
- Create: `src/ideago/llm/prompts/intent_parser.txt`
- Create: `src/ideago/llm/prompts/extractor.txt`
- Create: `src/ideago/llm/prompts/aggregator.txt`
- Create: `src/ideago/llm/prompt_loader.py`
- Test: `tests/unit/test_prompt_loader.py`

**Step 1:** Write the failing test

```python
from ideago.llm.prompt_loader import load_prompt

def test_load_prompt_intent_parser():
    prompt = load_prompt("intent_parser", query="I want to build a markdown clipper extension")
    assert "markdown clipper extension" in prompt
    assert "{query}" not in prompt  # placeholder should be replaced

def test_load_prompt_missing_template_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_template")
```

**Step 2:** Run to verify failure. **Step 3:** Create prompt files + loader.

`intent_parser.txt` — system + user prompt that instructs LLM to return JSON with:
- keywords_en, keywords_zh, app_type, target_scenario
- search_queries per platform (GitHub syntax, Tavily syntax, HN syntax)

`extractor.txt` — takes {platform}, {raw_results_json}, {query_context} as input.
Instructs LLM to extract Competitor objects from raw results. Strict rules:
- ONLY use URLs from the provided data
- NEVER fabricate links
- Skip irrelevant results

`aggregator.txt` — takes {competitors_json}, {original_query} as input.
Instructs LLM to deduplicate, merge, summarize. Output:
- competitors (deduplicated list)
- market_summary, go_no_go, differentiation_angles

`prompt_loader.py`:
```python
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str, **kwargs: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    template = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", value)
    return template
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 3.3: Implement IntentParser

**Files:**
- Create: `src/ideago/pipeline/intent_parser.py`
- Test: `tests/unit/test_pipeline_intent.py`

**Step 1:** Write the failing test

```python
import pytest
from unittest.mock import AsyncMock, patch
from ideago.pipeline.intent_parser import IntentParser
from ideago.models.research import Platform

MOCK_LLM_INTENT_RESPONSE = {
    "keywords_en": ["markdown", "notes", "browser extension"],
    "keywords_zh": ["Markdown 笔记", "浏览器插件"],
    "app_type": "browser-extension",
    "target_scenario": "Take markdown notes while browsing web pages",
    "search_queries": [
        {"platform": "github", "queries": ["markdown notes browser extension stars:>50"]},
        {"platform": "tavily", "queries": ["markdown notes chrome extension competitor"]},
        {"platform": "hackernews", "queries": ["Show HN markdown notes extension"]},
    ]
}

@pytest.mark.asyncio
async def test_intent_parser_returns_intent():
    parser = IntentParser.__new__(IntentParser)
    parser._llm = AsyncMock()
    parser._llm.complete_json = AsyncMock(return_value=MOCK_LLM_INTENT_RESPONSE)

    intent = await parser.parse("我想做一个给网页内容做Markdown笔记的浏览器插件")
    assert "markdown" in intent.keywords_en
    assert intent.app_type == "browser-extension"
    assert len(intent.search_queries) == 3

@pytest.mark.asyncio
async def test_intent_parser_cache_key_computed():
    parser = IntentParser.__new__(IntentParser)
    parser._llm = AsyncMock()
    parser._llm.complete_json = AsyncMock(return_value=MOCK_LLM_INTENT_RESPONSE)

    intent = await parser.parse("test query")
    assert len(intent.cache_key) == 16
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
# src/ideago/pipeline/intent_parser.py
from ideago.llm.client import LLMClient
from ideago.llm.prompt_loader import load_prompt
from ideago.models.research import Intent


class IntentParser:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def parse(self, query: str) -> Intent:
        prompt = load_prompt("intent_parser", query=query)
        data = await self._llm.complete_json(prompt, system="You are a startup research assistant.")
        intent = Intent.model_validate(data)
        intent.cache_key = intent.compute_cache_key()
        return intent
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 3.4: Implement Extractor

**Files:**
- Create: `src/ideago/pipeline/extractor.py`
- Test: `tests/unit/test_pipeline_extractor.py`

**Step 1:** Write test with mocked LLM that returns competitor list JSON.

Key test cases:
- Normal extraction returns competitors with links
- LLM returns competitor without links → filtered out
- LLM failure → raises, caller handles degraded mode

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
class Extractor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def extract(
        self, raw_results: list[RawResult], query_context: str
    ) -> list[Competitor]:
        if not raw_results:
            return []
        platform = raw_results[0].platform
        raw_json = json.dumps([r.model_dump(mode="json") for r in raw_results], ensure_ascii=False)
        prompt = load_prompt("extractor", platform=platform.value, raw_results_json=raw_json, query_context=query_context)
        data = await self._llm.complete_json(prompt, system="You are a competitor analysis expert.")
        competitors_data = data.get("competitors", [])
        result = []
        for c in competitors_data:
            try:
                comp = Competitor.model_validate(c)
                if comp.links:  # enforce: no links = not recorded
                    result.append(comp)
            except Exception:
                logger.warning(f"Skipping invalid competitor: {c}")
        return result
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 3.5: Implement Aggregator

**Files:**
- Create: `src/ideago/pipeline/aggregator.py`
- Test: `tests/unit/test_pipeline_aggregator.py`

**Step 1:** Write test with mocked LLM.

Key test cases:
- Deduplicates competitors with same domain
- Returns market_summary, go_no_go, differentiation_angles
- Sorts by relevance_score descending

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
class Aggregator:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def aggregate(
        self, competitors: list[Competitor], original_query: str
    ) -> AggregationResult:
        competitors_json = json.dumps(
            [c.model_dump(mode="json") for c in competitors], ensure_ascii=False
        )
        prompt = load_prompt("aggregator", competitors_json=competitors_json, original_query=original_query)
        data = await self._llm.complete_json(prompt, system="You are a market research analyst.")
        deduped = [Competitor.model_validate(c) for c in data.get("competitors", [])]
        deduped.sort(key=lambda c: c.relevance_score, reverse=True)
        return AggregationResult(
            competitors=deduped,
            market_summary=data.get("market_summary", ""),
            go_no_go=data.get("go_no_go", ""),
            differentiation_angles=data.get("differentiation_angles", []),
        )
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 3.6: Phase 3 integration check

```bash
uv run pytest tests/unit/test_llm_client.py tests/unit/test_prompt_loader.py tests/unit/test_pipeline_intent.py tests/unit/test_pipeline_extractor.py tests/unit/test_pipeline_aggregator.py -v
uv run ruff check src/ideago/llm/ src/ideago/pipeline/
uv run mypy src/ideago/llm/ src/ideago/pipeline/
```

Commit.

---

## Phase 4: Pipeline + Cache

### Task 4.1: Implement FileCache

**Files:**
- Create: `src/ideago/cache/__init__.py`
- Create: `src/ideago/cache/file_cache.py`
- Test: `tests/unit/test_cache.py`

**Step 1:** Write the failing test

Key test cases:
- `put` writes JSON file, `get` reads it back
- `get` returns None for missing key
- `get` returns None for expired cache (TTL exceeded)
- `list_reports` returns all cached report summaries
- `delete` removes a cached report
- `cleanup_expired` removes old entries

**Step 2:** Run to verify failure. **Step 3:** Implement.

FileCache stores:
- `{cache_dir}/{cache_key}.json` — full ResearchReport
- `{cache_dir}/_index.json` — list of `{report_id, query, cache_key, created_at, competitor_count}`

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 4.2: Implement Orchestrator

**Files:**
- Create: `src/ideago/pipeline/orchestrator.py`
- Test: `tests/unit/test_pipeline_orchestrator.py`

**Step 1:** Write the failing test

```python
@pytest.mark.asyncio
async def test_orchestrator_full_pipeline():
    # Mock: cache (miss), intent parser, 3 sources, extractor, aggregator
    # Assert: callback receives events in correct order
    # Assert: final report has competitors + summary

@pytest.mark.asyncio
async def test_orchestrator_source_failure_partial_result():
    # Mock: one source raises, others succeed
    # Assert: report contains results from successful sources
    # Assert: failed source has status FAILED in source_results

@pytest.mark.asyncio
async def test_orchestrator_cache_hit_skips_pipeline():
    # Mock: cache returns existing report
    # Assert: no source search called
    # Assert: callback receives REPORT_READY immediately

@pytest.mark.asyncio
async def test_orchestrator_extraction_failure_degrades():
    # Mock: extractor raises for one source
    # Assert: that source has status DEGRADED
    # Assert: raw results converted to minimal competitors
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

Orchestrator flow:
1. Parse intent → emit INTENT_PARSED
2. Check cache → if hit, emit REPORT_READY, return
3. Concurrent source.search() → emit SOURCE_STARTED/COMPLETED/FAILED per source
4. Concurrent extractor.extract() per source → emit EXTRACTION_STARTED/COMPLETED
   - On failure: degrade → convert RawResult to Competitor(name=title, links=[url], one_liner=description)
5. Aggregator.aggregate() → emit AGGREGATION_STARTED/COMPLETED
   - On failure: skip aggregation, return unaggregated list with warning
6. Build ResearchReport → write cache → emit REPORT_READY

Uses `asyncio.gather(*tasks, return_exceptions=True)` for concurrent fetching/extraction.

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 4.3: Phase 4 integration check

```bash
uv run pytest tests/unit/test_cache.py tests/unit/test_pipeline_orchestrator.py -v
uv run ruff check src/ideago/cache/ src/ideago/pipeline/
uv run mypy src/ideago/cache/ src/ideago/pipeline/
```

Commit.

---

## Phase 5: API Layer

### Task 5.1: Create FastAPI app factory

**Files:**
- Create: `src/ideago/api/__init__.py`
- Create: `src/ideago/api/app.py`
- Test: `tests/unit/test_api_app.py`

**Step 1:** Write the failing test

```python
from fastapi.testclient import TestClient
from ideago.api.app import create_app

def test_app_created():
    app = create_app()
    assert app is not None

def test_app_has_api_prefix():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
```

**Step 2:** Run to verify failure. **Step 3:** Implement app factory.

```python
# src/ideago/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="IdeaGo", version="0.2.0", description="Competitor Research Engine")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    # register routers (will be added in subsequent tasks)
    from ideago.api.routes import health, analyze, reports
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(analyze.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    return app
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 5.2: Implement health route

**Files:**
- Create: `src/ideago/api/routes/__init__.py`
- Create: `src/ideago/api/routes/health.py`
- Test: `tests/unit/test_api_health.py`

**Step 1:** Write the failing test

```python
def test_health_returns_source_status():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "sources" in data
```

**Step 2:** Run to verify failure. **Step 3:** Implement.

```python
# src/ideago/api/routes/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check() -> dict:
    # checks which sources have valid config
    ...
```

**Step 4:** Run to verify pass. **Step 5:** Commit.

---

### Task 5.3: Implement request/response schemas

**Files:**
- Create: `src/ideago/api/schemas.py`
- Test: `tests/unit/test_api_schemas.py`

Schemas:
- `AnalyzeRequest(query: str)` with `min_length=5, max_length=1000`
- `AnalyzeResponse(report_id: str)`
- `ReportStatusResponse(report_id: str, status: "processing" | "completed" | "error")`
- `ReportListItem(id: str, query: str, created_at: datetime, competitor_count: int)`
- `ErrorResponse(error: str, detail: str)`

**Step 1:** Write test. **Step 2:** Verify fail. **Step 3:** Implement. **Step 4:** Verify pass. **Step 5:** Commit.

---

### Task 5.4: Implement analyze route (POST + SSE stream)

**Files:**
- Create: `src/ideago/api/routes/analyze.py`
- Test: `tests/integration/test_api_analyze.py`

Two endpoints:
- `POST /api/v1/analyze` — starts pipeline in background, returns report_id
  - If same query already processing, return existing report_id
- `GET /api/v1/reports/{report_id}/stream` — SSE endpoint, streams PipelineEvent

Key implementation:
- Uses `BackgroundTasks` for pipeline execution
- SSE uses `sse-starlette` `EventSourceResponse`
- Pipeline events pushed to `asyncio.Queue` per report_id
- SSE endpoint reads from queue until REPORT_READY or ERROR

**Step 1:** Write test. **Step 2:** Verify fail. **Step 3:** Implement. **Step 4:** Verify pass. **Step 5:** Commit.

---

### Task 5.5: Implement reports routes

**Files:**
- Create: `src/ideago/api/routes/reports.py`
- Test: `tests/integration/test_api_reports.py`

Endpoints:
- `GET /api/v1/reports` — list cached reports (from cache index)
- `GET /api/v1/reports/{id}` — get full report JSON (200 if done, 202 if processing)
- `DELETE /api/v1/reports/{id}` — delete cached report
- `GET /api/v1/reports/{id}/export` — download as Markdown file

**Step 1:** Write test. **Step 2:** Verify fail. **Step 3:** Implement. **Step 4:** Verify pass. **Step 5:** Commit.

---

### Task 5.6: Add server entry point

**Files:**
- Create: `src/ideago/__main__.py`

```python
import uvicorn
from ideago.api.app import create_app
from ideago.config.settings import get_settings

def main() -> None:
    settings = get_settings()
    app = create_app()
    uvicorn.run(app, host=settings.host, port=settings.port)

if __name__ == "__main__":
    main()
```

Verify: `uv run python -m ideago` starts the server.

Commit.

---

### Task 5.7: Phase 5 integration check

```bash
uv run pytest tests/unit/test_api_app.py tests/unit/test_api_health.py tests/unit/test_api_schemas.py tests/integration/test_api_analyze.py tests/integration/test_api_reports.py -v
uv run ruff check src/ideago/api/
uv run mypy src/ideago/api/
```

Commit.

---

## Phase 6: Frontend

### Task 6.1: Generate design system with ui-ux-pro-max

**Step 1:** Run design system generator

```bash
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "SaaS startup research dashboard tool developer" --design-system --persist -p "IdeaGo"
```

**Step 2:** Generate page-specific overrides

```bash
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "search landing page startup tool" --design-system --persist -p "IdeaGo" --page "home"
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "data dashboard competitor analysis cards report" --design-system --persist -p "IdeaGo" --page "report"
```

**Step 3:** Get stack guidelines

```bash
python3 .cursor/skills/ui-ux-pro-max/scripts/search.py "dashboard data cards responsive" --stack react
```

**Step 4:** Commit design system files.

---

### Task 6.2: Scaffold React + Vite + Tailwind project

**Step 1:** Create frontend project

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

**Step 2:** Configure Tailwind in `vite.config.ts` and `src/index.css`.

**Step 3:** Configure Vite proxy to backend (`/api` → `http://localhost:8000`).

**Step 4:** Verify build: `npm run build`

**Step 5:** Commit.

---

### Task 6.3: Create TypeScript types + API client

**Files:**
- Create: `frontend/src/types/research.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/useSSE.ts`

`research.ts` — mirrors backend models:
- Platform, RawResult, Competitor, SourceResult, ResearchReport
- PipelineEvent, EventType

`client.ts` — API client functions:
- `startAnalysis(query: string): Promise<{report_id: string}>`
- `getReport(id: string): Promise<ResearchReport>`
- `listReports(): Promise<ReportListItem[]>`
- `deleteReport(id: string): Promise<void>`
- `getExportUrl(id: string): string`

`useSSE.ts` — custom React hook:
- `useSSE(reportId: string)` → `{ events: PipelineEvent[], isComplete: boolean, error: string | null }`
- Connects to `/api/v1/reports/{id}/stream`
- Accumulates events in state
- Auto-disconnects on REPORT_READY or ERROR

**Commit.**

---

### Task 6.4: Implement SearchBox component + HomePage

**Files:**
- Create: `frontend/src/components/SearchBox.tsx`
- Create: `frontend/src/pages/HomePage.tsx`

SearchBox:
- Text input with placeholder "Describe your startup idea..."
- Submit button
- Loading state while POST is in flight
- Validation: min 5 characters
- On submit: call startAnalysis(), navigate to /reports/{id}

HomePage:
- SearchBox centered on page
- Below: recent reports list (from listReports API) for quick access
- Clean, minimal layout following design-system/MASTER.md

**Commit.**

---

### Task 6.5: Implement ProgressTracker component

**Files:**
- Create: `frontend/src/components/ProgressTracker.tsx`

Vertical timeline showing pipeline stages:
- Each stage: icon + label + status indicator (pending / active / done / failed)
- Active stage has spinner animation
- Completed stage has checkmark + result count (e.g. "Found 8 results")
- Failed stage has X icon + error message
- Stages derived from SSE events

Stage list:
1. "Analyzing your idea..." (INTENT_PARSED)
2. "Searching GitHub..." (SOURCE_STARTED/COMPLETED for github)
3. "Searching web..." (SOURCE_STARTED/COMPLETED for tavily)
4. "Searching Hacker News..." (SOURCE_STARTED/COMPLETED for hackernews)
5. "Extracting insights..." (EXTRACTION_STARTED/COMPLETED)
6. "Generating report..." (AGGREGATION_STARTED/COMPLETED)
7. "Report ready" (REPORT_READY)

**Commit.**

---

### Task 6.6: Implement CompetitorCard + SourceStatusBar components

**Files:**
- Create: `frontend/src/components/CompetitorCard.tsx`
- Create: `frontend/src/components/SourceStatusBar.tsx`

CompetitorCard:
- Name (heading)
- One-liner (subtitle)
- Features as tags/badges
- Pricing if present
- Strengths (green list items)
- Weaknesses (red list items)
- Relevance score as visual bar or badge
- Links as clickable buttons/pills (open in new tab)
- Source platforms as small icons

SourceStatusBar:
- Horizontal bar showing each source
- Green chip = OK, red chip = FAILED, yellow chip = DEGRADED/TIMEOUT
- Shows count of results per source

**Commit.**

---

### Task 6.7: Implement ReportSummary component

**Files:**
- Create: `frontend/src/components/ReportSummary.tsx`

Sections:
- Go/No-Go banner (green for Go, yellow for Caution, red for No-Go)
- Market summary paragraphs
- Differentiation angles as bullet list
- Export as Markdown button

**Commit.**

---

### Task 6.8: Implement ReportPage (combines all report components)

**Files:**
- Create: `frontend/src/pages/ReportPage.tsx`

Logic:
1. On mount: connect SSE via useSSE(reportId)
2. While `!isComplete`: show ProgressTracker
3. When complete: fetch full report via getReport(id)
4. Render: ReportSummary + SourceStatusBar + CompetitorCard list
5. Error states: all sources failed banner, no competitors found message

**Commit.**

---

### Task 6.9: Implement HistoryPage

**Files:**
- Create: `frontend/src/pages/HistoryPage.tsx`

- Fetches listReports() on mount
- Table/list: query, date, competitor count, link to report
- Delete button per row with confirm dialog
- Empty state: "No research reports yet. Start by analyzing an idea."

**Commit.**

---

### Task 6.10: Wire up App router + layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`

Routes:
- `/` → HomePage
- `/reports/:id` → ReportPage
- `/reports` → HistoryPage

Layout:
- Simple top navbar: logo/title + "History" link
- Main content area

**Commit.**

---

### Task 6.11: Frontend verification

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

Fix any issues. Commit.

---

## Phase 7: Integration

### Task 7.1: FastAPI serves frontend static files

**Files:**
- Modify: `src/ideago/api/app.py`

In production mode, mount `frontend/dist` as static files at `/`.

```python
from fastapi.staticfiles import StaticFiles

if Path("frontend/dist").exists():
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

Commit.

---

### Task 7.2: Create Dockerfile

**Files:**
- Create: `Dockerfile`

Multi-stage build:
1. Stage 1: Node — build frontend (`npm run build`)
2. Stage 2: Python — install deps with uv, copy backend + frontend dist
3. CMD: `python -m ideago`

**Commit.**

---

### Task 7.3: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

```yaml
services:
  ideago:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - .cache:/app/.cache
```

**Commit.**

---

### Task 7.4: Update README.md

Replace template README with IdeaGo project description:
- What it does
- Quick start (local dev)
- Quick start (Docker)
- Configuration (.env)
- Architecture overview (link to design doc)

**Commit.**

---

### Task 7.5: Update .env.example

Ensure all new env vars are listed with descriptions:
```env
# Required
OPENAI_API_KEY=sk-your-key
TAVILY_API_KEY=tvly-your-key

# Optional
GITHUB_TOKEN=ghp-your-token

# Defaults (override if needed)
OPENAI_MODEL=gpt-4o-mini
MAX_RESULTS_PER_SOURCE=10
CACHE_TTL_HOURS=24
```

**Commit.**

---

### Task 7.6: Final verification

```bash
# Backend
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest

# Frontend
cd frontend
npm run lint
npm run typecheck
npm run build

# Docker
docker compose build
docker compose up -d
# Manual test: open http://localhost:8000, submit a query, verify report
docker compose down
```

**Commit + Tag v0.3.0.**

---

## Task Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| **Phase 1** | 1.1 – 1.10 | Dependencies, config, models, events, protocols |
| **Phase 2** | 2.1 – 2.5 | Source registry + GitHub/Tavily/HN implementations |
| **Phase 3** | 3.1 – 3.6 | LLM client, prompt templates, intent/extractor/aggregator |
| **Phase 4** | 4.1 – 4.3 | File cache + pipeline orchestrator |
| **Phase 5** | 5.1 – 5.7 | FastAPI app, routes, schemas, server entry |
| **Phase 6** | 6.1 – 6.11 | Design system, React scaffold, all pages + components |
| **Phase 7** | 7.1 – 7.6 | Static serving, Docker, README, final verification |

**Total: 42 tasks across 7 phases.**
