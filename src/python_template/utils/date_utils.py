"""Date and time utilities module.

提供日期时间处理相关的常用功能。
"""

import traceback
from datetime import datetime, timedelta, timezone

from python_template.observability.log_config import get_logger

logger = get_logger(__name__)


def get_timestamp(include_timezone: bool = True) -> str:
    """获取当前时间戳(ISO 格式)。

    Args:
        include_timezone: 是否包含时区信息

    Returns:
        ISO 格式的时间戳字符串
    """
    if include_timezone:
        return datetime.now(timezone.utc).isoformat()
    else:
        return datetime.now().isoformat()


def parse_timestamp(timestamp_str: str) -> datetime | None:
    """解析 ISO 格式时间戳字符串。

    Args:
        timestamp_str: ISO 格式时间戳字符串

    Returns:
        datetime 对象,失败时返回 None
    """
    try:
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        logger.error(f"Invalid timestamp format: {timestamp_str}")
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return None


def format_datetime(
    dt: datetime,
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """格式化 datetime 对象。

    Args:
        dt: datetime 对象
        format_str: 格式化字符串

    Returns:
        格式化后的时间字符串
    """
    try:
        return dt.strftime(format_str)
    except Exception as e:
        logger.error(f"Failed to format datetime: {e}")
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return str(dt)


def parse_datetime(
    date_str: str,
    format_str: str = "%Y-%m-%d %H:%M:%S",
) -> datetime | None:
    """解析时间字符串为 datetime 对象。

    Args:
        date_str: 时间字符串
        format_str: 格式化字符串

    Returns:
        datetime 对象,失败时返回 None
    """
    try:
        return datetime.strptime(date_str, format_str)
    except ValueError as e:
        logger.error(f"Failed to parse datetime string '{date_str}': {e}")
        logger.debug(f"Traceback:\n{traceback.format_exc()}")
        return None


def get_current_date(
    format_str: str = "%Y-%m-%d",
    use_utc: bool = True,
) -> str:
    """获取当前日期。

    Args:
        format_str: 格式化字符串
        use_utc: 是否使用 UTC 时间

    Returns:
        格式化后的日期字符串
    """
    now = datetime.now(timezone.utc) if use_utc else datetime.now()
    return now.strftime(format_str)


def get_current_time(
    format_str: str = "%H:%M:%S",
    use_utc: bool = True,
) -> str:
    """获取当前时间。

    Args:
        format_str: 格式化字符串
        use_utc: 是否使用 UTC 时间

    Returns:
        格式化后的时间字符串
    """
    now = datetime.now(timezone.utc) if use_utc else datetime.now()
    return now.strftime(format_str)


def get_time_difference(
    dt1: datetime,
    dt2: datetime,
    unit: str = "seconds",
) -> float:
    """计算两个时间之间的差值。

    Args:
        dt1: 第一个 datetime 对象
        dt2: 第二个 datetime 对象
        unit: 返回单位 (seconds, minutes, hours, days)

    Returns:
        时间差值
    """
    diff = abs((dt1 - dt2).total_seconds())

    if unit == "seconds":
        return diff
    elif unit == "minutes":
        return diff / 60
    elif unit == "hours":
        return diff / 3600
    elif unit == "days":
        return diff / 86400
    else:
        logger.warning(f"Unknown unit '{unit}', returning seconds")
        return diff


def is_weekend(dt: datetime | None = None) -> bool:
    """判断是否为周末。

    Args:
        dt: datetime 对象,默认为当前时间

    Returns:
        是周末返回 True,否则返回 False
    """
    if dt is None:
        dt = datetime.now()
    return dt.weekday() >= 5  # 5=Saturday, 6=Sunday


def humanize_timedelta(
    td: timedelta | float,
    precision: int = 2,
) -> str:
    """将 timedelta 或秒数转换为人类可读格式。

    Args:
        td: timedelta 对象或秒数
        precision: 显示的时间单位数量

    Returns:
        人类可读的时间字符串
    """
    if isinstance(td, int | float):
        td = timedelta(seconds=td)

    total_seconds = int(td.total_seconds())

    if total_seconds == 0:
        return "0 seconds"

    units = [
        ("day", 86400),
        ("hour", 3600),
        ("minute", 60),
        ("second", 1),
    ]

    parts = []
    for unit_name, unit_seconds in units:
        if total_seconds >= unit_seconds:
            value = total_seconds // unit_seconds
            total_seconds %= unit_seconds
            unit_str = unit_name if value == 1 else f"{unit_name}s"
            parts.append(f"{value} {unit_str}")

            if len(parts) >= precision:
                break

    return ", ".join(parts)


def get_unix_timestamp(dt: datetime | None = None) -> int:
    """获取 Unix 时间戳(秒)。

    Args:
        dt: datetime 对象,默认为当前时间

    Returns:
        Unix 时间戳
    """
    if dt is None:
        dt = datetime.now()

    return int(dt.timestamp())


def from_unix_timestamp(timestamp: int) -> datetime:
    """从 Unix 时间戳创建 datetime 对象。

    Args:
        timestamp: Unix 时间戳(秒)

    Returns:
        datetime 对象
    """
    return datetime.fromtimestamp(timestamp)


def add_days(dt: datetime, days: int) -> datetime:
    """为 datetime 添加指定天数。

    Args:
        dt: datetime 对象
        days: 要添加的天数(可为负数)

    Returns:
        新的 datetime 对象
    """
    return dt + timedelta(days=days)


def add_hours(dt: datetime, hours: int) -> datetime:
    """为 datetime 添加指定小时数。

    Args:
        dt: datetime 对象
        hours: 要添加的小时数(可为负数)

    Returns:
        新的 datetime 对象
    """
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """为 datetime 添加指定分钟数。

    Args:
        dt: datetime 对象
        minutes: 要添加的分钟数(可为负数)

    Returns:
        新的 datetime 对象
    """
    return dt + timedelta(minutes=minutes)


def get_week_start(dt: datetime | None = None) -> datetime:
    """获取给定日期所在周的周一(00:00:00)。

    Args:
        dt: datetime 对象,默认为当前时间

    Returns:
        该周周一的 datetime 对象(时间为 00:00:00)
    """
    if dt is None:
        dt = datetime.now()
    # weekday() 返回 0=Monday, 6=Sunday
    days_since_monday = dt.weekday()
    monday = dt - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_month_start(dt: datetime | None = None) -> datetime:
    """获取给定日期所在月的第一天(00:00:00)。

    Args:
        dt: datetime 对象,默认为当前时间

    Returns:
        该月第一天的 datetime 对象(时间为 00:00:00)
    """
    if dt is None:
        dt = datetime.now()
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
