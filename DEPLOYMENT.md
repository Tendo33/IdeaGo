# IdeaGo 生产部署完整指南

本文档面向拥有一台 VPS 的开发者，从零到上线，涵盖平台注册、服务配置、部署上线、域名绑定、HTTPS、监控的全流程。

---

## 目录

1. [你距离上线还差什么](#1-你距离上线还差什么)
2. [需要注册的平台清单](#2-需要注册的平台清单)
3. [VPS 基础环境准备](#3-vps-基础环境准备)
4. [Supabase 配置](#4-supabase-配置)
5. [Stripe 配置](#5-stripe-配置)
6. [域名与 DNS](#6-域名与-dns)
7. [部署到 VPS](#7-部署到-vps)
8. [Sentry 监控](#8-sentry-监控)
9. [上线后验证清单](#9-上线后验证清单)
10. [日常运维](#10-日常运维)
11. [更新与回滚](#11-更新与回滚)

---

## 1. 你距离上线还差什么

### 代码层面（已完成）

| 能力 | 状态 |
|------|------|
| 用户认证（Supabase + LinuxDo OAuth） | 已实现 |
| Stripe 订阅计费 | 已实现 |
| 配额管理 + 速率限制 | 已实现 |
| 管理后台 | 已实现 |
| 安全头 + CSRF + CORS | 已实现 |
| Sentry 错误监控 | 已集成 |
| 审计日志 | 已实现 |
| Docker 镜像 + CI/CD | 已实现 |
| i18n 双语 | 已实现 |
| 法律页面（Terms / Privacy） | 已实现 |

### 运维层面（需要你完成）

| 待办 | 说明 |
|------|------|
| 购买域名 | 如 `ideago.com` 或 `ideago.cc` |
| VPS 安装 Docker + Caddy | 反向代理 + 自动 HTTPS |
| 注册 Supabase | 免费额度足够起步 |
| 注册 Stripe | 收款必须 |
| 注册 Sentry | 错误监控（免费额度够用） |
| 获取 API Keys | OpenAI、Tavily 等 |
| 配置 DNS A 记录 | 域名指向 VPS IP |
| 配置 Stripe Webhook | 指向你的域名 |

---

## 2. 需要注册的平台清单

### 必须注册

| 平台 | 用途 | 注册地址 | 费用 |
|------|------|----------|------|
| **OpenAI** | LLM 分析引擎 | https://platform.openai.com | 按量付费 |
| **Supabase** | 数据库 + 认证 | https://supabase.com | 免费额度 500MB |
| **Stripe** | 收款 + 订阅 | https://stripe.com | 交易 2.9%+30¢ |
| **域名注册商** | 域名 | Cloudflare / Namecheap / 阿里云 | ~$10/年 |

### 强烈推荐

| 平台 | 用途 | 注册地址 | 费用 |
|------|------|----------|------|
| **Tavily** | 网络搜索数据源 | https://tavily.com | 免费 1000 次/月 |
| **Sentry** | 错误监控 | https://sentry.io | 免费 5K events/月 |
| **Docker Hub** | 镜像仓库 | https://hub.docker.com | 免费 |

### 可选（增强数据源）

| 平台 | 用途 | 注册地址 |
|------|------|----------|
| **GitHub** | PAT 提升 API 限额 | https://github.com/settings/tokens |
| **Product Hunt** | 产品数据源 | https://www.producthunt.com/v2/oauth/applications |
| **Reddit** | 社区数据源 | https://www.reddit.com/prefs/apps |

---

## 3. VPS 基础环境准备

### 3.1 推荐配置

- **最低**: 1 vCPU / 2GB RAM / 20GB SSD
- **推荐**: 2 vCPU / 4GB RAM / 40GB SSD
- **系统**: Ubuntu 22.04 或 Debian 12

### 3.2 SSH 登录并安装基础工具

```bash
# 以 root 登录后，创建普通用户（替换 yourname）
adduser yourname
usermod -aG sudo yourname
su - yourname

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y curl git ufw
```

### 3.3 配置防火墙

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

### 3.4 安装 Docker

```bash
# 官方一键安装脚本
curl -fsSL https://get.docker.com | sudo sh

# 让当前用户无需 sudo 运行 docker
sudo usermod -aG docker $USER

# 重新登录使 docker 组生效
exit
# 重新 SSH 登录

# 验证
docker --version
docker compose version
```

### 3.5 安装 Caddy（反向代理 + 自动 HTTPS）

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy -y

# Caddy 会自动启动并管理 HTTPS 证书
sudo systemctl enable caddy
```

---

## 4. Supabase 配置

### 4.1 创建项目

1. 打开 https://supabase.com → Sign Up → New Project
2. 选择离 VPS 最近的 Region（如 Singapore / Tokyo）
3. 设置一个强 Database Password（保存好）
4. 等待项目初始化完成（~2 分钟）

### 4.2 获取密钥

进入 **Project Settings → API**，记录：

| 变量名 | 对应位置 |
|--------|----------|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | `anon` `public` key |
| `SUPABASE_SERVICE_ROLE_KEY` | `service_role` `secret` key（不要泄露） |
> 新版 Supabase 默认使用 JWT Signing Keys / JWKS。后端会自动通过
> `/.well-known/jwks.json` 做本地验签，不需要额外查找或填写 `JWT Secret`。

### 4.3 创建数据库表

进入 **SQL Editor**，执行以下 SQL：

```sql
-- 用户档案表
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY,
  display_name TEXT DEFAULT '',
  avatar_url TEXT DEFAULT '',
  bio TEXT DEFAULT '',
  role TEXT DEFAULT 'user',
  plan TEXT DEFAULT 'free',
  plan_limit INTEGER DEFAULT 5,
  usage_count INTEGER DEFAULT 0,
  usage_reset_at TIMESTAMPTZ DEFAULT (date_trunc('month', now()) + interval '1 month'),
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  auth_provider TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 启用 RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- 报告缓存表
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  query_hash TEXT,
  data JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ
);

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- 处理中的报告（去重用）
CREATE TABLE IF NOT EXISTS processing_reports (
  query_hash TEXT PRIMARY KEY,
  report_id TEXT NOT NULL,
  user_id UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Stripe Webhook 幂等性表
CREATE TABLE IF NOT EXISTS processed_webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  processed_at TIMESTAMPTZ DEFAULT now()
);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  actor_id TEXT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata JSONB DEFAULT '{}',
  ip_address TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 速率限制 RPC
CREATE OR REPLACE FUNCTION check_rate_limit(
  p_key TEXT,
  p_max_requests INTEGER,
  p_window_seconds INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
  current_count INTEGER;
BEGIN
  -- 清理过期记录
  DELETE FROM rate_limit_entries
  WHERE key = p_key
    AND created_at < now() - (p_window_seconds || ' seconds')::interval;

  -- 计数
  SELECT count(*) INTO current_count
  FROM rate_limit_entries
  WHERE key = p_key;

  IF current_count >= p_max_requests THEN
    RETURN true; -- 超限
  END IF;

  -- 插入新记录
  INSERT INTO rate_limit_entries (key, created_at)
  VALUES (p_key, now());

  RETURN false; -- 未超限
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 速率限制辅助表
CREATE TABLE IF NOT EXISTS rate_limit_entries (
  id BIGSERIAL PRIMARY KEY,
  key TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_key ON rate_limit_entries(key, created_at);

-- 配额检查与递增 RPC
CREATE OR REPLACE FUNCTION check_and_increment_quota(p_user_id UUID)
RETURNS JSONB AS $$
DECLARE
  profile_row profiles%ROWTYPE;
  result JSONB;
BEGIN
  SELECT * INTO profile_row FROM profiles WHERE id = p_user_id FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('error', 'profile_not_found');
  END IF;

  -- 月度重置
  IF profile_row.usage_reset_at <= now() THEN
    UPDATE profiles SET
      usage_count = 0,
      usage_reset_at = date_trunc('month', now()) + interval '1 month'
    WHERE id = p_user_id;
    profile_row.usage_count := 0;
  END IF;

  result := jsonb_build_object(
    'allowed', profile_row.usage_count < profile_row.plan_limit,
    'usage_count', profile_row.usage_count,
    'plan_limit', profile_row.plan_limit,
    'plan', profile_row.plan
  );

  IF profile_row.usage_count < profile_row.plan_limit THEN
    UPDATE profiles SET usage_count = usage_count + 1 WHERE id = p_user_id;
  END IF;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 4.4 配置 OAuth Provider（可选，用于 GitHub/Google 登录）

1. 进入 **Authentication → Providers**
2. 启用 GitHub：填入 GitHub OAuth App 的 Client ID 和 Secret
3. 启用 Google：填入 Google OAuth 的 Client ID 和 Secret
4. Redirect URL 设为: `https://你的域名/auth/callback`

---

## 5. Stripe 配置

### 5.1 注册与激活

1. 打开 https://dashboard.stripe.com/register 注册
2. 完成商家身份验证（个人或公司）
3. 开始时可用 **Test Mode** 测试

### 5.2 创建产品和价格

1. 进入 **Products → + Add Product**
2. 产品名: `IdeaGo Pro`
3. 定价: $19/month（或你想要的价格），Recurring
4. 保存后，记录 **Price ID**（格式 `price_xxx`）

### 5.3 获取密钥

进入 **Developers → API Keys**，记录：

| 变量名 | 对应位置 |
|--------|----------|
| `STRIPE_SECRET_KEY` | Secret key（`sk_test_...` 或 `sk_live_...`） |
| `STRIPE_PRO_PRICE_ID` | 上一步创建的 Price ID |

### 5.4 配置 Webhook（部署上线后再做）

1. 进入 **Developers → Webhooks → + Add Endpoint**
2. Endpoint URL: `https://你的域名/api/v1/billing/webhook`
3. 勾选事件:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. 保存后记录 **Signing secret**（`whsec_...`）→ 填入 `STRIPE_WEBHOOK_SECRET`

> 注意: Webhook 必须在域名和 HTTPS 就绪后才能配置。先用 Test Mode 的密钥测试。

---

## 6. 域名与 DNS

### 6.1 购买域名

推荐在 **Cloudflare Registrar**（价格透明、无加价）或 **Namecheap** 购买。

### 6.2 配置 DNS

在你的域名注册商的 DNS 管理面板中添加：

```
类型    名称    值              TTL
A       @       你的VPS IP      Auto
A       www     你的VPS IP      Auto
```

如果使用 Cloudflare DNS（推荐）：
- 将 Proxy Status 设为 **DNS only**（灰色云朵），让 Caddy 处理 HTTPS
- 或者设为 **Proxied**（橙色云朵），在 Cloudflare 上终止 TLS

验证 DNS 生效：

```bash
# 在本地终端执行
dig +short 你的域名
# 应该返回你的 VPS IP
```

---

## 7. 部署到 VPS

### 7.1 创建项目目录

```bash
# SSH 登录 VPS
mkdir -p ~/ideago && cd ~/ideago
```

### 7.2 创建 docker-compose.prod.yml

```bash
cat > docker-compose.prod.yml << 'COMPOSE_EOF'
services:
  ideago:
    image: simonsun3/ideago:latest
    pull_policy: always
    ports:
      - "127.0.0.1:8000:8000"
    env_file: .env
    volumes:
      - ideago-cache:/app/.cache/ideago
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"

volumes:
  ideago-cache:
COMPOSE_EOF
```

> 注意 `127.0.0.1:8000:8000` 只监听本地，由 Caddy 反向代理对外暴露。

### 7.3 创建 .env 文件

```bash
cat > .env << 'ENV_EOF'
# ========== 运行环境 ==========
ENVIRONMENT=production
LOG_LEVEL=INFO

# ========== API Keys（必填） ==========
OPENAI_API_KEY=sk-你的openai密钥
TAVILY_API_KEY=tvly-你的tavily密钥

# ========== LLM 配置 ==========
OPENAI_MODEL=gpt-4o-mini
# 如需使用第三方兼容 API，取消下行注释
# OPENAI_BASE_URL=https://openrouter.ai/api/v1

# ========== Supabase ==========
SUPABASE_URL=https://你的项目.supabase.co
SUPABASE_ANON_KEY=你的anon-key
## JWT 使用 Supabase JWKS 自动验签，无需额外配置 JWT Secret
SUPABASE_SERVICE_ROLE_KEY=你的service-role-key

# ========== 认证 ==========
# 用 openssl rand -hex 32 生成
AUTH_SESSION_SECRET=在此粘贴一个64字符的随机hex字符串
AUTH_SESSION_EXPIRE_HOURS=720
FRONTEND_APP_URL=https://你的域名

# ========== LinuxDo OAuth（如果需要） ==========
# LINUXDO_CLIENT_ID=
# LINUXDO_CLIENT_SECRET=

# ========== Stripe ==========
STRIPE_SECRET_KEY=sk_live_你的stripe密钥
STRIPE_WEBHOOK_SECRET=whsec_你的webhook签名密钥
STRIPE_PRO_PRICE_ID=price_你的价格ID

# ========== 可选数据源 ==========
# GITHUB_TOKEN=ghp_你的token
# PRODUCTHUNT_DEV_TOKEN=
# REDDIT_CLIENT_ID=
# REDDIT_CLIENT_SECRET=

# ========== 速率限制 ==========
RATE_LIMIT_ANALYZE_MAX=10
RATE_LIMIT_ANALYZE_WINDOW_SECONDS=60

# ========== 监控 ==========
SENTRY_DSN=https://你的sentry-dsn
SENTRY_TRACES_SAMPLE_RATE=0.1

# ========== 服务 ==========
HOST=0.0.0.0
PORT=8000
CORS_ALLOW_ORIGINS=https://你的域名
ENV_EOF
```

生成 AUTH_SESSION_SECRET：

```bash
openssl rand -hex 32
```

### 7.4 配置 Caddy

```bash
sudo tee /etc/caddy/Caddyfile << 'CADDY_EOF'
你的域名 {
    reverse_proxy localhost:8000

    encode gzip zstd

    header {
        # 安全头（应用层已设置大部分，这里补充 CSP）
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://connect.linux.do"
        -Server
    }

    log {
        output file /var/log/caddy/ideago.log {
            roll_size 50mb
            roll_keep 5
        }
    }
}
CADDY_EOF

# 创建日志目录
sudo mkdir -p /var/log/caddy

# 验证配置
sudo caddy validate --config /etc/caddy/Caddyfile

# 重载 Caddy
sudo systemctl reload caddy
```

### 7.5 启动服务

```bash
cd ~/ideago

# 拉取最新镜像并启动
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f

# 等待出现类似 "Uvicorn running on ..." 的日志
```

### 7.6 验证

```bash
# 本地测试（在 VPS 上）
curl http://localhost:8000/api/v1/health
# 应返回 {"status":"ok"}

# 外部测试（在你本机）
curl https://你的域名/api/v1/health
# 应返回 {"status":"ok"}
```

打开浏览器访问 `https://你的域名`，应该看到 IdeaGo 的 Landing Page。

### 7.7 配置 Stripe Webhook（现在域名已就绪）

回到 Stripe Dashboard → Developers → Webhooks：
1. 添加端点: `https://你的域名/api/v1/billing/webhook`
2. 选择事件（见第 5.4 节）
3. 复制 Signing Secret 填入 `.env` 的 `STRIPE_WEBHOOK_SECRET`
4. 重启服务: `docker compose -f docker-compose.prod.yml restart`

---

## 8. Sentry 监控

### 8.1 注册

1. 打开 https://sentry.io → Sign Up
2. 创建 Organization

### 8.2 创建项目

创建 **两个** Sentry 项目（为了分开追踪前后端错误）：

**后端**:
1. Create Project → Platform: **Python** → Framework: **FastAPI**
2. 记录 DSN（格式 `https://xxx@oXXX.ingest.sentry.io/xxx`）
3. 填入 `.env` 的 `SENTRY_DSN`

**前端**:
1. Create Project → Platform: **JavaScript** → Framework: **React**
2. 记录 DSN
3. 填入前端部署时的 `VITE_SENTRY_DSN`（构建镜像时需要）

### 8.3 重启服务

```bash
cd ~/ideago
docker compose -f docker-compose.prod.yml restart
```

---

## 9. 上线后验证清单

逐项检查，全部通过才算上线成功：

```
[ ] 域名解析正确 (dig +short 你的域名 = VPS IP)
[ ] HTTPS 证书正常 (浏览器地址栏有锁)
[ ] Landing Page 正常加载
[ ] 可以注册 / 登录 (Supabase Auth)
[ ] 可以提交分析 (OpenAI API 连通)
[ ] SSE 实时流正常 (进度条动态更新)
[ ] 报告正常生成并持久化
[ ] 报告历史页面正常
[ ] 个人资料编辑正常
[ ] Pricing 页面显示正确
[ ] Stripe Checkout 流程完整 (用 Test Mode 验证)
[ ] Stripe Webhook 接收正常 (Stripe Dashboard → Webhooks 无报错)
[ ] 配额限制生效 (Free 用户到达 5 次后提示升级)
[ ] 速率限制生效 (快速连续请求返回 429)
[ ] 删除账户功能正常
[ ] 中英文切换正常
[ ] 暗色模式正常
[ ] 移动端响应式正常
[ ] Sentry 收到测试错误 (访问一个不存在的 API)
[ ] 管理后台可访问 (/admin, 需手动在 DB 设 role='admin')
```

设置管理员：

```sql
-- 在 Supabase SQL Editor 执行，替换为你的 user id
UPDATE profiles SET role = 'admin' WHERE id = '你的用户UUID';
```

---

## 10. 日常运维

### 10.1 查看日志

```bash
# 应用日志
docker compose -f docker-compose.prod.yml logs -f --tail 100

# Caddy 日志
sudo tail -f /var/log/caddy/ideago.log
```

### 10.2 监控磁盘

```bash
# 检查 Docker 占用
docker system df

# 清理未使用的镜像
docker image prune -f
```

### 10.3 备份

Supabase 提供每日自动备份（Pro Plan）。免费 Plan 需要手动备份：

```bash
# 导出 Supabase 数据（需要数据库直连 URL）
# pg_dump "postgresql://postgres:密码@db.你的项目.supabase.co:5432/postgres" > backup_$(date +%Y%m%d).sql
```

### 10.4 监控服务状态

```bash
# 检查容器状态
docker compose -f docker-compose.prod.yml ps

# 检查健康状态
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

---

## 11. 更新与回滚

### 11.1 常规更新

当你推送新的 git tag（如 `v0.4.0`），GitHub Actions 会自动构建并推送新的 Docker 镜像。

```bash
cd ~/ideago

# 拉取最新镜像
docker compose -f docker-compose.prod.yml pull

# 滚动更新（几乎零停机）
docker compose -f docker-compose.prod.yml up -d

# 确认新容器运行正常
docker compose -f docker-compose.prod.yml logs --tail 20
```

### 11.2 回滚到指定版本

```bash
# 编辑 docker-compose.prod.yml，将 image 改为指定版本
# image: simonsun3/ideago:v0.3.4

docker compose -f docker-compose.prod.yml up -d
```

### 11.3 修改环境变量

```bash
# 编辑 .env
nano ~/ideago/.env

# 重启生效
docker compose -f docker-compose.prod.yml restart
```

---

## 附录: 完整操作时间线

按顺序执行，预计 2-3 小时完成首次部署：

```
1. 注册 Supabase          → 获取 URL + Keys              (~10 min)
2. 注册 Stripe            → 获取 Secret Key + Price ID    (~15 min)
3. 注册 Sentry            → 获取 DSN                     (~5 min)
4. 购买域名               → 配置 DNS A 记录               (~10 min)
5. VPS 安装 Docker + Caddy → 准备运行环境                 (~20 min)
6. Supabase 建表           → 执行 SQL                     (~10 min)
7. VPS 创建 .env + compose → 配置所有密钥                  (~15 min)
8. 配置 Caddy              → 反向代理 + HTTPS              (~10 min)
9. 启动服务                → docker compose up              (~5 min)
10. 配置 Stripe Webhook    → 填入 signing secret            (~5 min)
11. 验证清单               → 逐项测试                      (~30 min)
```

---

## 常见问题

**Q: Caddy 证书申请失败?**
A: 确认 DNS 已生效（`dig +short 域名`），确认 80/443 端口已开放（`sudo ufw status`），确认没有其他进程占用 80 端口。

**Q: 前端加载空白?**
A: 检查 `.env` 中 `CORS_ALLOW_ORIGINS` 是否设为你的域名（不是 `*`），检查 `FRONTEND_APP_URL` 是否正确。

**Q: Stripe Webhook 返回 400?**
A: 确认 `STRIPE_WEBHOOK_SECRET` 是 Webhook endpoint 的 signing secret（`whsec_...`），不是 API key。

**Q: LinuxDo 登录回调失败?**
A: 确认 `FRONTEND_APP_URL` 与 LinuxDo OAuth 应用中配置的 Redirect URI 一致。

**Q: 分析请求超时?**
A: 检查 `OPENAI_API_KEY` 是否有效，检查 VPS 是否能访问 OpenAI API（部分地区需要代理）。如需代理，设置 `OPENAI_BASE_URL` 指向中转服务。
