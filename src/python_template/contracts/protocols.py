"""Protocol 定义模块。

提供可复用的接口协议，用于类型提示和运行时类型检查。
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Serializable(Protocol):
    """可序列化接口。

    实现此协议的对象可以转换为字典格式。
    """

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            字典表示
        """
        ...


@runtime_checkable
class FileReader(Protocol):
    """同步文件读取器接口。"""

    def read(self, path: str) -> str:
        """读取文件内容。

        Args:
            path: 文件路径

        Returns:
            文件内容
        """
        ...


@runtime_checkable
class AsyncFileReader(Protocol):
    """异步文件读取器接口。"""

    async def read(self, path: str) -> str:
        """异步读取文件内容。

        Args:
            path: 文件路径

        Returns:
            文件内容
        """
        ...


@runtime_checkable
class FileWriter(Protocol):
    """同步文件写入器接口。"""

    def write(self, path: str, content: str) -> bool:
        """写入文件内容。

        Args:
            path: 文件路径
            content: 要写入的内容

        Returns:
            是否成功
        """
        ...


@runtime_checkable
class AsyncFileWriter(Protocol):
    """异步文件写入器接口。"""

    async def write(self, path: str, content: str) -> bool:
        """异步写入文件内容。

        Args:
            path: 文件路径
            content: 要写入的内容

        Returns:
            是否成功
        """
        ...


@runtime_checkable
class Closeable(Protocol):
    """可关闭资源接口。"""

    def close(self) -> None:
        """关闭资源。"""
        ...


@runtime_checkable
class AsyncCloseable(Protocol):
    """异步可关闭资源接口。"""

    async def close(self) -> None:
        """异步关闭资源。"""
        ...


@runtime_checkable
class Configurable(Protocol):
    """可配置接口。"""

    def configure(self, **kwargs: Any) -> None:
        """配置对象。

        Args:
            **kwargs: 配置参数
        """
        ...


__all__ = [
    "Serializable",
    "FileReader",
    "AsyncFileReader",
    "FileWriter",
    "AsyncFileWriter",
    "Closeable",
    "AsyncCloseable",
    "Configurable",
]
