# Scripts Guide

项目维护脚本位于 `scripts/` 目录。

## rename_package.py — 包名重命名

将整个项目从 `python_template` / `python-template` 重命名为新名称。

覆盖范围：
- `src/python_template/` 目录重命名
- 所有 `.py`, `.toml`, `.md`, `.yaml`, `.json`, `.ts`, `.tsx`, `.html`, `.css`, `.mdc` 文件中的文本替换
- `frontend/package.json` 的 `name` 字段
- `frontend/index.html` 的 `<title>`

```bash
# 预览（不修改文件）
python scripts/rename_package.py --dry-run my_new_project

# 执行（交互确认）
python scripts/rename_package.py my_new_project

# 跳过确认
python scripts/rename_package.py -y my_new_project
```

执行后需要：
1. `git diff` 检查变更
2. `uv pip install -e .` 重新安装
3. `uv run pytest` 确认测试通过
4. `git add -A && git commit -m 'chore: rename package'`

## update_version.py — 版本号更新

同步更新项目中所有版本号（后端 + 前端）。

更新的文件：
- `pyproject.toml` — `version = "X.Y.Z"`
- `src/<package>/__init__.py` — `__version__ = "X.Y.Z"`（自动检测包目录）
- `frontend/package.json` — `"version": "X.Y.Z"`（如存在）

```bash
# 预览
python scripts/update_version.py --dry-run 1.0.0

# 执行
python scripts/update_version.py 1.0.0
```

版本格式：`MAJOR.MINOR.PATCH`（语义化版本）。

## 其他脚本

| 脚本 | 用途 |
|------|------|
| `setup_pre_commit.py` | 安装 pre-commit hooks |
| `run_vulture.py` | 检测无用代码 |
| `generate_release_notes.py` | 生成 release notes |
