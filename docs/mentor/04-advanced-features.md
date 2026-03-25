# 04 · 高级特性深挖

> 本篇聚焦当前版本里最值得理解、也最容易被改坏的 5 组机制。

## 1) LLM 可靠性：重试、故障切换、JSON 恢复

实现位置：

- `src/ideago/llm/chat_model.py`

它解决的问题：

- 429、超时、瞬时网络问题不会直接击穿整条链路
- 主 endpoint 失败时可以尝试 fallback endpoint
- 结构化输出失败时可以做 JSON 恢复或再次调用

阅读时重点看：

- 哪些错误被认定为 retryable
- 哪些场景允许 failover
- 元数据怎么记到调用结果里

常见误区：

- 只看最终是否失败，不看中间经历了多少次 retry/failover
- 忽略元数据，导致以为“模型很稳定”，其实只是兜底做得好

调试建议：

```bash
uv run pytest tests/test_llm_layer.py -q
```

重点关注：

- `llm_calls`
- `endpoint_failovers`
- `fallback_used`
- `last_error_class`

## 2) 提取降级与链接约束

实现位置：

- `src/ideago/pipeline/extractor.py`
- `src/ideago/pipeline/nodes.py`

它解决的问题：

- 防止模型编造来源链接
- 单个 source 抽取失败时，尽量保留“可用但降级”的结果

为什么它很重要：

- 这个项目的可信度不只看“有没有结论”，还看“结论能不能回溯到真实来源”

常见误区：

- 看见有 competitors 就以为系统完全成功
- 忽略 `source_results[].status`，把 `degraded` 当成 `ok`

调试建议：

```bash
uv run pytest tests/test_langgraph_engine.py -q
```

看这些信息：

- `source_results[].status`
- `source_results[].error_msg`
- 报告中的 `links` 是否都能在 raw source results 中找到来源

## 3) SSE 稳定性：历史重放、ping、终态恢复、前端重连

实现位置：

- 后端：`src/ideago/api/routes/analyze.py`
- 运行态：`src/ideago/api/dependencies.py`
- 前端：`frontend/src/lib/api/useSSE.ts`

它解决的问题：

- 前端中途进入页面，也能补收到历史事件
- 长时间没有新业务事件时，连接不会假死
- 流异常关闭时，前端可以自动重连
- 后端运行态已经不在，但 status 文件还在时，仍能推导终态

当前版本相比简单 SSE 的高级点在于：

- 不是只有“在线时推”，还有“重连后补”
- 不是只有“消息队列”，还有“状态文件兜底”

常见误区：

- 只盯着前端不更新，忽略后端其实已经只剩 status 文件
- 没处理终止事件，导致前端无限重连

调试建议：

```bash
uv run pytest tests/test_api.py -q
pnpm --prefix frontend test
```

手工观察：

- Network 中 `/stream` 是否出现 `ping`
- 是否能收到 `report_ready`、`error`、`cancelled`
- 若没有终态，去看 `.cache/ideago` 下的状态文件与 checkpoint

## 4) 持久化实现：FileCache 与本地 SQLite checkpoint

实现位置：

- `src/ideago/cache/file_cache.py`
- `src/ideago/api/dependencies.py:get_cache()`
- `src/ideago/pipeline/langgraph_engine.py`

它解决的问题：

- 本地个人部署可以零门槛跑起来
- 报告内容、运行状态和 pipeline checkpoint 都能在单机模式下恢复

你需要理解的是：

- 业务代码尽量依赖 `ReportRepository` 抽象
- `status` 不只是“附属信息”，它是恢复运行态和 SSE 历史的重要依据

常见误区：

- 假设所有环境都有本地状态文件
- 修改状态写入逻辑时忘记兼容匿名报告恢复语义

## 5) 报告页体验：状态协调与大列表虚拟化

实现位置：

- `frontend/src/features/reports/components/useReportLifecycle.ts`
- `frontend/src/features/reports/components/ReportContentPane.tsx`
- `frontend/src/features/reports/components/VirtualizedCompetitorList.tsx`

它解决的问题：

- SSE 完成但实体尚未可读时，页面不会闪崩
- 竞品数量较多时，页面不会一次性渲染所有卡片

这个模块真正复杂的地方不是 UI，而是状态协调：

- 初始加载
- processing 中的 SSE 订阅
- complete 后的补拉
- failed/cancelled 的恢复与重试
- 切换到 ready 后的展示节奏

常见误区：

- 只改 UI 组件，不管 lifecycle
- 只改 SSE 逻辑，不验证 ready/missing/processing 三种切换

## 动手任务

做一次“故障故事线”复盘：

1. 假设主 LLM endpoint 暂时不可用，但 fallback 可用
2. 说清楚：
   - 哪一层先发现问题
   - 哪一层做 retry / failover
   - 哪些元数据会变化
   - 报告最终会留下什么痕迹
   - 前端用户最终看到的是什么

完成标准：

- 你能把“底层异常 -> pipeline 继续或失败 -> 前端最终状态”完整讲出来

---

下一篇：`docs/mentor/05-learning-plan.md`
