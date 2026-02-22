"""Source registry for managing data source plugins.

数据源注册表，管理所有数据源插件的注册与发现。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ideago.models.research import Platform

if TYPE_CHECKING:
    from ideago.contracts.protocols import DataSource


class SourceRegistry:
    """Registry for data source plugins.

    Each platform can only have one registered source.
    """

    def __init__(self) -> None:
        self._sources: dict[Platform, DataSource] = {}

    def register(self, source: DataSource) -> None:
        """Register a data source plugin.

        Raises:
            ValueError: If a source for this platform is already registered.
        """
        if source.platform in self._sources:
            raise ValueError(f"Source for {source.platform.value} already registered")
        self._sources[source.platform] = source

    def get(self, platform: Platform) -> DataSource | None:
        """Get a registered source by platform."""
        return self._sources.get(platform)

    def get_available(self) -> list[DataSource]:
        """Get all sources that have their credentials configured."""
        return [s for s in self._sources.values() if s.is_available()]

    def get_all(self) -> list[DataSource]:
        """Get all registered sources regardless of availability."""
        return list(self._sources.values())
