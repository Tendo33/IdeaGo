# IdeaGo saas 全量体检修复

## Goal

在不改变 IdeaGo 现有产品形态的前提下，把 2026-08-17 全量体检报告
(`docs/health-check/2026-08-17-full-audit.md`) 里确证的 30 项问题全部修完，
让 `saas` 分支从「工程纪律好但交付链和运行时经济性有真问题」变成
「验证基线可信、发布物可用、热路径成本合理、状态一致、运维闭环完整」。

**非目标**：不重写流水线、不改报告契约、不引入新框架、不重做设计系统、
不把 hosted-only 依赖挪回 `main`。所有修复都在现有能力之上做增量。

## Source Of Truth

- 体检报告：`docs/health-check/2026-08-17-full-audit.md`（含每一项的文件行号证据）
- 本次已确认的 4 个前置决策：
  1. 用父任务 + 子任务树推进
  2. 范围是全部 30 项（🔥6 + ⚡️14 + 🌱10）
  3. 发布镜像前端配置**改为运行时配置**（不走 build-args 绑定）
  4. 生产是**单进程 docker compose 单容器** → 分布式取消降为「为未来铺路」，
     不按现网 bug 处理，但仍要修，排在 ⚡️ 尾部

## Requirements

### R1 验证基线必须先恢复可信

当前 `uv run pytest` 在干净 HEAD 上 2 failed。在基线红的情况下做任何其他修复，
真实回归都会被噪声掩盖。因此 `ci-baseline` 是唯一的硬前置，必须最先合入。

### R2 发布物必须开箱可用

Docker Hub 上发布的镜像当前登录完全不可用。修复后，任何人 `docker pull` +
配好 `.env` 即可运行，镜像不绑定任何特定 Supabase 项目。

### R3 安全修复不得依赖运维配置生效

OAuth state 绑定、生产关文档、日志脱敏、外链白名单必须是代码层默认行为，
不能是「文档里写了要配」。

### R4 性能修复不得放宽安全语义

认证缓存会把「会话撤销立即生效」放宽为「≤N 秒生效」。这是一个需要显式
承认并写进 spec 的权衡，且撤销路径（logout / delete_account / admin 操作）
必须主动失效本地缓存，把实际延迟压回 0。

### R5 状态一致性修复必须保持向后兼容

`report_status`、`processing_reports`、`processed_webhook_events` 的 schema 变更
必须是加列而非改列，且新旧代码在滚动期间都能工作。

### R6 每一项修复都要有新的验证证据

按项目 `CLAUDE.md`：声明完成前必须跑与改动面匹配的检查。禁止「应该可以」收尾。

### R7 文档与代码必须同步

`.trellis/spec/`、`.env.example`、`DEPLOYMENT.md`、`README.md` 里凡是被本次
改动影响的部分，都在对应子任务里一起改，不留到最后统一补。

## Task Map

| 子任务 | 覆盖体检报告项 | 优先级 | 依赖 |
|---|---|---|---|
| `08-18-ci-baseline` | #1 | P0 | 无（硬前置） |
| `08-18-release-runtime-config` | #2 + `.dockerignore` + CI 断言 | P0 | ci-baseline |
| `08-18-security-hardening` | #3 #5 #16 #17 #28 + 注销细节 + 头像 referrer | P1 | ci-baseline |
| `08-18-runtime-perf` | #4 #7 #8 #9 #13 #14 #15 + 共享 httpx client | P1 | ci-baseline |
| `08-18-state-consistency` | #6 #11 #12 #18 #22 + refund 丢失更新 | P1 | ci-baseline |
| `08-18-frontend-ux` | #10 #19 #20 + reconcile 简化 | P2 | state-consistency(#22) |
| `08-18-ops-observability` | #23 #24 #25 + proxy-headers + 审计补全 | P2 | ci-baseline |
| `08-18-codebase-hygiene` | #26 #27 #29 + migration 编号 | P2 | 其余全部（最后清理） |
| `08-18-e2e-contract-tests` | #21 + 中间件顺序测试 | P2 | state-consistency, runtime-perf |
| `08-18-product-increments` | #30 + 配额告警幂等 | P3 | state-consistency(#11) |

