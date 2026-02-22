#!/usr/bin/env python3
"""Version update script for python-template project.

This script updates the version number across all relevant files in the project:
- pyproject.toml
- src/python_template/__init__.py

该脚本用于更新项目中所有相关文件的版本号。

Usage:
    python scripts/update_version.py <new_version> [--dry-run]

Examples:
    python scripts/update_version.py 0.2.0
    python scripts/update_version.py 1.0.0 --dry-run
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VersionTarget:
    """Configuration for a file version replacement target."""

    path: Path
    pattern: str
    replacement: str
    optional: bool = False


class VersionUpdater:
    """Version updater for the project.

    项目版本更新器。
    """

    def __init__(self, project_root: Path):
        """Initialize version updater.

        初始化版本更新器。

        Args:
            project_root: Path to project root directory
        """
        self.project_root = project_root
        self.files_to_update = [
            VersionTarget(
                path=project_root / "pyproject.toml",
                pattern=r'^version = "([^"]+)"',
                replacement='version = "{version}"',
            ),
            VersionTarget(
                path=project_root / "src" / "python_template" / "__init__.py",
                pattern=r'^__version__ = "([^"]+)"',
                replacement='__version__ = "{version}"',
            ),
        ]

    @staticmethod
    def validate_version(version: str) -> bool:
        """Validate semantic version format.

        验证语义化版本格式。

        Args:
            version: Version string to validate

        Returns:
            True if valid, False otherwise
        """
        # Semantic versioning pattern: MAJOR.MINOR.PATCH
        pattern = r"^\d+\.\d+\.\d+$"
        return bool(re.match(pattern, version))

    def get_current_version(self) -> str:
        """Get current version from pyproject.toml.

        从pyproject.toml获取当前版本。

        Returns:
            Current version string
        """
        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)
        if not match:
            raise ValueError("Could not find version in pyproject.toml")

        return match.group(1)

    def update_file(self, target: VersionTarget, new_version: str) -> tuple[str, str]:
        """Update version in a single file.

        更新单个文件中的版本。

        Args:
            target: Version target configuration
            new_version: New version string

        Returns:
            Tuple of (status, message)
        """
        file_path = target.path
        pattern = target.pattern
        replacement = target.replacement

        if not file_path.exists():
            if target.optional:
                return "SKIP", f"Optional file not found: {file_path}"
            return "ERROR", f"Required file not found: {file_path}"

        try:
            content = file_path.read_text(encoding="utf-8")
            original_content = content

            # Find current version
            match = re.search(pattern, content, re.MULTILINE)
            if not match:
                if target.optional:
                    return (
                        "SKIP",
                        f"Version pattern not found in optional file: {file_path}",
                    )
                return "ERROR", f"Version pattern not found in {file_path}"

            old_version = match.group(1)

            # Replace version
            new_line = replacement.format(version=new_version)
            content = re.sub(pattern, new_line, content, flags=re.MULTILINE)

            if content == original_content:
                return "SKIP", f"No changes made to {file_path}"

            return "OK", f"Updated {file_path.name}: {old_version} -> {new_version}"

        except Exception as e:
            return "ERROR", f"Error updating {file_path}: {e}"

    def update_all(self, new_version: str, dry_run: bool = False) -> list[str]:
        """Update version in all project files.

        更新所有项目文件中的版本。

        Args:
            new_version: New version string
            dry_run: If True, only show what would be changed

        Returns:
            List of status messages
        """
        messages = []

        # Validate version format
        if not self.validate_version(new_version):
            messages.append(
                f"[ERROR] Invalid version format: {new_version}. "
                "Expected format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
            )
            return messages

        # Get current version
        try:
            current_version = self.get_current_version()
            messages.append(f"[INFO] Current version: {current_version}")
            messages.append(f"[INFO] New version: {new_version}")
            messages.append("")
        except Exception as e:
            messages.append(f"[ERROR] Error getting current version: {e}")
            return messages

        if dry_run:
            messages.append("[DRY RUN] No files will be modified")
            messages.append("")

        # Update each file
        for target in self.files_to_update:
            status, message = self.update_file(target, new_version)

            if status == "OK":
                if not dry_run:
                    # Write the updated content
                    content = target.path.read_text(encoding="utf-8")
                    new_line = target.replacement.format(version=new_version)
                    content = re.sub(
                        target.pattern, new_line, content, flags=re.MULTILINE
                    )
                    target.path.write_text(content, encoding="utf-8")
                    messages.append(f"[OK] {message}")
                else:
                    messages.append(f"[DRY RUN] {message}")
            elif status == "SKIP":
                messages.append(f"[INFO] {message}")
            else:
                messages.append(f"[ERROR] {message}")

        return messages


def main():
    """Main entry point for the script.

    脚本的主入口点。
    """
    parser = argparse.ArgumentParser(
        description="Update version number across all project files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 0.2.0              Update version to 0.2.0
  %(prog)s 1.0.0 --dry-run    Preview changes without modifying files
        """,
    )
    parser.add_argument(
        "version", help="New version number (format: MAJOR.MINOR.PATCH)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )

    args = parser.parse_args()

    # Determine project root (script is in scripts/ directory)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Create updater and run
    updater = VersionUpdater(project_root)
    messages = updater.update_all(args.version, dry_run=args.dry_run)

    # Print all messages
    for message in messages:
        print(message)

    # Exit with error code if any errors occurred
    if any("[ERROR]" in msg for msg in messages):
        sys.exit(1)

    if not args.dry_run:
        print("\n[SUCCESS] Version update completed successfully!")
    else:
        print("\n[SUCCESS] Dry run completed. Use without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
