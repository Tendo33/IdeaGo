# Backend Index

Read this before backend work on IdeaGo `main`.

## Current Backend

IdeaGo is a FastAPI application under `src/ideago` with a typed LangGraph
Source Intelligence V2 pipeline. The `main` branch is anonymous and
personal-deployment oriented. It uses local file cache report persistence and
SQLite checkpoints, and it must boot without Supabase, Stripe, LinuxDo, account,
profile, quota, admin, or billing settings.

## Module Boundaries

- `api/`: FastAPI app factory, dependencies, middleware, schemas, structured
  errors, and route families for `analyze`, `reports`, and `health`.
- `cache/`: report cache abstractions and local file cache implementation.
- `config/`: `Settings` and cached settings helpers.
- `contracts/`: shared protocols.
- `core/`: runtime context helpers.
- `llm/`: model invocation, prompt loading, and OpenAI-compatible settings.
- `models/`: project `BaseModel` and report/domain contracts.
- `observability/`: logging and metrics helpers.
- `pipeline/`: LangGraph orchestration, query planning, source fetch,
  extraction, aggregation, report assembly, confidence, and event emission.
- `sources/`: Tavily, Reddit, GitHub, Hacker News, App Store, Product Hunt.
- `utils/`: shared file, JSON, date, decorator, text, and common helpers.

## API Contract

- All public API routes are mounted under `/api/v1`.
- Route families on `main`: `analyze`, `reports`, `health`.
- No auth, billing, profile, admin, quota, or hosted ownership routes on
  `main`.
- Analyze, report detail, report status, report export, and history are
  anonymous.
- Mutating API routes require `X-Requested-With`.
- Anonymous report reads, export, status, and streams may carry
  `X-Session-Id` for client-scoped rate-limit isolation.
- API routes must win before the SPA static fallback. Unknown `/api/*` paths
  return API errors, not `index.html`.

## Pipeline Contract

- Reports are decision-first and Source Intelligence V2 shaped.
- Keep pipeline state, extraction outputs, and report assembly typed.
- `pipeline/merger.py` is deterministic competitor dedupe only.
- Whitespace and entry-wedge synthesis belongs in `pipeline/aggregator.py`.
- Source roles stay fixed unless a task explicitly changes them: Tavily,
  Reddit, GitHub, Hacker News, App Store, Product Hunt.
- Ranking stays opportunity-first: pain, commercial, migration, and whitespace
  evidence should beat raw popularity when signals conflict.
- Runtime source concurrency overrides must be restored after each fetch run.

## Security And Runtime State

- CSRF protection uses `X-Requested-With` for mutating routes.
- Rate limiting is in-memory and split across analyze, report read, status,
  stream, and mutation flows.
- Production CORS must be explicit.
- API responses keep a baseline `Content-Security-Policy`.
- Production logging defaults keep verbose exception backtrace/diagnose output
  off.
- Never log raw secrets, tokens, auth headers, or sensitive personal data.

## More Specific Guides

- `python-package.md`
- `directory-structure.md`
- `type-safety.md`
- `config-logging.md`
- `models.md`
- `http-api-when-added.md`
- `database-when-added.md`
- `testing.md`
