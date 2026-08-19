#!/usr/bin/env python
"""Measure evidence-retrieval quality against a fixed set of benchmark ideas.

Why this is a script and not a pytest case: it calls real third-party APIs, costs
money, takes minutes, and produces *data for a human to read* rather than a
pass/fail assertion. Putting it in the test suite would corrupt what a green CI
run means.

The point is to make "retrieval got better" a claim that can be checked. Run it
once before changing anything, once after, and diff the two.

    # free — shows the queries that would be sent, calls nothing
    uv run python scripts/eval_retrieval.py --dry-run

    # one LLM call per case, caches the parsed intent back into the case file
    uv run python scripts/eval_retrieval.py --refresh-intents

    # real retrieval
    uv run python scripts/eval_retrieval.py --out eval/results/baseline.json

Intents are cached on purpose. If intent parsing re-ran each time, a baseline and
an after run would differ partly because the LLM phrased things differently, and
the comparison would not isolate the retrieval change.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ideago.config.settings import get_settings  # noqa: E402
from ideago.models.research import (  # noqa: E402
    Intent,
    Platform,
    RawResult,
)
from ideago.pipeline.pre_filter import build_opportunity_score_breakdown  # noqa: E402
from ideago.pipeline.query_builder import build_queries  # noqa: E402

DEFAULT_CASES = REPO_ROOT / "eval" / "retrieval_cases.json"
_CJK = re.compile(r"[一-鿿]")

# Mirrors the freshness buckets in pre_filter so the report speaks the same
# language as the ranking the pipeline actually applies.
_FRESHNESS_BUCKETS = (
    (30, "<=30d"),
    (90, "<=90d"),
    (180, "<=180d"),
    (365, "<=1y"),
    (730, "<=2y"),
)


@dataclass
class Case:
    id: str
    lang: str
    app_type: str
    query: str
    known_competitors: list[str] = field(default_factory=list)
    intent: dict[str, Any] | None = None

    def to_intent(self) -> Intent | None:
        return Intent.model_validate(self.intent) if self.intent else None


def load_cases(path: Path) -> tuple[dict[str, Any], list[Case]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [Case(**case) for case in payload["cases"]]
    return payload, cases


def save_cases(path: Path, payload: dict[str, Any], cases: list[Case]) -> None:
    payload["cases"] = [
        {k: v for k, v in vars(case).items() if v is not None} for case in cases
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")


async def refresh_intents(cases: list[Case]) -> None:
    """Parse each case with the real IntentParser and cache the result."""
    from ideago.llm.chat_model import ChatModelClient
    from ideago.pipeline.intent_parser import IntentParser

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required for --refresh-intents")

    parser = IntentParser(
        ChatModelClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )
    )
    for case in cases:
        print(f"  parsing {case.id} ...", flush=True)
        intent = await parser.parse(case.query)
        case.intent = intent.model_dump(mode="json")


def queries_for(intent: Intent, platforms: list[Platform]) -> dict[str, list[str]]:
    """Build the queries each platform would actually receive."""
    out: dict[str, list[str]] = {}
    for platform in platforms:
        try:
            out[platform.value] = [str(q) for q in build_queries(platform, intent)]
        except Exception as exc:  # a builder blowing up is itself a finding
            out[platform.value] = [f"<error: {type(exc).__name__}: {exc}>"]
    return out


def _has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _freshness_bucket(result: RawResult) -> str:
    raw = result.raw_data.get("freshness_timestamp")
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - parsed).days
    for limit, label in _FRESHNESS_BUCKETS:
        if age_days <= limit:
            return label
    return ">2y"


def _rank_metrics(case: Case, ranked: list[RawResult]) -> dict[str, Any]:
    """Where do known competitors land once the scorer has sorted the results?

    This is the metric that survives a change to the scoring function. Absolute
    scores cannot be compared across such a change — the scale moves — but
    "did the scorer push known-good results toward the top" stays meaningful.
    """
    if not ranked or not case.known_competitors:
        return {"first_hit_rank": None, "mrr": 0.0, "precision_at_5": 0.0}

    def is_hit(result: RawResult) -> bool:
        hay = f"{result.title} {result.description} {result.url}".lower()
        return any(name.lower() in hay for name in case.known_competitors)

    hit_ranks = [i + 1 for i, r in enumerate(ranked) if is_hit(r)]
    top5 = sum(1 for r in ranked[:5] if is_hit(r))
    return {
        "first_hit_rank": hit_ranks[0] if hit_ranks else None,
        "mrr": round(1.0 / hit_ranks[0], 4) if hit_ranks else 0.0,
        "precision_at_5": round(top5 / min(5, len(ranked)), 3),
    }


def _serialize(result: RawResult) -> dict[str, Any]:
    """Store enough to re-score offline without re-fetching.

    `description` must be kept whole: the scorer scans it for pain / commercial
    vocabulary, so truncating it makes an offline replay disagree with the live
    run it is supposed to reproduce. Only `raw_content` is dropped — it is bulky
    and nothing in scoring reads it.
    """
    return {
        "title": result.title,
        "description": result.description,
        "url": result.url,
        "platform": result.platform.value,
        "fetched_at": result.fetched_at.isoformat(),
        "raw_data": {
            k: v
            for k, v in result.raw_data.items()
            if k != "raw_content"  # bulky and unused by scoring
        },
    }


def _deserialize(payload: dict[str, Any]) -> RawResult:
    return RawResult(
        title=payload["title"],
        description=payload.get("description", ""),
        url=payload["url"],
        platform=Platform(payload["platform"]),
        raw_data=dict(payload.get("raw_data", {})),
        fetched_at=datetime.fromisoformat(payload["fetched_at"]),
    )


def score_results(case: Case, results: list[RawResult]) -> dict[str, Any]:
    """Summarize one source's results for one case."""
    if not results:
        return {
            "count": 0,
            "competitor_hits": [],
            "competitor_hit_rate": 0.0,
            "cjk_ratio": 0.0,
            "freshness": {},
            "opportunity_score": {},
        }

    haystacks = [f"{r.title} {r.description} {r.url}".lower() for r in results]
    hits = sorted(
        {
            name
            for name in case.known_competitors
            if any(name.lower() in hay for hay in haystacks)
        }
    )

    cjk = sum(1 for r in results if _has_cjk(f"{r.title} {r.description}"))

    buckets: dict[str, int] = {}
    for result in results:
        bucket = _freshness_bucket(result)
        buckets[bucket] = buckets.get(bucket, 0) + 1

    ranked = sorted(
        results, key=lambda r: build_opportunity_score_breakdown(r).score, reverse=True
    )
    scores = sorted(build_opportunity_score_breakdown(r).score for r in results)
    mid = len(scores) // 2

    return {
        "count": len(results),
        **_rank_metrics(case, ranked),
        "competitor_hits": hits,
        "competitor_hit_rate": round(
            len(hits) / max(1, len(case.known_competitors)), 3
        ),
        "cjk_ratio": round(cjk / len(results), 3),
        "freshness": dict(sorted(buckets.items())),
        "opportunity_score": {
            "min": round(scores[0], 4),
            "median": round(scores[mid], 4),
            "max": round(scores[-1], 4),
        },
    }


