# 03 · 引擎核心与扩展点

> 这一篇不把 IdeaGo 当成“通用 Agent 框架”来讲，而是把它当成一个真实产品里的 AI 研究引擎来拆开看。

## 1) 核心装配入口

- 文件：`src/ideago/api/dependencies.py`
- 关键函数：`get_orchestrator()`

当前版本里，`get_orchestrator()` 会创建并连接这些核心对象：

1. `ChatModelClient`
2. `IntentParser`
3. `Extractor`
4. `Aggregator`
5. `SourceRegistry`
6. `LangGraphEngine`
7. `ReportRepository` 的具体实现

这里有两个你必须记住的现实点：

- `main` 默认并且只依赖 `FileCache` + 本地 SQLite checkpoint
- source registry 已经不只是 GitHub/Tavily/HN，还包含 App Store、Product Hunt、Reddit

## 2) 这个装配层真正解决了什么

### A. 把“运行策略”从路由层隔离出去

`start_analysis()` 不需要知道每个数据源怎么初始化，也不需要知道缓存是本地文件还是远端存储。

### B. 把“功能替换点”集中到一个地方

你要替换模型、增减 source、改缓存实现，优先看 `dependencies.py`。

### C. 保持路由层薄

API 层负责请求协议、状态登记、响应契约；真正的研究流程交给 orchestrator 和 pipeline。

## 3) 契约层：为什么这个项目能演进

- `src/ideago/cache/base.py`
  - `ReportRepository`
- `src/ideago/contracts/protocols.py`
  - `DataSource`
  - `ProgressCallback`

它们的价值是把“主流程”与“具体实现”拆开：

- `ReportRepository` 让报告持久化和运行态访问从业务逻辑中解耦
- `DataSource` 让新 source 可以接进 registry
- `ProgressCallback` 让节点事件能被 SSE 运行态消费，而不是写死在 pipeline 里

## 4) 模型层与 prompt 层如何协作

- Prompt 模板：`src/ideago/llm/prompts/*.txt`
- 加载器：`src/ideago/llm/prompt_loader.py`
- 调用器：`src/ideago/llm/chat_model.py`
- 结构化消费端：
  - `intent_parser.py`
  - `extractor.py`
  - `aggregator.py`

职责分工可以这样记：

- prompt：告诉模型“要什么输出”
- parser/extractor/aggregator：把输出压回结构化模型
- `ChatModelClient`：兜底可靠性，包括 timeout、重试、fallback 和 JSON 恢复

## 5) 运行时状态：真正支撑 SSE 的不是路由，而是这三张表

位置：`src/ideago/api/dependencies.py`

关键结构：

- `_processing_reports`
  - 记录“哪个 query 正在处理”
- `_pipeline_tasks`
  - 记录“哪个 report_id 对应哪个后台 task”
- `_report_runs`
  - 记录“这个 report 的 SSE 历史、订阅者和终态信息”

这些结构共同提供：

- 并发去重
- 取消任务
- 事件历史重放
- 终态 TTL 清理

## 6) 当前最常见的扩展点

### 扩展点 A：新增数据源

通常至少会碰这些位置：

- `src/ideago/sources/<new>_source.py`
- `src/ideago/api/dependencies.py`
- `src/ideago/models/research.py`
- `frontend/src/lib/types/research.ts`
- `frontend/src/features/reports/components/PlatformIcons.tsx`
- `frontend/src/features/reports/components/useCompetitorFilters.ts`
- 测试文件

### 扩展点 B：调整 pipeline 节点

- `src/ideago/pipeline/langgraph_engine.py`
- `src/ideago/pipeline/nodes.py`
- `src/ideago/pipeline/graph_state.py`
- `tests/test_langgraph_engine.py`

### 扩展点 C：新增报告字段

- `src/ideago/models/research.py`
- `src/ideago/pipeline/nodes.py`
- `frontend/src/lib/types/research.ts`
- `frontend/src/features/reports/components/*`

### 扩展点 D：新增进度事件

- `src/ideago/pipeline/events.py`
- `src/ideago/pipeline/nodes.py`
- `frontend/src/lib/api/useSSE.ts`
- `frontend/src/features/reports/components/ReportProgressPane.tsx`

## 7) 一些“看起来不核心，但实际很要命”的配套点

### A. 匿名运行态与恢复

`main` 的关键约束不是登录态，而是匿名运行态是否可恢复。

这意味着你做 feature 时不能只改 pipeline，还要确认：

- `status` 是否还能表达 processing / complete / failed / cancelled
- `ReportRunState` 历史重放是否还能工作
- 报告尚未落盘时，前端补拉是否还能正确兜底

## 8) 学习时可以暂时靠后的部分

以下内容不是第一轮理解主链路的阻塞项：

- `src/ideago/core/*`
- 更细的 prompt 调优策略
- 指标聚合和埋点细节

先把“分析主链路 + 报告页 + SSE”吃透，再回来看这些模块会更轻松。

## 动手任务

做一个“只写设计不改代码”的演练：

1. 假设你要新增一个 source
2. 写出至少 6 个你会改的文件
3. 每个文件写一句为什么要改
4. 补上最小验证命令

完成标准：

- 你能清楚解释“为什么只写一个 `<new>_source.py` 远远不够”

---

下一篇：`docs/mentor/04-advanced-features.md`
