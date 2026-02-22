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
from python_template.config.settings import get_settings

settings = get_settings()
print(f"Env: {settings.environment}")
print(f"Log level: {settings.log_level}")
```

## 如何添加自己的配置 / How to Add Your Own Settings

### 步骤 1: 在 Settings 类中添加字段

```python
# 在 config/settings.py 的 Settings 类中添加
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
