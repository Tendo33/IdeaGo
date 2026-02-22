"""Loguru logging configuration module.

This module provides a centralized logging configuration using loguru,
a modern and powerful logging library for Python.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
    log_file: str | None = None,
    rotation: str = "10 MB",
    retention: str = "1 week",
    compression: str = "gz",
    serialize: bool = False,
    backtrace: bool = True,
    diagnose: bool = True,
    enqueue: bool = False,
    catch: bool = True,
) -> None:
    """Setup loguru logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        log_file: Path to log file (optional)
        rotation: Log rotation policy
        retention: Log retention policy
        compression: Compression format for rotated logs
        serialize: Whether to serialize logs as JSON
        backtrace: Whether to include backtrace in exception logs
        diagnose: Whether to include variable values in exception logs
        enqueue: Whether to enqueue log messages
        catch: Whether to catch errors during logging
    """
    # 移除默认的处理器
    logger.remove()

    # 如果未指定日志文件，则使用默认路径
    if log_file is None:
        # 获取项目根目录 (假设当前文件在 src/python_template/observability/log_config.py)
        # 向上回溯4级: observability -> python_template -> src -> python-template (root)
        project_root = Path(__file__).resolve().parents[3]
        log_dir = project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 生成带日期的日志文件名
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = str(log_dir / f"{current_date}.log")

    # 默认格式字符串
    if format_string is None:
        if serialize:
            format_string = "{message}"
        else:
            format_string = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )

    # 控制台输出处理器
    logger.add(
        sys.stderr,
        level=level,
        format=format_string,
        backtrace=backtrace,
        diagnose=diagnose,
        enqueue=enqueue,
        catch=catch,
        serialize=serialize,
    )

    # 文件输出处理器（如果指定了日志文件）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_path,
            level=level,
            format=format_string,
            rotation=rotation,
            retention=retention,
            compression=compression,
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=enqueue,
            catch=catch,
            serialize=serialize,
        )


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance.

    Args:
        name: Logger name (optional)

    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


def configure_json_logging(
    level: str = "INFO",
    log_file: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Configure JSON structured logging.

    Args:
        level: Logging level
        log_file: Path to log file
        extra_fields: Additional fields to include in JSON logs
    """
    setup_logging(
        level=level,
        log_file=log_file,
        serialize=True,
    )
    logger.configure(extra=extra_fields or {})


def log_function_calls(func):
    """Decorator to log function calls with parameters and return values.

    Args:
        func: Function to be decorated

    Returns:
        Decorated function
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        func_logger = get_logger(f"{func.__module__}.{func.__name__}")

        # 记录函数调用
        func_logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")

        try:
            # 执行函数
            result = func(*args, **kwargs)

            # 记录返回值
            func_logger.debug(f"{func.__name__} returned: {result}")

            return result
        except Exception as e:
            # 记录异常
            func_logger.exception(f"Exception in {func.__name__}: {e}")
            raise

    return wrapper


# 延迟初始化标志
_logging_initialized = False


def _ensure_logging_initialized() -> None:
    """确保日志系统已初始化（懒加载）。"""
    global _logging_initialized
    if not _logging_initialized:
        setup_logging()
        _logging_initialized = True


def get_default_logger():
    """获取默认日志器（懒加载初始化）。

    Returns:
        默认日志器实例
    """
    _ensure_logging_initialized()
    return get_logger("python_template")


# 便捷的日志函数
def debug(message: str, **kwargs) -> None:
    """Log debug message."""
    get_default_logger().debug(message, **kwargs)


def info(message: str, **kwargs) -> None:
    """Log info message."""
    get_default_logger().info(message, **kwargs)


def warning(message: str, **kwargs) -> None:
    """Log warning message."""
    get_default_logger().warning(message, **kwargs)


def error(message: str, **kwargs) -> None:
    """Log error message."""
    get_default_logger().error(message, **kwargs)


def critical(message: str, **kwargs) -> None:
    """Log critical message."""
    get_default_logger().critical(message, **kwargs)


def exception(message: str, **kwargs) -> None:
    """Log exception with traceback."""
    get_default_logger().exception(message, **kwargs)
