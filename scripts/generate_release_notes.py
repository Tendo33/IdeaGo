#!/usr/bin/env python3
"""Generate release notes for tag-based GitHub releases."""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MODEL_ENDPOINT = "https://api.openai.com/v1/chat/completions"


@dataclass(frozen=True)
class ReleaseContext:
    """Context payload used to generate release note summaries."""

    tag: str
    previous_tag: str | None
    changelog_section: str | None
    commits: list[str]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate markdown release notes for a git tag.",
    )
    parser.add_argument(
        "--tag", required=True, help="Release git tag (for example v0.2.0)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output markdown file path.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory).",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=200,
        help="Maximum commits to include in the notes.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("RELEASE_NOTES_MODEL", DEFAULT_MODEL),
        help=f"Model id for summary generation (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--model-timeout",
        type=int,
        default=30,
        help="Model request timeout in seconds.",
    )
    return parser.parse_args()


def run_git_command(repo_root: Path, *args: str) -> str:
    """Run a git command in repo_root and return trimmed stdout."""
    process = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() or "unknown git error"
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout.strip()


def normalize_version_from_tag(tag: str) -> str:
    """Normalize a version tag to changelog version token."""
    return tag[1:] if tag.startswith("v") else tag


def extract_changelog_section(changelog_text: str, version: str) -> str | None:
    """Extract a single changelog section body for the given version."""
    heading_pattern = re.compile(rf"^## \[{re.escape(version)}\].*$", re.MULTILINE)
    heading_match = heading_pattern.search(changelog_text)
    if not heading_match:
        return None

    body_start = heading_match.end()
    next_heading_pattern = re.compile(r"^## \[", re.MULTILINE)
    next_heading_match = next_heading_pattern.search(changelog_text, body_start)
    body_end = next_heading_match.start() if next_heading_match else len(changelog_text)
    section = changelog_text[body_start:body_end].strip()
    return section or None


def load_changelog_section(repo_root: Path, tag: str) -> str | None:
    """Load changelog section from CHANGELOG.md if available."""
    changelog_path = repo_root / "CHANGELOG.md"
    if not changelog_path.exists():
        return None

    changelog_text = changelog_path.read_text(encoding="utf-8")
    return extract_changelog_section(
        changelog_text=changelog_text,
        version=normalize_version_from_tag(tag),
    )


def get_previous_tag(repo_root: Path, tag: str) -> str | None:
    """Resolve previous tag relative to the release tag."""
    try:
        previous = run_git_command(
            repo_root, "describe", "--tags", "--abbrev=0", f"{tag}^"
        )
    except RuntimeError:
        return None
    return previous or None


def get_commit_lines(
    repo_root: Path,
    tag: str,
    previous_tag: str | None,
    max_commits: int,
) -> list[str]:
    """Return commit lines for the release range."""
    revision_range = f"{previous_tag}..{tag}" if previous_tag else tag
    pretty = "%h %s (%an)"
    raw = run_git_command(
        repo_root,
        "log",
        "--no-merges",
        f"-n{max_commits}",
        f"--pretty=format:{pretty}",
        revision_range,
    )
    return [line for line in raw.splitlines() if line.strip()]


def sanitize_model_summary(raw_summary: str) -> str:
    """Normalize model output into clean markdown list content."""
    content = raw_summary.strip()
    content = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", content)
    content = re.sub(r"\n?```$", "", content)
    content = re.sub(r"^##\s+Highlights\s*\n?", "", content, flags=re.IGNORECASE)
    return content.strip()


def build_summary_prompt(context: ReleaseContext) -> tuple[str, str]:
    """Build system and user prompts for release-summary generation."""
    previous = context.previous_tag or "N/A (first release)"
    changelog_block = (
        context.changelog_section or "No matching CHANGELOG section found."
    )
    commit_block = (
        "\n".join(f"- {line}" for line in context.commits) or "- No commits found."
    )
    system_prompt = (
        "You are a release manager writing concise, enterprise-grade release highlights. "
        "Return markdown bullet points only. Do not include a heading."
    )
    user_prompt = (
        f"Release tag: {context.tag}\n"
        f"Previous tag: {previous}\n\n"
        "CHANGELOG section:\n"
        f"{changelog_block}\n\n"
        "Commits in release:\n"
        f"{commit_block}\n\n"
        "Write 4-8 bullets covering key changes, risk areas, and rollout notes."
    )
    return system_prompt, user_prompt


