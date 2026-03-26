# Settings Configuration Guide / 配置指南

## 概述 / Overview

这是一个简化的配置管理模板，使用 Pydantic Settings 实现类型安全的配置加载。

This is a simplified configuration management template using Pydantic Settings for type-safe configuration loading.

## 快速开始 / Quick Start

### 1. 设置环境变量
复制示例文件并修改配置值：
```bash
cp .env.example .env
```

### 2. 使用配置
```python
from ideago.config.settings import get_settings

settings = get_settings()
print(f"Env: {settings.environment}")
print(f"Log level: {settings.log_level}")
```

## 如何添加自己的配置 / How to Add Your Own Settings

### 步骤 1: 在 Settings 类中添加字段

```python
# 在 src/ideago/config/settings.py 的 Settings 类中添加
database_url: str = Field(
    default="sqlite:///./app.db",
    description="Database connection URL"
)
```

### 步骤 2: 添加到 .env.example

```bash
DATABASE_URL=sqlite:///./app.db
```

### 步骤 3: 使用配置

```python
settings = get_settings()
print(settings.database_url)
```

## 配置优先级 / Priority

1. 环境变量（最高）
2. .env 文件
3. 默认值（最低）

## Reddit Source Notes

- Update (2026-03): `REDDIT_ENABLE_PUBLIC_FALLBACK` should default to `false` in server environments.
- Reason: unauthenticated Reddit `.json` search frequently returns 403 from hosted/server IPs and is no longer a stable production retrieval path.
- Current backend behavior: when OAuth credentials are missing and public fallback is disabled, the Reddit source is skipped instead of retrying `search.json`.
- Only enable `REDDIT_ENABLE_PUBLIC_FALLBACK=true` if you have explicitly verified that anonymous Reddit JSON access still works from your deployment environment.

- `REDDIT_CLIENT_ID` 和 `REDDIT_CLIENT_SECRET` 仍然是 Reddit 数据源的首选配置方式。
- 当这两个 OAuth 凭证缺失时，后端可以根据 `REDDIT_ENABLE_PUBLIC_FALLBACK` 自动退化到公开只读抓取模式。
- 公开只读 fallback 仅用于有限的公开帖子搜索，结果稳定性和完整性低于 OAuth 模式。
- 可通过 `REDDIT_PUBLIC_FALLBACK_LIMIT` 和 `REDDIT_PUBLIC_FALLBACK_DELAY_SECONDS` 控制 fallback 的结果数和请求节奏。
