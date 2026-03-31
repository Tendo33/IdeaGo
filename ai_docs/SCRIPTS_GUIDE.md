# Scripts Guide

Project maintenance scripts live in `scripts/`.

This guide documents the scripts that actually exist in this repository.

## `rename_package.py`

Renames the Python package from `ideago` to a new package name.

What it updates:

- `src/ideago/` directory rename
- Python imports and text references across supported source and doc files
- project/package name references in repository text files

Examples:

```bash
python scripts/rename_package.py my_new_package --dry-run
python scripts/rename_package.py my_new_package
```

After running it:

1. inspect `git diff`
2. reinstall the editable package
3. run verification

```bash
uv pip install -e .
uv run pytest
```

## `update_version.py`

Updates the backend package version in the files the script currently supports:

- `pyproject.toml`
- `src/ideago/__init__.py`

Examples:

```bash
python scripts/update_version.py 0.4.0 --dry-run
python scripts/update_version.py 0.4.0
```

Important:

- the current script does not update `frontend/package.json`
- if you need backend and frontend version numbers aligned, update the frontend version separately

## `setup_pre_commit.py`

Helper for installing project pre-commit hooks.

If you prefer the direct command, this is equivalent to:

```bash
uv run pre-commit install
```

## `run_vulture.py`

Runs the dead-code detection workflow used by this repo.

Use it when cleaning up stale modules or checking whether refactors left orphaned code behind.

## `generate_release_notes.py`

Generates release-note content from the current repository state.

Use it when preparing a release summary or changelog draft.

## `debug_producthunt_chain.py`

Debug helper for the Product Hunt source path and related retrieval/debugging workflows.

Use it when investigating Product Hunt source behavior rather than as a normal development step.
