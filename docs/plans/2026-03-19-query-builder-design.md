# Query Builder Design — Per-Platform Deterministic Query Generation

**Date**: 2026-03-19
**Status**: Approved
**Problem**: Low recall across all sources because a single LLM prompt generates queries for 5 platforms simultaneously, without understanding each platform's search API semantics.

## Architecture

### Before

```
IntentParser (LLM) → Intent { keywords, app_type, scenario, search_queries[] }
  → fetch_sources_node → match search_queries by platform → source.search(queries)
```

### After

```
IntentParser (LLM) → Intent { keywords, app_type, scenario }
  → fetch_sources_node → QueryBuilder.build(platform, intent) → source.search(queries)
```

## Changes

1. **New module**: `src/ideago/pipeline/query_builder.py`
   - Single entry point: `build_queries(platform, intent) -> list[str]`
   - Per-platform builder functions (pure, testable)
   - Static `app_type` → platform-hints mapping table

2. **Intent model**: `search_queries` field becomes `default_factory=list` (backward compat with cached data)

3. **Intent parser prompt**: Remove `search_queries` generation requirement, save tokens

4. **nodes.py**: Replace `_resolve_queries_for_source()` with `build_queries()` call

5. **GitHub normalizer**: Preserve `topic:` qualifiers, strip only sort/ranking qualifiers

## Per-Platform Query Rules

### GitHub
- All keywords joined (max 4 words): `"markdown notes browser extension"`
- Topic qualifiers from keywords: `"topic:markdown topic:notes"`
- app_type extra term: `"chrome extension markdown"`

### App Store
- Individual keywords (top 2): `"markdown"`, `"notes"`
- Keyword pairs (max 2): `"markdown notes"`
- Genre from app_type: `"productivity"`

### Product Hunt
- app_type → topic slug candidates: `["browser-extensions", "chrome-extensions", "productivity"]`
- Broadest 1-2 keywords: `"markdown"`, `"notes"`

### Hacker News
- All keywords joined: `"markdown notes browser extension"`
- Keyword pairs: `"markdown notes"`, `"browser extension"`
- app_type extra: `"chrome extension"`

### Tavily
- Keywords + "alternative": `"markdown notes browser extension alternative"`
- Keywords + "competitor": `"markdown notes browser extension competitor"`
- Best-of phrasing: `"best markdown note taking browser extension"`
- Chinese query if keywords_zh present

## Files Touched

- `src/ideago/pipeline/query_builder.py` (new)
- `src/ideago/models/research.py` (Intent.search_queries default)
- `src/ideago/llm/prompts/intent_parser.txt` (simplify)
- `src/ideago/pipeline/nodes.py` (integrate QueryBuilder)
- `src/ideago/sources/github_source.py` (preserve topic: in normalizer)
- `tests/test_query_builder.py` (new)
- `tests/test_langgraph_engine.py` (update)
- `tests/test_sources.py` (update)
