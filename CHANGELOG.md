# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.7] - 2026-03-27

### Added
- Introduced a typed `query_planning_rewriting` stage so retrieval now flows through explicit intent parsing, query planning, platform adaptation, extraction, and aggregation.

### Changed
- Improved competitor discovery prompts, intent anchors, and platform-specific query shaping to preserve exact entities such as `Claude Code`.
- Updated GitHub and Tavily retrieval heuristics to favor exact-anchor and product-page matches over generic or blog-heavy results.
- Aligned shared report contracts and reusable report card UI between backend and frontend.
- Unified release version markers across backend, frontend, and version tooling.

### Fixed
- Hardened extractor evidence normalization so optional fields like `None` no longer cause valid evidence items to be skipped.
- Ensured the main-branch orchestration wiring instantiates the new query planner cleanly.

## [0.3.4] - 2026-03-19

### Changed
- Bumped backend and frontend versions for release.

## [0.3.5] - 2026-03-26

### Changed
- Refreshed `main` branch README content and structure for a clearer release-facing presentation.
- Aligned release version markers across backend, frontend, and lockfiles.

## [0.2.11] - 2026-03-15

### Changed
- Bumped version for release.

## [0.2.10] - 2026-03-13

### Changed
- Refined bilingual README content and formatting for clarity and consistency.

## [0.2.9] - 2026-03-12

### Added
- Added optional Tavily API base URL support and aligned related configuration inputs.

### Changed
- Increased OpenAI API timeout and extraction timeout defaults for improved reliability, plus enhanced aggregation-failure logging.
- Updated Tavily base URL documentation and design notes.
- Ignored worktree directory to reduce repo noise.
- Optimized images.

### Fixed
- Fixed asyncio event loop shutdown during test teardown.

## [0.2.8] - 2026-03-09

### Changed
- Removed the temporary `APP_API_KEY` / `X-API-Key` authentication path across backend, frontend, runtime injection, and deployment docs.
- Simplified runtime/container wiring by removing `env-config.js` injection and related dev/prod shims.
- Updated report stepper to a data-driven model with dynamic source stages, including Product Hunt.
- Updated i18n text entries and aligned zh/en stepper keys.

### Fixed
- Fixed SQLite checkpoint lifecycle leak on task cancellation by making saver enter/exit cancellation-safe.
- Hardened API test lifecycle cleanup and TestClient shutdown handling to avoid unclosed resource warnings.
- Optimized report rendering hotspots by replacing repeated rank lookups with precomputed index maps.

## [0.2.7] - 2026-03-06

### Changed
- Completed and normalized historical changelog entries for versions `0.2.1` through `0.2.5`.
- Corrected version compare links for `0.2.1` to `0.2.6`.

## [0.2.6] - 2026-03-06

### Added
- Platform icons and sourcing information in `ComparePanel`, `CompetitorCard`, and `CompetitorRow` for better visual identification of source platforms.
- Support for 'Product Hunt' as a competitor source and filtering option.
- Breathing animation to the app title highlight for improved aesthetics.
- Intent parser enhancements for better keyword extraction and query generation.
- Competitor fusion logic to merge duplicates across different sources.

### Changed
- Refactored `EvidenceCostCard` to improve evidence item rendering and expansion logic.
- Improved competitor ranking logic to maintain consistent ordering across grid and list views.
- Updated UI color scheme and shadows for a more polished look.
- Normalized GitHub search queries to improve results.
- Enhanced pipeline node logging to track per-source competitor extraction counts, with related test coverage.

### Fixed
- Decoded Hacker News HTML content before downstream processing.
- Added SPA deep-link fallback in FastAPI to prevent 404s on direct route refresh.

## [0.2.5] - 2026-03-06

### Added
- Product Hunt channel setup documentation.

## [0.2.4] - 2026-03-05

### Added
- SSE CRLF parsing test coverage.

### Changed
- Ensured competitor grid uses a single-column layout.
- Refreshed website palette and visual styles.
- Improved App Store extraction quality.

## [0.2.3] - 2026-03-05

