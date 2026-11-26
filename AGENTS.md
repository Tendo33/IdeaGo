# IdeaGo

AI 驱动的创业点子竞品调研产品：FastAPI 后端 + React/Vite 前端。本文件是唯一入口，`CLAUDE.md` 只做指针。

## 双版本分支

- `main`：匿名 / 个人部署版。
- `saas`：托管 / 商业版，含认证、计费、Supabase、配额与后台。
- 共享的产品改动优先落 `main`，再合到 `saas`。
- **不要把 saas 专有的运行时依赖（auth、billing、Supabase、quota、admin）搬回 `main`。**
- 动手前先看当前分支，改动要落在正确的版本上。

## 结构

- `src/ideago/`：后端包。`api/app.py` 是 FastAPI 入口，其余按 `auth/`、`billing/`、`llm/`、`pipeline/`、`sources/`、`models/`、`observability/` 分层。
- `frontend/`：React + Vite，包管理固定 pnpm（`frontend/pnpm-lock.yaml`）。
- `supabase/`：迁移与策略。`eval/`：评测。`docs/`：设计文档。
- `skills/`、`.agents/`：agent 技能目录，不要随手删。

## 命令

```bash
uv sync                          # 后端依赖
uv run python -m ideago          # 本地起后端
uv run pytest                    # 全量测试，带覆盖率
uv run ruff check .
pnpm --prefix frontend install
pnpm --prefix frontend run dev
pnpm --prefix frontend run lint
pnpm --prefix frontend run test
pnpm --prefix frontend run build
```

Python `>=3.10`。

## 验证

改了哪一层就跑到哪一层：后端改动跑 pytest 与 ruff，前端改动跑 lint、test、build。没跑过对应检查不要说完成。
