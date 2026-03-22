# 01 · 20 分钟上手路径

> 目标：把项目真正跑起来，并确认“哪些入口是现在仍然有效的”。

## 0) 先校正认知

当前版本和早期文档相比，有 4 个关键变化：

1. 前端依赖管理固定为 `pnpm`
2. 公开接口只有最小健康检查，分析主链路默认需要登录
3. 前端路由已经迁到 `features/*`，不再走 `pages/*`
4. 后端除了分析链路，还包含 auth、billing、admin 等真实业务模块

## 1) 准备环境

```bash
uv sync --all-extras
pnpm --prefix frontend install
Copy-Item .env.example .env
```

最小建议配置：

- 必需：`OPENAI_API_KEY`
- 建议：`TAVILY_API_KEY`
- 如果你要完整验证登录流程：补好 Supabase 和 LinuxDo 相关配置

## 2) 启动服务

终端 A：

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

终端 B：

```bash
pnpm --prefix frontend dev
```

先验证公开健康检查：

```bash
curl http://localhost:8000/api/v1/health
```

你现在应该只看到最小返回，例如：

```json
{"status":"ok"}
```

这里故意不返回 `sources` 和 `dependencies`，详细健康信息在管理侧。

## 3) 用“正确的入口”开始阅读

### 3.1 服务启动入口

- `src/ideago/__main__.py`
  - `main()`：读取 settings，调用 `create_app()` 启动服务

### 3.2 FastAPI 装配入口

- `src/ideago/api/app.py`
  - `create_app()`：装配中间件、异常处理、路由、前端静态资源

### 3.3 前端应用入口

- `frontend/src/app/App.tsx`
  - 路由、主题、语言、认证上下文、受保护页面都在这里

### 3.4 报告链路入口

- `frontend/src/features/reports/ReportPage.tsx`
- `frontend/src/features/reports/components/useReportLifecycle.ts`
- `frontend/src/lib/api/useSSE.ts`

这三个文件决定了“报告页如何进入 processing、何时订阅 SSE、何时回退到补拉状态、何时展示 ready/error/cancelled”。

## 4) 如何体验一次真实分析

最简单的方式不是手写匿名 `curl`，而是：

1. 打开前端页面
2. 完成登录
3. 在首页输入 idea
4. 观察页面跳转到 `/reports/:id`
5. 同时打开浏览器 Network 看 `/analyze`、`/reports/:id/stream`、`/reports/:id`

如果你已经有有效 token，也可以手工请求：

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer <token>" \
  -H "X-Requested-With: IdeaGo" \
  -H "Content-Type: application/json" \
  -d '{"query":"An AI assistant for indie game analytics"}'
```

拿到 `report_id` 后：

```bash
curl -N http://localhost:8000/api/v1/reports/<report_id>/stream \
  -H "Authorization: Bearer <token>"
```

## 5) 你在这一篇必须确认的入口函数

- `src/ideago/api/routes/analyze.py:start_analysis()`
- `src/ideago/api/routes/analyze.py:_run_pipeline()`
- `src/ideago/api/routes/analyze.py:_stream_events()`
- `src/ideago/api/dependencies.py:get_orchestrator()`
- `src/ideago/pipeline/langgraph_engine.py:LangGraphEngine.run()`
- `frontend/src/features/reports/components/useReportLifecycle.ts:useReportLifecycle()`
- `frontend/src/lib/api/useSSE.ts:useSSE()`

## 6) 为什么这几个入口必须掌握

因为后续几乎所有改动都会穿过它们：

- API 契约调整，会碰 `api/routes/*` 和 `lib/api/client.ts`
- 认证、权限、配额问题，会碰 `auth/*`、`api/routes/auth.py`、`analyze.py`
- pipeline 顺序变化，会碰 `langgraph_engine.py` 和 `nodes.py`
- 进度体验和报告页异常恢复，会碰 `useReportLifecycle.ts` 和 `useSSE.ts`

## 7) 动手任务

任务：

1. 跑起前后端
2. 验证 `/api/v1/health`
3. 打开 `src/ideago/api/app.py`，确认有哪些中间件
4. 打开 `frontend/src/app/App.tsx`，确认 `/reports/:id` 和 `/reports` 的路由定义
5. 如果你有登录环境，跑一次真实分析并观察 SSE

完成标准：

- 你能说清楚“为什么现在不能再把匿名 `curl /analyze` 当成默认学习入口”

---

下一篇：`docs/mentor/02-request-lifecycle.md`
