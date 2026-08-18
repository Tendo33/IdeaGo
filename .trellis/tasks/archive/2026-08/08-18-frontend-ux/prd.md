# 前端 UX 与可访问性

## 已完成

### 1. 401 静默续期 + 重放（体检 #10）

原来 `core.ts` 收到**任何** 401 就清 token、`supabase.auth.signOut()`、
清历史缓存、整页跳转登录页。瞬时故障（Supabase JWKS 抖动、session store
网络失败）也会把用户踢出去，正在填的表单全丢。而后端一直有
`/auth/refresh`（含 7 天宽限期），前端 `refreshAuthToken` **零调用点**。

现在：401 → 尝试一次续期 → 用新 token 重放原请求 → 只有续期失败或重放仍 401
才真正结束会话。

- `skipRefreshRetry` 内部标记保证不会形成 401 循环
- 模块级 in-flight promise 让并发 401 只触发一次续期，不会打爆 `/auth/refresh`
- `mergeAuthHeader` 重新盖章 Authorization，处理 `Headers` / 数组 / 普通对象三种形态
- `allowUnauthorized` 的调用方（如 LinuxDo start）行为不变

原 `fetchWithTimeout` 被拆成 `sendOnce`（一次带超时的请求）+ 外层重试逻辑，
超时与 abort 语义逐字保留。

### 2. SSE 事件批量 drain（体检的 SSE 观感项）

`flush` 原来每 300ms 只取 `pendingEvents[0]`。后端在重连时会回放全量历史，
一次分析约 30–50 个事件 → 要 9–15 秒才追平，进度面板看起来是卡住的。

改为每次取 `ceil(pending/4)`：实时场景下队列本来就短，节奏感保留；
积压场景下 40 个事件约 5 个 tick 就追平。

### 3. ErrorBoundary 上报 Sentry 且不再展示原始异常（体检 #20）

`Sentry.init` 在 bootstrap 就跑了，但渲染崩溃从来没上报过——用户真正遇到的
错误在生产是不可见的。现在 `componentDidCatch` 调
`Sentry.captureException(error, { contexts: { react: { componentStack } } })`。

同时 UI 不再渲染 `this.state.error?.message`：原始异常文本属于控制台和 Sentry，
不属于用户界面。

### 4. 加载态改叠加，不再整块替换（体检 #19）

`AdminPage` 与 `HistoryPage` 原来是 `loading ? spinner : content`，
翻页/搜索/删除时整块内容消失换成 spinner，布局跳动、滚动位置丢失。

改为：只有**首次**加载才显示骨架/spinner（`hasLoadedOnce` ref 判定），
后续刷新保留旧内容并加 `opacity-60 pointer-events-none` + `aria-busy`。

### 5. a11y 与信息完整性

- `AdminPage` 表格补 `<caption class="sr-only">` 与 `<th scope="col">`
- 结果计数与分页位置加 `aria-live="polite"`
- 错误 Alert 加 `role="alert"`
- 首屏 spinner 补 `sr-only` 文案 + `aria-hidden` 图标
- 分页从只显示当前页改为 `当前 / 总页数`（`total` 本来就拿到了，只是没用）

## 未做：`useReportStatusResolution` 简化

原计划在 C2 把报告终态原子化之后，把这里的三层递归 reconcile 塌成
「一次读取 + 一次短重试」。

**推迟，理由**：C2 最终采用的是**顺序保证**（先写报告、再写状态、最后 emit）
而非单事务 RPC，可观测窗口已经关闭但并非形式化消除。而这块有 397 行既有测试，
是全项目最复杂的状态机之一，删掉两层递归属于高风险重构。

**正确的顺序是先有端到端测试再动它**——而那正是 `e2e-contract-tests`
子任务要建的安全网。因此把这项挪到 E1 完成之后作为后续动作，
并已记入该子任务的遗留清单。半路拆掉重试而没有覆盖全链路的测试，
风险明显高于收益。

## 验证证据

```
pnpm --prefix frontend lint       → 通过
pnpm --prefix frontend typecheck  → 通过
pnpm --prefix frontend test       → 38 files / 246 tests passed
pnpm --prefix frontend build      → ✓ built in 8.06s
```

新增 `src/lib/api/__tests__/sessionRefresh.test.ts` 7 个：
续期后重放成功、续期失败则结束会话、重放仍 401 则结束会话、
`allowUnauthorized` 不重试、重放用新 token 而非旧 token、
并发续期合并为一次请求、续期网络失败视为失败。