### Added
- Temporary API access guard middleware.
- Temporary frontend runtime config injection at container startup.
- Temporary dev-server runtime config shim to avoid local 404 noise.

### Changed
- Replaced `EventSource` with `fetch + ReadableStream` in `useSSE.ts` to support custom request headers for SSE streams
- Docker image is now fully stateless (no secrets baked in); CI builds a generic image and injects runtime config via environment variables

### Changed (Breaking)
- **Breaking:** refactored module layout by moving `setting/context/protocols/logger_util` out of `utils` into `config/settings`, `core/context`, `contracts/protocols`, and `observability/log_config`; removed legacy import paths.
- Simplified default app configuration: removed `APP_NAME`/`APP_VERSION` and kept only `ENVIRONMENT` (dropped `DEBUG`) from baseline runtime mode env vars.
- Unified retry implementation by reusing `decorator_utils` retry internals from `common_utils`.
- Removed `Settings/get_settings/reload_settings` re-exports from `common_utils` to reduce cross-module coupling.
- Unified JSON write contracts so `write_json` and `async_write_json` both return `bool`.
- Unified current date/time defaults to UTC in `date_utils` (`get_current_date`/`get_current_time`), with `use_utc=False` for local time.

## [0.2.2] - 2026-03-04

### Fixed
- Resolved Hatchling editable build failure.

## [0.2.1] - 2026-03-04

### Added
- Initial frontend core UI components and pages (search input, section navigation, comparison panel, and global styles).
- Docker build workflow on tag push.

### Changed
- Modernized bilingual README files.

## [0.2.0] - 2026-02-20

### Changed
- **Breaking:** narrowed `ideago.utils` top-level exports to a stable core API surface.
- Moved non-core utility imports to submodule-based usage in tests and documentation.
- Enforced test coverage gate with `--cov-fail-under=80`.
- Removed duplicated dependency declarations by dropping `[dependency-groups]`.
- Tightened sdist exclusions to keep assistant/tooling and local artifacts out of release packages.
- Removed unused CLI placeholder configuration from project metadata.

### Added
- Async decorators support (`async_timing_decorator`, `async_retry_decorator`, `async_catch_exceptions`)

## [0.1.0] - 2026-01-20

### Added
- Initial public IdeaGo release
- **Utils Module**
  - `logger_util`: Loguru-based logging configuration and management
  - `json_utils`: JSON read/write and serialization utilities
  - `file_utils`: File system operations (sync and async)
  - `decorator_utils`: Common decorators (timing, retry, catch_exceptions, etc.)
  - `date_utils`: Date and time manipulation utilities
  - `common_utils`: General utility functions (list chunking, dict operations, etc.)
  - `setting`: Pydantic Settings-based configuration management
  - `context`: Thread-safe runtime context storage
- **Models Module**
  - Base Pydantic models for data validation
- **Scripts**
  - `rename_package.py`: Package renaming utility
  - `setup_pre_commit.py`: Git hooks configuration
  - `update_version.py`: Version update utility
  - `run_vulture.py`: Dead code detection
- **Documentation**
  - Settings guide
  - Models guide
  - SDK usage guide
  - Pre-commit guide
- **Configuration**
  - `pyproject.toml` with full project metadata
  - Ruff linting and formatting configuration
  - Pytest and coverage configuration
  - Pre-commit hooks configuration

[Unreleased]: https://github.com/Tendo33/ideago/compare/v0.3.5...HEAD
[0.3.5]: https://github.com/Tendo33/ideago/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/Tendo33/ideago/compare/v0.3.3...v0.3.4
[0.2.11]: https://github.com/Tendo33/ideago/compare/v0.2.10...v0.2.11
[0.2.10]: https://github.com/Tendo33/ideago/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/Tendo33/ideago/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/Tendo33/ideago/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/Tendo33/ideago/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/Tendo33/ideago/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/Tendo33/ideago/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/Tendo33/ideago/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Tendo33/ideago/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Tendo33/ideago/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Tendo33/ideago/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Tendo33/ideago/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Tendo33/ideago/releases/tag/v0.1.0
