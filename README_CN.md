<div align="center">
  <img src="docs/assets/icon_new.png" alt="IdeaGo Icon" width="120" />
</div>

# IdeaGo

<p align="center">
  <img src="docs/assets/banner_new.png" alt="IdeaGo Banner" width="100%" />
</p>

IdeaGo 是一个 Source Intelligence V2 创业想法验证系统。当前 `main` 分支是匿名个人部署版：不依赖 Supabase，不需要登录，不包含支付和账户体系。

简体中文 | [English](README.md)

## 分支职责

- `main`：个人/开源部署版。匿名分析、匿名历史、匿名报告查看与导出，本地文件缓存，本地 SQLite checkpoint。
- `saas`：与 `main` 共享同一套核心产品能力，但额外包含登录、支付、Profile、Admin 和 SaaS 专属环境变量。

长期同步规则：

- 公共能力统一先到 `main`
- 再从 `main` 合并到 `saas`
- 商业化差异仅保留在 `saas`

## 它能做什么

IdeaGo 会把一句创业想法转成决策优先的报告，包含：

- 推荐结论与 why-now
- pain signals
- commercial signals
- whitespace opportunities
- competitors
- evidence 与 confidence

核心数据源：

- Tavily
- Reddit
- GitHub
- Hacker News
- App Store
- Product Hunt

## `main` 分支运行模型

- 后端公开路由：`/api/v1/analyze`、`/api/v1/reports`、`/api/v1/health`
- 报告持久化：本地 `FileCache`
- 管道 checkpoint：本地 SQLite
- 进度更新：SSE
- 典型流程：匿名提交想法 -> 实时查看进度 -> 打开报告 -> 从 history 重新打开 -> 导出 Markdown

## 快速开始

### 前置要求

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- Node.js 20+
- `pnpm`

### 安装依赖

```bash
uv sync --all-extras
pnpm --prefix frontend install
```

### 配置环境

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

最小可用配置：

- 必需：`OPENAI_API_KEY`
- 推荐：`TAVILY_API_KEY`

### 开发模式

终端 1：

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

终端 2：

```bash
pnpm --prefix frontend dev
```

打开：

- 前端：[http://localhost:5173](http://localhost:5173)
- 后端健康检查：[http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 单进程本地运行

```bash
pnpm --prefix frontend build
uv run python -m ideago
```

打开：[http://localhost:8000](http://localhost:8000)

## 配置说明

`main` 里最重要的配置：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TAVILY_API_KEY`
- `CACHE_DIR`
- `ANONYMOUS_CACHE_TTL_HOURS`
- `FILE_CACHE_MAX_ENTRIES`
- `LANGGRAPH_CHECKPOINT_DB_PATH`
- `CORS_ALLOW_ORIGINS`

Reddit 说明：

- `REDDIT_CLIENT_ID` 和 `REDDIT_CLIENT_SECRET` 是可选的。
- 如果缺失，只要 `REDDIT_ENABLE_PUBLIC_FALLBACK=true`，`main` 仍可退化到公开只读抓取。

## API 概览

- `POST /api/v1/analyze`
- `GET /api/v1/reports`
- `GET /api/v1/reports/{id}`
- `GET /api/v1/reports/{id}/status`
- `GET /api/v1/reports/{id}/stream`
- `GET /api/v1/reports/{id}/export`
- `DELETE /api/v1/reports/{id}`
- `DELETE /api/v1/reports/{id}/cancel`
- `GET /api/v1/health`

`main` 不暴露 auth、billing、pricing、profile、admin 相关接口。

## 开发规则

- 报告契约必须保持 decision-first。
- 后端 report schema 与前端共享类型要同步维护。
- `pipeline/merger.py` 只做确定性竞品去重。
- whitespace 和 entry-wedge 合成只放在 `pipeline/aggregator.py`。
- 不要把 SaaS 运行时依赖重新加回 `main`。

## 验证命令

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

## 部署

`main` 分支的个人部署说明见 [DEPLOYMENT.md](DEPLOYMENT.md)。

SaaS 部署文档只保留在 `saas` 分支，不再放在 `main`。
