"""Tests for the release notes generation script."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_generate_release_notes_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "generate_release_notes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_release_notes_script",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_changelog_section_returns_target_version() -> None:
    """The parser should return only the target version section content."""
    module = _load_generate_release_notes_module()
    changelog = """
# Changelog

## [Unreleased]

### Added
- pending

## [0.2.0] - 2026-02-20

### Changed
- update A

### Added
- update B

## [0.1.0] - 2026-01-20

### Added
- initial
"""
    section = module.extract_changelog_section(changelog, "0.2.0")
    assert section is not None
    assert "update A" in section
    assert "update B" in section
    assert "initial" not in section
    assert "pending" not in section


def test_compose_release_notes_uses_fallback_when_model_summary_absent() -> None:
    """Release notes should include a deterministic fallback highlights section."""
    module = _load_generate_release_notes_module()
    body = module.compose_release_notes(
        tag="v0.2.0",
        previous_tag="v0.1.0",
        changelog_section="### Changed\n- update A",
        commits=["a1b2c3d add feature", "d4e5f6g fix bug"],
        model_summary=None,
    )
    assert "## Highlights" in body
    assert "Auto-generated summary unavailable" in body
    assert "## Changelog Extract" in body
    assert "update A" in body
    assert "## Commits" in body
    assert "a1b2c3d add feature" in body


def test_sanitize_model_summary_strips_markdown_fence() -> None:
    """Model summary should be normalized before insertion to release notes."""
    module = _load_generate_release_notes_module()
    raw = "```markdown\n## Highlights\n- one\n```"
    cleaned = module.sanitize_model_summary(raw)
    assert "```" not in cleaned
    assert "- one" in cleaned
