# Contributing to Python Template

感谢你对本项目的兴趣！我们欢迎所有形式的贡献。

## 🚀 快速开始

### 1. Fork 并克隆项目

```bash
git clone https://github.com/Tendo33/python-template.git
cd python-template
```

### 2. 设置开发环境

```bash
# 安装 uv (如果尚未安装)
pip install uv

# 同步项目依赖
uv sync --all-extras

# 配置 pre-commit hooks
python scripts/setup_pre_commit.py
```

### 3. 创建分支

```bash
git checkout -b feature/your-feature-name
```

## 📝 开发规范

### 代码风格

本项目使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码格式化和检查。

```bash
# 格式化代码
uv run ruff format src tests scripts

# 检查代码
uv run ruff check src tests scripts

# 自动修复问题
uv run ruff check src tests scripts --fix

# 类型检查
uv run mypy src
```

### 类型提示

- 所有函数必须包含类型提示
- 使用 Python 3.10+ 的类型语法 (如 `list[str]` 而非 `List[str]`)

### 文档字符串

使用 Google 风格的文档字符串：

```python
def example_function(param1: str, param2: int) -> bool:
    """函数简要描述。

    更详细的描述（如需要）。

    Args:
        param1: 参数1的描述
        param2: 参数2的描述

    Returns:
        返回值的描述

    Raises:
        ValueError: 异常情况描述
    """
    pass
```

### 测试

- 所有新功能必须包含测试
- 测试文件放在 `tests/` 目录
- 测试函数以 `test_` 开头

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_your_module.py

# 生成覆盖率报告
uv run pytest --cov=python_template --cov-report=html
```

## 🔄 提交流程

### 1. 提交信息格式

使用语义化的提交信息：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型 (type):**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式 (不影响功能)
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具变更

**示例:**
```
feat(utils): add async file operations

- Add async_read_text_file function
- Add async_write_text_file function
```

### 2. 提交前检查

确保以下检查通过：

```bash
# Pre-commit hooks 会自动运行，也可手动执行
uv run pre-commit run --all-files

# 运行测试
uv run pytest
```

### 3. 创建 Pull Request

1. 推送你的分支到 GitHub
2. 创建 Pull Request 到 `main` 分支
3. 填写 PR 模板，描述你的更改
4. 等待代码审查

## 📋 贡献类型

### 报告 Bug

如果你发现了 bug，请创建一个 [Issue](https://github.com/Tendo33/python-template/issues)，包含：

- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息 (Python 版本、操作系统等)

### 功能建议

欢迎提交功能建议！请在 Issue 中描述：

- 功能描述
- 使用场景
- 可能的实现方案

### 文档改进

文档改进同样重要！你可以：

- 修复文档中的错误
- 添加更多示例
- 改善文档结构

## 📜 行为准则

请保持友好和尊重。我们致力于营造一个开放、包容的社区环境。

## ❓ 问题和帮助

如有任何问题，请通过以下方式联系：

- 创建 [Issue](https://github.com/Tendo33/python-template/issues)

---

再次感谢你的贡献！🎉
