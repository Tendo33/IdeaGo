# Source Intelligence V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the current report pipeline from a competitor-search workflow into a full idea-validation workflow using only the existing source set: `tavily`, `reddit`, `github`, `hackernews`, `appstore`, and `producthunt`.

**Architecture:** Keep the existing source list fixed, but significantly upgrade the retrieval pipeline, evidence model, aggregation method, and report UX. This is a structural V2 effort: intent-driven query strategies, source-role-aware orchestration, opportunity-first ranking, evidence-backed synthesis, and a front-end report experience centered on decision quality instead of raw competitor listing.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, LangGraph, pytest, ruff, mypy, React 19, TypeScript, Vite, Vitest, Testing Library.

---

## Scope Lock

This plan explicitly **does**:

- keep the current six sources
- perform large pipeline changes where needed
- perform significant report UX changes
- reposition the product around idea validation and whitespace discovery

This plan explicitly **does not**:

- add new sources
- add trend sources such as Google Trends
- introduce new paid data providers
- replace the current stack

## Product Repositioning

Current user-visible product behavior is still too close to:

- “帮我查竞品”

V2 should feel like:

- “帮我判断这个 idea 值不值得做”
- “告诉我用户在痛什么”
- “告诉我现有产品哪里没满足”
- “告诉我我该从哪个切口切进去”
- “告诉我这些判断的证据够不够硬”

Competitor discovery remains essential, but it becomes one section inside a broader decision system.

## V2 Design Principles

1. Competitor discovery stays, but is not the only output.
2. Tavily remains the broad-recall leader, but not the only source of truth.
3. Native-platform signals should outrank SEO noise when they better express real pain or real product adoption.
4. Every important conclusion should be traceable back to evidence.
5. The report page should answer “Should we build this?” before it answers “Who else exists?”

## Source Roles In V2

Keep the sources unchanged, but assign explicit responsibilities:

- `Tavily`: broad recall, official pages, alternatives pages, reviews, comparisons, media mentions
- `Reddit`: pain, complaints, alternatives, migration, authentic user language
- `GitHub`: open-source/devtool competitors, activity, maturity, ecosystem density
- `Hacker News`: builder sentiment, technical discourse, sharper adoption commentary
- `App Store`: review clusters, rating volume, recurring consumer pain
- `Product Hunt`: launch messaging, positioning, early discovery, perceived novelty

## V2 Architecture Summary

The end-state flow should look like this:

1. Parse user intent
2. Generate multiple research-intent query families
3. Orchestrate existing sources according to source roles and budget
4. Preserve provenance for each raw result
5. Rank by opportunity, not popularity
6. Extract competitors plus pain/commercial/evidence signals
7. Synthesize whitespace and entry wedges
8. Compute confidence from source diversity and evidence density
9. Present a decision-first report UI

## Success Criteria

V2 is successful when:

- reports still find competitors reliably
- reports also surface pain signals and unmet needs
- conclusions cite usable evidence
- confidence feels materially more trustworthy
- the report page feels fundamentally different from a standard competitor report

## Delivery Strategy

Implement V2 in six major phases:

1. Domain and report contract redesign
2. Query and orchestration redesign
3. Opportunity ranking and evidence provenance
4. Extraction and aggregation redesign
5. Report API and front-end redesign
6. Observability, verification, and documentation

---

### Task 1: Redesign Domain Models For Decision-First Reports

**Files:**
- Modify: `src/ideago/models/research.py`
- Test: `tests/test_research_models.py`

**Step 1: Write the failing tests**

Add tests for new report structures and backward compatibility.

Required new models:

- `PainSignal`
- `CommercialSignal`
- `WhitespaceOpportunity`
- `OpportunityScoreBreakdown`
- `EvidenceCategory`
- `EvidenceItem` expansion if needed

Required new report fields:

- `pain_signals`
- `commercial_signals`
- `whitespace_opportunities`
- `opportunity_score`
- richer `evidence_summary`

Cover:

