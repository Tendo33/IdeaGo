# 00 · Codebase 全景地图

> 目标：先把「这库到底怎么分层」一次性建立起来，再进入链路细节。

## 1) 顶层结构：你真正要关注的目录

- `src/ideago/`：后端主代码（重点）
- `frontend/src/`：前端主代码（重点）
- `tests/`：后端 pytest 测试（高价值阅读）
- `doc/`：工程规范与配置说明
- `scripts/`：发布/维护脚本（次重点）

你可以暂时忽略：`htmlcov/`、`logs/`、`.history/`、`.cache/`。

## 2) 后端模块地图（按执行价值排序）

### A. API 层

- `src/ideago/api/app.py`
  - `create_app()`：FastAPI 应用工厂，挂中间件、路由、前端静态资源
  - `api_key_auth`：可选 API Key 鉴权（`X-API-Key`）
  - `rate_limit_analyze`：`/analyze` 内存限流
- `src/ideago/api/routes/analyze.py`
  - `start_analysis()`：启动任务，返回 `report_id`
  - `_run_pipeline()`：后台协程跑完整管道
  - `stream_progress()` + `_stream_events()`：SSE 事件流
  - `cancel_analysis()`：取消运行中任务
- `src/ideago/api/routes/reports.py`
  - 报告查询、状态查询、导出、删除

### B. 依赖装配层（非常关键）

- `src/ideago/api/dependencies.py`
  - `get_orchestrator()`：把 LLM、数据源、管道组件装起来
  - `reserve_processing_report()`：相同 query 去重并发
  - `ReportRunState`：SSE 订阅队列与事件历史

### C. 管道执行层（核心）

- `src/ideago/pipeline/langgraph_engine.py`
  - `LangGraphEngine.run()`：图执行入口
  - `_build_graph()`：定义节点和跳转关系
- `src/ideago/pipeline/nodes.py`
  - `parse_intent_node`
  - `cache_lookup_node`
  - `fetch_sources_node`
  - `extract_map_node`
  - `aggregate_node`
  - `assemble_report_node`
  - `persist_report_node`

### D. 领域能力层

- `src/ideago/pipeline/intent_parser.py`
- `src/ideago/pipeline/extractor.py`
- `src/ideago/pipeline/aggregator.py`
- `src/ideago/llm/chat_model.py`（重试、故障切换、元数据）
- `src/ideago/sources/*.py`（GitHub/Tavily/HN/AppStore/ProductHunt）
- `src/ideago/cache/file_cache.py`（报告缓存与状态文件）

### E. 模型与契约

- `src/ideago/models/research.py`：核心数据模型
- `src/ideago/contracts/protocols.py`：`DataSource` / `ProgressCallback`

## 3) 前端模块地图（按用户路径）

- `frontend/src/App.tsx`：路由入口，主题/语言切换，ErrorBoundary
- `frontend/src/pages/HomePage.tsx`：提交 query，查看最近报告
- `frontend/src/pages/ReportPage.tsx`：报告页容器
- `frontend/src/pages/report/useReportLifecycle.ts`：报告加载与状态机
- `frontend/src/api/useSSE.ts`：SSE 连接、重连、事件解析
- `frontend/src/pages/report/ReportContentPane.tsx`：报告渲染主视图
- `frontend/src/components/VirtualizedCompetitorList.tsx`：大列表虚拟化

## 4) 一张图看端到端

```mermaid
flowchart LR
  U[User Query] --> FE1[HomePage submit]
  FE1 --> API1[POST /api/v1/analyze]
  API1 --> R1[start_analysis]
  R1 --> BG[_run_pipeline task]
  BG --> G1[LangGraphEngine.run]
  G1 --> N1[parse_intent]
  N1 --> N2[cache_lookup]
  N2 -->|miss| N3[fetch_sources]
  N3 --> N4[extract_map]
  N4 --> N5[aggregate]
  N5 --> N6[assemble_report]
  N6 --> N7[persist_report]
  N7 --> C1[FileCache JSON]
  BG --> SSE[GET /reports/{id}/stream]
  SSE --> FE2[useSSE/useReportLifecycle]
  FE2 --> FE3[ReportContentPane]
```

## 5) 推荐阅读顺序（文件级）

1. `src/ideago/__main__.py`
2. `src/ideago/api/app.py`
3. `src/ideago/api/routes/analyze.py`
4. `src/ideago/api/dependencies.py`
5. `src/ideago/pipeline/langgraph_engine.py`
6. `src/ideago/pipeline/nodes.py`
7. `src/ideago/pipeline/intent_parser.py` / `extractor.py` / `aggregator.py`
8. `src/ideago/llm/chat_model.py`
9. `frontend/src/pages/report/useReportLifecycle.ts`
10. `frontend/src/api/useSSE.ts`

## 6) 动手任务（10 分钟）

执行以下命令，手工对照上面的地图：

```bash
rg -n "def create_app|start_analysis|_run_pipeline|class LangGraphEngine|async def parse_intent_node" src
rg -n "export function useReportLifecycle|export function useSSE" frontend/src
```

完成标准：
- 你能口述“一个 query 从前端到报告生成”的 6 个步骤。

---

下一篇：`docs/mentor/01-quickstart-path.md`（20 分钟内跑通并定位关键入口）。
