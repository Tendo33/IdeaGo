# 执行计划：IdeaGo saas 全量体检修复

## 执行原则

1. **ci-baseline 是硬前置**，必须第一个完成并验证通过，否则后续所有验证都不可信。
2. **一个子任务 = 一个提交**。提交前必须跑与改动面匹配的检查（见下方 Gate 定义）。
3. **每个子任务完成后回到本文件打勾**，并在父任务 `prd.md` 的 Cross-Child AC 上
   核对是否有新满足的条目。
4. 遇到与 `design.md` 冲突的实现约束时，**先回来改 design.md 再继续写代码**，
   不要让代码和设计悄悄分叉。

## 提交策略（2026-08-18 用户决策）

- **全部 10 个子任务做完、全部 Gate 跑绿后一次性提交**，中途不 commit。
- `.trellis/tasks/08-18-*` 的规划产物**一并入库**。
- 因此下方每个子任务里的「提交 xxx」不再是独立 commit，而是最终提交信息的一个条目；
  各子任务仍然必须独立跑完自己的 Gate 才算完成。
- 父任务 `prd.md` 的 AC9「每个子任务独立提交」相应作废，替换为：
  最终提交的信息中必须逐条列出覆盖了体检报告的哪些项。

## Gate 定义

| Gate | 命令 | 何时跑 |
|---|---|---|
| `G-py` | `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src && uv run pytest` | 改了任何 `src/` 或 `tests/` |
| `G-fe` | `pnpm --prefix frontend lint && pnpm --prefix frontend typecheck && pnpm --prefix frontend test && pnpm --prefix frontend build` | 改了任何 `frontend/` |
| `G-full` | `G-py` + `G-fe` | 跨层改动、docs/平台改动、以及每个子任务的最后一次迭代 |
| `G-docker` | `docker compose build`（若本机可用）或至少 `docker build .` | 改了 Dockerfile / .dockerignore / compose |
| `G-vulture` | `uv run python scripts/run_vulture.py` | codebase-hygiene 子任务 |

## 阶段与顺序

### Phase A — 恢复基线（阻塞其余全部）

- [x] **A1 `08-18-ci-baseline`** — 完成，803 passed / 覆盖率 84.62%
  - `pre_filter.filter_raw_results` 增加 `now` 关键字参数，内部不再直接
    `datetime.now()`；调用方不传，行为不变
  - `tests/test_pre_filter.py` 传固定 `now`，断言从 `score >= 0.52` 改为
    `signal_rich.score > popularity_only.score`（保留分量断言）
  - `git grep -nE '20[0-9]{2}-[0-9]{2}-[0-9]{2}' tests/` 全量排查，产出清单，
    逐项判断是否参与时间衰减，全部处理
  - Gate：`G-py`，且 pytest 必须 **777+ passed, 0 failed**
  - 提交：`fix(tests): make pre-filter scoring tests time-independent`

### Phase B — 交付链与安全（可并行，互不冲突）

- [x] **B1 `08-18-release-runtime-config`** — 完成，端到端证明发布形态产物零烧入配置
  - 后端 `routes/config.py` + 白名单构造 + 挂载
  - 前端 `lib/config/runtime.ts` + `main.tsx` 加载时序 + `supabase/client.ts`
    懒初始化 Proxy + `featureFlags` / `LoginPage` 取值来源
  - `Dockerfile` 删 VITE ARG、`docker-compose.yml` 删 build args、
    `.dockerignore` 删 `!frontend/.env` 两行
  - CI 增加断言：构建产物里不得出现硬编码的 supabase 域名
  - 文档：`DEPLOYMENT.md` §3/§7、`README.md` 配置章节、`.trellis/spec/frontend/`
  - Gate：`G-full` + `G-docker`
  - 提交：`fix(deploy): load public frontend config at runtime instead of build time`

