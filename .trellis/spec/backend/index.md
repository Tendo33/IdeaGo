# Backend Index

Read this before backend work on IdeaGo `saas`.

## Current Backend

IdeaGo is a FastAPI application under `src/ideago` with a typed LangGraph
Source Intelligence V2 pipeline. The hosted branch adds Supabase auth/profile
ownership, cookie-session recovery for LinuxDo OAuth, Supabase-backed report
persistence/runtime state/rate limiting, admin APIs, and Stripe billing
plumbing.

## Module Boundaries

- `api/`: FastAPI app factory, middleware, schemas, structured errors, rate
  limiting, runtime state, and route families for `analyze`, `reports`, `auth`,
  `admin`, `billing`, and `health`.
- `auth/`: Supabase JWT/profile helpers, LinuxDo cookie-session helpers,
  session store, and current-user/admin dependencies.
- `billing/`: Stripe checkout, portal, customer/subscription, webhook, and
  processed-event logic.
- `cache/`: `ReportRepository` protocol plus file and Supabase-backed
  implementations.
- `config/`: `Settings` and cached settings helpers.
- `contracts/`: shared protocols.
- `core/`: runtime context helpers.
- `llm/`: model invocation, prompt loading, and OpenAI-compatible settings.
- `models/`: project `BaseModel` and report/domain contracts.
- `observability/`: logging, audit, metrics, and error catalog helpers.
- `pipeline/`: LangGraph orchestration, query planning, extraction,
  aggregation, report assembly, confidence, and event emission.
- `sources/`: Tavily, Reddit, GitHub, Hacker News, App Store, Product Hunt.

## Hosted API Contract

- All public API routes are mounted under `/api/v1`.
- Route families on `saas`: `analyze`, `reports`, `auth`, `admin`, `billing`,
  `health`.
- Mutating API routes require `X-Requested-With` except Stripe webhook.
- Production CORS must be explicit; wildcard CORS is rejected in production.
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

## Security And Hosted State

- Never expose `SUPABASE_SERVICE_ROLE_KEY` or Stripe secrets to the browser.
- Hosted ownership checks should fail closed: missing owner means not found.
- Supabase sessions and LinuxDo cookie-backed recovery must keep the same user
  model aligned.
- `/auth/linuxdo/start` is a `POST`.
- Billing checkout, portal, and status route handlers intentionally return
  not-found while public pricing is hidden; the webhook remains mounted.

## More Specific Guides

- `python-package.md`
- `directory-structure.md`
- `type-safety.md`
- `config-logging.md`
- `models.md`
- `http-api-when-added.md`
- `database-when-added.md`
- `hosted-operations.md`
- `testing.md`
