# Scripts And Maintenance

Project maintenance scripts live in `scripts/`.

## Current Scripts

- `scripts/rename_package.py`: renames the Python package and project text
  references. Inspect the diff and reinstall editable package afterwards.
- `scripts/update_version.py`: updates backend version in `pyproject.toml` and
  `src/ideago/__init__.py`; it does not update `frontend/package.json`.
- `scripts/setup_pre_commit.py`: helper for `uv run pre-commit install`.
- `scripts/run_vulture.py`: dead-code detection workflow.
- `scripts/generate_release_notes.py`: release-note draft generation.
- `scripts/debug_producthunt_chain.py`: Product Hunt source debugging helper.
- `scripts/benchmark_extract_token_subject.py`: extractor/token subject
  benchmark helper.

## Commands

```bash
uv run pre-commit install
uv run pre-commit run --all-files
python scripts/update_version.py 0.4.0 --dry-run
python scripts/rename_package.py my_new_package --dry-run
```

## Rules

- Update script docs and tests when script behavior changes.
- Keep frontend package manager behavior as `pnpm`.
- Do not reintroduce legacy AI-doc adapter or sync scripts.
