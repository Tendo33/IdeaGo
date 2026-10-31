# Scoring

Two numbers go in the report. Both are judgment calls anchored to evidence — show the components so
the reader can disagree with a specific one.

## Opportunity score (0-1)

Rate each component 0-1 from the evidence you gathered:

| component | high (≥0.7) means | low (≤0.3) means |
|---|---|---|
| pain_intensity | repeated, emotional complaints; people hacking workarounds | mild annoyance, few mentions |
| solution_gap | incumbents miss the core job, are abandoned, or serve another segment | mature, well-loved products cover it |
| commercial_intent | pricing pages exist, people say they pay or would pay, paid alternatives do well | "should be free", only OSS hobby projects |
| freshness | most evidence from the last 12 months; something recently changed | evidence mostly >2 years old |
| competition_density | many strong direct competitors with traction | none or only adjacent/abandoned ones |

```
score = 0.30·pain + 0.28·gap + 0.26·commercial + 0.08·freshness + 0.08·(1 − competition_density)
```

Rough reading: ≥0.65 strong, 0.45-0.65 mixed, <0.45 weak. The score informs the recommendation but
doesn't decide it — a strong pain signal with zero willingness to pay is usually `caution`.

## Confidence (0-100)

How much the reader should trust the report, not how good the idea is.

```
diversity   = min(1, platforms_with_useful_evidence / 4)
density     = min(1, cited_evidence_items / 12)
recency     = share of cited evidence from the last 12 months
success     = sources that worked / sources tried  (a partially working source counts 0.7)
sample      = min(1, max(competitors, evidence_items, pain+commercial signals) / 6)

base        = 100 · (0.22·diversity + 0.18·density + 0.12·recency + 0.28·success + 0.20·sample)
penalty     = 24·(share of sources that failed or degraded) + 26·contradiction
confidence  = clamp(round(base − penalty), 0, 100)
```

`contradiction` is 0 when signals agree, ~0.5 when some evidence points the other way,
~1 when the evidence is split or concentrated in one narrow segment.

List the reasons that moved the number, e.g. "Reddit only reachable through web search",
"pain evidence comes from a single thread", "no pricing data found".
