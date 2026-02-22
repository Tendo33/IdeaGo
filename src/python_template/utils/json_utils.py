"""JSON utilities module."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiofiles

from python_template.observability.log_config import get_logger
from python_template.utils.decorator_utils import timing

logger = get_logger(__name__)


# =============================================================================
# 同步 JSON 操作
# =============================================================================


@timing
def read_json(
    file_path: str | Path,
    encoding: str = "utf-8",
    default: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any] | list[Any] | None:
    """读取 JSON 文件。

    Args:
        file_path: JSON 文件路径
        encoding: 文件编码
        default: 读取失败时返回的默认值

    Returns:
        dict | list | None: 成功时返回解析后的 JSON 数据，失败返回 default
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return default

        with open(file_path, encoding=encoding) as f:
            data = json.load(f)
            logger.debug(f"Read JSON from: {file_path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return default
    except Exception as e:
        logger.error(f"Failed to read JSON file {file_path}: {e}")
        return default


@timing
def write_json(
    data: Any,
    file_path: str | Path,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
    create_dirs: bool = True,
    **kwargs: Any,
) -> bool:
    """写入 JSON 文件。

    Args:
        data: 要写入的数据
        file_path: JSON 文件路径
        encoding: 文件编码
        indent: 缩进空格数
        ensure_ascii: 是否确保 ASCII 编码
        create_dirs: 是否自动创建父目录
        **kwargs: 传递给 json.dumps 的其他参数

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        file_path = Path(file_path)

        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        json_str = json.dumps(
            data,
            indent=indent,
            ensure_ascii=ensure_ascii,
            **kwargs,
        )

        with open(file_path, "w", encoding=encoding) as f:
            f.write(json_str)

        logger.debug(f"Wrote JSON to: {file_path}")
        return True
    except TypeError as e:
        logger.error(f"JSON serialization error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to write JSON file {file_path}: {e}")
        return False


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全解析 JSON 字符串。

    Args:
        json_str: JSON 字符串
        default: 解析失败时的默认值

    Returns:
        解析后的数据或默认值
    """
    try:
        return json.loads(json_str)
    except (TypeError, json.JSONDecodeError):
        return default


def safe_json_dumps(
    obj: Any,
    default: Callable[[Any], Any] | None = None,
    indent: int | None = 2,
    fallback: str | None = None,
    ensure_ascii: bool = False,
    **kwargs: Any,
) -> str | None:
    """安全序列化 JSON。

    Args:
        obj: 要序列化的对象
        default: 传递给 json.dumps 的默认序列化函数
        indent: 缩进
        fallback: 序列化失败时返回的回退值
        ensure_ascii: 是否确保 ASCII
        **kwargs: 传递给 json.dumps 的其他参数

    Returns:
        str | None: 成功时返回 JSON 字符串
    """
    try:
        return json.dumps(
            obj,
            default=default,
            indent=indent,
            ensure_ascii=ensure_ascii,
            **kwargs,
        )
    except TypeError as e:
        logger.error(f"JSON serialization error: {e}")
        return fallback
    except Exception as e:
        logger.error(f"Failed to serialize JSON: {e}")
        return fallback


@timing
def merge_json_files(
    file_paths: list[str | Path],
    output_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """合并多个 JSON 文件。

    Args:
        file_paths: JSON 文件路径列表
        output_path: 输出文件路径(可选)

    Returns:
        dict | None: 成功时返回合并后的字典，失败返回 None
    """
    merged: dict[str, Any] = {}

    for path in file_paths:
        data = read_json(path)
        if data is None:
            logger.error(f"Failed to read {path}")
            return None

        if isinstance(data, dict):
            merged.update(data)
        else:
            logger.warning(f"Skipping non-dict JSON file: {path}")

    if output_path and not write_json(merged, output_path):
        logger.error(f"Failed to write merged JSON to {output_path}")
        return None

    return merged


def pretty_print_json(data: Any, indent: int = 2) -> None:
    """美化打印 JSON 数据。

    Args:
        data: 要打印的数据
        indent: 缩进空格数
    """
    try:
        print(json.dumps(data, indent=indent, ensure_ascii=False))
    except TypeError as e:
        logger.error(f"Failed to pretty print JSON: {e}")
        print(str(data))


def validate_json_schema(
    data: dict[str, Any],
    required_keys: list[str],
) -> bool:
    """验证 JSON 数据是否包含必需的键。

    Args:
        data: 要验证的数据
        required_keys: 必需的键列表

    Returns:
        bool: 验证通过返回 True
    """
    missing_keys = [key for key in required_keys if key not in data]

    if missing_keys:
        logger.error(f"Missing required keys: {missing_keys}")
        return False

    return True


def json_path_get(
    data: dict[str, Any] | list[Any],
    path: str,
    separator: str = ".",
) -> Any | None:
    """使用路径从 JSON 数据中获取值。

    Args:
        data: JSON 数据
        path: 路径字符串 (例如 "a.b.c" 或 "items.0.name")
        separator: 路径分隔符

    Returns:
        Any | None: 成功时返回获取的值，失败返回 None
    """
    keys = path.split(separator)
    current: Any = data

    try:
        for key in keys:
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    return None
            elif isinstance(current, list):
                index = int(key)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        return current
    except Exception:
        return None


# =============================================================================
# 异步 JSON 操作
# =============================================================================


async def async_read_json(
    file_path: str | Path,
    encoding: str = "utf-8",
) -> dict[str, Any] | list[Any] | None:
    """异步读取 JSON 文件。

    Args:
        file_path: JSON 文件路径
        encoding: 文件编码

    Returns:
        dict | list | None: 成功时包含解析后的 JSON 数据，失败返回 None
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        async with aiofiles.open(file_path, encoding=encoding) as f:
            content = await f.read()
            data = json.loads(content)
            logger.debug(f"Async read JSON from: {file_path}")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to read JSON file {file_path}: {e}")
        return None


async def async_write_json(
    data: Any,
    file_path: str | Path,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
    create_dirs: bool = True,
) -> bool:
    """异步写入 JSON 文件。

    Args:
        data: 要写入的数据
        file_path: JSON 文件路径
        encoding: 文件编码
        indent: 缩进空格数
        ensure_ascii: 是否确保 ASCII 编码
        create_dirs: 是否自动创建父目录

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        file_path = Path(file_path)

        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        json_str = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)

        async with aiofiles.open(file_path, "w", encoding=encoding) as f:
            await f.write(json_str)

        logger.debug(f"Async wrote JSON to: {file_path}")
        return True
    except TypeError as e:
        logger.error(f"JSON serialization error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to write JSON file {file_path}: {e}")
        return False


async def async_merge_json_files(
    file_paths: list[str | Path],
    output_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """异步合并多个 JSON 文件。

    Args:
        file_paths: JSON 文件路径列表
        output_path: 输出文件路径(可选)

    Returns:
        dict | None: 成功时返回合并后的字典，失败返回 None
    """
    merged: dict[str, Any] = {}

    for path in file_paths:
        data = await async_read_json(path)
        if data is None:
            logger.error(f"Failed to read {path}")
            return None

        if isinstance(data, dict):
            merged.update(data)
        else:
            logger.warning(f"Skipping non-dict JSON file: {path}")

    if output_path:
        write_ok = await async_write_json(merged, output_path)
        if not write_ok:
            logger.error(f"Failed to write merged JSON to {output_path}")
            return None

    return merged


async def async_load_json_batch(
    file_paths: list[str | Path],
    max_concurrency: int = 5,
) -> list[dict[str, Any] | list[Any] | None]:
    """并发异步加载多个 JSON 文件。

    Args:
        file_paths: JSON 文件路径列表
        max_concurrency: 最大并发数

    Returns:
        各文件加载结果列表 (成功返回数据，失败返回 None)
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def load_with_semaphore(
        path: str | Path,
    ) -> dict[str, Any] | list[Any] | None:
        async with semaphore:
            return await async_read_json(path)

    tasks = [load_with_semaphore(path) for path in file_paths]
    return await asyncio.gather(*tasks)


__all__ = [
    # 同步操作
    "read_json",
    "write_json",
    "safe_json_loads",
    "safe_json_dumps",
    "merge_json_files",
    "pretty_print_json",
    "validate_json_schema",
    "json_path_get",
    # 异步操作
    "async_read_json",
    "async_write_json",
    "async_merge_json_files",
    "async_load_json_batch",
]