- default values
- validation bounds
- additive compatibility with older cached reports

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_research_models.py -v
```

Expected:

- FAIL because the new V2 models and fields do not exist yet

**Step 3: Write the minimal implementation**

Update `src/ideago/models/research.py` to make report structure support:

- decision-making signals
- evidence categories
- whitespace suggestions
- richer opportunity scoring

Keep the competitor structures intact, but make them one part of a larger report.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_research_models.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/models/research.py tests/test_research_models.py
git commit -m "feat: redesign report models for source intelligence v2"
```

---

### Task 2: Redesign Query Builder Around Research Intent Families

**Files:**
- Modify: `src/ideago/pipeline/query_builder.py`
- Test: `tests/test_query_builder.py`

**Step 1: Write the failing tests**

Add tests that require query generation across research-intent families:

- competitor discovery
- pain discovery
- alternative discovery
- workflow discovery
- migration discovery
- commercial discovery

Add source-role-specific expectations:

- Tavily receives the broadest recall set
- Reddit receives pain/alternative/switching queries
- GitHub receives ecosystem and repository-style discovery queries
- Hacker News receives discussion-style queries
- App Store receives review/problem/category phrasing
- Product Hunt receives launch/positioning queries

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_query_builder.py -v
```

Expected:

- FAIL because the current builder is too shallow and competitor-centric

**Step 3: Write the minimal implementation**

Refactor `src/ideago/pipeline/query_builder.py` so it can:

- model query families explicitly
- assign default weights or budgets by source role
- distinguish discovery queries from validation queries
- remain deterministic and testable

Keep the output shape compatible with the pipeline if possible, but allow a richer internal representation where needed.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_query_builder.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/query_builder.py tests/test_query_builder.py
git commit -m "feat: redesign query builder around research intent families"
```

---

### Task 3: Add Source-Role-Aware Orchestration Without Changing The Source Set

**Files:**
- Modify: `src/ideago/pipeline/nodes.py`
- Modify: `src/ideago/config/settings.py`
- Test: `tests/test_langgraph_engine.py`
- Test: `tests/test_settings.py`

**Step 1: Write the failing tests**

Add tests for orchestration behavior such as:

- Tavily gets the largest recall budget
- Reddit receives higher priority for pain-oriented queries
- GitHub and Hacker News get boosted for devtool/API/CLI ideas
- App Store gets boosted for mobile-facing ideas
- Product Hunt gets used for launch-positioning support, not broad recall

Add settings tests for:

- per-source query caps
- per-query-family weight defaults
- per-app-type orchestration profiles

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_settings.py -v
```

Expected:

- FAIL because orchestration is still too flat

**Step 3: Write the minimal implementation**

Refactor `src/ideago/pipeline/nodes.py` and `src/ideago/config/settings.py` to:

- assign source budgets by source role
- trim low-value query families before execution
- preserve adaptive degradation
- keep orchestration logic internal to current pipeline structure

Do not add any new source registration.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_settings.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/nodes.py src/ideago/config/settings.py tests/test_langgraph_engine.py tests/test_settings.py
git commit -m "feat: add source-role-aware orchestration to current sources"
```

---

### Task 4: Preserve Full Provenance And Native Signals In Raw Results

**Files:**
- Modify: `src/ideago/sources/tavily_source.py`
- Modify: `src/ideago/sources/reddit_source.py`
- Modify: `src/ideago/sources/github_source.py`
- Modify: `src/ideago/sources/hackernews_source.py`
- Modify: `src/ideago/sources/appstore_source.py`
- Modify: `src/ideago/sources/producthunt_source.py`
- Test: `tests/test_sources.py`

**Step 1: Write the failing tests**

Require each raw result to preserve:

- matched query
- query family
- source-native score
- engagement proxy
- freshness timestamp if available
- source-specific metadata useful for later ranking or UI explanation

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_sources.py -v
```

Expected:

- FAIL because current result provenance is too thin

**Step 3: Write the minimal implementation**

Update source adapters so all current sources expose consistent metadata in `raw_data`.

Implementation rule:

- standardize what can be standardized
- preserve native richness where useful
- do not invent fields a source cannot provide

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_sources.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/sources/tavily_source.py src/ideago/sources/reddit_source.py src/ideago/sources/github_source.py src/ideago/sources/hackernews_source.py src/ideago/sources/appstore_source.py src/ideago/sources/producthunt_source.py tests/test_sources.py
git commit -m "feat: preserve provenance and native source signals"
```

