"""Base models and mixins for Pydantic models.

Provides common configurations and reusable mixins for all Pydantic models.
为所有Pydantic模型提供通用配置和可复用的Mixin。
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class BaseModel(PydanticBaseModel):
    """Base model with common Pydantic v2 configuration.

    基础模型，包含通用的Pydantic v2配置。

    This model provides sensible defaults for all project models:
    - Allows population by field name or alias
    - Uses snake_case for field names
    - Validates assignments
    - Allows arbitrary types when needed

    该模型为所有项目模型提供合理的默认配置。
    """

    model_config = ConfigDict(
        # Allow population by field name or alias
        populate_by_name=True,
        # Validate field values when they are assigned
        validate_assignment=True,
        # Use snake_case for JSON schema field names
        alias_generator=None,
        # Strict mode for better type safety
        strict=False,
        # Allow extra fields (can be set to 'forbid' for stricter validation)
        extra="ignore",
    )

    def model_dump_json_safe(self) -> dict[str, Any]:
        """Dump model to JSON-safe dictionary.

        转储模型为JSON安全的字典。

        Returns:
            Dictionary with JSON-serializable values
        """
        return self.model_dump(mode="json")


class TimestampMixin(BaseModel):
    """Mixin that provides UTC timestamps for created/updated times."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp in UTC",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp in UTC",
    )
