# 02 · 一次请求的完整生命周期

> 目标：把当前系统压缩成一条真实、可追踪、可验证的黄金路径。

## 总览：从点击到报告

1. 登录用户在首页提交 query
2. 前端调用 `POST /api/v1/analyze`
3. 后端校验配额并创建后台任务
4. `_run_pipeline()` 执行 LangGraph
5. 前端报告页订阅 `/reports/{id}/stream`
6. 后端通过 `ReportRunState` 推送事件
7. 报告落到 `FileCache` 或 Supabase
8. 前端补拉 `/reports/{id}` 和 `/reports/{id}/status`，进入 ready 或 error/cancelled

## Step 1：前端发起分析

- 文件：`frontend/src/features/home/HomePage.tsx`
- 文件：`frontend/src/lib/api/client.ts`

实际链路：

- 页面收集用户输入
- `startAnalysis(query)` 发 `POST /api/v1/analyze`
- 请求头里会带上：
  - `Authorization`
  - `X-Requested-With: IdeaGo`

这里要记住两个现实点：

- 这个接口需要认证，不再是匿名入口
- CSRF 保护要求 state-changing 请求带 `X-Requested-With`

## Step 2：后端接收并创建任务

- 文件：`src/ideago/api/routes/analyze.py`
  - `start_analysis()`

执行顺序：

1. `check_and_increment_quota(user.id)` 校验套餐额度
2. 清洗 query
3. 计算 `query_hash = sha256(query)[:16]`
4. `reserve_processing_report(query_hash, report_id, user_id=user.id)` 做去重
5. 写入 `processing` 状态
6. 创建 `ReportRunState`
7. `asyncio.create_task(_run_pipeline(...))`
8. 立即返回 `report_id`

为什么现在要强调“按用户去重”：

- 相同 query 不再是全局共用一个任务
- 不同用户的相同 query 会各自拿到自己的 `report_id`

## Step 3：后台运行 pipeline

- 文件：`src/ideago/api/routes/analyze.py`
  - `_run_pipeline()`
- 文件：`src/ideago/api/dependencies.py`
  - `get_orchestrator()`

`_run_pipeline()` 做的事：

- 通过 `get_orchestrator()` 获取单例 `LangGraphEngine`
- 把 `_RunStateCallback` 传给 orchestrator，让节点事件进入 SSE 运行态
- 成功时写 `complete`
- 失败时写 `failed` 并发布 `error`
- 取消时写 `cancelled` 并发布 `cancelled`
- 结束后释放 processing slot 和 task 映射

此外还有两个现在版本里很重要的细节：

- 任务完成后可能触发 `notify_report_ready`
- 配额接近上限时可能触发 `notify_quota_warning`

## Step 4：LangGraph 节点链

- 文件：`src/ideago/pipeline/langgraph_engine.py`
- 文件：`src/ideago/pipeline/nodes.py`

主链节点：

- `parse_intent`
- `cache_lookup`
- `fetch_sources`
- `extract_map`
- `aggregate`
- `assemble_report`
- `persist_report`

你可以把它理解成三段：

- 前半段：理解 query 和查缓存
- 中段：查 source、抽取结构化竞争信息、做聚合
- 后段：组装最终报告并持久化

## Step 5：节点职责速记

- `parse_intent_node`
  - 用 `IntentParser` 把自然语言 idea 变成结构化意图
- `cache_lookup_node`
  - 先查缓存，命中时可直接短路
- `fetch_sources_node`
  - 并发调用注册过的数据源
- `extract_map_node`
  - 对原始结果做结构化抽取，失败时可以降级
- `aggregate_node`
  - 去重、归并、形成结论
- `assemble_report_node`
  - 生成 `ResearchReport`，带上置信度、证据、成本等信息
- `persist_report_node`
  - 写缓存并发 `report_ready`

## Step 6：SSE 如何送到前端

### 后端侧

- 文件：`src/ideago/api/routes/analyze.py`
- 文件：`src/ideago/api/dependencies.py`

核心机制：

- `ReportRunState.publish()`：保存历史并广播给订阅者
- `history_snapshot()`：新订阅者先补历史
- `_stream_events()`：无事件时发 `ping`
- 如果内存态已丢，但状态文件仍在，后端会尝试从 status 推导终态事件

### 前端侧

- 文件：`frontend/src/lib/api/useSSE.ts`

核心机制：

- 用 `fetch()` 自己解析 SSE block
- 遇到 `ping` 只更新连接状态，不进入业务事件
- 识别 `report_ready`、`error`、`cancelled` 作为终止事件
- 异常断开时做指数退避重连
- 401 时清理会话并跳转登录页

## Step 7：为什么还需要状态补拉

- 文件：`frontend/src/features/reports/components/useReportLifecycle.ts`
- 文件：`src/ideago/api/routes/reports.py`

`useReportLifecycle()` 并不是“只听 SSE”，它会同时协调：

- `getReportWithStatus(id)`
- `getReportRuntimeStatus(id)`
- `useSSE(reportId)`

原因是 SSE 只能告诉你“过程事件”，但不能保证前端拿到事件时报告实体已经可读。

所以它做了两类恢复：

- 初次进入报告页时，先判断是 `ready`、`processing` 还是 `missing`
- SSE 已经收到了完成事件，但报告还没读到时，再做几轮带退避的补拉

这正是为什么“状态到了，但报告还没落盘”不会直接把页面打坏。

## Step 8：报告如何展示

- 文件：`frontend/src/features/reports/ReportPage.tsx`
- 文件：`frontend/src/features/reports/components/ReportContentPane.tsx`
- 文件：`frontend/src/features/reports/components/ReportProgressPane.tsx`

高层逻辑很简单：

- `processing`：显示进度页
- `ready`：显示报告内容
- `failed/cancelled/not_found`：显示错误态或可重试态

## 动手任务

如果你有可用登录环境，做一次真实追踪：

1. 登录后发起一次分析
2. 在浏览器 Network 里观察：
   - `POST /api/v1/analyze`
   - `GET /api/v1/reports/:id/stream`
   - `GET /api/v1/reports/:id`
   - `GET /api/v1/reports/:id/status`
3. 同时打开：
   - `src/ideago/api/routes/analyze.py`
   - `src/ideago/pipeline/langgraph_engine.py`
   - `src/ideago/pipeline/nodes.py`
   - `frontend/src/features/reports/components/useReportLifecycle.ts`
   - `frontend/src/lib/api/useSSE.ts`

完成标准：

- 你能解释“为什么这个项目不是只有 SSE，而是 SSE + 状态补拉 + 实体补拉一起工作”

---

下一篇：`docs/mentor/03-agent-core.md`
