"""SSE pipeline event types.

管道进度事件类型，用于实时推送执行状态到前端。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field

from ideago.models.base import BaseModel


class EventType(str, Enum):
    """Pipeline stage event types / 管道阶段事件类型。"""

    INTENT_STARTED = "intent_started"
    INTENT_PARSED = "intent_parsed"
    QUERY_PLANNING_STARTED = "query_planning_started"
    QUERY_PLANNING_COMPLETED = "query_planning_completed"
    SOURCE_STARTED = "source_started"
    SOURCE_COMPLETED = "source_completed"
    SOURCE_FAILED = "source_failed"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    AGGREGATION_STARTED = "aggregation_started"
    AGGREGATION_COMPLETED = "aggregation_completed"
    REPORT_READY = "report_ready"
    CANCELLED = "cancelled"
    ERROR = "error"


class PipelineEvent(BaseModel):
    """A single progress event emitted during pipeline execution."""

    type: EventType
    stage: str = Field(description="Human-readable stage name")
    message: str = Field(description="Human-readable progress message")
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_sse(self) -> str:
        """Serialize to SSE-compatible JSON string."""
        return self.model_dump_json()
