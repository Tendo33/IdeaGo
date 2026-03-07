# 03 · 引擎核心与扩展点（Agent Core 视角）

> 虽然 IdeaGo 不是“通用 Agent 框架”，但它具备典型 Agent Core 结构：模型层、工具层（数据源）、状态机编排、事件回调与持久化。

## 1) 核心组件装配图

- 装配入口：`src/ideago/api/dependencies.py:get_orchestrator()`

它创建并连接了这些对象：

1. `ChatModelClient`（LLM 调用与容错）
2. `IntentParser`（query -> intent）
3. `Extractor`（raw -> competitors）
4. `Aggregator`（全局去重+结论）
5. `SourceRegistry`（统一管理数据源插件）
6. `FileCache`（报告缓存 + 状态文件）
7. `LangGraphEngine`（节点编排）

## 2) 契约层：让组件可替换的关键

- `src/ideago/contracts/protocols.py`
  - `DataSource`：统一数据源接口
  - `ProgressCallback`：统一事件回调接口

这个设计的价值：
- 你可以“加新数据源”而不改动 pipeline 主流程
- 你可以替换 callback 消费方式（例如以后推到 MQ）

## 3) Prompt 与模型层的协作

- Prompt 模板：`src/ideago/llm/prompts/*.txt`
- 加载器：`src/ideago/llm/prompt_loader.py:load_prompt`
- 调用器：`src/ideago/llm/chat_model.py:ChatModelClient`

三层职责分离：
- Prompt 负责“输入约束”
- Parser/Extractor/Aggregator 负责“结构化输出验证”
- ChatModelClient 负责“重试、故障切换、元数据统计”

## 4) 运行时状态与去重

- 位置：`src/ideago/api/dependencies.py`

关键结构：
- `_processing_reports`: `query_hash -> report_id`
- `_pipeline_tasks`: `report_id -> asyncio.Task`
- `_report_runs`: `report_id -> ReportRunState`

功能：
- 并发去重
- 取消任务
- SSE 历史重放
- 终态 TTL 清理（避免内存涨）

## 5) 你最常用的 4 个扩展点

### 扩展点 A：新增数据源

- 新增文件：`src/ideago/sources/<new>_source.py`
- 实现 `DataSource` 协议：`platform/is_available/search`
- 在 `get_orchestrator()` 中 `registry.register(...)`
- 在 `models/research.py:Platform` 增加枚举
- 可选：补前端 platform 映射（颜色/图标/过滤项）

### 扩展点 B：新增或重排节点

- 修改：`src/ideago/pipeline/langgraph_engine.py:_build_graph`
- 实现节点函数：`src/ideago/pipeline/nodes.py`
- 若影响状态字段，更新：`src/ideago/pipeline/graph_state.py`

### 扩展点 C：新增报告字段

- 后端模型：`src/ideago/models/research.py`
- 前端类型：`frontend/src/types/research.ts`
- 前端展示：`frontend/src/pages/report/ReportContentPane.tsx`（或子组件）

### 扩展点 D：新增进度事件

- 事件枚举：`src/ideago/pipeline/events.py:EventType`
- 节点发事件：`src/ideago/pipeline/nodes.py:_emit`
- 前端接收：`frontend/src/api/useSSE.ts` 中 `STREAM_EVENT_TYPES`

## 6) 设计上的一个现实点

`src/ideago/core/context.py` 是比较通用的上下文工具，当前主链路基本不依赖它（主要在测试覆盖）。

学习建议：
- 第一轮可暂时放后，不要阻塞你理解主链路。

## 动手任务（25 分钟）

做一个“只写设计不改代码”的扩展演练：

1. 设想新增数据源 `reddit`。
2. 列出你要改的文件清单（至少 6 个）。
3. 对每个文件写一句改动目的。
4. 写出最小验证命令（至少包含 1 条后端测试 + 1 条前端测试/检查）。

完成标准：
- 你能说清楚“为什么只加 source 文件是不够的”。

---

下一篇：`docs/mentor/04-advanced-features.md`（最值得深挖的高级机制）。