---

### Task 5: Replace Popularity Ranking With Opportunity-First Ranking

**Files:**
- Modify: `src/ideago/pipeline/pre_filter.py`
- Modify: `src/ideago/models/research.py`
- Test: `tests/test_pre_filter.py`
- Test: `tests/test_research_models.py`

**Step 1: Write the failing tests**

Add tests proving ranking now prefers:

- explicit pain over generic mention
- migration/alternative language over listicle noise
- commercial language over vanity popularity alone
- fresh, corroborated evidence over stale but famous items
- real app review complaints over polished homepage copy when both exist

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_pre_filter.py tests/test_research_models.py -v
```

Expected:

- FAIL because ranking is still mostly popularity-based

**Step 3: Write the minimal implementation**

Refactor `src/ideago/pipeline/pre_filter.py` to compute an `OpportunityScoreBreakdown` from:

- `pain_intensity`
- `solution_gap`
- `commercial_intent`
- `freshness`
- `competition_density`

Keep the scoring deterministic and LLM-free.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_pre_filter.py tests/test_research_models.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/pre_filter.py src/ideago/models/research.py tests/test_pre_filter.py tests/test_research_models.py
git commit -m "feat: rank source evidence by opportunity score"
```

---

### Task 6: Redesign Extraction Around Signals, Not Just Competitors

**Files:**
- Modify: `src/ideago/pipeline/extractor.py`
- Modify: `src/ideago/pipeline/nodes.py`
- Test: `tests/test_langgraph_engine.py`

**Step 1: Write the failing tests**

Add tests requiring the extraction stage to output:

- competitors
- pain signals
- commercial signals
- categorized evidence items

Cover cases where:

- competitor discovery comes from Tavily
- strongest pain comes from Reddit or App Store
- strongest product maturity signal comes from GitHub

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py -v
```

Expected:

- FAIL because extraction is still too competitor-centric

**Step 3: Write the minimal implementation**

Update `src/ideago/pipeline/extractor.py` so extraction distinguishes:

- competitor identity
- pain evidence
- commercial evidence
- migration evidence
- supporting snippets

Update `src/ideago/pipeline/nodes.py` to pass richer extracted state forward.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/extractor.py src/ideago/pipeline/nodes.py tests/test_langgraph_engine.py
git commit -m "feat: redesign extraction around actionable signals"
```

---

### Task 7: Redesign Aggregation Around Whitespace And Entry Wedges

**Files:**
- Modify: `src/ideago/pipeline/aggregator.py`
- Modify: `src/ideago/pipeline/merger.py`
- Modify: `src/ideago/pipeline/nodes.py`
- Test: `tests/test_langgraph_engine.py`
- Test: `tests/test_merger.py`

**Step 1: Write the failing tests**

Add tests requiring aggregation to synthesize:

- top pain themes
- whitespace opportunities
- entry wedges
- differentiated recommendations
- evidence-backed confidence inputs

Add scenarios such as:

- market is crowded, but a niche wedge appears underserved
- product category is noisy, but user complaint clusters are narrow and actionable
- open-source competition exists, but commercial packaging opportunity remains open

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_merger.py -v
```

Expected:

- FAIL because aggregation is still too close to summarization

**Step 3: Write the minimal implementation**

Refactor `src/ideago/pipeline/aggregator.py` so it performs actual synthesis:

- consolidate cross-source pain signals
- identify underserved segments
- derive one or more entry wedges
- keep competitor merge logic intact where useful, but make it secondary to the decision layer

Update `src/ideago/pipeline/nodes.py` so final report assembly reflects this V2 structure.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_merger.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/aggregator.py src/ideago/pipeline/merger.py src/ideago/pipeline/nodes.py tests/test_langgraph_engine.py tests/test_merger.py
git commit -m "feat: redesign aggregation for whitespace and entry wedges"
```

---

### Task 8: Strengthen Confidence And Evidence Summary For Decision Trust

**Files:**
- Modify: `src/ideago/pipeline/aggregator.py`
- Modify: `src/ideago/models/research.py`
- Test: `tests/test_langgraph_engine.py`
- Test: `tests/test_research_models.py`

**Step 1: Write the failing tests**

