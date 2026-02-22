"""Pipeline-specific exception types.

管道专用异常类型：用于区分意图解析、提取、聚合阶段的错误。
"""


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class IntentParsingError(PipelineError):
    """Raised when intent parsing fails (LLM or validation)."""


class ExtractionError(PipelineError):
    """Raised when competitor extraction from raw results fails."""


class AggregationError(PipelineError):
    """Raised when deduplication / market analysis fails."""