- [x] **B2 `08-18-security-hardening`** — 完成，826 passed / 84.72%，OAuth 攻击复现被挡在 code 交换前
  - OAuth state 与 HttpOnly cookie 双向绑定（一次性、SameSite=Lax、600s）
  - `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` when production；
    `http_middleware` 的 docs CSP 分支相应收敛
  - `lib/utils/safeUrl.ts` + `CompetitorCard` / `PainSignalsCard` /
    `EvidenceSummaryPanel` 统一走它；外链加 `referrerPolicy="no-referrer"`
  - 头像 `<img>` 同样白名单 + `referrerPolicy`
  - 日志脱敏：`supabase_admin.py` / `admin.py` 不再打 `resp.text` 全文
  - Supabase HS256：允许降级远程验证 + 启动期 JWKS 自检告警
  - 注销失败响应只回 `phase` + `cleanup` 枚举态 + `incident_id`
  - Gate：`G-full`
  - 提交：`fix(security): bind OAuth state, close prod docs, sanitize logs and links`

### Phase C — 性能与一致性（C1/C2 可并行）

- [x] **C1 `08-18-runtime-perf`** — 完成，839 passed / 84.72%；稳态认证往返 6→1
  - `/health` 去外部依赖 + 探测结果 TTL 缓存 + 共享 client
  - `http/clients.py` 收敛全部 httpx client，lifespan 统一关闭
  - `request.state` 认证复用（层 1）
  - `auth/session_cache.py` TTL 缓存 + 全部撤销路径主动失效（层 2）
  - migration `021` 合并 RPC（层 3）
  - 删 `/analyze` 的 `check_quota_available`
  - migration `022` dedup 槽位有效性下沉，删掉请求内 10.5s×3 轮询
  - `metrics` 改记路由模板 + 500 key 软上限
  - SSE status-only 轮询指数退避
  - **必须新增测试**：断言 `POST /analyze` 的 Supabase 出站请求次数 ≤2
  - Gate：`G-py`（+ `G-fe` 若动到 SSE 前端侧）
  - 提交：`perf(api): cut auth round-trips, fix metrics leak, remove health amplifier`

- [x] **C2 `08-18-state-consistency`** — 完成，851 passed / 84.81%；分布式取消已明确推迟并记录理由
  - 中间件顺序：CORS 移到最外层 + `expose_headers=["X-Trace-Id"]`
    + 测试断言 429/403 带 CORS 头
  - 缓存命中退配额（或把扣减下移到 cache 分支之后——实现时二选一并记录理由）
  - migration `019` + `put_with_terminal_status`，`persist_report_node` 改用，
    删掉 `_run_pipeline` 报告路径上的独立 complete 写入
  - migration `020` Stripe webhook 三态（claim → process → completed），
    失败释放 claim
  - `refund_quota_charge` 删掉读改写回退，改为记指标 + 留待对账
  - 分布式取消：`report_status.cancel_requested` + 节点边界检查（放最后）
  - Gate：`G-py`
  - 提交：`fix(consistency): atomic report terminal state, webhook idempotency, CORS ordering`

### Phase D — 前端与运维（D1 依赖 C2）

- [x] **D1 `08-18-frontend-ux`** — 完成，246 tests；reconcile 简化推迟到 E1 之后（需要先有 e2e 安全网）
  - 401 自动 refresh + 重放（模块级 promise 去重），跳转改 router navigate + toast
  - `useReportStatusResolution` 简化：删两层递归 reconcile
  - `sseReducer.flush` 批量 drain
  - 加载态改叠加（AdminPage / HistoryPage），保留旧数据 + `aria-busy`
  - `aria-live`、表格 `<caption>` / `<th scope>`、分页总页数
  - ErrorBoundary `Sentry.captureException` + UI 不再显示原始 message
  - Gate：`G-fe`
  - 提交：`fix(frontend): silent token refresh, simplify reconcile, a11y and loading polish`

- [x] **D2 `08-18-ops-observability`** — 完成，856 passed / 84.74%；Prometheus 与 trace 贯穿明确未做并记录理由
  - 全部 `cleanup_*` RPC 接入 `_periodic_cleanup()`；migration `023` 补
    `auth_sessions` 清理函数
  - `uvicorn.run(..., proxy_headers=True, forwarded_allow_ips=...)` +
    新增 settings 项 + `DEPLOYMENT.md` §8 说明
  - 业务常量配置化：`daily_analysis_limit`、配额告警阈值；与 DB
    `get_plan_limit()` 对齐
  - Prometheus 端点 + `X-Trace-Id` 贯穿到流水线事件与 Supabase 请求头
  - `exception_handlers` 显式 `sentry_sdk.capture_exception` + trace tag
  - 审计补全：报告删除、导出；审计写入失败落告警而非静默
  - Gate：`G-py`
  - 提交：`feat(ops): schedule all cleanups, fix proxy headers, add prometheus and trace propagation`

