---
name: ideago
description: Validate a product or startup idea with live evidence and produce a decision-first report (go / caution / no-go, pain signals, willingness to pay, whitespace, direct vs adjacent competitors, cited evidence, confidence). Use when the user asks whether an idea is worth building, whether similar products already exist, who the competitors are, or wants market/demand validation — e.g. "这个想法值得做吗", "有没有人做过类似的", "帮我验证一下这个点子", "竞品调研", "validate this idea", "is there demand for X", "find competitors for X". Not for general market-size reports with no concrete idea, or for reviewing an existing product's code.
---

# IdeaGo — idea validation

Turn a rough idea into a decision-first report backed by evidence you actually looked at.
Competitor discovery is one section, not the whole job: the user wants to know whether to build it,
for whom, and where the gap is.

## Ground rules

- **Only cite URLs you saw** in search results or fetched pages. Never construct or guess a URL.
- **Preserve exact anchors.** "Claude Code 的 GUI" is about Claude Code, not "Claude" or "AI editors".
  A generic tool with a similar shape is an *adjacent* analogue, not a direct competitor.
- **Write in the user's language** (Chinese input → Chinese report; brand names and URLs stay as-is).
- Prefer evidence from the last ~2 years. Older items only count as background.
- When a source fails or returns nothing useful, say so in the confidence section instead of hiding it.

## Workflow

### 1. Parse the intent

Write down (briefly, for yourself) before searching:

- `keywords_en` (3-6 concrete noun phrases; English equivalents even for Chinese input) and `keywords_zh` if relevant
- `exact_entities`: product / tool / protocol names verbatim (`Claude Code`, `VS Code`, `Notion API`)
- `comparison_anchors`: "like Cursor", "alternative to X"
- `app_type`: web, mobile, browser-extension, cli, api, desktop, saas, library
- `target_scenario`: one sentence — who uses it, for what

Avoid vague keywords ("AI tool", "next-gen", "platform"). If the idea is too vague to search
(no user, no problem), ask one clarifying question before going further.

### 2. Plan queries

Build 2-6 query groups, 1-4 queries each, from these families — skip ones that don't apply:

| family | looks for | example for "Claude Code GUI" |
|---|---|---|
| direct_competitor | same problem, same anchor | `"Claude Code" GUI`, `Claude Code desktop app` |
| adjacent_analogy | same shape, other ecosystem | `Cursor alternative GUI agent` |
| workflow_interface | other forms of the same job | `Claude Code VS Code extension`, `Claude Code web UI` |
| pain_discovery | complaints, friction | `Claude Code terminal annoying`, `Claude Code hard to review diffs` |
| commercial_discovery | paying, pricing, budget | `Claude Code GUI paid`, `pay for Claude Code wrapper` |
| discussion_discovery | threads where people compare | `site:reddit.com Claude Code GUI`, `Show HN Claude Code` |

Every query in direct / pain / commercial groups must keep the exact anchor. No near-duplicate rewrites.

### 3. Gather evidence

Run the sources in parallel where you can:

- **Web search** (your built-in search tool) — direct competitors, pricing pages, pain and commercial queries.
  Reddit: search with `site:reddit.com <query>` (its JSON API blocks anonymous calls); if your search
  tool ignores `site:`, try `reddit <query>` or a domain filter option.
  Product Hunt: `site:producthunt.com <query>`.
- **Hacker News + GitHub (+ App Store)** via the bundled script:

  ```bash
  python3 <skill-dir>/scripts/search.py all "<query 1>" "<query 2>" [--with-appstore --country us]
  ```

  Add `--with-appstore` for mobile ideas (use `--country cn` for a Chinese market). Single sources:
  `search.py hn|github|appstore ...`. GitHub uses `GITHUB_TOKEN`/`GH_TOKEN` or an existing `gh` login; anonymous search is rate-limited
  to a few queries per minute, so keep GitHub queries to the 2-4 that matter.
  Output is JSON `{results: [{platform, title, url, snippet, date, metrics}], errors: [...]}`.

Then **open the 5-12 most promising items** (fetch tool): competitor homepages and pricing,
high-engagement HN/Reddit threads (comments are where pain and willingness-to-pay live),
GitHub READMEs and issue counts. Rank by engagement × relevance × freshness, favoring items
that mention pain, alternatives/switching, or paying.

Stop gathering when new searches mostly return things you've already seen.

### 4. Extract signals

From what you read, build these lists (each item carries its source URLs):

- **Competitors** — name, link, one-liner, key features, pricing, strengths, weaknesses,
  `direct` or `adjacent`, and a traction note (stars, ratings, points, last update).
  Abandoned projects (no update in a year, few stars) count as weak competition, not none.
- **Pain signals** — theme, summary, intensity (how much it hurts) and frequency (how often it shows up).
- **Commercial signals** — evidence people pay or would pay: pricing pages, "I'd pay for", budget talk, paid alternatives.
- **Migration signals** — people switching away from an incumbent and why.
- **Evidence items** — the quotable snippets behind all of the above.

### 5. Synthesize

- **Recommendation**: exactly one of `go` / `caution` / `no_go`, with 2-3 sentences of differentiated
  reasoning. If there's a viable entry wedge, name it. Generic advice ("focus on UX") is not a wedge.
- **Why now**: what changed recently (new platform, pricing shift, incumbent stagnation) — or say nothing has.
- **Whitespace** (1-3): title, why the gap exists, target segment, concrete wedge, supporting URLs.
- **Differentiation angles** (3-5): specific weaknesses of named competitors.
- **Opportunity score** and **confidence**: compute per [references/scoring.md](references/scoring.md).

### 6. Write the report

Use [references/report-template.md](references/report-template.md). Save it to
`./reports/<YYYY-MM-DD>-<idea-slug>.md` in the current directory unless the user asked for chat-only
output, then give a short summary in chat: the verdict, the strongest reason, the best wedge,
and the confidence score.
