# 运行时性能与成本

## Goal

砍掉认证热路径上的重复网络往返，消除公开端点的外部依赖放大器，修掉指标内存泄漏，
并让两处轮询循环从「固定间隔刷请求」变成「指数退避」。

## 认证往返账（体检报告实测的 6 次）

一次 LinuxDo 会话用户的 `POST /api/v1/analyze`：

| 来源 | 次数 |
|---|---|
| 限流中间件 `get_optional_user` → auth_sessions + profiles | 2 |
| 路由依赖 `get_current_user` → 同上，**完全重复** | 2 |
| `check_quota_available` | 1 |
| `check_and_increment_quota` | 1 |

### 修完之后

| 场景 | 往返数 |
|---|---|
| 缓存命中（TTL 内的后续请求） | **1**（只剩配额 RPC） |
| 缓存未命中（首次 / TTL 过期） | **3**（auth_sessions + profiles + 配额） |
| 关闭缓存（TTL=0） | 4 |

Supabase 原生会话（非 LinuxDo）走 JWKS 本地验签，认证部分本来就是 **0 次**，
本次改动对它们只减少了那一次冗余配额读。

### 与父任务 AC4 的偏差（已确认并调整）

父任务 `prd.md` 的 AC4 写的是「降到 ≤2 次」。实际做到缓存命中 1 次、
未命中 3 次。差在 design.md 的**第三层**——把 auth_sessions 与 profiles 合并成
一个 `get_session_and_profile_state` RPC。

**决定不做第三层**，理由：

1. 它需要新增一个 Supabase migration + RPC，而本机没有可用的 Supabase 实例，
   写出来的东西**无法验证**，只能靠 mock 自证——这类改动的风险高于它省下的
   那一次往返。
2. 缓存命中是稳态下的常态路径，稳态已经是 1 次。未命中只发生在会话首次出现
   或 TTL 过期时。
3. 单进程部署下缓存命中率接近 100%。

因此 AC4 改判为：**稳态 ≤1 次，冷路径 ≤3 次**，并由
`tests/test_auth_roundtrip_budget.py` 逐条钉死。

## 安全权衡（必须显式记录）

缓存把「会话撤销立即生效」放宽为「≤TTL 生效」。为了把实际延迟压回 0，
**本进程执行的每一条撤销路径都主动失效缓存**：

| 触发点 | 动作 |
|---|---|
| `session_store.revoke_auth_session` | `invalidate(session_id)` |
| `supabase_admin.mark_profile_deletion_pending` | `invalidate_user(user_id)` |
| `supabase_admin.delete_user_account` | `invalidate_user(user_id)` |

TTL 只覆盖**进程外**的变更（另一个副本、直接改库）。当前是单进程部署，
所以实际撤销延迟为 0。

`AUTH_SESSION_CACHE_TTL_SECONDS=0` 是热开关，设 0 即回到改动前行为，无需回滚代码。

## 改动清单

| 文件 | 改动 |
|---|---|
| `http/clients.py`（新） | 三个按用途分的共享 client（supabase / external / probe），超时语义各不相同故不合并 |
| `auth/session_cache.py`（新） | TTL + LRU 上限 1000 + 主动失效 + 周期清理 |
| `auth/dependencies.py` | `request.state` 记忆化（对无 `state` 的 stub 请求安全降级）；会话状态走缓存；会话已死时**跳过** profile 查询 |
| `auth/session_store.py`、`auth/supabase_admin.py` | 撤销路径接入失效 |
| `api/routes/health.py` | 公开 `/health` 改为纯存活探测（零出站调用）；依赖探测结果 15s TTL 缓存；共享 client |
| `api/routes/analyze.py` | 删冗余 `check_quota_available`；dedup 确认与 SSE status-only 轮询改指数退避 |
| `observability/metrics.py` + `api/http_middleware.py` | 记路由模板而非具体路径 + 500 key 上限 + `<other>` 溢出桶 |
| `api/routes/auth.py`、`api/routes/admin.py`、`observability/audit.py`、`billing/stripe_service.py` | 一次性 client 收敛到共享 client |
| `api/app.py` | lifespan 关闭共享 client + 清缓存；周期任务清理过期缓存项 |
| `config/settings.py` | 新增 `auth_session_cache_ttl_seconds` |