def request_model_summary(
    context: ReleaseContext,
    model: str,
    api_key: str,
    timeout: int,
) -> str | None:
    """Request summary text from an OpenAI-compatible chat endpoint."""
    system_prompt, user_prompt = build_summary_prompt(context)
    endpoint = os.getenv("OPENAI_BASE_URL", DEFAULT_MODEL_ENDPOINT)
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        print(f"[WARN] Model request HTTP error: {exc.code}", file=sys.stderr)
        return None
    except URLError as exc:
        print(f"[WARN] Model request URL error: {exc.reason}", file=sys.stderr)
        return None
    except TimeoutError:
        print("[WARN] Model request timeout", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("[WARN] Model response JSON decode failed", file=sys.stderr)
        return None

    choices = response_payload.get("choices", [])
    if not choices:
        return None
    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str):
        return None
    cleaned = sanitize_model_summary(content)
    return cleaned or None


def build_fallback_highlights(previous_tag: str | None, tag: str) -> list[str]:
    """Return deterministic fallback highlights."""
    release_range = f"{previous_tag}..{tag}" if previous_tag else tag
    return [
        "Auto-generated summary unavailable; review changelog and commit details below.",
        f"Release scope: {release_range}.",
        "Validation recommendation: run regression tests before production rollout.",
    ]


def compose_release_notes(
    tag: str,
    previous_tag: str | None,
    changelog_section: str | None,
    commits: list[str],
    model_summary: str | None,
) -> str:
    """Compose complete markdown release notes body."""
    highlights = (
        sanitize_model_summary(model_summary).splitlines()
        if model_summary
        else build_fallback_highlights(previous_tag, tag)
    )
    highlight_lines = [line for line in highlights if line.strip()]
    normalized_highlights = [
        line if line.lstrip().startswith("- ") else f"- {line.lstrip('- ').strip()}"
        for line in highlight_lines
    ]
    if not normalized_highlights:
        normalized_highlights = ["- Auto-generated summary unavailable."]

    commit_lines = commits or ["No commits found for this tag."]
    formatted_commits = [
        line if line.lstrip().startswith("- ") else f"- {line}" for line in commit_lines
    ]

    previous = previous_tag or "N/A"
    changelog_markdown = changelog_section or "_No matching CHANGELOG section found._"

    sections = [
        f"# Release {tag}",
        "",
        f"- Release tag: `{tag}`",
        f"- Previous tag: `{previous}`",
        "",
        "## Highlights",
        *normalized_highlights,
        "",
        "## Changelog Extract",
        changelog_markdown,
        "",
        "## Commits",
        *formatted_commits,
        "",
    ]
    return "\n".join(sections)


def generate_release_notes(
    repo_root: Path,
    tag: str,
    model: str,
    max_commits: int,
    timeout: int,
) -> str:
    """Build release notes body."""
    previous_tag = get_previous_tag(repo_root=repo_root, tag=tag)
    changelog_section = load_changelog_section(repo_root=repo_root, tag=tag)
    commits = get_commit_lines(
        repo_root=repo_root,
        tag=tag,
        previous_tag=previous_tag,
        max_commits=max_commits,
    )

    context = ReleaseContext(
        tag=tag,
        previous_tag=previous_tag,
        changelog_section=changelog_section,
        commits=commits,
    )

    api_key = os.getenv("OPENAI_API_KEY")
    model_summary: str | None = None
    if api_key:
        model_summary = request_model_summary(
            context=context,
            model=model,
            api_key=api_key,
            timeout=timeout,
        )

    return compose_release_notes(
        tag=tag,
        previous_tag=previous_tag,
        changelog_section=changelog_section,
        commits=commits,
        model_summary=model_summary,
    )


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        notes = generate_release_notes(
            repo_root=repo_root,
            tag=args.tag,
            model=args.model,
            max_commits=args.max_commits,
            timeout=args.model_timeout,
        )
    except Exception as exc:
        print(f"[ERROR] Failed to generate release notes: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(notes, encoding="utf-8")
    print(f"[INFO] Release notes written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
