#!/usr/bin/env python3
"""Setup script for pre-commit hooks.

This script automates the installation and configuration of pre-commit hooks
for automatic code formatting and linting.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> int:
    """Run a command and return the exit code.

    Args:
        cmd: Command to run as a list of strings
        cwd: Working directory for the command

    Returns:
        Exit code of the command
    """
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Error: Command '{cmd[0]}' not found. Please ensure it's installed.")
        return 1


def check_pre_commit_installed() -> bool:
    """Check if pre-commit is installed.

    Returns:
        True if pre-commit is installed, False otherwise
    """
    try:
        result = subprocess.run(
            ["pre-commit", "--version"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            print(f"✅ pre-commit is installed: {result.stdout.strip()}")
            return True
        return False
    except FileNotFoundError:
        return False


def install_pre_commit_hooks(project_root: Path) -> int:
    """Install pre-commit hooks.

    Args:
        project_root: Root directory of the project

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    config_file = project_root / ".pre-commit-config.yaml"

    if not config_file.exists():
        print(f"❌ Pre-commit config file not found: {config_file}")
        return 1

    print("📦 Installing pre-commit hooks...")
    return run_command(["pre-commit", "install"], cwd=project_root)


def update_pre_commit_hooks(project_root: Path) -> int:
    """Update pre-commit hooks to latest versions.

    Args:
        project_root: Root directory of the project

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    print("🔄 Updating pre-commit hooks...")
    return run_command(["pre-commit", "autoupdate"], cwd=project_root)


def test_pre_commit_hooks(project_root: Path) -> int:
    """Test pre-commit hooks on all files.

    Args:
        project_root: Root directory of the project

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    print("🧪 Testing pre-commit hooks on all files...")
    return run_command(["pre-commit", "run", "--all-files"], cwd=project_root)


def main() -> int:
    """Main entry point for the setup script.

    Returns:
        Exit code
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Setup pre-commit hooks for automatic code formatting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_pre_commit.py                # Install hooks
  python scripts/setup_pre_commit.py --update       # Update hooks
  python scripts/setup_pre_commit.py --test         # Test hooks
  python scripts/setup_pre_commit.py --all          # Install, update, and test
        """,
    )

    parser.add_argument(
        "--update", action="store_true", help="Update hooks to latest versions"
    )

    parser.add_argument("--test", action="store_true", help="Test hooks on all files")

    parser.add_argument(
        "--all", action="store_true", help="Install, update, and test hooks"
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        help="Root directory of the project (default: parent of script directory)",
    )

    args = parser.parse_args()

    # Determine project root
    project_root = args.project_root
    if project_root is None:
        project_root = Path(__file__).parent.parent

    if not project_root.exists():
        print(f"❌ Project root does not exist: {project_root}")
        return 1

    print(f"📁 Project root: {project_root}")

    # Check if pre-commit is installed
    if not check_pre_commit_installed():
        print("❌ pre-commit is not installed.")
        print("💡 Install it with: pip install pre-commit")
        print("💡 Or with uv: uv add --dev pre-commit")
        return 1

    exit_code = 0

    try:
        if args.all:
            # Install, update, and test
            exit_code = install_pre_commit_hooks(project_root)
            if exit_code == 0:
                exit_code = update_pre_commit_hooks(project_root)
            if exit_code == 0:
                exit_code = test_pre_commit_hooks(project_root)
        else:
            # Install hooks (default action)
            if not (args.update or args.test):
                exit_code = install_pre_commit_hooks(project_root)

            # Update if requested
            if args.update and exit_code == 0:
                exit_code = update_pre_commit_hooks(project_root)

            # Test if requested
            if args.test and exit_code == 0:
                exit_code = test_pre_commit_hooks(project_root)

        if exit_code == 0:
            print("\n✅ Pre-commit setup completed successfully!")
            print("💡 Now ruff format will run automatically on every commit.")
            print("💡 To bypass hooks temporarily, use: git commit --no-verify")
        else:
            print("\n❌ Pre-commit setup failed.")

        return exit_code

    except KeyboardInterrupt:
        print("\n⚠️  Setup interrupted by user.")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
