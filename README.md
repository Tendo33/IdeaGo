# Python Template

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

一个面向 Python 3.10+ 的现代化工具库模板：
- `uv` 管理依赖
- `ruff` 负责 lint/format
- `mypy` 类型检查
- `pytest` 测试与覆盖率

内置内容聚焦在“开箱可用的基础工程能力”：
- 配置管理（`pydantic-settings`）
- 日志（`loguru`）
- 文件 / JSON / 日期时间工具
- 装饰器、上下文、通用工具函数
- 可直接发布的打包与 CI 质量门禁
- Tag 驱动的 GitHub Release 自动发布（支持模型生成 release message）

## 快速开始

### 1) 安装依赖

```bash
uv sync --all-extras
```

### 2) 初始化环境变量

```bash
cp .env.example .env
```

默认配置最小化：

```env
ENVIRONMENT=development
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### 3) 运行质量检查

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

## 用这个 Template 创建新项目

### 1) 复制模板仓库

```bash
git clone https://github.com/Tendo33/python-template.git my-new-project
cd my-new-project
```

### 2) 重命名包名（建议第一步就做）

```bash
# 先预览
python scripts/rename_package.py my_new_project --dry-run

# 再执行
python scripts/rename_package.py my_new_project
```

### 3) 更新项目信息

建议至少更新：
- `pyproject.toml`：`name`、`description`、`authors`、`urls`
- `src/<your_package>/__init__.py`：`__version__`
- `README.md`：项目名与示例导入路径

如需统一改版本号：

```bash
python scripts/update_version.py 0.2.0
```

### 4) 验证模板改名后可用

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

### 5) （可选）启用提交前检查

```bash
python scripts/setup_pre_commit.py
```

## 导入约定

### Canonical 导入（推荐）

```python
from python_template.config.settings import get_settings
from python_template.observability.log_config import get_logger, setup_logging
from python_template.utils import read_json, read_text_file, write_json, write_text_file
```

### 高级能力请从子模块导入

```python
from python_template.utils.decorator_utils import retry_decorator
from python_template.utils.common_utils import chunk_list
from python_template.core.context import Context
```

## 常用示例

### 日志

```python
from python_template.observability.log_config import get_logger, setup_logging

setup_logging(level="INFO", log_file="logs/app.log")
logger = get_logger(__name__)
logger.info("service started")
```

### 配置

```python
from python_template.config.settings import get_settings

settings = get_settings()
print(settings.environment)
print(settings.log_level)
```

### 文件与 JSON

```python
from python_template.utils import read_json, write_json, read_text_file, write_text_file

write_text_file("hello", "data/hello.txt")
content = read_text_file("data/hello.txt")

write_json({"ok": True}, "data/config.json")
config = read_json("data/config.json", default={})
```

## 项目结构

```text
python-template/
├── src/python_template/
│   ├── config/
│   ├── contracts/
│   ├── core/
│   ├── models/
│   ├── observability/
│   └── utils/
├── tests/
├── scripts/
├── doc/
├── pyproject.toml
└── README.md
```

## 维护脚本

- `python scripts/rename_package.py my_new_project`
- `python scripts/setup_pre_commit.py`
- `python scripts/update_version.py 0.2.0`
- `python scripts/generate_release_notes.py --tag v0.2.0 --output .github/release-notes.md`
- `uv run python scripts/run_vulture.py --min-confidence 80`

## Release 自动发布

- 推送 tag（如 `v0.3.0`）会触发 `/Users/simonsun/github_project/python-template/.github/workflows/release.yml`。
- Workflow 会生成 release notes，并执行“存在则更新，不存在则创建”。
- 模型相关配置统一走 CI 环境变量（如 `OPENAI_API_KEY`、`RELEASE_NOTES_MODEL`、`OPENAI_BASE_URL`）。
- 若未配置模型密钥或模型调用失败，会自动回退到 deterministic 的非模型说明，不会阻塞发布。

## 文档

- `doc/SETTINGS_GUIDE.md`
- `doc/MODELS_GUIDE.md`
- `doc/SDK_USAGE.md`
- `doc/PRE_COMMIT_GUIDE.md`
- `doc/AI_TOOLING_STANDARDS.md`
- `doc/BACKEND_STANDARDS.md`

## 许可证

MIT，见 `LICENSE`。