## Cross-Child Acceptance Criteria

这些是父任务级别的、跨子任务才能验收的标准。子任务各自的验收写在各自 `prd.md`。

- [ ] **AC1 全栈校验全绿**：`uv run ruff check src tests scripts` /
      `uv run ruff format --check src tests scripts` / `uv run mypy src` /
      `uv run pytest` / `pnpm --prefix frontend lint` / `typecheck` / `test` / `build`
      全部通过，且 pytest 覆盖率不低于当前的 84.47%
- [ ] **AC2 测试不含挂钟依赖**：全仓不存在「今天跑过、某天会自己变红」的用例。
      以 `git grep` 检查测试里的硬编码日期字面量，凡参与时间衰减计算的都已注入固定时间源
- [ ] **AC3 发布物可用**：从 `Dockerfile` 构建的镜像在**不传任何 `VITE_*`**
      的情况下，前端登录页能拿到 Supabase 与 Turnstile 配置并正常渲染登录入口
- [x] **AC4 认证热路径往返数下降**：`POST /api/v1/analyze` 的出站 Supabase 请求
      从基线 6 次（4 认证 + 2 配额）降到**稳态 1 次、冷路径 3 次**，
      由 `tests/test_auth_roundtrip_budget.py` 逐条断言。
      原目标写的是「≤2 次」，实际未做 design.md 的第三层（合并 RPC），
      因为本机无法验证新增的 Supabase RPC；理由记在 runtime-perf 的 prd.md
- [ ] **AC5 无未调度的清理函数**：`supabase/migrations/` 里定义的每一个
      `cleanup_*` 函数，要么被 `_periodic_cleanup()` 调用，要么在 `DEPLOYMENT.md`
      里有明确的 pg_cron 配置说明
- [ ] **AC6 无生产死代码**：`scripts/run_vulture.py` 对 `src/` 的输出中，
      本报告点名的死代码项全部消失
- [ ] **AC7 文档零漂移**：`.env.example` 中每一个变量名都能在
      `config/settings.py` 找到对应字段，每一个示例值都不会导致启动失败；
      `.trellis/spec/` 中被本次改动影响的条目全部更新
- [ ] **AC8 端到端链路有测试**：存在一个集成测试覆盖
      `POST /analyze → SSE 终态 → GET /reports/{id} 可读`，并在 CI 中运行
- [ ] **AC9 每个子任务独立可验证**：每个子任务有独立提交，提交信息说明覆盖了
      报告的哪几项，且该提交单独 checkout 时全栈校验通过

## Constraints

- 分支：全部工作在 `saas`，base branch `saas`
- 包管理：前端 `pnpm`，Python `uv`
- 不得把 hosted-only 的 auth / billing / Supabase / quota / admin 依赖引入 `main` 可共享的路径
- 单进程部署是当前现实：不得引入要求多副本才正确的设计
- Supabase schema 变更一律新增 migration 文件（从 `019_` 开始），不改历史文件
- 保持 `mypy src` 零报错、`ruff` 零报错的现状，不新增 `# type: ignore` 除非有注释说明

## Rollout / Rollback Shape

- 每个子任务一个独立提交，可单独 revert
- 涉及 DB 的子任务（`state-consistency`、`ops-observability`）的 migration 必须
  是加列/加表/加函数，可在不回滚 DB 的前提下 revert 代码
- 认证缓存（`runtime-perf`）用 settings 开关控制 TTL，设为 0 即退回当前行为
- 前端运行时配置（`release-runtime-config`）保留对 `VITE_*` 的兼容读取作为回退，
  两条路径都可用时优先运行时值
