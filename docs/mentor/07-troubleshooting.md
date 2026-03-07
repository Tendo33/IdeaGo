# 07 · Troubleshooting 速查表

> 目标：遇到问题时，5 分钟内先定位到“哪一层出问题”。

## 1) 常见故障矩阵

| 现象 | 优先检查 | 典型位置 |
|---|---|---|
| `/health` 不是 `ok` | 配置和依赖注入 | `src/ideago/api/routes/health.py`, `src/ideago/api/dependencies.py` |
| 一直 `processing` | 后台任务状态 + status 文件 | `src/ideago/api/routes/analyze.py`, `.cache/ideago/*.status.json` |
| SSE 断流/不更新 | 事件终态 + 前端重连 | `src/ideago/api/routes/analyze.py:_stream_events`, `frontend/src/api/useSSE.ts` |
| 返回报告但内容很少 | source 可用性/提取降级 | `src/ideago/pipeline/nodes.py:extract_map_node`, `src/ideago/sources/*.py` |
| 报告里链接可疑 | 链接过滤逻辑 | `src/ideago/pipeline/extractor.py` |
| 前端卡顿 | 虚拟化是否启用 | `frontend/src/pages/report/ReportContentPane.tsx`, `VirtualizedCompetitorList.tsx` |

## 2) 快速诊断命令

### 后端健康与状态

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/reports/<report_id>/status
ls -la .cache/ideago
```

### SSE 连通性

```bash
curl -N http://localhost:8000/api/v1/reports/<report_id>/stream
```

如果只有 `ping` 没有终态：
- 检查 pipeline 是否真的还在跑
- 检查 status 文件是否写成 `failed/cancelled/complete`

### 单点测试

```bash
uv run pytest tests/test_api.py -q
uv run pytest tests/test_langgraph_engine.py -q
uv run pytest tests/test_llm_layer.py -q
uv run pytest tests/test_sources.py -q
npm --prefix frontend run test
```

## 3) 三类高频根因

### A. 配置问题（最常见）

表现：
- 某些 source 永远不可用
- LLM 请求直接失败

看哪里：
- `.env`
- `src/ideago/config/settings.py`
- `/api/v1/health` 返回的 `sources`

### B. 运行时状态不一致

表现：
- 已完成但前端没拿到报告
- 前端以为 processing，后端其实失败了

看哪里：
- `ReportRunState` 内存态：`src/ideago/api/dependencies.py`
- status 文件：`FileCache.put_status/get_status`
- 前端恢复逻辑：`useReportLifecycle.ts`

### C. 外部 API 波动

表现：
- 某源超时/失败比例升高
- 报告样本量突降

看哪里：
- `source_results[].status`
- `cost_breakdown`
- 日志 `logs/*.log`

## 4) 调试顺序（推荐）

1. 先看 API 层状态（health/status）
2. 再看 pipeline 终态（SSE + status file）
3. 再看 source 粒度状态（source_results）
4. 最后看前端呈现逻辑

不要反过来：先盯前端样式通常会浪费时间。

## 5) 预防性检查清单（改代码前）

- 是否会破坏 `ReportRuntimeStatus` 的语义？
- 是否会新增 SSE 事件但忘了前端白名单？
- 是否会改动模型字段但忘了更新 TS 类型？
- 是否会影响缓存 key 规则（命中率）？

## 动手任务（15 分钟）

选一个历史 bug（或你自己假想一个），按下列模板写一次故障复盘：

```md
- 现象：
- 影响范围：
- 根因定位路径（按时间线）：
- 修复思路：
- 如何防止复发：
```

完成标准：
- 你能把“现象 -> 根因 -> 验证”闭环讲完整。