Require confidence to reflect:

- source diversity
- evidence density
- recency
- degraded-source penalties
- contradiction or weak corroboration penalties

Require evidence summary to support the V2 UI with:

- category
- title
- URL
- platform
- snippet
- freshness hint if available

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_research_models.py -v
```

Expected:

- FAIL because confidence and evidence summary are not rich enough

**Step 3: Write the minimal implementation**

Upgrade confidence and evidence logic so V2 reports can explain:

- what the strongest evidence is
- what is still uncertain
- whether the recommendation is broad-market strong or only niche-strong

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_research_models.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/aggregator.py src/ideago/models/research.py tests/test_langgraph_engine.py tests/test_research_models.py
git commit -m "feat: strengthen decision confidence and evidence transparency"
```

---

### Task 9: Update API Contracts For V2 Report Structure

**Files:**
- Modify: `src/ideago/api/schemas.py`
- Test: `tests/test_api.py`

**Step 1: Write the failing tests**

Add schema tests for:

- pain signals
- commercial signals
- whitespace opportunities
- opportunity score
- richer evidence summary

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_api.py -v
```

Expected:

- FAIL because the current API contracts do not fully expose the V2 report structure

**Step 3: Write the minimal implementation**

Update `src/ideago/api/schemas.py` so the V2 report sections serialize cleanly and remain additive.

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_api.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/api/schemas.py tests/test_api.py
git commit -m "feat: expose source intelligence v2 report contracts"
```

---

### Task 10: Redesign Report Frontend Around Decision-First Information Architecture

**Files:**
- Modify: `frontend/src/features/reports/ReportPage.tsx`
- Modify: `frontend/src/features/reports/components/ReportContentPane.tsx`
- Modify: `frontend/src/features/reports/components/MarketOverview.tsx`
- Modify: `frontend/src/features/reports/components/ConfidenceCard.tsx`
- Modify: `frontend/src/features/reports/components/EvidenceCostCard.tsx`
- Modify: `frontend/src/features/reports/components\SectionNav.tsx`
- Modify: `frontend/src/features/reports/components\InsightCard.tsx`
- Modify: `frontend/src/features/reports/components\ReportHeader.tsx`
- Create: `frontend/src/features/reports/components/WhitespaceOpportunityCard.tsx`
- Create: `frontend/src/features/reports/components/PainSignalsCard.tsx`
- Create: `frontend/src/features/reports/components/CommercialSignalsCard.tsx`
- Create: `frontend/src/features/reports/components/EvidenceSummaryPanel.tsx`
- Test: `frontend/src/features/reports/__tests__/ReportPage.test.tsx`
- Test: `frontend/src/features/reports/__tests__/ConfidenceCard.test.tsx`
- Test: `frontend/src/features/reports/__tests__/EvidenceCostCard.test.tsx`
- Test: `frontend/src/features/reports/__tests__/SectionNav.test.tsx`

**Step 1: Write the failing UI tests**

Add tests that require the report page to present this order:

1. should we build this
2. why this matters now
3. top pain signals
4. whitespace / entry wedge
5. key competitors
6. evidence and confidence

Also verify that:

- competitors remain visible
- pain/commercial/whitespace sections render when present
- evidence is inspectable
- confidence reasons are understandable

**Step 2: Run tests to verify they fail**

Run:

```bash
pnpm --prefix frontend test -- ReportPage ConfidenceCard EvidenceCostCard SectionNav
```

Expected:

- FAIL because the current report page does not reflect V2 information architecture

**Step 3: Write the minimal implementation**

Refactor the report UI to make V2 feel like a different product category:

- decision-first summary at the top
- whitespace and pain before competitor catalog
- competitor section retained but demoted
- evidence and confidence made more explicit
- navigation updated to reflect the new structure

Preserve current design language where practical, but allow significant layout and component changes.

**Step 4: Run tests to verify they pass**

Run:

