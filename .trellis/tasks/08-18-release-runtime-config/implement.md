# 执行计划：发布镜像运行时配置

## 方案

把公开前端配置从「Vite 构建期内联」改为「启动时从后端拉取」。

```
浏览器加载 index.html
  └─ main.tsx bootstrap()
       ├─ await loadRuntimeConfig(API_BASE)   → GET /api/v1/config
       ├─ initSentry(config)
       ├─ await import('@/lib/i18n/i18n')
       └─ await import('./App')               ← 动态导入是关键
            └─ 模块图求值，lib/supabase/client.ts 此时才读 getRuntimeConfig()
```

### 为什么必须用动态 import 而不是 Proxy

`lib/supabase/client.ts` 在**模块作用域**调用 `createClient`。静态
`import App from './App'` 会在 `bootstrap()` 的 await 之前就把整个模块图求值完，
Supabase client 会被永久钉死在空配置上。

父任务 `design.md` 原本设想用 Proxy 包装 `supabase` 导出来延迟初始化。实际实现
改用**动态 import 推迟整个模块图**：改动面更小（`client.ts` 只换了取值来源，
导出形状不变，100 处调用点零改动），也不需要维护一个假的 Proxy 语义。

### 回退链

`运行时配置（非空字段）` → `构建期 VITE_*` → `空串（调用方显式降级）`

`loadRuntimeConfig` **永不 reject**：后端挂了、或旧后端没有该端点，都退回构建期值，
不阻塞渲染。空配置下 `createFallbackSupabaseClient` 与 `authBlocked` 已有的降级
提示继续生效，因此没有再单独做「配置加载失败」全屏页——现有降级路径已经能说明问题。
（此处与 design.md 的描述有出入，以本文为准。）

## 步骤

- [x] **S1** settings 新增 `turnstile_site_key` / `frontend_sentry_dsn` / `pricing_enabled`
- [x] **S2** `src/ideago/api/routes/config.py`：`PublicConfig` 显式白名单 +
      `build_public_config()` + `GET /config`（`Cache-Control: public, max-age=60`）
- [x] **S3** `api/app.py` 挂载 config router
- [x] **S4** `frontend/src/lib/config/runtime.ts`：三层回退 + 测试 seam
- [x] **S5** `main.tsx` bootstrap 时序 + 动态 import
- [x] **S6** `lib/supabase/client.ts` 改读 `getRuntimeConfig()`
- [x] **S7** `lib/featureFlags.ts` 由 `const PRICING_ENABLED` 改为
      `isPricingEnabled()`（常量会冻结构建期默认值），迁移 App/LandingPage/UserMenu
      共 9 处调用点
- [x] **S8** `LoginPage.tsx` turnstile site key 改读运行时配置
- [x] **S9** `Dockerfile` 删 5 个公开配置 ARG，只留 `VITE_API_BASE_URL`
- [x] **S10** `docker-compose.yml` 删 5 个 build args
- [x] **S11** `.dockerignore` 删 `!frontend/.env` / `!frontend/.env.*` 两行
- [x] **S12** CI `env_consistency` job 加 4 组结构守卫
- [x] **S13** 后端测试 `tests/test_config_route.py`（7 个）
- [x] **S14** 前端测试 `lib/config/__tests__/runtime.test.ts`（9 个）
- [x] **S15** `DEPLOYMENT.md` §3/§7/§11 与 `README.md` 更新
- [x] **S16** Gate `G-full`

## 执行结果（2026-08-18）

### 过程中修掉的两个自己引入的问题

1. **测试污染 Sentry**：`test_config_route.py` 的 fixture 里放了一个 DSN 形状的
   `sentry_dsn`（为了让泄露测试有东西可查），结果 `create_app()` 真的初始化了
   Sentry 并排队发送 3 个事件。改为在 fixture 里 stub 掉 `app_module._init_sentry`。
2. **前端 typecheck 失败**：fetch mock 的 `json: () => ({...})` 返回的不是 Promise，
   而 `Response.json()` 的类型是 `() => Promise<any>`。改成 helper 接收 `body`
   再用 `Promise.resolve` 包装。vitest 不做类型检查，所以测试先绿了、typecheck 才报错。

### 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 126 files already formatted
uv run mypy src                            → Success: no issues found in 85 source files
uv run pytest                              → 810 passed, 0 failed, 覆盖率 84.67%
pnpm --prefix frontend typecheck           → 通过
pnpm --prefix frontend lint                → 通过
pnpm --prefix frontend test                → 36 files / 218 tests passed
pnpm --prefix frontend build               → ✓ built in 2.36s
```

### 端到端验证（关键证据）

**发现**：第一次验证时 dist 里仍然出现了真实的
`oniydowvvhdaqoqeenfk.supabase.co`。原因是本机存在 `frontend/.env`，
`pnpm build` 时 Vite 会加载它，走了构建期回退层。这正是 R5 描述的可复现性问题
在本地的表现（Docker 侧已因 `.dockerignore` 修复而免疫）。

于是按 **release.yml 的真实形态**重做验证：临时移走 `frontend/.env`、
不设任何 `VITE_*`、清空 dist 后重建：

```
=== dist 中是否仍有烧入的 supabase 域名 ===
PASS: 无任何烧入的 supabase 项目地址
=== dist 中是否保留了运行时 config 拉取 ===
/config
```

再用同一个后端同时提供该产物与配置（部署方的值来自后端 `.env`，与构建机无关）：

```
GET /api/v1/config -> 200
  payload: {'supabase_url': 'https://deployer-project.supabase.co',
            'supabase_anon_key': 'deployer-anon-key',
            'turnstile_site_key': 'deployer-turnstile-site-key',
            'sentry_dsn': '', 'pricing_enabled': False, 'environment': 'development'}
GET /login (SPA fallback) -> 200 text/html
  index.html 内含 supabase 项目地址: False
```

即：**构建产物零配置，运行时拿到部署方配置**。原缺陷（发布镜像登录不可用）
被证伪成立并已修复。验证后 `frontend/.env` 已恢复。

### CI 守卫本地自检

```
OK: Dockerfile 无公开配置 build arg
OK: compose 无公开配置 build arg
OK: config 路由存在
OK: config 路由已挂载
OK: 前端 bootstrap 加载运行时配置
```

### AC 核对

| AC | 结果 |
|---|---|
| `/api/v1/config` 返回 6 字段 + Cache-Control | ✅ `test_returns_public_values` / `test_is_cacheable` |
| 密钥不泄露 | ✅ `test_never_leaks_secrets` 覆盖 12 个密钥类字段 |
| 字段集合被锁死 | ✅ `test_response_field_set_is_locked_down` |
| release 形态构建产物无烧入配置 | ✅ 见上方端到端验证 |
| 运行时返回部署方的值 | ✅ 见上方端到端验证 |
| Dockerfile / compose 无公开配置 build arg | ✅ CI 守卫 + 本地自检 |
| `.dockerignore` 不再反向排除 | ✅ |
| CI 守卫存在 | ✅ `env_consistency` job 新增 4 组检查 |
| `G-full` 全绿 | ✅ |
| 文档更新 | ✅ DEPLOYMENT.md §3/§7/§11、README.md |

## 遗留

- 本机 `pnpm build` 仍会把 `frontend/.env` 的值烧进 dist（Vite 既定行为，
  且这是有意保留的回退层）。Docker 与 CI 路径不受影响。若要彻底消除，
  需在 `codebase-hygiene` 里考虑把 `frontend/.env` 从示例流程中移除，
  改为统一用根 `.env`——但那会影响 `pnpm dev` 体验，需单独权衡。
