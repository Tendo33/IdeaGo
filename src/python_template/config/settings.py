"""Settings module using Pydantic for configuration management.

This is a lightweight template for managing application settings.
这是一个轻量级的应用配置管理模板。

Features / 特性:
- Load from environment variables and .env file / 从环境变量和.env文件加载
- Type-safe with Pydantic validation / 使用Pydantic进行类型安全验证
- Singleton pattern / 单例模式
- Easy to extend / 易于扩展

Usage / 使用方法:
    from python_template.config.settings import get_settings

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

    # Example: Add your own settings here / 示例：在这里添加你自己的配置
    # database_url: str = Field(default="sqlite:///./app.db")
    # api_key: str = Field(default="")
    # max_connections: int = Field(default=10, ge=1, le=100)

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

    # Add your own validators here / 在这里添加你自己的验证器
    # Example:
    # @field_validator("api_key")
    # @classmethod
    # def validate_api_key(cls, v: str) -> str:
    #     if not v and cls.environment == "production":
    #         raise ValueError("API key is required in production")
    #     return v

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
        >>> from python_template.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.environment)
        development
    """
    return Settings()


def reload_settings(env_file: Path | None = None) -> Settings:
    """Reload settings from environment/file / 重新加载配置.

    Useful for testing or when configuration changes at runtime.
    在测试或运行时配置更改时很有用。

    Args:
        env_file: Optional path to .env file / 可选的.env文件路径

    Returns:
        New Settings instance / 新的配置实例
    """
    get_settings.cache_clear()
    if env_file is None:
        return get_settings()
    return Settings(_env_file=str(env_file))  # type: ignore[call-arg]
