# 代码卫生与文档对齐

## 已完成

### 1. 生产死代码清理（体检 #27，AC6）

| 项 | 处理 |
|---|---|
| `extract_token_subject` | 删除。生产零调用，只有测试和一个 benchmark 脚本引用 |
| `_run_async_for_sync_context` | 删除。起线程跑 `asyncio.run` 的同步/异步桥，存在的唯一理由就是上面那个函数 |
| `scripts/benchmark_extract_token_subject.py` | 删除（benchmark 的对象已不存在） |
| `settings.supabase_jwt_secret` | 删除。`src/` 内零消费，且 `.env.example` 早已注明新项目不需要 |
| 前端 `readCustomAuthSession` / `saveCustomAuthSession` / `clearCustomAuthSession` | 删除。三个空实现，注释写着「保留 API 兼容」但无任何调用点 |
| 前端 `refreshAuthToken` | 删除。已被 `core.ts` 的 `refreshSessionOnce` 取代——后者才是真正接进 401 路径的那个 |

`.trellis/spec/shared/scripts.md` 同步删掉 benchmark 脚本条目。

vulture 剩余报告全部是 `date_utils` / `decorator_utils` 里的通用工具函数
（60% 置信度，本次改动前就存在，属于工具库的正常冗余），体检点名的死代码项已全部消失。

### 2. 拆分 `supabase_admin.py`（体检 #26）

902 行 → **705 行**（删死代码）+ 新增 `auth/account_deletion.py` **300 行**。

拆出去的是账号注销 saga——它是跨 PostgREST / Stripe / Supabase auth 三套系统、
带补偿的多阶段编排，和「普通 PostgREST 数据访问」混在一个文件里。

**过程中踩到并修正的一个真问题**：第一版把共享 helper
（`_is_configured` / `_get_client` / `_headers` / `mark_profile_deletion_pending` …）
用 `from ... import <name>` 导进新模块。结果 12 个既有测试失败——
因为按名字导入会在新模块里绑定副本，
`patch("ideago.auth.supabase_admin._is_configured")` 对 saga **不再生效**。

这不只是测试问题：任何人以后 patch 或 monkeypatch 这些 helper 都会踩同样的坑，
而且是静默失效。改为 `from ideago.auth import supabase_admin` 并按
`supabase_admin.<helper>()` 调用，所有既有 patch 目标继续有效，
只有真正搬家的 saga 函数需要改 patch 目标。

`supabase_admin.py` 保留对 saga 函数的 re-export，既有 import 全部不受影响。

`pipeline/nodes.py`（1135 行）**未拆**：它是 LangGraph 节点集合，
节点之间共享大量私有 helper 与 `GraphState` 约定，拆分会制造跨模块的隐式耦合，
收益不如 saga 那次明确。记入遗留。

### 3. `.env.example` 全量对齐（体检 #29，AC7）

修掉体检点名的 6 处漂移：

| 变量 | 原值 | 问题 |
|---|---|---|
| `ENVIRONMENT` | 注释说可填 `testing` | 校验器只接受 development/staging/production，填 `testing` **直接启动失败** |
| `SOURCE_TIMEOUT_SECONDS` | 30 | 实际默认 60 |
| `EXTRACTION_TIMEOUT_SECONDS` | 180 | 实际默认 240 |
| `APPSTORE_COUNTRY` | cn | 实际默认 us |
| `LANGGRAPH_MAX_RETRIES` | 3 | 实际默认 2 |
| `CORS_ALLOW_ORIGINS=*` | 无说明 | 生产下该值会让应用拒绝启动，现已就地注明 |

补齐此前完全缺失的变量：`AGGREGATION_TIMEOUT_SECONDS`、
`SUPABASE_JWKS_CACHE_TTL_SECONDS`、`SOURCE_QUERY_CAPS`、
`QUERY_FAMILY_DEFAULT_WEIGHTS`、`APP_TYPE_ORCHESTRATION_PROFILES`，
以及本轮新增的 `TURNSTILE_SITE_KEY`、`FRONTEND_SENTRY_DSN`、`PRICING_ENABLED`、
`AUTH_SESSION_CACHE_TTL_SECONDS`、`DAILY_ANALYSIS_LIMIT`、
`QUOTA_WARNING_THRESHOLD`、`TRUST_PROXY_HEADERS`、`FORWARDED_ALLOW_IPS`。

删掉不再需要的 `VITE_*`（公开配置改由 `GET /api/v1/config` 运行时下发）。

**新增 `tests/test_env_example.py` 14 个用例**把这件事变成机制而非一次性清理：
每个文档变量必须能在 `Settings` 找到对应字段、`ENVIRONMENT` 的示例值必须能
真正构造出 Settings、运维必需变量必须被文档化、所有数字示例值必须落在字段
的校验区间内。

### 4. migration 编号消歧

`000_all_migrations.sql` 头部改写：明确它是 **001–012 的 bootstrap 快照**，
写清两种正确执行方式（跑 000 再跑 013+，或逐个跑 001+），
并说明它不会随新 migration 更新。

### 5. Trellis spec 更新（AC7）

`.trellis/spec/backend/hosted-operations.md` 新增四节：认证会话缓存
（含「任何新的撤销路径都必须失效缓存」这条硬约束）、Retention（含 SQL↔调度
对应关系由测试守住）、公开运行时配置（含「永远不要整体序列化 Settings」）、
单进程约束。

`.trellis/spec/shared/verification.md` 新增跨层检查小节，把
`uv run pytest tests/integration -q` 纳入验证命令。

## 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 138 files already formatted
uv run mypy src                            → Success: no issues found in 90 source files
uv run pytest                              → 879 passed, 0 failed, 覆盖率 84.77%
pnpm --prefix frontend lint / typecheck    → 通过
pnpm --prefix frontend test                → 38 files / 246 tests passed
uv run python scripts/run_vulture.py       → 仅剩通用工具函数（改动前即存在）
```
