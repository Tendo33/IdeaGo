# 状态一致性与正确性

## Goal

修掉四类会让系统进入自相矛盾状态的问题，并让一处跨域错误真正能被前端读到。

## 已完成

### 1. CORS 中间件顺序（体检 #6）

Starlette 的 `add_middleware` 是 `insert(0, ...)`，**最后注册的在最外层**。
原注册顺序把 CORS 放在第一位 = 最内层，于是限流的 429 和 CSRF 的 403
在到达 CORS 之前就短路返回，跨域浏览器拿不到 `Access-Control-Allow-Origin`，
SPA 只能看到一个不透明的网络错误，而不是「已限流」或「CSRF 校验失败」。

- CORS 改为最后注册（最外层），执行顺序变成
  `CORS → trace_id → security_headers → rate_limit → csrf → routes`
- 顺带补上 `expose_headers=["X-Trace-Id"]` —— 否则跨域时前端 JS 读不到
  trace id，而那恰恰是最需要它的场景
- 测试同时钉住**症状**（403 带 CORS 头）和**成因**（`user_middleware[0]` 就是
  CORSMiddleware），避免以后有人调整注册顺序时只改对一半

### 2. 缓存命中不再扣配额（体检 #11）

配额在流水线启动前就扣了，而 `cache_lookup_node` 才判命中。同一个 idea
一小时后再提交，LLM 成本为 0，用户却被扣掉每日 5 次里的 1 次。

实现上没有把配额逻辑下沉进流水线（那会让 pipeline 依赖 hosted 概念），
而是让 `cache_lookup_node` 在 `REPORT_READY` 事件里带上 `cache_hit: True`，
`_run_pipeline` 收尾时据此退款并记 `quota_refunded{reason=cache_hit}` 指标。

### 3. 报告终态顺序（体检 #22 的后端一半）

`REPORT_READY` 是客户端去取报告的信号，所以事件发出时客户端要找的东西
必须都已经落库。原来状态行是**之后**由调用方单独写的，留下一个
「流式说 ready 了但 `GET /reports/{id}` 还answers processing」的窗口——
这正是前端长出三层递归 reconcile 轮询的原因。

`persist_report_node` 现在先写报告、再写 `complete` 状态、**最后**才 emit。
仍是两次写而非一个事务，但可观测窗口已经关闭。

（design.md 原计划用 migration 019 的 `persist_report_complete` RPC 做成
单事务。未做，理由与 runtime-perf 第三层相同：本机无 Supabase 实例，
新增 RPC 无法验证。顺序调整已经消除了实际可观测的竞态，收益/风险比更好。）

### 4. Stripe webhook 事件不再永久丢失（体检 #18）

原实现 claim-before-process 且失败不释放：处理抛异常 → 路由返回 500 →
Stripe 重投 → claim 命中 → `return` → 路由返回 200 → **这笔订阅变更永远不会生效**，
且没有任何告警。

改成 claim → process → 失败则 `_release_event_claim` 删除 claim 行，
让 Stripe 的重投能真正重跑。释放本身失败时打 ERROR 级日志并明确写出
「需要人工重放」。

### 5. 配额退款不再丢失更新

`refund_quota_charge` 的回退路径是读改写：两个并发退款都读到 5、都写 4，
少退一次。直接删掉回退路径，只保留原子 RPC；失败时记
`quota_refund_failed` 指标 + `QUOTA_REFUND_FAILED` 错误事件，留给对账，
而不是用一次有竞态的写把问题盖过去。

## 未做：分布式取消（体检 #12）

**决定推迟，理由明确记录：**

1. 用户已确认生产是**单进程 docker compose 单容器**。单进程下
   `get_pipeline_task_for_report` 一定能找到本地 task，
   「配额已退但报告仍完成、状态从 cancelled 翻回 complete」这个 bug
   **在现网不会发生**。
2. 正确的修法需要给 `report_status` 加 `cancel_requested` 列 + 流水线节点边界
   轮询该标志。这是一个无法在本机验证的 schema 变更。
3. 半成品比不做更危险：一个只在部分路径生效的取消标志，会让人误以为
   多副本已经安全。

**代替动作**：把多副本的真实约束写进 `DEPLOYMENT.md`（在 ops-observability
子任务里一并做），明确列出「多副本前必须先解决：分布式取消、SSE run_state
跨进程、metrics 跨进程聚合」三项，而不是让代码里的 PG dedup / PG checkpointer
暗示多副本已经可用。

## 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 133 files already formatted
uv run mypy src                            → Success: no issues found in 88 source files
uv run pytest                              → 851 passed, 0 failed, 覆盖率 84.81%
```

新增 `tests/test_state_consistency.py` 12 个：CORS 跨域可读性 3、
缓存命中判定 3、webhook claim 释放 3、退款无丢失更新 3。

## 既有测试的行为变更

| 测试 | 变更 |
|---|---|
| `test_supabase_admin_refund_quota_prefers_rpc_and_falls_back_to_patch` | 更名为 `..._uses_only_the_atomic_rpc`；断言反转：RPC 失败时返回 `False`，且**既不** `patch` **也不**读 profile。原测试断言的正是被移除的丢失更新行为 |
