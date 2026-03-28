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

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SOURCE_QUERY_CAPS: dict[str, int] = {
    "github": 5,
    "tavily": 5,
    "hackernews": 5,
    "appstore": 5,
    "producthunt": 5,
    "reddit": 5,
}

_DEFAULT_QUERY_FAMILY_WEIGHTS: dict[str, float] = {
    "competitor_discovery": 1.0,
    "alternative_discovery": 1.1,
    "pain_discovery": 1.15,
    "commercial_discovery": 1.0,
    "migration_discovery": 1.0,
    "workflow_discovery": 0.75,
    "ecosystem_discovery": 0.7,
    "launch_discovery": 0.85,
    "positioning_discovery": 0.85,
    "discussion_discovery": 0.8,
}

_DEFAULT_ROLE_QUERY_BUDGETS: dict[str, int] = {
    "builder_signal": 5,
    "market_scan": 5,
    "user_feedback": 5,
    "launch_signal": 4,
    "discussion_signal": 4,
    "general": 4,
}

_DEFAULT_ORCHESTRATION_PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "role_query_budgets": deepcopy(_DEFAULT_ROLE_QUERY_BUDGETS),
        "family_weight_overrides": {},
        "family_trim_threshold": 0.0,
    },
    "web": {
        "role_query_budgets": {
            "builder_signal": 5,
            "market_scan": 5,
            "user_feedback": 4,
            "launch_signal": 4,
            "discussion_signal": 4,
            "general": 4,
        },
        "family_weight_overrides": {
            "pain_discovery": 1.2,
            "commercial_discovery": 1.1,
        },
        "family_trim_threshold": 0.0,
    },
    "mobile": {
        "role_query_budgets": {
            "builder_signal": 3,
            "market_scan": 4,
            "user_feedback": 5,
            "launch_signal": 4,
            "discussion_signal": 4,
            "general": 4,
        },
        "family_weight_overrides": {
            "pain_discovery": 1.25,
            "commercial_discovery": 1.15,
            "ecosystem_discovery": 0.5,
        },
        "family_trim_threshold": 0.0,
    },
    "browser-extension": {
        "role_query_budgets": {
            "builder_signal": 5,
            "market_scan": 4,
            "user_feedback": 4,
            "launch_signal": 4,
            "discussion_signal": 5,
            "general": 4,
        },
        "family_weight_overrides": {
            "discussion_discovery": 1.15,
            "ecosystem_discovery": 1.0,
        },
        "family_trim_threshold": 0.0,
    },
    "desktop": {
        "role_query_budgets": {
            "builder_signal": 4,
            "market_scan": 4,
            "user_feedback": 4,
            "launch_signal": 4,
            "discussion_signal": 4,
            "general": 4,
        },
        "family_weight_overrides": {
            "pain_discovery": 1.1,
        },
        "family_trim_threshold": 0.0,
    },
    "cli": {
        "role_query_budgets": {
            "builder_signal": 5,
            "market_scan": 4,
            "user_feedback": 3,
            "launch_signal": 3,
            "discussion_signal": 5,
            "general": 4,
        },
        "family_weight_overrides": {
            "discussion_discovery": 1.2,
            "workflow_discovery": 1.0,
        },
        "family_trim_threshold": 0.0,
    },
    "api": {
        "role_query_budgets": {
            "builder_signal": 5,
            "market_scan": 5,
            "user_feedback": 3,
            "launch_signal": 3,
            "discussion_signal": 4,
            "general": 4,
        },
        "family_weight_overrides": {
            "commercial_discovery": 1.2,
            "alternative_discovery": 1.15,
        },
        "family_trim_threshold": 0.0,
    },
}


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
    openai_base_url: str = Field(
        default="",
        description=(
            "OpenAI-compatible API base URL, optional / "
            "OpenAI 兼容接口 Base URL（可选）"
        ),
    )
    openai_timeout_seconds: int = Field(
        default=120,
        ge=5,
        le=300,
        description="LLM request timeout in seconds / LLM 请求超时秒数",
    )
    openai_fallback_endpoints: str = Field(
        default="",
        description=(
            "JSON array for fallback LLM endpoints. Each item supports: "
            "name, base_url, api_key, model, timeout"
        ),
    )
    tavily_api_key: str = Field(
        default="",
        description="Tavily search API key / Tavily 搜索密钥",
    )
    tavily_base_url: str = Field(
        default="",
        description="Tavily API base URL (optional) / Tavily API Base URL（可选）",
    )
    github_token: str = Field(
        default="",
        description="GitHub PAT, optional, improves rate limit / GitHub 令牌（可选）",
    )
    appstore_country: str = Field(
        default="us",
        description="iTunes Search country code / iTunes 搜索国家代码",
    )
    producthunt_dev_token: str = Field(
        default="",
        description=(
            "Product Hunt developer token for GraphQL source / Product Hunt 开发者令牌"
        ),
    )
    reddit_client_id: str = Field(
        default="",
        description="Reddit OAuth client ID (from https://www.reddit.com/prefs/apps)",
    )
    reddit_client_secret: str = Field(
        default="",
        description="Reddit OAuth client secret",
    )
    reddit_enable_public_fallback: bool = Field(
        default=False,
        description="Allow public read-only Reddit fallback when OAuth credentials are missing",
    )
    reddit_public_fallback_limit: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Per-query result limit for public Reddit fallback",
    )
    reddit_public_fallback_delay_seconds: float = Field(
        default=1.5,
        ge=0.0,
        le=10.0,
        description="Delay between public Reddit fallback requests in seconds",
    )

    # --- Pipeline / 管道配置 ---
    max_results_per_source: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Max fetched results per data source / 每个数据源抓取结果上限",
    )
    extractor_max_results_per_source: int = Field(
        default=15,
        ge=1,
        le=50,
        description=(
            "Max ranked results per data source sent to extractor / "
            "每个数据源送入提取器的排序后结果上限"
        ),
    )
    source_timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=120,
        description="Per-source fetch timeout / 单源抓取超时秒数",
    )
    source_query_concurrency: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Max concurrent requests per source / 每个数据源内部最大并发请求数",
    )
    source_global_concurrency: int = Field(
        default=3,
        ge=1,
        le=8,
        description="Max concurrent source fetches across platforms / 跨数据源全局并发上限",
    )
    source_query_caps: str = Field(
        default="",
        description=(
            "JSON object mapping source platform to max query count. "
            'Example: {"github": 4, "tavily": 5}'
        ),
    )
    query_family_default_weights: str = Field(
        default="",
        description=(
            "JSON object mapping query family to orchestration weight. "
            'Example: {"pain_discovery": 1.2, "workflow_discovery": 0.6}'
        ),
    )
    app_type_orchestration_profiles: str = Field(
        default="",
        description=(
            "JSON object mapping app_type to orchestration profile. "
            "Each profile can override role_query_budgets, "
            "family_weight_overrides, and family_trim_threshold."
        ),
    )
    producthunt_posted_after_days: int = Field(
        default=730,
        ge=1,
        le=3650,
        description="Product Hunt post freshness window in days / "
        "Product Hunt 抓取时间窗口（天）",
    )
    extraction_timeout_seconds: int = Field(
        default=240,
        ge=10,
        le=300,
        description="Per-source LLM extraction timeout / 单源 LLM 提取超时秒数",
    )
    aggregation_timeout_seconds: int = Field(
        default=180,
        ge=1,
        le=300,
        description="Aggregation timeout / 聚合分析超时秒数",
    )
    langgraph_checkpoint_db_path: str = Field(
        default=".cache/ideago/langgraph-checkpoints.db",
        description="LangGraph checkpoint SQLite path / LangGraph 检查点数据库路径",
    )
    langgraph_max_retries: int = Field(
        default=2,
        ge=0,
        le=8,
        description="Max LLM retries for retryable errors / 可重试错误最大重试次数",
    )
    langgraph_json_parse_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Max retries when LLM returns invalid JSON / LLM 返回非法 JSON 时的最大重试次数",
    )

    # --- Supabase Auth / 认证配置 ---
    supabase_url: str = Field(
        default="",
        description="Supabase project URL / Supabase 项目地址",
    )
    supabase_anon_key: str = Field(
        default="",
        description="Supabase anon (publishable) key / Supabase 匿名密钥",
    )
    supabase_jwt_secret: str = Field(
        default="",
        description="Supabase JWT secret for local token verification "
        "(Dashboard → Settings → API → JWT Secret)",
    )
    supabase_service_role_key: str = Field(
        default="",
        description="Supabase service_role key for backend-only DB operations "
        "(Dashboard → Settings → API → service_role). NEVER expose to frontend.",
    )
    supabase_jwt_audience: str = Field(
        default="authenticated",
        description="Expected Supabase JWT audience for local JWKS verification",
    )
    supabase_jwks_cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        le=86400,
        description="How long to cache Supabase JWKS responses in memory",
    )
    supabase_db_url: str = Field(
        default="",
        description="Direct PostgreSQL connection string for Supabase DB "
        "(Dashboard → Settings → Database → Connection string). "
        "Used for LangGraph checkpoints and distributed state. "
        "Use direct connection (port 5432), not pooler.",
    )

    auth_session_secret: str = Field(
        default="",
        description="Backend session JWT secret for custom OAuth providers",
    )
    auth_session_expire_hours: int = Field(
        default=24 * 30,
        ge=1,
        le=24 * 365,
        description="Backend session JWT expiration time in hours",
    )
    frontend_app_url: str = Field(
        default="",
        description="Public frontend base URL for OAuth callback redirects",
    )
    turnstile_secret_key: str = Field(
        default="",
        description="Cloudflare Turnstile secret key for backend verification",
    )
    linuxdo_client_id: str = Field(
        default="",
        description="LinuxDoConnect OAuth client id",
    )
    linuxdo_client_secret: str = Field(
        default="",
        description="LinuxDoConnect OAuth client secret",
    )
    linuxdo_authorize_url: str = Field(
        default="https://connect.linux.do/oauth2/authorize",
        description="LinuxDoConnect OAuth authorize endpoint",
    )
    linuxdo_token_url: str = Field(
        default="https://connect.linux.do/oauth2/token",
        description="LinuxDoConnect OAuth token endpoint",
    )
    linuxdo_userinfo_url: str = Field(
        default="https://connect.linux.do/api/user",
        description="LinuxDoConnect user info endpoint",
    )
    linuxdo_scope: str = Field(
        default="openid profile email",
        description="LinuxDoConnect OAuth scopes",
    )

    # --- Cache / 缓存配置 ---
    cache_dir: str = Field(
        default=".cache/ideago",
        description="Cache directory path / 缓存目录路径",
    )
    anonymous_cache_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="TTL for anonymous (unowned) reports. "
        "User-owned reports persist indefinitely.",
    )
    file_cache_max_entries: int = Field(
        default=500,
        ge=10,
        le=10000,
        description="Maximum number of entries in the local file cache. "
        "Oldest entries are evicted when limit is reached.",
    )

    # --- Rate limiting ---
    rate_limit_analyze_max: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max analyze requests per user within the rate-limit window",
    )
    rate_limit_analyze_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate-limit sliding window for analyze (seconds)",
    )
    rate_limit_reports_max: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Max report read requests per user within the rate-limit window",
    )
    rate_limit_reports_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate-limit sliding window for report reads (seconds)",
    )

    # --- Stripe billing ---
    stripe_secret_key: str = Field(
        default="",
        description="Stripe secret key (sk_live_... or sk_test_...)",
    )
    stripe_webhook_secret: str = Field(
        default="",
        description="Stripe webhook endpoint signing secret (whsec_...)",
    )
    stripe_pro_price_id: str = Field(
        default="",
        description="Stripe Price ID for the Pro plan (price_...)",
    )

    # --- Observability ---
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN for error tracking. Leave empty to disable.",
    )
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sentry performance traces sample rate (0.0-1.0)",
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
    cors_allow_origins: str = Field(
        default="*",
        description="Comma-separated CORS allow origins, use * for all",
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

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        """Ensure critical settings are present in production."""
        if self.environment != "production":
            return self
        required = {
            "auth_session_secret": self.auth_session_secret,
            "supabase_url": self.supabase_url,
            "supabase_service_role_key": self.supabase_service_role_key,
            "frontend_app_url": self.frontend_app_url,
        }
        missing = [k for k, v in required.items() if not v.strip()]
        if missing:
            names = ", ".join(k.upper() for k in missing)
            raise ValueError(f"Production requires the following settings: {names}")
        return self

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

    def get_cors_allow_origins(self) -> list[str]:
        """Return parsed CORS origins from comma-separated config."""
        raw = self.cors_allow_origins.strip()
        if not raw:
            return ["*"]
        if raw == "*":
            return ["*"]
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return origins or ["*"]

    def get_supabase_jwks_url(self) -> str:
        """Return the Supabase JWKS URL derived from the project URL."""
        base = self.supabase_url.strip().rstrip("/")
        if not base:
            return ""
        return f"{base}/auth/v1/.well-known/jwks.json"

    def get_supabase_jwt_issuer(self) -> str:
        """Return the expected Supabase JWT issuer."""
        base = self.supabase_url.strip().rstrip("/")
        if not base:
            return ""
        return f"{base}/auth/v1"

    def get_openai_fallback_endpoints(self) -> list[dict[str, Any]]:
        """Parse fallback endpoint JSON config for ChatModelClient."""
        raw = self.openai_fallback_endpoints.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []

        endpoints: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            endpoints.append(
                {
                    "name": item.get("name"),
                    "base_url": item.get("base_url"),
                    "api_key": item.get("api_key"),
                    "model": item.get("model"),
                    "timeout": item.get("timeout"),
                }
            )
        return endpoints

    def get_source_query_caps(self) -> dict[str, int]:
        """Return per-source query caps merged with defaults."""
        caps = deepcopy(_DEFAULT_SOURCE_QUERY_CAPS)
        overrides = self._parse_json_object_setting(self.source_query_caps)
        for source_name, raw_value in overrides.items():
            key = str(source_name).strip().lower()
            if key not in caps:
                continue
            parsed = self._coerce_positive_int(raw_value)
            if parsed is None:
                continue
            caps[key] = parsed
        return caps

    def get_query_family_default_weights(self) -> dict[str, float]:
        """Return query-family weights merged with defaults."""
        weights = deepcopy(_DEFAULT_QUERY_FAMILY_WEIGHTS)
        overrides = self._parse_json_object_setting(self.query_family_default_weights)
        for family_name, raw_value in overrides.items():
            key = str(family_name).strip().lower()
            if key not in weights:
                continue
            parsed = self._coerce_non_negative_float(raw_value)
            if parsed is None:
                continue
            weights[key] = parsed
        return weights

    def get_orchestration_profiles(self) -> dict[str, dict[str, Any]]:
        """Return app-type orchestration profiles merged with defaults."""
        profiles = deepcopy(_DEFAULT_ORCHESTRATION_PROFILES)
        overrides = self._parse_json_object_setting(
            self.app_type_orchestration_profiles
        )
        for app_type, raw_profile in overrides.items():
            app_key = str(app_type).strip().lower()
            if not app_key or not isinstance(raw_profile, dict):
                continue
            base_profile = deepcopy(profiles.get(app_key, profiles["default"]))
            role_budgets = self._parse_json_object_setting(
                raw_profile.get("role_query_budgets")
            )
            family_overrides = self._parse_json_object_setting(
                raw_profile.get("family_weight_overrides")
            )
            threshold = self._coerce_non_negative_float(
                raw_profile.get("family_trim_threshold")
            )
            if threshold is not None:
                base_profile["family_trim_threshold"] = threshold

            base_role_budgets = base_profile.get("role_query_budgets", {})
            if isinstance(base_role_budgets, dict):
                for role_name, raw_budget in role_budgets.items():
                    role_key = str(role_name).strip().lower()
                    if role_key not in _DEFAULT_ROLE_QUERY_BUDGETS:
                        continue
                    parsed_budget = self._coerce_positive_int(raw_budget)
                    if parsed_budget is None:
                        continue
                    base_role_budgets[role_key] = parsed_budget
                base_profile["role_query_budgets"] = base_role_budgets

            base_family_overrides = base_profile.get("family_weight_overrides", {})
            if isinstance(base_family_overrides, dict):
                for family_name, raw_weight in family_overrides.items():
                    family_key = str(family_name).strip().lower()
                    if family_key not in _DEFAULT_QUERY_FAMILY_WEIGHTS:
                        continue
                    parsed_weight = self._coerce_non_negative_float(raw_weight)
                    if parsed_weight is None:
                        continue
                    base_family_overrides[family_key] = parsed_weight
                base_profile["family_weight_overrides"] = base_family_overrides

            profiles[app_key] = base_profile
        return profiles

    @staticmethod
    def _parse_json_object_setting(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}
        payload = raw.strip()
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _coerce_positive_int(raw: Any) -> int | None:
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _coerce_non_negative_float(raw: Any) -> float | None:
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None


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
