#!/usr/bin/env python3
"""Search public idea-validation sources and print normalized JSON.

Stdlib only. Each source returns a list of items with the same shape:
  {platform, title, url, snippet, date, metrics}

Usage:
  search.py hn "claude code gui" "claude code desktop"
  search.py appstore "habit tracker" --country cn
  search.py github "claude code gui" --max-age-days 365
  search.py all "claude code gui"            # hn + github (+ appstore with --with-appstore)

Reddit blocks anonymous JSON search, so use web search with site:reddit.com instead.

Failures are reported per query under "errors" instead of aborting, so the
caller can note degraded sources in the confidence section.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

USER_AGENT = "ideago-skill/1.0 (idea validation research)"
TIMEOUT = 20


def _get_json(url: str, params: dict, headers: dict | None = None) -> dict:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        full_url, headers={"User-Agent": USER_AGENT, **(headers or {})}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)


def _iso_from_ts(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(float(ts), tz=UTC).date().isoformat()


def _clip(text: str | None, limit: int = 400) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def search_hn(query: str, limit: int, max_age_days: int, **_: object) -> list[dict]:
    params: dict[str, object] = {"query": query, "tags": "story", "hitsPerPage": limit}
    if max_age_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        params["numericFilters"] = f"created_at_i>{int(cutoff.timestamp())}"
    data = _get_json("https://hn.algolia.com/api/v1/search", params)
    items = []
    for hit in data.get("hits", []):
        object_id = hit.get("objectID")
        if not object_id:
            continue
        discussion = f"https://news.ycombinator.com/item?id={object_id}"
        items.append(
            {
                "platform": "hackernews",
                "title": hit.get("title") or "",
                "url": hit.get("url") or discussion,
                "discussion_url": discussion,
                "snippet": _clip(hit.get("story_text")),
                "date": _iso_from_ts(hit.get("created_at_i")),
                "metrics": {
                    "points": hit.get("points") or 0,
                    "comments": hit.get("num_comments") or 0,
                },
            }
        )
    return items


def search_appstore(query: str, limit: int, country: str, **_: object) -> list[dict]:
    data = _get_json(
        "https://itunes.apple.com/search",
        {"term": query, "entity": "software", "country": country, "limit": limit},
    )
    items = []
    for app in data.get("results", []):
        url = app.get("trackViewUrl")
        if not url:
            continue
        items.append(
            {
                "platform": "appstore",
                "title": app.get("trackName") or "",
                "url": url.split("?")[0],
                "snippet": _clip(app.get("description"), 300),
                "date": (app.get("currentVersionReleaseDate") or "")[:10],
                "metrics": {
                    "rating": round(app.get("averageUserRating") or 0, 2),
                    "rating_count": app.get("userRatingCount") or 0,
                    "price": app.get("formattedPrice") or "",
                    "genre": app.get("primaryGenreName") or "",
                    "seller": app.get("sellerName") or "",
                },
            }
        )
    return items


def _gh_token() -> str:
    """Reuse the gh CLI login so anonymous search rate limits don't bite."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def search_github(query: str, limit: int, max_age_days: int, **_: object) -> list[dict]:
    q = query
    if max_age_days > 0:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        q = f"{q} pushed:>{cutoff.date().isoformat()}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or _gh_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = _get_json(
        "https://api.github.com/search/repositories",
        {"q": q, "per_page": limit},
        headers,
    )
    items = []
    for repo in data.get("items", []):
        items.append(
            {
                "platform": "github",
                "title": repo.get("full_name") or "",
                "url": repo.get("html_url") or "",
                "snippet": _clip(repo.get("description"), 300),
                "date": (repo.get("pushed_at") or "")[:10],
                "metrics": {
                    "stars": repo.get("stargazers_count") or 0,
                    "forks": repo.get("forks_count") or 0,
                    "open_issues": repo.get("open_issues_count") or 0,
                    "language": repo.get("language") or "",
                },
            }
        )
    return items


SOURCES = {
    "hn": search_hn,
    "appstore": search_appstore,
    "github": search_github,
}


def run(source_names: list[str], queries: list[str], options: dict) -> dict:
    results: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for name in source_names:
        for query in queries:
            try:
                items = SOURCES[name](query, **options)
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                errors.append({"source": name, "query": query, "error": str(exc)})
                continue
            for item in items:
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                item["matched_query"] = query
                results.append(item)
    return {"results": results, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", choices=[*SOURCES, "all"])
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--limit", type=int, default=8, help="results per query")
    parser.add_argument("--max-age-days", type=int, default=730)
    parser.add_argument("--country", default="us", help="App Store storefront")
    parser.add_argument("--with-appstore", action="store_true")
    args = parser.parse_args()

    if args.source == "all":
        names = ["hn", "github"] + (["appstore"] if args.with_appstore else [])
    else:
        names = [args.source]
    options = {
        "limit": args.limit,
        "max_age_days": args.max_age_days,
        "country": args.country,
    }
    json.dump(
        run(names, args.queries, options), sys.stdout, ensure_ascii=False, indent=2
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
