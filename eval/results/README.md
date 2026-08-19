# Retrieval eval artifacts

Saved runs of `scripts/eval_retrieval.py`. Compare **rescore↔rescore** or
**live↔live** only; mixing the two is not a valid comparison.

| File | Captured | Trust |
| --- | --- | --- |
| `dryrun-before.json` | structural dry run, no network | fine for shape checks only |
| `baseline-2026-08-18.json` | live, before query-builder experiment | see caveat below |
| `after-2026-08-18.json` | live, with bare-hint combination (since reverted) | see caveat below |
| `corpus-2026-08-19.json` | live, full raw results for offline replay | **partially lossy — see below** |

## Caveat: descriptions are truncated in every file above

All four were captured while `_serialize` truncated `description` to 400
characters. In `corpus-2026-08-19.json` that hit **418 of 653 results (64%)**.

The scorer reads `description` to detect pain, alternative and commercial
vocabulary, so offline rescoring of these corpora **under-detects those terms**
relative to a live run. That is why the offline baseline reads 0.2845 MRR where
an earlier live run read 0.2911.

They remain usable as a *fixed internal reference* — every rescore against the
same corpus is affected identically, so A/B comparisons within a corpus are
still valid. They are **not** usable as an estimate of real production ranking.

`_serialize` has since been fixed to keep `description` whole (dropping only
`raw_content`, which the scorer never reads). Re-capture for a faithful corpus:

```bash
uv run python scripts/eval_retrieval.py --out eval/results/corpus-<date>.json
```

Requires working API keys. As of 2026-08-19 the LLM gateway returns 401 and
Reddit returns 403 on every unauthenticated call, so a re-capture will still
have `intent` hand-authored and Reddit empty.
