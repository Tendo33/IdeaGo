# Pre-commit 使用指南

Pre-commit 是一个 Git 钩子管理工具，可以在你执行 `git commit` 时**自动运行**代码检查和格式化。

## 快速开始

### 1. 安装 pre-commit 钩子（只需一次）

```bash
# 使用 uv 运行
uv run pre-commit install
```

运行后会显示：
```
pre-commit installed at .git/hooks/pre-commit
```

**这一步很关键**，如果不执行，pre-commit 不会自动触发！

### 2. 正常使用 Git

安装钩子后，每次 `git commit` 都会自动运行检查：

```bash
git add .
git commit -m "feat: add new feature"
```

如果代码有问题，commit 会被阻止，并显示错误信息。

## 工作流程

```
git add . → git commit → pre-commit 自动触发
                              ↓
                    ┌─────────────────────┐
                    │  检查通过？          │
                    └─────────────────────┘
                        ↓           ↓
                      是 ✅        否 ❌
                        ↓           ↓
                   提交成功      提交失败
                                    ↓
                            自动修复 + 手动修复
                                    ↓
                            重新 git add && commit
```

## 常用命令

```bash
# 安装 git 钩子（首次克隆项目后必须执行）
uv run pre-commit install

# 手动对所有文件运行检查（不需要 git commit）
uv run pre-commit run --all-files

# 手动对暂存的文件运行检查
uv run pre-commit run

# 跳过 pre-commit 检查（紧急情况使用，不推荐）
git commit --no-verify -m "紧急提交"

# 更新 pre-commit hooks 到最新版本
uv run pre-commit autoupdate

# 卸载 git 钩子
uv run pre-commit uninstall
```

## 本项目配置的检查项

查看 `.pre-commit-config.yaml`，本项目配置了：

| 检查项 | 说明 |
|--------|------|
| `trailing-whitespace` | 删除行尾空格 |
| `end-of-file-fixer` | 确保文件以换行符结尾 |
| `check-yaml` | 验证 YAML 语法 |
| `check-toml` | 验证 TOML 语法 |
| `check-json` | 验证 JSON 语法 |
| `check-added-large-files` | 阻止提交大文件 |
| `check-merge-conflict` | 检测合并冲突标记 |
| `debug-statements` | 检测遗留的 print/debugger 语句 |
| `ruff` | Python 代码 lint 检查 |
| `ruff-format` | Python 代码自动格式化 |

## 常见问题

### Q: 为什么 pre-commit 没有自动运行？

**A:** 你可能没有安装 git 钩子。运行：
```bash
uv run pre-commit install
```

### Q: 检查失败了怎么办？

1. **如果是自动修复**（如格式化），文件会被自动修改，需要：
   ```bash
   git add .
   git commit -m "你的提交信息"
   ```

2. **如果是需要手动修复**（如 lint 错误），根据错误提示修改代码，然后重新提交。

### Q: 新克隆的项目需要做什么？

```bash
# 1. 安装依赖
uv sync

# 2. 安装 pre-commit 钩子
uv run pre-commit install
```

### Q: 怎么让 VS Code 保存时自动格式化？

在 `.vscode/settings.json` 中添加：
```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

这样保存文件时会自动格式化，不用等到 commit 时才发现格式问题。
