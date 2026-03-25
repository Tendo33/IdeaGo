# 07 · Troubleshooting 速查表

> 目标：5 分钟内先判断是配置、运行态、pipeline、权限还是前端状态协调出了问题。

## 1) 常见故障矩阵

| 现象 | 优先检查 | 典型位置 |
|---|---|---|
| `/health` 不是 `ok` | 基础配置和依赖连通性 | `src/ideago/api/routes/health.py` |
| 匿名分析请求直接 4xx | `X-Requested-With`、请求体、限流或输入校验 | `frontend/src/lib/api/client.ts`, `src/ideago/api/routes/analyze.py`, `src/ideago/api/app.py` |
| 一直 `processing` | 后台任务、运行态、status 持久化 | `src/ideago/api/routes/analyze.py`, `src/ideago/api/dependencies.py`, cache 实现 |
| SSE 断流或不更新 | `_stream_events()`、前端重连逻辑、终态事件 | `src/ideago/api/routes/analyze.py`, `frontend/src/lib/api/useSSE.ts` |
| SSE 已完成但页面还没 ready | `useReportLifecycle` 的补拉和恢复逻辑 | `frontend/src/features/reports/components/useReportLifecycle.ts` |
| 报告内容明显偏少 | source 可用性、提取降级、聚合结果 | `src/ideago/pipeline/nodes.py`, `src/ideago/sources/*.py` |
| 报告里的链接可疑 | extractor 的链接过滤 | `src/ideago/pipeline/extractor.py` |
| history 或报告读取异常 | 本地索引、TTL、status 文件与实体文件是否一致 | `src/ideago/api/routes/reports.py`, `src/ideago/cache/*` |
| 报告页卡顿 | 虚拟化、图表或大组件渲染 | `frontend/src/features/reports/components/VirtualizedCompetitorList.tsx` |

## 2) 快速诊断命令

### 基础健康

```bash
curl http://localhost:8000/api/v1/health
```

### 后端关键测试

```bash
uv run pytest tests/test_api.py -q
uv run pytest tests/test_langgraph_engine.py -q
uv run pytest tests/test_llm_layer.py -q
uv run pytest tests/test_sources.py -q
```

### 前端关键测试

```bash
pnpm --prefix frontend test
pnpm --prefix frontend typecheck
```

### 本地文件缓存场景

```bash
Get-ChildItem .cache/ideago
```

如果你当前走的是本地 `FileCache`，这里通常能看到 report 和 status 相关文件。

## 3) 三类最常见根因

### A. 配置问题

表现：

- source 一直不可用
- LLM 请求马上失败

优先看：

- `.env`
- `src/ideago/config/settings.py`
- OpenAI / Tavily / GitHub / Product Hunt / Reddit 等配置是否完整

### B. 运行态与持久化不一致

表现：

- 页面显示 processing，但后台任务其实已经结束
- SSE 没有终态，但 status 已经写成 failed/cancelled/complete
- 报告 ready 事件到了，但实体还没读到

优先看：

- `ReportRunState`
- `status` 写入逻辑
- `useReportLifecycle()` 的恢复逻辑

### C. 匿名缓存索引与状态链路出错

表现：

- history 列表和详情页内容对不上
- SSE 或 status 已结束，但实体文件仍然缺失
- 清理逻辑删掉了该保留的匿名报告

优先看：

- `_index.json`
- `*.status.json`
- `cleanup_expired()`
- `useReportLifecycle()` 的补拉与终态判断

## 4) 推荐调试顺序

1. 先确认是不是基础环境问题：`/health`
2. 再看是不是请求协议问题：4xx、header、query、请求体
3. 再看运行态：processing map、pipeline task、ReportRunState
4. 再看持久化：report/status 是否真的写下来了
5. 最后才看前端渲染与交互

不要一上来就盯 UI，因为这个项目很多“看起来像前端问题”的现象，根因都在运行态或权限层。

## 5) 改代码前的预防性检查清单

- 是否会破坏 `ReportRuntimeStatus` 的语义
- 是否新增 SSE 事件却忘了前端事件白名单
- 是否修改报告模型却忘了同步 TS 类型
- 是否会影响匿名 status 恢复与历史列表
- 是否会影响 query 去重 key
- 是否会引入新的副作用，比如重复创建匿名任务或错误清理缓存

## 6) 故障复盘模板

```md
- 现象：
- 影响范围：
- 复现方式：
- 根因定位路径：
- 修复思路：
- 验证方法：
- 如何防止复发：
```

完成标准：

- 你能把“现象 -> 根因 -> 修复 -> 验证”闭环讲清楚
