# 04 · 高级特性深挖（附坑点与调试路径）

> 本篇聚焦 5 个“拉开项目质量差距”的高级机制。

## 1) LangGraph 检查点与可恢复执行

**实现位置**
- `src/ideago/pipeline/langgraph_engine.py`
  - `AsyncSqliteSaver.from_conn_string(...)`
  - `graph.aget_state(config)` + `graph.ainvoke(...)`

**它解决的问题**
- 任务中断后可恢复
- 状态机执行有一致持久化落点

**常见坑**
- 误以为每次都从头跑：实际上如果 `snapshot.next` 有值，会继续执行未完成节点。

**调试建议**
- 删除检查点 DB 再跑，观察行为差异：

```bash
rm -f .cache/ideago/langgraph-checkpoints.db
```

---

## 2) LLM 可靠性：重试 + 故障切换 + JSON 恢复

**实现位置**
- `src/ideago/llm/chat_model.py`
  - `_invoke_with_retry_meta`
  - `_is_retryable_exception`
  - `_is_failover_eligible`
  - `invoke_json_with_meta`

**它解决的问题**
- 429/超时/短暂网络错误不会立即失败
- 主端点异常可切到 fallback endpoint
- 返回非法 JSON 时可重试并切换端点

**常见坑**
- 只看最终失败，不看 `pop_last_call_metadata()`，错过关键信息（`endpoints_tried`、`last_error_class`）。

**调试建议**
- 先看测试样例：`tests/test_llm_layer.py`
- 重点验证字段：`llm_calls`、`endpoint_failovers`、`fallback_used`

---

## 3) 提取降级 + 链接真实性约束

**实现位置**
- `src/ideago/pipeline/extractor.py`
  - `_normalize_url`
  - 只保留来自 raw results 的链接
- `src/ideago/pipeline/nodes.py`
  - `extract_map_node`
  - `_degrade_raw_to_competitors`

**它解决的问题**
- 防止 LLM 编造链接（hallucinated links）
- 单源提取失败仍可返回“可用但降级”结果

**常见坑**
- 把降级结果误判成“系统成功”，其实 `SourceStatus` 会标 `degraded`，需在前端显式提示。

**调试建议**
- 看回归测试：`tests/test_langgraph_engine.py`（extraction failure 路径）
- 用 `source_results[].status/error_msg` 判断真实质量，不只看 HTTP 200。

---

## 4) SSE 稳定性：历史重放 + 心跳 + 指数重连

**实现位置**
- 后端：`src/ideago/api/routes/analyze.py:_stream_events`
- 前端：`frontend/src/api/useSSE.ts`

**它解决的问题**
- 前端中途重连后仍能收到历史事件
- 空闲期不断线（ping）
- 异常断流时自动重连（指数退避）

**常见坑**
- 忽略“终止事件”，导致前端一直重连。

**调试建议**
- 在浏览器 DevTools 观察 `/stream` 是否出现：
  - `ping`
  - `report_ready` / `error` / `cancelled`
- 如果只见 ping 不见终态，检查后端 status 文件：

```bash
ls -la .cache/ideago/*.status.json
```

---

## 5) 前端大数据量体验：竞品列表虚拟化

**实现位置**
- `frontend/src/pages/report/ReportContentPane.tsx`
  - `VIRTUALIZATION_THRESHOLD = 35`
- `frontend/src/components/VirtualizedCompetitorList.tsx`
  - 动态测量行高 + 二分定位可视区域

**它解决的问题**
- 竞品多时避免一次性渲染，降低卡顿

**常见坑**
- 只做固定行高虚拟化，遇到动态内容错位。

**调试建议**
- 关注：`binarySearchOffset`、`measuredHeights`、`offsets`
- 切换 `grid/list` 和窗口宽度，验证可视区域计算是否稳定。

---

## 动手任务（30 分钟）

做一次“故障演练”复盘（不改代码）：

1. 假设 LLM 主端点 401，fallback 可用。
2. 你预期 `chat_model` 元数据里哪些字段变化？
3. 这份变化最终在哪些对象里可见？（提示：report meta / cost / logs）
4. 前端最终应展示什么用户可感知信号？

完成标准：
- 你能把“异常 -> 重试 -> 切换 -> 用户看到的结果”讲成一条完整故事线。

---

下一篇：`docs/mentor/05-learning-plan.md`（给你一套可执行 4 周计划）。
