# 技术设计：IdeaGo saas 全量体检修复

本文只写**跨子任务的共享决策**。单个子任务内部的实现细节写在各自的
`design.md` / `implement.md`。

---

## D1 前端公开配置：构建期烧入 → 运行时读取

### 问题

`Dockerfile` 在 `pnpm build` 前 export `VITE_*`，Vite 把它们内联进 bundle。
`release.yml` 没传 build-args，于是发布镜像里这些值是空串，
`lib/supabase/client.ts:56` 退化成 `createFallbackSupabaseClient()`，
`LoginPage.tsx:61` 的 `authBlocked` 恒为 true。

### 方案

新增后端端点，前端在挂载前拉取一次：

```
GET /api/v1/config   →  200 {
  "supabase_url": "...",
  "supabase_anon_key": "...",
  "turnstile_site_key": "...",
  "sentry_dsn": "...",
  "pricing_enabled": false,
  "environment": "production"
}
```

- 只暴露**本来就要进浏览器**的公开值。`SUPABASE_SERVICE_ROLE_KEY` /
  `AUTH_SESSION_SECRET` / `STRIPE_SECRET_KEY` / `OPENAI_API_KEY` 绝不出现在这里，
  用一个显式白名单构造响应，不做 `model_dump()` 式的批量导出。
- 无需认证（这些值本来就在 HTML/JS 里公开），但必须走
  `Cache-Control: public, max-age=60` 减少请求量。
- 端点放在 `health.py` 同级的新 `routes/config.py`，挂 `/api/v1` 前缀。

### 前端加载时序

```
main.tsx
  └─ await loadRuntimeConfig()        // fetch /api/v1/config，失败则回退 VITE_*
       └─ setRuntimeConfig(cfg)       // 写入模块级单例
            └─ ReactDOM.createRoot(...).render(<App />)
```

- `lib/config/runtime.ts` 持有单例 + `getRuntimeConfig()` 同步读取器。
- `lib/supabase/client.ts` 从 `createClient(...)` 的**模块级立即执行**改为
  懒初始化 `getSupabaseClient()`，因为配置在模块求值时还没到。
  为了不改 100 处调用点，导出的 `supabase` 改成一个 Proxy，
  首次属性访问时才真正 `createClient`。
- **回退链**：运行时配置 → `import.meta.env.VITE_*` → fallback client。
  这样本地 `pnpm dev`（没起后端时）和现有测试都不用改。
- 加载失败不阻塞渲染：显示一个明确的「配置加载失败」界面而不是白屏。

### 为什么不是 `/config.js` + `index.html` script 标签

`/config.js` 方案不需要改前端加载时序，但要在容器启动时生成文件、要处理
静态挂载路径、且 CSP 需要额外放行。`fetch` 方案在现有的
`_register_spa_fallback` 架构下零额外基础设施。

### 影响面

`Dockerfile`（删 VITE ARG 相关行）、`docker-compose.yml`（删 build args）、
`release.yml`（无需改，问题自动消失）、`.dockerignore`（删 `!frontend/.env`）、
`frontend/src/app/main.tsx`、`lib/config/runtime.ts`(新)、
`lib/supabase/client.ts`、`lib/featureFlags.ts`、
`features/auth/LoginPage.tsx`（turnstile site key 来源）、
`src/ideago/api/routes/config.py`(新)、`api/app.py`、
`DEPLOYMENT.md`、`README.md`、`.trellis/spec/frontend/`。

---

## D2 认证热路径：单请求复用 + 短 TTL 缓存

### 问题

`POST /analyze` 一次请求要打 6 次 Supabase：

| 来源 | 次数 | 位置 |
|---|---|---|
| 限流中间件 `get_optional_user` → session + profile | 2 | `rate_limit.py:257` |
| 路由依赖 `get_current_user` → session + profile（重复） | 2 | `analyze.py:213` |
| `check_quota_available` | 1 | `analyze.py:255` |
| `check_and_increment_quota` | 1 | `analyze.py:268` |

### 方案（三层，按性价比递进）

**层 1 — 单请求复用（零语义变化）**

在 `get_optional_user` 里把结果挂到 `request.state.auth_user`（用一个哨兵值区分
「没解析过」和「解析过但是 None」）。限流中间件先解析，路由依赖直接复用。
→ 6 次降到 4 次。

**层 2 — 短 TTL 会话状态缓存**

新增 `auth/session_cache.py`：`dict[str, tuple[float, SessionState]]`，
key 是 `sid`，TTL 由 `settings.auth_session_cache_ttl_seconds` 控制（默认 30，
设 0 即关闭）。缓存 `is_auth_session_active` 与 profile 活跃性的**合并结果**。

主动失效（把撤销延迟压回 0）：
- `revoke_auth_session(sid)` → `invalidate(sid)`
- `delete_user_account(user_id)` → `invalidate_by_user(user_id)`
- `mark_profile_deletion_pending(user_id)` → `invalidate_by_user(user_id)`

