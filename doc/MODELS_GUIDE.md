# Pydantic Models 使用指南 (Models Usage Guide)

本文档介绍如何在 `python_template` 项目中使用 Pydantic BaseModel 定义和管理数据模型。

## 📌 核心原则

**所有数据模型必须继承自 Pydantic BaseModel**

- ✅ **DO**: 在 `models/` 目录下的所有类都必须继承 `BaseModel`
- ✅ **DO**: 使用 Pydantic v2 语法和特性
- ❌ **DON'T**: 不要在 `models/` 中使用普通 Python 类、dataclass 或 dict
- ❌ **DON'T**: 不要在 `utils/` 中定义数据模型类

## 🏗️ Models 目录结构

```
src/python_template/models/
├── __init__.py        # 导出所有公开模型
├── base.py            # 基础模型和 Mixins
└── examples.py        # 示例模型实现
```

### 1. `base.py` - 基础模型

包含项目的基础 BaseModel 和可复用的 Mixins。

```python
from pydantic import BaseModel as PydanticBaseModel, ConfigDict

class BaseModel(PydanticBaseModel):
    """项目的基础模型,所有模型都应继承这个类"""

    model_config = ConfigDict(
        populate_by_name=True,      # 允许使用字段名或别名
        validate_assignment=True,   # 赋值时验证
        extra="ignore",             # 忽略额外字段
    )
```

### 2. `examples.py` - 示例模型

提供常见用例的模型实现,包括:
- `User`: 用户模型 (带验证)
- `ApiResponse[T]`: 泛型 API 响应模型
- `PaginatedResponse[T]`: 分页响应模型
- `ConfigModel`: 配置模型示例

### 3. `__init__.py` - 导出接口

统一导出所有公开模型:

```python
from .base import BaseModel, TimestampMixin
from .examples import User, ApiResponse, ConfigModel

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "User",
    "ApiResponse",
    "ConfigModel",
]
```

## 📝 如何创建新模型

### 基础模型定义

```python
from pydantic import Field
from python_template.models import BaseModel

class Product(BaseModel):
    """产品模型 / Product model."""

    id: int = Field(..., description="产品ID / Product ID", ge=1)
    name: str = Field(
        ...,
        description="产品名称 / Product name",
        min_length=1,
        max_length=100,
    )
    price: float = Field(..., description="价格 / Price", gt=0)
    is_active: bool = Field(default=True, description="是否激活 / Is active")
```

### 使用 Mixins

```python
from python_template.models import BaseModel, TimestampMixin

class Article(TimestampMixin):
    """文章模型,自动包含 created_at 和 updated_at 字段"""

    title: str = Field(..., description="标题 / Title")
    content: str = Field(..., description="内容 / Content")
    author: str = Field(..., description="作者 / Author")
```

### 字段验证

#### 1. 使用 Field 参数进行基础验证

```python
from pydantic import Field
from python_template.models import BaseModel

class User(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",  # 正则验证
    )
    age: int = Field(..., ge=0, le=150)  # 数值范围
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    )
```

#### 2. 使用 field_validator 进行自定义验证

```python
from pydantic import field_validator
from python_template.models import BaseModel

class User(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must be alphanumeric")
        return v.lower()  # 转小写

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码强度"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        return v
```

#### 3. 使用 model_validator 进行跨字段验证

```python
from pydantic import model_validator
from python_template.models import BaseModel

class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRange":
        """验证日期范围"""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self
```

### 泛型模型

```python
from typing import Generic, TypeVar, List, Optional
from python_template.models import BaseModel

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    """泛型响应模型"""

    success: bool = Field(..., description="是否成功")
    data: Optional[T] = Field(None, description="响应数据")
    message: str = Field(default="", description="响应消息")

# 使用泛型模型
user_response: Response[User] = Response(
    success=True,
    data=User(id=1, username="alice", email="alice@example.com"),
    message="User fetched successfully"
)
```

## 🔧 模型使用

### 1. 创建实例

```python
from python_template.models import User

# 直接传参
user = User(
    id=1,
    username="john_doe",
    email="john@example.com",
    full_name="John Doe",
)

# 从字典创建
data = {"id": 1, "username": "john_doe", "email": "john@example.com"}
user = User(**data)

# 使用 model_validate (推荐,Pydantic v2)
user = User.model_validate(data)
```

### 2. 序列化

```python
# 转换为字典
user_dict = user.model_dump()
# 输出: {'id': 1, 'username': 'john_doe', ...}

# 转换为 JSON 字符串
user_json = user.model_dump_json()
# 输出: '{"id": 1, "username": "john_doe", ...}'

# 只导出部分字段
user_dict = user.model_dump(include={"id", "username"})
# 或排除某些字段
user_dict = user.model_dump(exclude={"password"})
```

### 3. 反序列化

