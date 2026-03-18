# SDK Usage Guide

本项目采用标准 `src` 布局。导入时不需要加 `src` 前缀。

## 安装

```bash
# 本地可编辑安装（推荐）
uv pip install -e .

# 或 pip
pip install -e .
```

## 导入

```python
from python_template.utils import read_json

data = read_json("data.json")
```

测试文件中同样直接导入，不写 `from src.python_template...`。

## 原理

1. `src` 布局规范：`pip install -e .` 会将 `src/` 加入 `sys.path`，Python 直接找到 `python_template` 包。
2. Pytest 配置：`pyproject.toml` 中 `pythonpath = ["src"]`，测试运行时也能定位到包。

## 路径注意事项

`pythonpath` 只影响 `import`，不影响文件读写路径。文件路径始终相对于 CWD。

建议使用 `pathlib` 获取绝对路径：

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
data_path = PROJECT_ROOT / "data" / "test.json"
```