def build_registry(source_names: list[str]):  # type: ignore[no-untyped-def]
    """Construct sources exactly as the app does, so results are faithful."""
    from ideago.sources.appstore_source import AppStoreSource
    from ideago.sources.github_source import GitHubSource
    from ideago.sources.hackernews_source import HackerNewsSource
    from ideago.sources.producthunt_source import ProductHuntSource
    from ideago.sources.reddit_source import RedditSource
    from ideago.sources.registry import SourceRegistry
    from ideago.sources.tavily_source import TavilySource

    s = get_settings()
    builders = {
        "github": lambda: GitHubSource(
            token=s.github_token,
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
            max_age_days=s.source_max_age_days,
        ),
        "tavily": lambda: TavilySource(
            api_key=s.tavily_api_key,
            base_url=s.tavily_base_url,
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
            max_age_days=s.source_max_age_days,
        ),
        "hackernews": lambda: HackerNewsSource(
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
            max_age_days=s.source_max_age_days,
        ),
        "appstore": lambda: AppStoreSource(
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
            country=s.appstore_country,
        ),
        "producthunt": lambda: ProductHuntSource(
            dev_token=s.producthunt_dev_token,
            posted_after_days=s.producthunt_posted_after_days,
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
        ),
        "reddit": lambda: RedditSource(
            client_id=s.reddit_client_id,
            client_secret=s.reddit_client_secret,
            timeout=s.source_timeout_seconds,
            max_concurrent_queries=s.source_query_concurrency,
            enable_public_fallback=s.reddit_enable_public_fallback,
            public_fallback_limit=s.reddit_public_fallback_limit,
            public_fallback_delay_seconds=s.reddit_public_fallback_delay_seconds,
            max_age_days=s.source_max_age_days,
        ),
    }
    registry = SourceRegistry()
    for name in source_names:
        if name not in builders:
            raise SystemExit(f"unknown source: {name}")
        registry.register(builders[name]())
    return registry


async def run_case(case: Case, registry, limit: int) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    intent = case.to_intent()
    if intent is None:
        raise SystemExit(
            f"case {case.id} has no cached intent — run --refresh-intents first"
        )

    per_source: dict[str, Any] = {}
    for source in registry.get_all():
        name = source.platform.value
        if not source.is_available():
            per_source[name] = {"skipped": "unavailable"}
            continue
        queries = [str(q) for q in build_queries(source.platform, intent)]
        try:
            results = await source.search(queries, limit=limit)
        except Exception as exc:
            per_source[name] = {
                "error": f"{type(exc).__name__}: {exc}",
                "queries": queries,
            }
            continue
        summary = score_results(case, results)
        summary["queries"] = queries
        summary["query_count"] = len(queries)
        # Keep the raw results so metrics can be recomputed offline. Changing a
        # metric — or the scoring function itself — should not require paying
        # for the API calls again.
        summary["raw"] = [_serialize(r) for r in results]
        per_source[name] = summary
        print(
            f"    {name:12s} queries={len(queries):2d} results={summary['count']:3d} "
            f"hits={len(summary['competitor_hits'])}/{len(case.known_competitors)}",
            flush=True,
        )
    return per_source


