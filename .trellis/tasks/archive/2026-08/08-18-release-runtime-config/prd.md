# 交付链修复：发布镜像运行时配置

## Goal

让公开发布的 Docker 镜像开箱可用。当前 Docker Hub 上的 `ideago:latest` 前端
登录完全不可用，任何人拉下来都用不了。

## Background

三处配置互相矛盾：

| 位置 | 行为 |
|---|---|
| `Dockerfile:5-19` | 声明 `ARG VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY / VITE_TURNSTILE_SITE_KEY`，在 `pnpm build` 前 export，Vite 把它们**内联进 bundle** |
| `docker-compose.yml:6-13` | 通过 `build.args` 传了这些值 → **本地构建正常** |
| `.github/workflows/release.yml` 的 `docker/build-push-action` | **完全没有 `build-args`** → 发布镜像里这些值是空串 |

后果链：

- `lib/supabase/client.ts:56-59`：URL/key 为空 → 退化成
  `createFallbackSupabaseClient()`，所有 auth 方法直接返回 error
- `features/auth/LoginPage.tsx:61`：`authBlocked = !turnstileSiteKey || ...`
  恒为 `true` → 登录/注册按钮永久禁用

因为 compose 传了参数，本地和 CI 都测不出来，只有拉发布镜像的人会踩到。

## Requirements

### R1 镜像与部署方解耦

公开镜像不得绑定任何特定 Supabase 项目。同一个 image tag 必须能被任意部署方
用自己的 `.env` 跑起来。

### R2 公开配置走运行时下发

新增 `GET /api/v1/config`，前端挂载前拉取一次。

### R3 只暴露本来就公开的值

`SUPABASE_SERVICE_ROLE_KEY` / `AUTH_SESSION_SECRET` / `TURNSTILE_SECRET_KEY` /
`STRIPE_SECRET_KEY` / `OPENAI_API_KEY` / `SUPABASE_DB_URL` 等**绝不允许**出现在
该端点。必须用显式白名单构造响应，禁止 `model_dump()` 式批量导出——否则将来
新增一个密钥字段就会静默泄露给所有浏览器。

### R4 不能破坏本地开发与既有测试

`pnpm dev`、既有 209 个前端测试、以及没有后端可连的场景都必须继续工作。
因此保留 `VITE_*` 作为回退层。

### R5 构建产物可复现

`.dockerignore` 里的 `!frontend/.env` 反向排除让开发者本地的 env 进入构建上下文，
Vite 会加载它并覆盖 build arg → 同一份代码在不同机器上产出不同 bundle。必须删掉。

### R6 回归必须被 CI 拦住

加结构化守卫，防止有人把配置改回构建期烧入。

## Acceptance Criteria

- [ ] `GET /api/v1/config` 返回 6 个公开字段，且响应带 `Cache-Control`
- [ ] 有测试断言全部密钥类 settings 都不出现在响应里
- [ ] 有测试锁死响应字段集合（新增字段必须显式改测试）
- [ ] 在**完全不设任何 `VITE_*`、且不存在 `frontend/.env`** 的条件下构建，
      产物中不含任何 supabase 项目地址，但保留运行时 config 拉取路径
- [ ] 同一后端同时提供该产物与配置时，`GET /api/v1/config` 返回**部署方**的值
- [ ] `Dockerfile` 与 `docker-compose.yml` 不再有公开配置 build arg
- [ ] `.dockerignore` 不再反向排除 `frontend/.env`
- [ ] CI 有守卫拦住上述回归
- [ ] `G-full` 全绿
- [ ] `DEPLOYMENT.md` / `README.md` 更新

## Out Of Scope

- `VITE_API_BASE_URL` 保持构建期输入。它用于定位 `/api/v1/config` 本身，
  无法由该端点下发（先有鸡先有蛋）。同源部署（本镜像的默认形态）留空即可。
- 不改任何认证逻辑，只改配置来源。