单进程部署下这是完整正确的。多副本下会有 ≤TTL 的撤销延迟，这个权衡写进
`.trellis/spec/backend/hosted-operations.md`。
→ 4 次降到 2 次（仅缓存未命中时）。

**层 3 — 合并 RPC**

新增 `get_session_and_profile_state(p_session_id, p_user_id)` RPC，
一次往返返回 `{session_active, profile_active, role}`。
→ 缓存未命中时从 2 次降到 1 次。

**配额**

删掉 `check_quota_available`。`check_and_increment_quota` 本身是原子的
check+increment，先读一次不但多一次往返，还给了竞态一个窗口
（读到未超限 → 并发请求扣满 → 自己再扣就超了）。
错误信息里需要的 `plan_limit` 从 `check_and_increment_quota` 的返回值取。
→ 2 次降到 1 次。

**最终**：6 次 → 缓存命中时 1 次（仅配额），未命中时 2 次。满足 AC4。

### 风险与缓解

- 缓存导致「刚撤销的会话还能用」→ 主动失效覆盖所有撤销路径 + TTL 默认只有 30s
- 内存增长 → 缓存加 LRU 上限（1000 条）+ 在 `_periodic_cleanup` 里清过期项
- 测试不确定性 → 测试 fixture 里把 TTL 设为 0

---

## D3 时间源注入：消灭挂钟依赖的测试

### 问题

`tests/test_pre_filter.py` 把 `freshness_timestamp` 写死成 `2026-03-20`，
`pre_filter` 内部用 `datetime.now()` 算 freshness 衰减，于是用例的结果随
真实日期漂移，5 个月后越过 `0.52` 阈值。

### 方案（读源码后修正）

**初判有误，此处已更正。** `pre_filter` 并没有直接调 `datetime.now()`：
`pre_filter.py:175` 是 `_freshness_signal(raw.get("freshness_timestamp"),
result.fetched_at)`，`pre_filter.py:353` 的 `anchor = fetched_at`。
生产代码的时间来源**本来就是可注入的**。

真正的漏点在 `models/research.py:40-43`——`RawResult.fetched_at` 的
`default_factory` 是 `datetime.now(timezone.utc)`，而测试 helper
`_raw()` 不设置它。于是 fixture 拿到「今天」，与钉死的 `freshness_timestamp`
做差，随日期穿越 30/90/180/365/730 的分桶边界。

所以修复只在测试侧：钉死 `fetched_at`，并让 fixture 时间戳落在一个明确的
freshness 桶里。**零生产代码变更**，风险面大幅小于初判。

同时把断言从**魔法阈值**改成**相对比较**：

```python
# before — 断言一个小数，任何权重微调都会误伤
assert breakdown.score >= 0.52

# after — 断言意图：信号丰富的结果确实排在只有热度的结果前面
assert filtered["tavily"][0].title == "Need a Better Team Wiki"
assert breakdown.score > popularity_breakdown.score
assert getattr(breakdown, expected_component) > 0.55   # 这条保留，它测的是分量本身
```

### 推广检查

`ci-baseline` 子任务要 `git grep` 全部测试里的日期字面量，逐个判断是否参与
时间衰减计算，形成一份清单，全部处理掉（AC2）。

---

## D4 共享 HTTP 客户端

### 问题

项目里有两套习惯：`auth/dependencies.py`、`auth/supabase_admin.py`、
`auth/session_store.py`、`api/rate_limit.py` 用「模块级共享 client +
lifespan 关闭」；而 `routes/auth.py:142,159,339`、`routes/admin.py:169`、
`routes/health.py:27`、`billing/stripe_service.py:52,200,245` 每次调用
`async with httpx.AsyncClient(...)` 新建，每次一个 TLS 握手。

### 方案

新增 `src/ideago/http/clients.py`，按用途提供命名的共享 client：

```python
get_supabase_client()   # timeout 10, max_conn 50   — PostgREST / RPC / auth admin
get_external_client()   # timeout 10, max_conn 20   — LinuxDo / Turnstile
get_probe_client()      # timeout 5,  max_conn 10   — 健康探测 / 审计
close_all_clients()     # lifespan 调用
```

不同 timeout 语义必须保留（探测要快失败，PostgREST 要能等），所以是三个而不是一个。
现有的四处模块级 client 一并收敛过来，`app.py::_lifespan` 的关闭列表塌成一行。

**注意**：`stripe_service.py` 的 Stripe SDK 调用走的是同步 SDK +
`run_in_executor`，不受此影响；只有它里面手写的 PostgREST 调用要改。

---

## D5 中间件顺序

### 问题

Starlette 的 `add_middleware` 是 `user_middleware.insert(0, ...)`，
**最后注册的在最外层**。当前注册顺序：

```
CORS → CSRF → rate_limit → security_headers → trace_id
```

