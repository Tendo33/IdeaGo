# 安全加固

## Goal

关闭体检报告中的安全问题，且全部为代码层默认行为，不依赖运维配置生效。

## Requirements 与验收

### R1 OAuth state 必须与浏览器绑定（最严重）

**问题**：`auth.py` 的 `_build_state_token` 生成了 `nonce` 但从不落库、
`_parse_state_token` 也从不比对任何 cookie。签名只证明「这个 state 是我们签的」，
不证明「完成回调的浏览器就是发起的那个」。

**攻击路径**：攻击者用自己的 Turnstile token 调 `/auth/linuxdo/start?prefetch=true`
拿到合法 state → 自己在 LinuxDo 侧完成授权拿到 code → 诱导受害者浏览器访问
`GET /api/v1/auth/linuxdo/callback?code=<攻击者的>&state=<合法的>` →
受害者浏览器被种上**攻击者身份**的 HttpOnly session cookie。

- [x] state 内只放 binding 的 **sha256 哈希**（`bh`），明文 binding 只进 HttpOnly cookie
- [x] cookie `SameSite=Lax`（不能用 Strict：回调是来自 OAuth provider 的跨站顶级
      GET 重定向，Strict 下浏览器不会带上 cookie）、`max_age=600`、`HttpOnly`
- [x] 校验用 `secrets.compare_digest` 常量时间比较
- [x] 校验位置在 **code 交换之前**，不匹配则零成本拒绝
- [x] 成功后立即清除 cookie（一次性）
- [x] 无 `bh` 字段的旧 state（本次修复前签发的）一律拒绝

### R2 生产关闭交互式文档

- [x] `environment == "production"` 时 `docs_url` / `redoc_url` / `openapi_url` 全为 `None`
- [x] 验收时确认：`/openapi.json` 返回 404；`/docs` `/redoc` 因 SPA catch-all 仍返回
      200，但响应体是应用外壳，不含 swagger/redoc/openapi 任何标记

### R3 外部链接协议白名单

- [x] 新增 `lib/utils/safeUrl.ts`：`safeHttpUrl` / `safeImageUrl` / `safeUrlHostname`
- [x] 6 个渲染点接入：`CompetitorCard` / `CompetitorRow` / `EvidenceSummaryPanel` /
      `PainSignalsCard` / `AdminPage` 头像 / `ProfilePage` 头像
- [x] 全部外链加 `referrerPolicy="no-referrer"`

### R4 日志不得回显上游响应体

- [x] `_safe_upstream_detail()` 只提取 PostgREST 的错误码，截断到 64 字符
- [x] `supabase_admin.py` 16 处、`admin.py` 1 处、`supabase_cache.py` 2 处全部改造

### R5 Supabase 对称密钥兼容

- [x] 新增 `_UnsupportedLocalAlgorithmError`，把「项目用对称密钥所以无法本地验签」
      与「这个 token 是假的」区分开；前者降级到远程验证，后者仍然拒绝

### R6 注销失败不回显内部细节

- [x] 响应只保留 `phase` + `cleanup` 枚举态 + `incident_id`；`details`（内部表名+
      上游状态码）改走日志与审计，用 `incident_id` 关联

## 实现记录

### 改动清单

| 文件 | 改动 |
|---|---|
| `auth/session.py` | 新增 `OAUTH_STATE_COOKIE_NAME` + `set/clear_oauth_state_cookie` |
| `api/routes/auth.py` | `_build_state_token` 返回 `(token, binding)`；新增 `_hash_state_binding` / `_state_binding_matches`；`linuxdo_start` 注入 `Response` 并在两条返回路径分别种 cookie；`linuxdo_callback` 在 code 交换前校验绑定；注销错误改 `incident_id` |
| `api/app.py` | 生产关闭 docs |
| `auth/dependencies.py` | `_UnsupportedLocalAlgorithmError` + 远程降级分支 |
| `auth/supabase_admin.py` | `_safe_upstream_detail` + 16 处日志改造 |
| `api/routes/admin.py`、`cache/supabase_cache.py` | 日志改造 |
| 前端 6 个组件 + `lib/utils/safeUrl.ts` | 协议白名单 + referrerPolicy |

### 过程中修掉的自己引入的问题

**批量替换误伤控制流**：用正则把 `resp.text` 统一换成 `_safe_upstream_detail(resp)`
时，误伤了 `get_profile` 和 `list_profiles` 里两处
`if resp.status_code == 400 and "deletion_pending" in resp.text:`——那是**控制流**
（旧 schema 缺列时 PostgREST 会在 400 正文里点名该列，据此走降级查询），不是日志。
已还原为读原始 `resp.text`，并加注释说明「此处读正文是控制流，永远不要记它」。

### 既有测试的行为变更（6 个，全部是有意的）

| 测试 | 原断言 | 新断言与理由 |
|---|---|---|
| `test_linuxdo_callback_sets_cookie_and_redirects_to_callback` | 无绑定即可回调 | 必须带 binding cookie |
| `test_build_and_parse_state_token_round_trip` | 返回单个 token | 返回 `(token, binding)`，并断言 `bh` 一致 |
| `test_auth_route_remaining_error_branches` | 同上 | 解包 + 提供 binding |
| `test_auth_callback_quota_and_profile_success_paths` | 无绑定 | stub state 带 `bh`，fake request 带 cookie |
| `test_auth_profile_and_delete_account_error_paths` | `detail["details"] == [...]` | 内部细节不再回显；改为断言 `details` 不存在、`incident_id` 存在，且审计里仍保留细节并与 `incident_id` 对应 |
| `test_app_middlewares_rate_limit_headers_and_spa_fallback_branches` | 生产下 `/docs` 返回宽松 docs CSP | 生产下 docs 已关闭，`/docs` 落到 SPA 并携带**严格** CSP |
| `CompetitorCard.test.tsx` `falls back to generic label for malformed links` | `not-a-valid-url` 渲染成 `<a>link</a>` | 改为不渲染链接。原行为会生成相对 URL，点击后把用户带进本站的死路由；另加一个 `javascript:` 用例 |

### 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 127 files already formatted
uv run mypy src                            → Success: no issues found in 85 source files
uv run pytest                              → 826 passed, 0 failed, 覆盖率 84.72%
pnpm --prefix frontend typecheck / lint    → 通过
pnpm --prefix frontend test                → 37 files / 239 tests passed
pnpm --prefix frontend build               → ✓ built
```

新增测试：`tests/test_security_hardening.py` 16 个（OAuth 绑定 7、docs 暴露 3、
日志脱敏 5、外加边界），`frontend/src/lib/utils/safeUrl.test.ts` 20 个。

其中最关键的一个是端到端攻击复现：
`test_callback_rejects_state_without_matching_cookie` 用一个**合法签名的 state**
+ **没有 binding cookie 的浏览器**打回调，断言返回 302 错误重定向、
且 `_exchange_linuxdo_code` **从未被调用**——证明攻击在 code 交换前就被挡住。

## 遗留

- `http_middleware.py` 的 `docs_csp` 分支在生产下已不可达（docs 关闭），
  但开发环境仍需要，故保留。
- Supabase 对称密钥的**启动期自检告警**未做（R5 只做了运行时降级）。
  移到 `ops-observability` 一起做，那里正好要加启动期检查。