async def main_async(args: argparse.Namespace) -> int:
    cases_path = Path(args.cases)
    payload, cases = load_cases(cases_path)

    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
        if not cases:
            raise SystemExit(f"no cases matched {args.only}")

    if args.refresh_intents:
        await refresh_intents(cases)
        save_cases(cases_path, payload, cases)
        print(f"cached intents for {len(cases)} cases -> {cases_path}")
        return 0

    source_names = [s.strip() for s in args.sources.split(",") if s.strip()]
    platforms = [Platform(name) for name in source_names]

    if args.dry_run:
        # Free, and diagnostic on its own: it shows exactly what each platform
        # is asked, including whether a Chinese idea produces Chinese queries.
        report: dict[str, Any] = {"mode": "dry-run", "cases": {}}
        for case in cases:
            intent = case.to_intent()
            if intent is None:
                report["cases"][case.id] = {"error": "no cached intent"}
                continue
            built = queries_for(intent, platforms)
            all_queries = [q for qs in built.values() for q in qs]
            report["cases"][case.id] = {
                "lang": case.lang,
                "app_type": case.app_type,
                "keywords_en": intent.keywords_en,
                "keywords_zh": intent.keywords_zh,
                "queries": built,
                "total_queries": len(all_queries),
                "cjk_query_count": sum(1 for q in all_queries if _has_cjk(q)),
            }
        _emit(report, args.out)
        return 0

    if args.rescore:
        corpus_path = Path(args.rescore)
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        by_id = {c.id: c for c in cases}
        rescored: dict[str, Any] = {
            "mode": "rescore",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_corpus": str(corpus_path),
            "conditions": corpus.get("conditions", {}),
            "cases": {},
        }
        for case_id, entry in corpus["cases"].items():
            case = by_id.get(case_id)
            if case is None:
                continue
            out: dict[str, Any] = {}
            for source_name, data in entry.items():
                if not isinstance(data, dict) or "raw" not in data:
                    out[source_name] = data
                    continue
                results = [_deserialize(r) for r in data["raw"]]
                summary = score_results(case, results)
                summary["queries"] = data.get("queries", [])
                summary["query_count"] = data.get("query_count", 0)
                summary["raw"] = data["raw"]
                out[source_name] = summary
            rescored["cases"][case_id] = out
        _emit(rescored, args.out)
        _print_summary(rescored, cases)
        return 0

    settings = get_settings()
    registry = build_registry(source_names)
    report = {
        "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conditions": {
            "sources": source_names,
            "source_max_age_days": settings.source_max_age_days,
            "max_results_per_source": settings.max_results_per_source,
            # Reddit without OAuth runs a throttled, lower-limit public path.
            # Recorded because baseline and after runs must share conditions.
            "reddit_oauth_configured": bool(
                settings.reddit_client_id and settings.reddit_client_secret
            ),
            "reddit_public_fallback": settings.reddit_enable_public_fallback,
        },
        "cases": {},
    }
    for case in cases:
        print(f"  {case.id} ({case.lang}/{case.app_type})", flush=True)
        report["cases"][case.id] = await run_case(case, registry, args.limit)

    _emit(report, args.out)
    _print_summary(report, cases)
    return 0


def _emit(report: dict[str, Any], out: str | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"\nwrote {path}")
    else:
        print(text)


def _print_summary(report: dict[str, Any], cases: list[Case]) -> None:
    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    empty_pairs = 0
    total_pairs = 0
    for case in cases:
        entry = report["cases"].get(case.id, {})
        hits, total_known = set(), len(case.known_competitors)
        counts = []
        for data in entry.values():
            if not isinstance(data, dict) or "count" not in data:
                continue
            total_pairs += 1
            if data["count"] == 0:
                empty_pairs += 1
            counts.append(data["count"])
            hits.update(data.get("competitor_hits", []))
        print(
            f"  {case.id:26s} results={sum(counts):4d} "
            f"competitors={len(hits)}/{total_known} "
            f"{'MISS' if not hits else ''}"
        )
    if total_pairs:
        print(f"\n  empty (case, source) pairs: {empty_pairs}/{total_pairs}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument(
        "--sources",
        default="tavily,github,hackernews,appstore,producthunt,reddit",
        help="comma-separated source names to exercise",
    )
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", help="write JSON report here")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the queries that would be sent; calls no APIs",
    )
    parser.add_argument(
        "--rescore",
        help="recompute metrics from a saved corpus; makes no API calls",
    )
    parser.add_argument(
        "--refresh-intents",
        action="store_true",
        help="re-parse every case with the real LLM and cache the intent",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
