# IdeaGo LangGraph Full Refactor Design

## Goals

- Replace legacy `LLMClient + Orchestrator` flow with LangGraph state-graph execution.
- Keep external API, response schemas, and SSE event payloads unchanged.
- Add SQLite checkpoint persistence for resumable execution on the same `report_id` thread.

## Node Graph

```text
parse_intent
  -> cache_lookup
    -> (cache hit) END
    -> (cache miss) fetch_sources
      -> extract_map
      -> aggregate
      -> assemble_report
      -> persist_report
      -> END
```

## State Contract (`GraphState`)

- Inputs: `query`, `report_id`
- Intermediate: `intent`, `raw_by_source`, `source_results`, `all_competitors`, `aggregation_result`
- Outputs: `report`
- Control fields: `is_cache_hit`, `error_code`, `cancelled`

## Compatibility Constraints

- Keep existing route semantics:
  - `POST /api/v1/analyze`
  - `GET /api/v1/reports/{id}/stream`
  - `GET /api/v1/reports/{id}`
  - `GET /api/v1/reports/{id}/export`
  - `DELETE /api/v1/reports/{id}/cancel`
  - `GET /api/v1/health`
- Keep `PipelineEvent` schema and `EventType` enum unchanged.
- Preserve fallback behaviors:
  - source timeout/failed/degraded statuses
  - extraction degrade to raw results
  - aggregation fallback summary for expected aggregation failures

## Checkpointing and Resume

- Checkpointer: `langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`
- Storage path: `LANGGRAPH_CHECKPOINT_DB_PATH` (default `.cache/ideago/langgraph-checkpoints.db`)
- Thread identity: `thread_id = report_id`
- Resume rule:
  - if `snapshot.next` is non-empty, execute `ainvoke(None, config=...)`
  - else start from initial input state

## LLM Layer

- New adapter: `ChatModelClient`
- Uses `langchain_openai.ChatOpenAI` with JSON response format and explicit retry loop.
- Retry policy:
  - retries for `429/500/502/503/504`
  - exponential backoff with configurable retry count (`LANGGRAPH_MAX_RETRIES`)

## Tests

- `tests/test_langgraph_engine.py` covers:
  - full success flow
  - cache hit short-circuit
  - partial source failure
  - extraction degrade
  - aggregation fallback
  - checkpoint resume after mid-graph failure
- `tests/test_llm_layer.py` updated to validate `ChatModelClient` behavior and parser/extractor/aggregator integration.
- `tests/test_api.py` remains compatibility gate for HTTP/SSE behavior.

## Operational Notes

- Keep report cache and checkpoint DB separate.
- Remove checkpoint DB to clear resume state without deleting historical reports.
- Engine injection remains centralized in `src/ideago/api/dependencies.py`.