```python
# 从 JSON 字符串
json_str = '{"id": 1, "username": "john_doe", "email": "john@example.com"}'
user = User.model_validate_json(json_str)

# 从字典
data = {"id": 1, "username": "john_doe", "email": "john@example.com"}
user = User.model_validate(data)
```

### 4. 更新模型

```python
user = User(id=1, username="john_doe", email="john@example.com")

# 使用 model_copy 创建副本并更新
updated_user = user.model_copy(update={"email": "newemail@example.com"})

# 或者直接赋值 (如果 validate_assignment=True)
user.email = "newemail@example.com"
```

## 🎯 最佳实践

### 1. 始终使用 Field() 添加描述

```python
from pydantic import Field
from python_template.models import BaseModel

class Good(BaseModel):
    """良好的模型定义"""

    name: str = Field(
        ...,
        description="用户名 / Username",
        min_length=3,
        max_length=50,
    )

# ❌ 不推荐
class Bad(BaseModel):
    name: str  # 没有描述,没有验证
```

### 2. 使用双语描述

```python
# ✅ 推荐:提供中英文描述
name: str = Field(..., description="用户名 / Username")
```

### 3. 使用 Optional 明确可选字段

```python
from typing import Optional

class User(BaseModel):
    username: str  # 必填
    full_name: Optional[str] = None  # 可选
```

### 4. 为可变默认值使用 default_factory

```python
from typing import List
from pydantic import Field

class User(BaseModel):
    # ✅ 正确
    tags: List[str] = Field(default_factory=list)

    # ❌ 错误 (会导致所有实例共享同一个列表)
    # tags: List[str] = []
```

### 5. 实现辅助方法

```python
from python_template.models import BaseModel

class User(BaseModel):
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        """计算属性:全名"""
        return f"{self.first_name} {self.last_name}"

    def to_display_dict(self) -> dict:
        """自定义序列化方法"""
        return {
            "name": self.full_name,
            "id": self.id,
        }
```

## 🚫 常见错误

### 1. 在 utils 中定义数据类

```python
# ❌ 错误:不要在 utils 中定义数据模型
# src/python_template/utils/my_utils.py
class UserData:  # 错误!
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

# ✅ 正确:在 models 中定义
# src/python_template/models/user.py
from python_template.models import BaseModel

class UserData(BaseModel):
    name: str
    email: str
```

### 2. 使用 Pydantic v1 语法

```python
# ❌ 错误:使用 v1 语法
from python_template.models import BaseModel

class User(BaseModel):
    name: str

    class Config:  # v1 语法
        validate_assignment = True

# ✅ 正确:使用 v2 语法
from pydantic import ConfigDict

class User(BaseModel):
    name: str

    model_config = ConfigDict(  # v2 语法
        validate_assignment=True,
    )
```

### 3. 不处理验证错误

```python
# ❌ 错误:不捕获验证错误
user = User(**invalid_data)  # 可能抛出 ValidationError

# ✅ 正确:处理验证错误
from pydantic import ValidationError

try:
    user = User.model_validate(data)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    # 处理错误
```

## 📚 进阶用法

### 1. 模型继承

```python
from python_template.models import BaseModel, TimestampMixin

class BaseUser(TimestampMixin):
    """基础用户模型"""
    id: int
    username: str

class AdminUser(BaseUser):
    """管理员用户,继承所有基础字段"""
    permissions: List[str] = Field(default_factory=list)
```

### 2. 字段别名

```python
from pydantic import Field

class ApiData(BaseModel):
    user_id: int = Field(..., alias="userId")  # JSON 中使用 userId
    full_name: str = Field(..., alias="fullName")

# 使用别名解析
data = {"userId": 1, "fullName": "John Doe"}
api_data = ApiData.model_validate(data)
print(api_data.user_id)  # 1
```

### 3. 嵌套模型

```python
from typing import List

class Address(BaseModel):
    street: str
    city: str
    country: str

class User(BaseModel):
    name: str
    address: Address  # 嵌套模型
    previous_addresses: List[Address] = Field(default_factory=list)

# 使用
user = User(
    name="John",
    address={"street": "123 Main St", "city": "NYC", "country": "USA"},
    previous_addresses=[
        {"street": "456 Oak Ave", "city": "LA", "country": "USA"}
    ]
)
```

## 🔗 相关文档

- [配置管理指南](SETTINGS_GUIDE.md) - 了解如何使用 Pydantic Settings
- [SDK 使用指南](SDK_USAGE.md) - 了解如何导入和使用模型
- [Pydantic 官方文档](https://docs.pydantic.dev/) - Pydantic v2 完整文档

## 💡 总结

1. **所有模型必须继承 Pydantic BaseModel**
2. **模型定义在 `models/` 目录中**
3. **使用 Pydantic v2 语法** (`model_config`, `model_dump()`, `model_validate()`)
4. **提供完整的字段描述和验证规则**
5. **使用 Field() 添加约束和文档**
6. **实现自定义验证器处理复杂逻辑**
7. **导出所有公开模型到 `__init__.py`**
