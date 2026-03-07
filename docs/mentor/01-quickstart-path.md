# 01 · 20 分钟上手路径

> 目标：不靠“猜”，直接跑起来 + 找到必须掌握的入口函数。

## 0) 准备

```bash
uv sync --all-extras
npm --prefix frontend install
cp .env.example .env
```

最小可跑配置：
- 必需：`OPENAI_API_KEY`
- 建议：`TAVILY_API_KEY`

## 1) 启动服务

终端 A：

```bash
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
```

终端 B：

```bash
npm --prefix frontend run dev
```

验证：

```bash
curl http://localhost:8000/api/v1/health
```

你应该看到 `status` 与 `sources` 字段。

## 2) 手动触发一次分析

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"An AI assistant for indie game analytics"}'
```

拿到 `report_id` 后：

```bash
curl -N http://localhost:8000/api/v1/reports/<report_id>/stream
```

观察事件顺序是否包含：
- `intent_started`
- `source_started`
- `extraction_completed`
- `aggregation_completed`
- `report_ready`

## 3) 必读入口文件（按顺序）

### 3.1 服务启动入口

- `src/ideago/__main__.py`
  - `main()`：读取 settings，创建 app，启动 uvicorn

### 3.2 FastAPI 组装入口

- `src/ideago/api/app.py`
  - `create_app()`：挂路由 + 中间件 + SPA fallback

### 3.3 分析任务入口

- `src/ideago/api/routes/analyze.py`
  - `start_analysis()`：生成/复用 `report_id`
  - `reserve_processing_report()`（在 dependencies 中）：同 query 并发去重

### 3.4 后台执行入口

- `src/ideago/api/routes/analyze.py`
  - `_run_pipeline()`：设置状态、执行 orchestrator、处理失败/取消

### 3.5 图执行入口

- `src/ideago/pipeline/langgraph_engine.py`
  - `run()`：通过 LangGraph 执行整条 pipeline

## 4) 为什么这套入口是“必须掌握”的

因为任何功能改动几乎都会穿过这 5 层：
- API 契约变更 -> `api/routes`
- 依赖注入/组件替换 -> `api/dependencies`
- 处理流程变更 -> `pipeline/langgraph_engine.py` + `pipeline/nodes.py`
- 模型/来源策略变更 -> `pipeline/*` + `sources/*`

## 5) 动手任务（15 分钟）

任务：
1. 启动一次分析。
2. 用 `curl -N` 观察 SSE。
3. 同时打开 `src/ideago/api/routes/analyze.py`，定位：
   - `start_analysis()`
   - `_run_pipeline()`
   - `_stream_events()`
4. 解释它们各自做什么（每个函数一句话）。

完成标准：
- 你可以回答“为什么同样 query 的并发请求会拿到同一个 report_id”。

---

下一篇：`docs/mentor/02-request-lifecycle.md`（从请求到报告，逐函数追踪）。
