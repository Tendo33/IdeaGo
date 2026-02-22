"""Data models using Pydantic for validation.

This module provides base models and example implementations using Pydantic v2
for data validation and configuration management.

提供使用Pydantic v2进行数据验证和配置管理的基础模型和示例实现。
"""

from .base import BaseModel, TimestampMixin
from .examples import ApiResponse, ConfigModel, PaginatedResponse, User

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "User",
    "ApiResponse",
    "PaginatedResponse",
    "ConfigModel",
]
