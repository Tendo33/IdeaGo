# 02 · 一次请求的完整生命周期

> 目标：把“看似复杂的系统”压缩成可追踪的 1 条黄金路径。

## 总览：从点击到报告

1. 前端 `HomePage` 提交 query。
2. 后端 `POST /api/v1/analyze` 返回 `report_id`。
3. 后台任务 `_run_pipeline()` 跑 LangGraph。
4. 前端订阅 `/reports/{id}/stream` 接收进度事件。
5. 报告落盘到 `FileCache`，前端拉取详情渲染。

## Step 1：前端发起分析

- 文件：`frontend/src/pages/HomePage.tsx`
  - `handleSubmit()` 调用 `startAnalysis()`
- 文件：`frontend/src/api/client.ts`
  - `startAnalysis(query)` -> `POST /api/v1/analyze`

关键点：
- 前端本地限制 query 长度（5~1000）
- 后端还会再次校验（双保险）

## Step 2：后端接收并创建任务

- 文件：`src/ideago/api/routes/analyze.py`
  - `start_analysis()`

执行细节：
- 计算 `query_hash = sha256(query)[:16]`
- 调用 `reserve_processing_report(query_hash, report_id)` 做并发去重
- `asyncio.create_task(_run_pipeline(query, report_id))`
- 立即返回 `AnalyzeResponse(report_id=...)`

这解释了：
- 为什么接口响应快（异步后台任务）
- 为什么同 query 并发可能拿同一 `report_id`

## Step 3：后台运行 Pipeline

- 文件：`src/ideago/api/routes/analyze.py`
  - `_run_pipeline()`
- 文件：`src/ideago/api/dependencies.py`
  - `get_orchestrator()`

运行顺序：
- `cache.put_status(..., "processing")`
- `orchestrator.run(query, callback=..., report_id=...)`
- 成功：`cache.put_status(..., "complete")`
- 异常：写 `failed`，并发 `error` 事件
- 取消：写 `cancelled`，并发 `cancelled` 事件

## Step 4：LangGraph 节点链

- 文件：`src/ideago/pipeline/langgraph_engine.py`
  - `_build_graph()`

图中节点顺序：
- `parse_intent`
- `cache_lookup`
- `fetch_sources`
- `extract_map`
- `aggregate`
- `assemble_report`
- `persist_report`

分支规则：
- `cache_lookup` 命中直接结束
- `aggregate` 出错走 `terminal_error`

## Step 5：每个节点干了什么

- 文件：`src/ideago/pipeline/nodes.py`

- `parse_intent_node`
  - 调 `IntentParser.parse()`，发 `intent_started/intent_parsed`
- `cache_lookup_node`
  - 用 `intent.cache_key` 查缓存
- `fetch_sources_node`
  - 并发调用每个可用数据源 `search()`
- `extract_map_node`
  - 每源调用 `Extractor.extract()`，失败降级为 `_degrade_raw_to_competitors`
- `aggregate_node`
  - 调 `Aggregator.aggregate()` 去重 + 结论
- `assemble_report_node`
  - 生成 `ResearchReport` + 置信度/证据/成本元数据
- `persist_report_node`
  - 写缓存并发 `report_ready`

## Step 6：SSE 实时事件如何送到前端

### 后端

- 文件：`src/ideago/api/routes/analyze.py`
  - `stream_progress()` -> `_stream_events()` -> `EventSourceResponse`
- 文件：`src/ideago/api/dependencies.py`
  - `ReportRunState.publish()/subscribe()`

机制要点：
- 新订阅者先收到 `history_snapshot()`（补历史）
- 运行中通过 queue 推送新事件
- 长时间无事件发 `ping`
- 若只剩 status 文件也能推导 terminal 事件

### 前端

- 文件：`frontend/src/api/useSSE.ts`
  - `useSSE(reportId)`

机制要点：
- `fetch` + 解析 `event:`/`data:` block
- 指数退避重连（1s -> 15s）
- 终止条件：`report_ready` / `error` / `cancelled`

## Step 7：报告读取与渲染

- 文件：`frontend/src/pages/report/useReportLifecycle.ts`
  - `getReportWithStatus()` + `getReportRuntimeStatus()` 联合状态机
- 文件：`frontend/src/pages/report/ReportContentPane.tsx`
  - 渲染 Hero / 置信度 / 竞品列表 / 对比面板

关键点：
- 即便 SSE 已 complete，前端也会补拉详情，处理“状态到了但报告还没落盘”的窗口期

## 动手任务（20 分钟）

请你做一次“带日志追踪”：

```bash
curl -X POST http://localhost:8000/api/v1/analyze -H "Content-Type: application/json" -d '{"query":"AI note taking app for meetings"}'
curl -N http://localhost:8000/api/v1/reports/<report_id>/stream
curl http://localhost:8000/api/v1/reports/<report_id>/status
```

边跑边打开：
- `src/ideago/api/routes/analyze.py`
- `src/ideago/pipeline/langgraph_engine.py`
- `src/ideago/pipeline/nodes.py`
- `frontend/src/api/useSSE.ts`

完成标准：
- 你能解释“为什么前端既要 SSE 又要轮询/补拉状态”。

---

下一篇：`docs/mentor/03-agent-core.md`（核心组件如何装配、如何扩展）。
