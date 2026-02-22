#!/usr/bin/env python
"""Vulture dead code detection script.

This script runs vulture to detect unused code in the project.
It can be run standalone or integrated into CI/CD pipelines.

Usage:
    python scripts/run_vulture.py [--min-confidence MIN] [--sort-by-size]
    uv run scripts/run_vulture.py --min-confidence 80
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def run_vulture(
    min_confidence: int = 60,
    sort_by_size: bool = False,
    paths: list[str] | None = None,
) -> int:
    """Run vulture on the project source code.

    Args:
        min_confidence: Minimum confidence percentage for reporting unused code.
        sort_by_size: If True, sort results by size.
        paths: Specific paths to scan. Defaults to src directory.

    Returns:
        Exit code from vulture (0 if no unused code found).
    """
    project_root = get_project_root()

    if paths is None:
        paths = [str(project_root / "src")]

    cmd = ["vulture", *paths, f"--min-confidence={min_confidence}"]

    if sort_by_size:
        cmd.append("--sort-by-size")

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        print("-" * 60)
        print("[OK] No unused code detected!")
    else:
        print("-" * 60)
        print(
            f"[WARN] Vulture found potential unused code (exit code: {result.returncode})"
        )

    return result.returncode


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Run vulture to detect unused code in the project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_vulture.py
    python scripts/run_vulture.py --min-confidence 80
    python scripts/run_vulture.py --sort-by-size
    python scripts/run_vulture.py src/python_template tests
        """,
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=60,
        help="Minimum confidence for reporting unused code (default: 60)",
    )
    parser.add_argument(
        "--sort-by-size",
        action="store_true",
        help="Sort results by size (number of lines)",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to scan (default: src directory)",
    )

    args = parser.parse_args()

    paths = args.paths if args.paths else None
    return run_vulture(
        min_confidence=args.min_confidence,
        sort_by_size=args.sort_by_size,
        paths=paths,
    )


if __name__ == "__main__":
    sys.exit(main())