实际执行顺序（外 → 内）：

```
trace_id → security_headers → rate_limit → csrf → CORS → 路由
```

`rate_limit` 的 429 和 `csrf` 的 403 在到达 CORS 层之前短路，响应里没有
`Access-Control-Allow-Origin`。前后端分域部署时浏览器把它们当 CORS 错误拦掉。

### 方案

把 `_configure_cors` 移到所有自定义中间件**之后**注册，使 CORS 成为最外层：

```python
register_csrf_protection_middleware(app)
register_rate_limit_middleware(app, settings=settings, logger=logger)
register_security_headers_middleware(app, environment=settings.environment)
register_trace_id_middleware(app)
_configure_cors(app, settings)          # 最后注册 = 最外层
```

新执行顺序：`CORS → trace_id → security_headers → rate_limit → csrf → 路由`。

**副作用检查**：CORS 变成最外层后，`trace_id` 中间件不再看到 CORS 的 preflight
响应，`metrics.record` 不再统计 OPTIONS。这是**期望的**（preflight 不是业务请求）。
但要确认 `X-Trace-Id` 响应头仍然出现在正常响应上——会的，CORS 中间件透传响应头，
只是需要在 `CORSMiddleware` 的 `expose_headers` 里加上 `X-Trace-Id`，
否则跨域时前端 JS 读不到它。这一点当前也是缺的，一并补。

必须有测试：断言 429 与 403 响应都带 `Access-Control-Allow-Origin`。

---

## D6 报告终态原子化

### 问题

`persist_report_node` 先 `cache.put()` 再 emit `REPORT_READY`（`nodes.py:977-989`），
但 `_run_pipeline` 之后还要**单独**写 `complete` 状态（`analyze.py:162-168`）。
两次 PostgREST 写之间有可见性窗口，SSE 说 ready 了但 `GET /reports/{id}`
可能还读不到。前端为此写了 459 行三层嵌套的 reconcile
（`useReportStatusResolution.ts`）。

### 方案

新增一个 RPC 把「写报告 + 写完成状态」并进一个事务：

```sql
-- migration 019
CREATE OR REPLACE FUNCTION public.persist_report_complete(
  p_report jsonb, p_status jsonb
) RETURNS void ...
-- 内部：INSERT ... ON CONFLICT DO UPDATE reports
--       INSERT ... ON CONFLICT DO UPDATE report_status (status='complete')
```

`SupabaseReportRepository` 增加 `put_with_terminal_status(report, status, ...)`，
`persist_report_node` 改用它，并在写成功**之后**才 emit `REPORT_READY`。
`_run_pipeline` 里那次独立的 `_persist_terminal_status(report_id, "complete", ...)`
在报告路径上删掉（失败/取消路径保留）。

前端 `useReportStatusResolution` 随之简化：`report_ready` 之后一次读取，
最多一次短重试（防 PostgREST 读副本延迟），删掉
`resolveMissingAfterComplete` / `resolveProcessingAfterComplete` 两层递归。

**顺序约束**：后端先改并上线，前端简化才安全。所以 `frontend-ux` 依赖
`state-consistency`。

---

## D7 Migration 编号与 schema 演进

- 本次所有 DB 变更从 `019_` 开始，一个子任务一个文件：
  - `019_persist_report_complete.sql`（state-consistency，D6）
  - `020_webhook_event_states.sql`（state-consistency，Stripe 三态）
  - `021_session_profile_state_rpc.sql`（runtime-perf，D2 层 3）
  - `022_reserve_slot_staleness.sql`（runtime-perf，dedup 下沉）
  - `023_cleanup_auth_sessions.sql`（ops-observability）
- 一律加列/加表/加函数，不改列、不删列。旧代码在新 schema 上照常工作。
- `000_all_migrations.sql` 在 `codebase-hygiene` 里重命名为
  `000_bootstrap_snapshot.sql` 并在头部写清「仅用于全新项目，跑完后从 013 继续」，
  或直接重生成到 018 的完整快照——由该子任务定夺，本文不预设。

---

## D8 单进程前提下的分布式取消

用户已确认生产是单进程 docker compose 单容器。因此：

- 现网**不存在**「取消后配额已退但报告仍完成」的 bug（task 一定在本进程）
- 但代码里的 PG dedup / PG checkpointer / PostgREST 限流都在暗示多副本可行，
  这是一个陷阱：有人照着暗示开了多 worker 就会踩坑

**决策**：仍然实现分布式取消（在 `report_status` 加 `cancel_requested` 列，
流水线在节点边界检查并自行 raise `CancelledError`，本地 task 命中时保留现有快路径），
但排在 `state-consistency` 的最后，且**同时**在 `DEPLOYMENT.md` 写明当前
多副本的其余约束（SSE run_state 仍是进程内、metrics 仍是进程内）。
不承诺「本次之后就能多副本」，只承诺「取消这一项不再是阻塞点」。
