# 06 · 分层练习任务（从读到改）

> 建议按难度顺序做。每个任务都给出目标、关键文件、最小验证。

## Level 1：理解与追踪（不改代码）

### 任务 1：画出你的请求时序图

- 目标：把 `analyze -> stream -> report` 画成 8~12 个步骤
- 关键文件：
  - `src/ideago/api/routes/analyze.py`
  - `src/ideago/pipeline/langgraph_engine.py`
  - `frontend/src/api/useSSE.ts`
- 验证：用 `curl` 跑一遍并对照事件顺序

### 任务 2：解释并发去重

- 目标：解释为什么同 query 多请求返回同一个 `report_id`
- 关键文件：`src/ideago/api/dependencies.py`
- 验证：阅读测试 `tests/test_api.py::test_analyze_endpoint_deduplicates_concurrent_same_query`

## Level 2：小范围改动（低风险）

### 任务 3：新增一个 SSE 事件文案映射（前端）

- 目标：在报告进度显示里加入更友好的事件描述
- 关键文件：
  - `frontend/src/api/useSSE.ts`
  - 报告进度相关组件（`frontend/src/pages/report/ReportProgressPane.tsx`）
- 验证：`npm --prefix frontend run test`

### 任务 4：扩展 status 导出信息（后端）

- 目标：让 `/reports/{id}/status` 返回额外可诊断字段（例如 message 细化）
- 关键文件：
  - `src/ideago/api/routes/reports.py`
  - `src/ideago/api/schemas.py`
- 验证：`uv run pytest tests/test_api.py -q`

## Level 3：跨模块改动（中等）

### 任务 5：新增报告字段并前后端联动

- 目标：新增一个报告字段并在 UI 展示
- 关键文件：
  - `src/ideago/models/research.py`
  - `src/ideago/pipeline/nodes.py`（组装字段）
  - `frontend/src/types/research.ts`
  - `frontend/src/pages/report/ReportContentPane.tsx`
- 验证：
  - `uv run pytest tests/test_research_models.py -q`
  - `npm --prefix frontend run typecheck`

### 任务 6：调整聚合降级策略

- 目标：当聚合失败时，给出更结构化的 fallback 说明
- 关键文件：
  - `src/ideago/pipeline/nodes.py:aggregate_node`
  - `src/ideago/pipeline/aggregator.py`
- 验证：`uv run pytest tests/test_langgraph_engine.py -q`

## Level 4：特性扩展（高价值）

### 任务 7：新增数据源（完整链路）

- 目标：接入一个新 source（示例：Reddit/Hugging Face Spaces）
- 关键文件：
  - `src/ideago/models/research.py`（Platform）
  - `src/ideago/sources/<new>_source.py`
  - `src/ideago/api/dependencies.py`（register）
  - `frontend/src/types/research.ts`
  - `frontend/src/pages/report/useCompetitorFilters.ts`（平台过滤）
- 验证：
  - `uv run pytest tests/test_sources.py -q`
  - `npm --prefix frontend run test`

### 任务 8：增强 SSE 断流恢复策略

- 目标：改善“流结束但报告未就绪”的用户体验
- 关键文件：
  - `frontend/src/api/useSSE.ts`
  - `frontend/src/pages/report/useReportLifecycle.ts`
- 验证：
  - `npm --prefix frontend run test`
  - 手工断网/限速观察重连行为

## 任务执行模板（建议复制）

```md
### 任务名称
- 目标：
- 改动文件：
- 预期风险：
- 验证命令：
- 回滚方案：
```

## 动手任务（现在就做）

从 Level 2 选一个你最有把握的任务，先只写“执行模板”，我可以帮你做一次 review 再开改。

---

下一篇：`docs/mentor/07-troubleshooting.md`（排错速查表）。
