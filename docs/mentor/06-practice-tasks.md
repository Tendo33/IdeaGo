# 06 · 分层练习任务

> 这些任务按“理解 -> 小改 -> 跨模块 -> 扩展”组织，适合拿来训练你对当前代码结构的掌握程度。

## Level 1：理解与追踪

### 任务 1：画出真实请求时序图

- 目标：把“匿名发起分析 -> SSE -> 报告 ready”画成 8 到 12 步
- 关键文件：
  - `src/ideago/api/routes/analyze.py`
  - `src/ideago/api/dependencies.py`
  - `frontend/src/features/reports/components/useReportLifecycle.ts`
  - `frontend/src/lib/api/useSSE.ts`
- 最小验证：
  - 手工跑一次分析
  - 对照浏览器 Network 或后端日志

### 任务 2：解释用户维度的并发去重

- 目标：解释为什么“同一用户、同一 query”会复用任务，而“不同用户、同一 query”不会
- 关键文件：
  - `src/ideago/api/dependencies.py`
  - `src/ideago/api/routes/analyze.py`
  - `tests/test_api.py`
- 最小验证：

```bash
uv run pytest tests/test_api.py -q
```

## Level 2：小范围改动

### 任务 3：优化报告进度文案

- 目标：把某个进度事件的展示文案改得更清晰
- 关键文件：
  - `frontend/src/lib/api/useSSE.ts`
  - `frontend/src/features/reports/components/ReportProgressPane.tsx`
  - i18n 文案文件
- 最小验证：

```bash
pnpm --prefix frontend test
pnpm --prefix frontend typecheck
```

### 任务 4：增强状态接口的诊断信息

- 目标：让 `/reports/{id}/status` 对失败场景给出更清晰的信息
- 关键文件：
  - `src/ideago/api/routes/reports.py`
  - `src/ideago/api/schemas.py`
  - `tests/test_api.py`
- 最小验证：

```bash
uv run pytest tests/test_api.py -q
```

## Level 3：跨模块改动

### 任务 5：新增报告字段并做前后端联动

- 目标：给报告新增一个字段并展示到 UI
- 关键文件：
  - `src/ideago/models/research.py`
  - `src/ideago/pipeline/nodes.py`
  - `frontend/src/lib/types/research.ts`
  - `frontend/src/features/reports/components/ReportContentPane.tsx`
- 最小验证：

```bash
uv run pytest tests/test_research_models.py -q
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
```

### 任务 6：调整聚合失败时的降级表现

- 目标：让聚合失败后的 fallback 更结构化、更可解释
- 关键文件：
  - `src/ideago/pipeline/aggregator.py`
  - `src/ideago/pipeline/nodes.py`
  - `tests/test_langgraph_engine.py`
- 最小验证：

```bash
uv run pytest tests/test_langgraph_engine.py -q
```

## Level 4：特性扩展

### 任务 7：新增一个数据源

- 目标：接入新的 source，并让报告和前端都认得它
- 关键文件：
  - `src/ideago/models/research.py`
  - `src/ideago/sources/<new>_source.py`
  - `src/ideago/api/dependencies.py`
  - `frontend/src/lib/types/research.ts`
  - `frontend/src/features/reports/components/PlatformIcons.tsx`
  - `frontend/src/features/reports/components/useCompetitorFilters.ts`
- 最小验证：

```bash
uv run pytest tests/test_sources.py -q
pnpm --prefix frontend test
pnpm --prefix frontend typecheck
```

### 任务 8：增强 SSE 断流恢复策略

- 目标：改善“流结束了，但报告还没 ready”的用户体验
- 关键文件：
  - `frontend/src/lib/api/useSSE.ts`
  - `frontend/src/features/reports/components/useReportLifecycle.ts`
  - 相关前端测试
- 最小验证：

```bash
pnpm --prefix frontend test
pnpm --prefix frontend typecheck
```

## 建议的任务执行模板

```md
### 任务名称
- 目标：
- 改动文件：
- 影响层：
- 风险点：
- 验证命令：
- 回滚方案：
```

## 开始前先自问 3 个问题

1. 这个任务会不会同时影响后端模型和前端类型
2. 这个任务会不会破坏匿名主流程、状态恢复或本地缓存语义
3. 这个任务是否需要同步更新测试和文档

## 现在就可以做的起步动作

从 Level 2 选一个任务，先把“任务执行模板”写出来，再开始动手。

---

下一篇：`docs/mentor/07-troubleshooting.md`
