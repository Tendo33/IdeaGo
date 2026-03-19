# Extract → Aggregate Pipeline Refactor

**Date**: 2026-03-19
**Status**: Approved
**Approach**: Split into 4-stage pipeline: pre_filter → extract_map → merge → analyze

## Problems Solved

1. Double dedup (code + LLM)
2. No pre-filtering before LLM extraction
3. Monolithic aggregation LLM call
4. Extraction lacks structured Intent context
5. Code dedup only matches exact URL/name
6. LLM asked to do arithmetic (score boost)
7. `_invoke_json_with_optional_meta` duplicated 3x
8. Poor degradation quality

## New Pipeline

```
fetch_sources → pre_filter → extract_map → merge → analyze → assemble_report
```

## Phases

- Phase 0: Extract shared invoke_helpers
- Phase 1: Pre-filter node (code-only quality scoring)
- Phase 2: Improve Extractor (Intent context + better degradation)
- Phase 3: Split Aggregation into Merge (code) + Analyze (LLM)
- Phase 4: Update graph structure
- Phase 5: Tests
