"""Settings module using Pydantic for configuration management.

This is a lightweight template for managing application settings.
这是一个轻量级的应用配置管理模板。

Features / 特性:
- Load from environment variables and .env file / 从环境变量和.env文件加载
- Type-safe with Pydantic validation / 使用Pydantic进行类型安全验证
- Singleton pattern / 单例模式
- Easy to extend / 易于扩展

Usage / 使用方法:
    from ideago.config.settings import get_settings

    settings = get_settings()
    print(settings.environment)
    print(settings.log_level)

How to add your own settings / 如何添加自己的配置项:
    1. Add field to Settings class / 在Settings类中添加字段
    2. Add corresponding env var to .env.example / 在.env.example中添加对应的环境变量
    3. Use Field() for validation and defaults / 使用Field()进行验证和设置默认值

    Example / 示例:
        database_url: str = Field(
            default="sqlite:///./app.db",
            description="Database connection URL"
        )
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings / 应用配置.

    Add your own configuration fields here following the examples below.
    参考下面的示例添加你自己的配置字段。

    Configuration priority (highest to lowest) / 配置优先级（从高到低）:
    1. Environment variables / 环境变量
    2. .env file / .env文件
    3. Default values / 默认值
    """

    # Basic runtime settings / 基础运行时配置
    environment: str = Field(
        default="development",
        description="Environment: development/staging/production / 运行环境",
    )

    # Logging settings / 日志配置
    log_level: str = Field(default="INFO", description="Log level / 日志级别")
    log_file: str = Field(
        default="logs/app.log", description="Log file path / 日志文件路径"
    )

    # --- API Keys / API 密钥 ---
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key / OpenAI 密钥",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name / 模型名称",
    )
    openai_timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=300,
        description="LLM request timeout in seconds / LLM 请求超时秒数",
    )
    tavily_api_key: str = Field(
        default="",
        description="Tavily search API key / Tavily 搜索密钥",
    )
    github_token: str = Field(
        default="",
        description="GitHub PAT, optional, improves rate limit / GitHub 令牌（可选）",
    )

    # --- Pipeline / 管道配置 ---
    max_results_per_source: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Max results per data source / 每个数据源最大结果数",
    )
    source_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Per-source fetch timeout / 单源抓取超时秒数",
    )
    extraction_timeout_seconds: int = Field(
        default=60,
        ge=10,
        le=180,
        description="Per-source LLM extraction timeout / 单源 LLM 提取超时秒数",
    )

    # --- Cache / 缓存配置 ---
    cache_dir: str = Field(
        default=".cache/ideago",
        description="Cache directory path / 缓存目录路径",
    )
    cache_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Cache TTL in hours / 缓存有效期（小时）",
    )

    # --- Server / 服务配置 ---
    host: str = Field(
        default="0.0.0.0",
        description="Server bind host / 服务绑定地址",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server bind port / 服务绑定端口",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        case_sensitive=False,
        extra="ignore",  # Allow extra fields for flexibility / 允许额外字段以提高灵活性
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value / 验证环境值."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level / 验证日志级别."""
        allowed = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v_upper

    def get_project_root(self) -> Path:
        """Get project root directory / 获取项目根目录.

        Returns:
            Path to project root / 项目根目录路径
        """
        # Assuming this file is in src/{package}/config/
        current_file = Path(__file__).resolve()
        # Go up: settings.py -> config -> package -> src -> project_root
        return current_file.parent.parent.parent.parent

    def get_log_file_path(self) -> Path:
        """Get absolute path to log file / 获取日志文件的绝对路径.

        Returns:
            Absolute path to log file / 日志文件的绝对路径
        """
        log_path = Path(self.log_file)
        if log_path.is_absolute():
            return log_path
        return self.get_project_root() / log_path


@lru_cache
def get_settings() -> Settings:
    """Get global settings instance (singleton) / 获取全局配置实例（单例）.

    This function is cached to ensure only one Settings instance exists.
    该函数使用缓存确保只存在一个Settings实例。

    Returns:
        Settings instance / 配置实例

    Example:
        >>> from ideago.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.environment)
        development
    """
    if _settings_override is not None:
        return _settings_override
    return Settings()


_settings_override: Settings | None = None


def reload_settings(env_file: Path | None = None) -> Settings:
    """Reload settings from environment/file / 重新加载配置.

    Useful for testing or when configuration changes at runtime.
    在测试或运行时配置更改时很有用。

    Args:
        env_file: Optional path to .env file / 可选的.env文件路径

    Returns:
        New Settings instance / 新的配置实例
    """
    global _settings_override
    get_settings.cache_clear()
    if env_file is not None:
        _settings_override = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    else:
        _settings_override = None
    return get_settings()