### Phase E — 收尾（依赖前面全部）

- [x] **E1 `08-18-e2e-contract-tests`** — 完成，12 个跨层用例 + CI 独立 job；868 passed
  - `tests/integration/test_analyze_flow.py`：`POST /analyze → SSE 终态 →
    GET /reports/{id}` 全链路（用 in-memory 假 Supabase / 假 LLM）
  - 中间件顺序契约测试
  - PostgREST 4xx 语义契约测试（含 `deletion_pending` 列缺失的回退分支）
  - CI 增加对应 job
  - Gate：`G-py`
  - 提交：`test: add end-to-end analyze flow and middleware ordering contracts`

- [x] **E2 `08-18-codebase-hygiene`** — 完成，879 passed；nodes.py 未拆并记录理由
  - 删死代码：`extract_token_subject` + `_run_async_for_sync_context` +
    `scripts/benchmark_extract_token_subject.py`、`settings.supabase_jwt_secret`、
    `token.ts` 三个空实现
  - `_raise_temporarily_unavailable` 改 `NoReturn`，处理暴露出来的不可达代码
  - 拆分 `auth/supabase_admin.py`(902) 与 `pipeline/nodes.py`(1114)
  - `.env.example` 全量对齐（6 处漂移 + 补齐缺失变量）
  - `DEPLOYMENT.md` 补 Supabase CAPTCHA、pg_cron、migration 顺序、单进程限制
  - `.trellis/spec/` 全量更新（scripts.md、hosted-operations.md、
    config-logging.md、frontend/、verification.md）
  - migration `000` 重命名/重生成
  - Gate：`G-full` + `G-vulture`
  - 提交：`chore: remove dead code, split oversized modules, align docs with code`

- [x] **E3 `08-18-product-increments`** — 完成，891 passed / 247 frontend；PDF 与分享链接未做并记录理由
  - `force_refresh` 参数（明确扣配额，绕过 cache_lookup）
  - PDF 导出 / 带过期 token 的只读分享链接
  - 配额告警幂等（每日只发一次）
  - Gate：`G-full`
  - 提交：`feat: force refresh, shareable report export, idempotent quota alerts`

### Phase F — 父任务收口

- [x] **F1** 逐条核对父任务 `prd.md` 的 AC1–AC9
- [x] **F2** 跑一次完整 `G-full` + `G-docker`
- [ ] **F3** 用体检报告的 30 项清单逐项标注「已修 / 已改方案 / 未做+理由」，
      把结果追加到 `docs/health-check/2026-08-17-full-audit.md` 末尾
- [ ] **F4** `python3 ./.trellis/scripts/task.py archive` 各子任务与父任务

## 回滚点

| 回滚点 | 触发条件 | 动作 |
|---|---|---|
| RB-1 | B1 的运行时配置导致首屏白屏或 SSR/测试大面积失败 | revert B1 提交，临时改用 `release.yml` 传 build-args 保住发布链 |
| RB-2 | C1 的认证缓存出现会话撤销不生效 | `AUTH_SESSION_CACHE_TTL_SECONDS=0` 热关闭，无需回滚代码 |
| RB-3 | C2 的 migration 019/020 在生产 Supabase 上失败 | migration 只加不改，revert 代码即可回到旧路径 |
| RB-4 | D1 的 401 refresh 造成登录死循环 | revert D1 提交；`fetchWithTimeout` 回到直接跳转 |
| RB-5 | 任一 Phase 后 `G-full` 变红且 30 分钟内定位不到 | revert 该 Phase 全部提交，回到上一个绿色基线再重来 |

## 当前状态

- 阶段：Phase 1 规划中
- 下一步：完成各子任务的 `prd.md` / `implement.md`，然后 `task.py start`
  `08-18-ci-baseline` 开始 Phase A