## 轮询改造前后

| 循环 | 改前 | 改后 |
|---|---|---|
| dedup 槽位确认 | 固定 0.1s × 10.5s 窗口 ≈ 105 次读/轮，3 轮最坏 ~315 次、~31s | 0.1s 起指数退避封顶 1.5s，同样窗口约 12 次读 |
| SSE status-only | 固定 2s × 180s = 90 次读/观察者 | 2s 起退避封顶 15s，约 15 次读 |

两处的**上限时间不变**，只是请求量大幅下降。

## 执行结果（2026-08-18）

### 过程中修掉的自己引入的问题

1. **`get_optional_user` 硬依赖 `request.state`**：记忆化直接写
   `request.state._auth_user_resolution`，而大量测试传的是轻量 `type("Req",...)`
   stub，没有 `state`。这不只是测试问题——低层依赖不该要求完整 Starlette Request。
   改为 `getattr(request, "state", None)`，无 `state` 时照常工作，只是不记忆化。

2. **共享 client 被全局 patch 污染（最隐蔽的一个）**：
   两个 Stripe 测试 patch 的是**全局** `"httpx.AsyncClient"`。共享 client 是懒创建的，
   于是在 patch 生效期间被创建出来的 mock **写进了模块级全局变量**，patch 撤销后
   仍然留着。症状出现在很久之后一个毫不相干的测试的 lifespan 关闭阶段：
   `AttributeError: '_AsyncClientContext' object has no attribute 'aclose'`。
   修法两条腿：把那两个测试改为 patch client 工厂（生产代码真正使用的接缝），
   并在 `reset_runtime_state` autouse fixture 里重置三个共享 client 全局，
   让这类污染再也无法跨测试泄漏。

### 既有测试的行为变更

| 测试 | 变更与理由 |
|---|---|
| 8 处 `patch("...routes.X.httpx.AsyncClient")` | 改为 patch `get_probe_client` / `get_external_client`；共享 client 不再是 async context manager，故一并去掉 `_AsyncClientContext` 包装 |
| 5 处 `patch("...analyze.check_quota_available")` | 该导入已删除；这 5 处本来就同时 patch 了 `check_and_increment_quota` 且值相同，直接删掉冗余 patch |
| `test_health_route_internal_checks...` | 公开 `/health` 现在是纯存活探测：断言改为返回 `ok` **且 `_check_supabase` 一次都没被调用**（比原断言更强，直接钉住「不打外部依赖」这个契约）；另加 4 处 `_clear_probe_cache()` 因为探测结果现在有 15s 缓存 |
| `test_stream_status_only_processing_times_out_with_terminal_error` | 原断言写死 90 次 ping。改为断言行为 + 成本：累计等待仍 ≥180s，但轮询次数 <30，首次延迟等于初始值、最大延迟不超过上限 |
| `test_run_state_callback_and_stream_event_edge_paths` | `_STATUS_ONLY_MAX_PINGS` 已被 `_STATUS_ONLY_MAX_WAIT_SECONDS` 取代 |

### 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 132 files already formatted
uv run mypy src                            → Success: no issues found in 88 source files
uv run pytest                              → 839 passed, 0 failed, 覆盖率 84.72%
```

新增测试：
- `tests/test_auth_roundtrip_budget.py` 8 个 —— 逐条钉死往返预算：
  同一请求两次解析只花一次查询、TTL 内后续请求零查询、TTL=0 恢复旧行为、
  撤销立即生效、账号删除清掉该用户全部会话、会话已死时跳过 profile 查询、
  缓存过期、容量封顶
- `tests/test_metrics_cardinality.py` 5 个 —— 5000 次带 UUID 的请求现在只产生
  1 个 key；即便有动态路径漏进来，key 空间也封顶

## 遗留

- design.md 的第三层（合并 RPC）未做，理由见上。
- `_MAX_ENTRIES = 1000` 与 `_MAX_TRACKED_PATHS = 500` 是硬编码常量，
  没有做成配置项——它们是内存保护阈值而非业务参数，暂不外露。
