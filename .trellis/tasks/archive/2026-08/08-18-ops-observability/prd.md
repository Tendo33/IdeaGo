# 运维与可观测性

## 已完成

### 1. 反向代理下的真实客户端 IP（体检 P2）

`uvicorn.run(app, ...)` 没传 `proxy_headers` / `forwarded_allow_ips`。
uvicorn 默认只信任来自 `127.0.0.1` 的 `X-Forwarded-*`，而 Docker 里反代是
**另一个容器**、地址不同 → 头被丢弃 → `request.client.host` 恒为反代地址。

后果是静默的：所有审计记录的 IP 都一样（审计轨迹失效），传给 Cloudflare 的
Turnstile `remoteip` 也是错的（削弱风险判定）。

- 新增 `TRUST_PROXY_HEADERS`（默认 true）与 `FORWARDED_ALLOW_IPS`（默认 `127.0.0.1`）
- `get_forwarded_allow_ips()` 支持逗号分隔列表与 `*`
- `DEPLOYMENT.md` §8 用一整节写清楚这个坑与配置方法

### 2. 全部 cleanup RPC 接入调度（体检 #23，AC5）

migration 005/010/011/012 定义了 4 个 `cleanup_*` 函数，Python 侧**一个都没调**；
`auth_sessions` 连清理函数都没有。四张表随部署时长无限增长。

- 新增 `migration 019_cleanup_auth_sessions.sql`（已撤销的留 24h 宽限、
  超过 token 生命周期的直接删）
- 新增 `observability/retention.py`：把全部保留策略集中成 `RetentionJob` 列表，
  由 `_periodic_cleanup()` 每小时执行；单个 job 失败不影响其余
- **`tests/test_retention.py` 扫描 `supabase/migrations/*.sql` 里定义的每一个
  `cleanup_*` 函数，断言它要么在 `build_retention_jobs()` 里、要么有独立调用点**
  —— 这条测试才是真正防止「再出现第五个孤儿函数」的机制

### 3. 业务常量配置化（体检 #24）

- `DAILY_ANALYSIS_LIMIT`：原来是 `supabase_admin.py` 里的 `_DAILY_ANALYSIS_LIMIT = 5`，
  改免费额度要改代码+发版。改为 settings（并在注释里点明必须与 DB 的
  `public.get_plan_limit()` 保持一致——RPC 路径以 DB 为准）
- `QUOTA_WARNING_THRESHOLD`：原来是 `analyze.py` 里硬编码的 `0.8`

### 4. Sentry 盲区（体检 #20 的后端一半）

注册全局 `@app.exception_handler(Exception)` 会**阻止异常传播到 Sentry 的
中间件**，所以未处理异常一直只落本地日志、从未上报。现在在 handler 里显式
`sentry_sdk.capture_exception`，并把 `trace_id` 与 `path` 设成 tag，
让日志与 Sentry 事件可以互查。未配置 DSN 时静默跳过。

### 5. 审计补全

`DELETE /reports/{id}` 是用户发起的破坏性操作，此前不进审计。已补
`report.delete` 事件（含 target_id 与客户端 IP）。

### 6. 部署文档补齐（体检 #29 的一部分）

`DEPLOYMENT.md` 新增/改写四处：

- §8 反向代理必须配 `FORWARDED_ALLOW_IPS`，说明失败是静默的
- §8b **单进程限制**：明确列出三项仍是进程内状态（在途 pipeline task、
  SSE run state、metrics）及各自的扩容后果，并写明「加 worker 不是纯配置变更」。
  代码里的 PG dedup / PG checkpointer 会让人误以为多副本已经可用
- §4 **Supabase Attack Protection 必须开启 CAPTCHA**：前端把 `captchaToken`
  传给了 Supabase，但只有项目里启用了 CAPTCHA 保护 Supabase 才会真正校验，
  否则验证码只是装饰，机器人可以直接用 anon key 批量注册并烧 LLM 配额
- §4 **migration 顺序消歧**：`000_all_migrations.sql` 只覆盖 001–012，
  写清两种正确的执行方式，以及不要两者都跑

## 未做

**Prometheus 端点与 trace 全链路贯穿**。原计划包含这两项，实际未做：

- 当前是单进程部署，`/admin/metrics` 的进程内快照就是完整视图，
  Prometheus 的主要价值（跨副本聚合）暂时不存在
- trace 贯穿要改动流水线事件结构与全部 Supabase 请求头，属于跨层改造，
  放在这个已经很宽的子任务里会稀释验证质量

两项都记入体检报告的「未做」清单，等真正要扩容时再做——那时
§8b 列的三项也必须一起解决。

## 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 135 files already formatted
uv run mypy src                            → Success: no issues found in 89 source files
uv run pytest                              → 856 passed, 0 failed, 覆盖率 84.74%
```

新增 `tests/test_retention.py` 5 个（含 SQL↔调度对应关系断言）。

## 既有测试的行为变更

| 测试 | 变更 |
|---|---|
| `test_health_route_internal_checks_and_main_entrypoint` | `uvicorn.run` 断言补上 `proxy_headers` / `forwarded_allow_ips`，并注释说明为什么这两个参数必须存在 |
| `test_billing_and_reports_remaining_success_and_error_branches` | `delete_report` 现在首参是 `Request`（用于审计 IP），补一个请求 stub |