```bash
pnpm --prefix frontend test -- ReportPage ConfidenceCard EvidenceCostCard SectionNav
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add frontend/src/features/reports/ReportPage.tsx frontend/src/features/reports/components/ReportContentPane.tsx frontend/src/features/reports/components/MarketOverview.tsx frontend/src/features/reports/components/ConfidenceCard.tsx frontend/src/features/reports/components/EvidenceCostCard.tsx frontend/src/features/reports/components/SectionNav.tsx frontend/src/features/reports/components/InsightCard.tsx frontend/src/features/reports/components/ReportHeader.tsx frontend/src/features/reports/components/WhitespaceOpportunityCard.tsx frontend/src/features/reports/components/PainSignalsCard.tsx frontend/src/features/reports/components/CommercialSignalsCard.tsx frontend/src/features/reports/components/EvidenceSummaryPanel.tsx frontend/src/features/reports/__tests__/ReportPage.test.tsx frontend/src/features/reports/__tests__/ConfidenceCard.test.tsx frontend/src/features/reports/__tests__/EvidenceCostCard.test.tsx frontend/src/features/reports/__tests__/SectionNav.test.tsx
git commit -m "feat: redesign report ui for source intelligence v2"
```

---

### Task 11: Add V2 Observability For Retrieval Quality And Recommendation Reliability

**Files:**
- Modify: `src/ideago/pipeline/nodes.py`
- Modify: `src/ideago/pipeline/aggregator.py`
- Modify: `src/ideago/observability/log_config.py`
- Test: `tests/test_langgraph_engine.py`
- Test: `tests/test_log_config.py`

**Step 1: Write the failing tests**

Add tests or assertions for V2 telemetry:

- query family coverage
- source-role budget usage
- evidence category counts
- degraded source ratio
- confidence penalty reasons
- whitespace generation rate

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_log_config.py -v
```

Expected:

- FAIL because V2 telemetry is not emitted yet

**Step 3: Write the minimal implementation**

Add structured telemetry that explains:

- how the retrieval budget was spent
- why some sources dominated a report
- why confidence was high or low
- whether whitespace was generated from real evidence or sparse evidence

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_langgraph_engine.py tests/test_log_config.py -v
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add src/ideago/pipeline/nodes.py src/ideago/pipeline/aggregator.py src/ideago/observability/log_config.py tests/test_langgraph_engine.py tests/test_log_config.py
git commit -m "feat: add observability for source intelligence v2"
```

---

### Task 12: Documentation And Verification Completion

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `ai_docs/AI_TOOLING_STANDARDS.md`
- Modify: `ai_docs/BACKEND_STANDARDS.md`
- Modify: `docs/plans/2026-03-24-source-intelligence-overhaul-plan.md`

**Step 1: Update docs**

Document:

- V2 product positioning
- fixed source boundary
- source-role architecture
- opportunity ranking method
- decision-first report structure
- verification expectations

**Step 2: Run full verification**

Run:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

Expected:

- PASS, or explicit tracking of any unrelated failures

**Step 3: Commit**

```bash
git add AGENTS.md CLAUDE.md ai_docs/AI_TOOLING_STANDARDS.md ai_docs/BACKEND_STANDARDS.md docs/plans/2026-03-24-source-intelligence-overhaul-plan.md
git commit -m "docs: align project docs with source intelligence v2"
```

---

## Recommended Execution Order

For best leverage, execute in this order:

1. Task 2
2. Task 3
3. Task 4
4. Task 5
5. Task 6
6. Task 7
7. Task 8
8. Task 1
9. Task 9
10. Task 10
11. Task 11
12. Task 12

Why this order:

- first improve what gets searched
- then improve how sources are budgeted
- then improve what evidence survives
- then improve how the system reasons over that evidence
- then expose the new structure through API and UI

## Risks And Mitigations

- Risk: Large pipeline changes increase regression risk.
  Mitigation: keep TDD discipline, preserve source boundaries, and verify at each stage.

- Risk: Tavily still dominates too heavily.
  Mitigation: broaden its recall role but explicitly protect native-platform evidence in ranking and aggregation.

- Risk: Frontend redesign outpaces backend shape.
  Mitigation: gate UI tasks behind stabilized report contracts and report fixtures.

- Risk: Whitespace recommendations become generic.
  Mitigation: require evidence support and confidence penalties for weak synthesis.

## Final Verification Gate

Before calling V2 complete, run:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

Plan complete and saved to `docs/plans/2026-03-24-source-intelligence-overhaul-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
