# Pre-commit Guide

Pre-commit 在 `git commit` 时自动运行代码检查和格式化。

## 安装（首次克隆后执行一次）

```bash
uv run pre-commit install
```

## 常用命令

```bash
uv run pre-commit run --all-files   # 手动检查所有文件
uv run pre-commit run               # 只检查暂存文件
uv run pre-commit autoupdate        # 更新 hooks 版本
git commit --no-verify -m "msg"     # 跳过检查（不推荐）
```

## 本项目检查项

见 `.pre-commit-config.yaml`：

| Hook | 说明 |
|------|------|
| `trailing-whitespace` | 删除行尾空格 |
| `end-of-file-fixer` | 确保文件以换行符结尾 |
| `check-yaml` / `check-toml` / `check-json` | 格式校验 |
| `check-added-large-files` | 阻止大文件提交 |
| `check-merge-conflict` | 检测合并冲突标记 |
| `debug-statements` | 检测遗留 print/debugger |
| `ruff` | Python lint |
| `ruff-format` | Python 自动格式化 |

## 检查失败怎么办

- **自动修复类**（格式化）：文件已被修改，重新 `git add . && git commit`。
- **手动修复类**（lint 错误）：按错误提示改代码，再提交。

## 新克隆项目

```bash
uv sync --all-extras
uv run pre-commit install
```
