# Pydantic Models 规范

本文档定义在 `python_template` 项目中使用 Pydantic 模型的规则。

## 核心规则

1. **所有数据模型必须继承项目的 `BaseModel`**（`python_template.models.base`），不要直接继承 `pydantic.BaseModel`。
2. **模型只能定义在 `models/` 目录下**，不要在 `utils/` 或其他位置定义数据类。
3. **统一使用 Pydantic v2 语法**：`model_config = ConfigDict(...)`，`model_dump()`，`model_validate()`。禁止 v1 的 `class Config` 或 `.dict()`。
4. **所有公开模型必须在 `models/__init__.py` 中导出**。

## 目录结构

```text
src/python_template/models/
├── __init__.py        # 统一导出
├── base.py            # 项目 BaseModel + Mixins
└── <domain>.py        # 按业务域组织模型文件
```

## 字段要求

- 每个字段必须使用 `Field()` 并提供 `description`。
- 数值型字段应加约束（`ge`, `le`, `gt`, `lt`）。
- 可变默认值使用 `default_factory`（如 `Field(default_factory=list)`），不要写 `= []`。
- 可选字段显式标注 `Optional[T] = None`。

## 验证

- 单字段验证用 `@field_validator`。
- 跨字段验证用 `@model_validator(mode="after")`。
- 调用方必须捕获 `ValidationError`，不要让验证异常无声传播。

## 序列化

- 转字典：`model.model_dump()`
- 转 JSON：`model.model_dump_json()`
- 从字典：`Model.model_validate(data)`
- 从 JSON：`Model.model_validate_json(json_str)`

## 参考

- [Pydantic v2 官方文档](https://docs.pydantic.dev/)
- 配置管理相关：`ai_docs/SETTINGS_GUIDE.md`
- SDK 导入相关：`ai_docs/SDK_USAGE.md`
