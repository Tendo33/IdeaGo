# Retrieval Scoring

How raw source results are ranked before they reach the LLM extractor, and how
to change that ranking without guessing.

## The Family Vocabulary Contract

`pre_filter.build_opportunity_score_breakdown` looks up a per-family signal
baseline in `_FAMILY_BASE_COMPONENTS`. An unmatched family falls through to
`(0.0, 0.0, 0.0)` — no baseline at all, so the result ranks on popularity alone.

Two producers write `raw_data["query_family"]`, and **they speak different
vocabularies**:

| Producer | Names | Matches scorer? |
| --- | --- | --- |
| Deterministic templates in `query_builder.py` | `competitor_discovery`, `alternative_discovery`, … | yes, natively |
| LLM planner (`QueryFamily` enum) | `direct_competitor`, `adjacent_analogy`, `workflow_interface`, … | **three of six do not** |

`_PLANNER_FAMILY_ALIASES` bridges the gap. Without it, an `adjacent_analogy`
result scored 0.204 where the equivalent `alternative_discovery` scored 0.589 —
a 2.9x gap purely from the name, and one that only appears when the LLM planner
is reachable.

**When adding a `QueryFamily` value, add its alias or its own baseline.**
`test_every_planner_family_is_understood` fails otherwise.

## Changing the Score

Do not reason about ranking changes from the code alone. Two plausible
improvements were refuted by measurement (bare-hint query combination: −4%
recall; query-term-overlap relevance: monotonic degradation) — see
`.trellis/tasks/08-18-retrieval-method/prd.md`.

Use the harness instead:

```bash
# Offline replay against a saved corpus — zero API calls, runs in seconds
uv run python scripts/eval_retrieval.py --rescore eval/results/<corpus>.json --out /tmp/x.json

# Free structural check, no network
uv run python scripts/eval_retrieval.py --dry-run

# Live run against real APIs; costs money, needs working keys
uv run python scripts/eval_retrieval.py --sources tavily,github --out eval/results/<name>.json
```

Judge with **MRR / precision@5 / first-hit-rank** against the hand-labelled
`known_competitors` in `eval/retrieval_cases.json`. These are scoring-independent,
so they stay comparable across scoring changes — unlike `opportunity_score`
itself, which cannot be used to evaluate the function that produces it.

Always compare rescore↔rescore or live↔live. Mixing the two is not a valid
comparison.

## Known Gaps

- The score has **no relevance component**. `matched_query` reaches
  `signal_text` but is only scanned for pain vocabulary, never for whether the
  result is on-topic. Literal term overlap is not the fix: competitors are named
  entities, and brand pages rarely repeat category words.
- HackerNews' median first competitor hit sits at rank 21 (Tavily's is rank 1).
- Reddit returns 403 on every unauthenticated `search.json` call. Verified not a
  user-agent problem. Needs `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`. A
  breaker now stops after the first 401/403 per instance, since the fallback
  path is serialized and would otherwise pay one round trip per query to learn
  the same thing. A 429 does not trip it — rate limiting is transient, lockout
  is not.
- Product Hunt rate-limits aggressively and previously treated every non-200
  alike, so a single 429 zeroed the source (1 of 8 eval cases). It now retries
  once, honouring `Retry-After` when the wait fits inside the ~30s source
  budget and failing fast when it does not.
