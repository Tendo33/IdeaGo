# IdeaGo Skill

Validate a product idea from inside your coding agent. IdeaGo searches the web, Hacker News,
GitHub, Reddit, and the App Store, then writes a decision-first report covering the verdict, pain
signals, willingness to pay, whitespace, competitors, cited evidence, and a confidence score.

This branch replaces the earlier hosted web app with a single agent skill. The web app is still
available on the `main` (self-hosted) and `saas` (hosted) branches.

## Install

Copy or symlink `skills/ideago` into your agent's skills directory:

```bash
# Claude Code (user-level)
ln -s "$(pwd)/skills/ideago" ~/.claude/skills/ideago

# Codex
ln -s "$(pwd)/skills/ideago" ~/.codex/skills/ideago
```

Requirements: Python 3.9+ (stdlib only) and an agent with web search and page fetching.
For GitHub search, set `GITHUB_TOKEN`/`GH_TOKEN` or log in with `gh`. This is optional but avoids rate limits.

## Use

Ask in plain language:

- "帮我验证一下这个想法：给 Claude Code 做一个桌面 GUI"
- "Is there demand for a habit tracker built for ADHD adults?"

The report is saved to `./reports/<date>-<slug>.md`.

## Example

See [examples/2026-10-31-claude-code-desktop-gui.md](examples/2026-10-31-claude-code-desktop-gui.md) for a full report.

## Layout

```
skills/ideago/
  SKILL.md                      workflow: intent → query plan → gather → extract → synthesize → report
  references/scoring.md         opportunity score and confidence formulas
  references/report-template.md report structure
  scripts/search.py             HN / GitHub / App Store search, normalized JSON
```

## License

MIT
