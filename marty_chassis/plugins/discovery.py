"""
Plugin discovery mechanisms.

This module provides different strategies for discovering plugins,
including directory-based discovery and entry point discovery.
"""

import importlib
import importlib.util
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

try:
    from importlib.metadata import entry_points
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import entry_points

from ..logger import get_logger
from .exceptions import PluginDiscoveryError
from .interfaces import IPlugin


class PluginDiscoverer(ABC):
    """Abstract base class for plugin discovery strategies."""

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def discover(self) -> list[dict[str, Any]]:
        """
        Discover plugins.

        Returns:
            List of plugin discovery results with metadata
        """


class DirectoryPluginDiscoverer(PluginDiscoverer):
    """
    Discovers plugins from filesystem directories.

    Scans specified directories for Python files and modules
    that contain plugin classes.
    """

    def __init__(self, directories: list[str], pattern: str = "*.py"):
        """
        Initialize directory-based plugin discoverer.

        Args:
            directories: List of directories to scan
            pattern: File pattern to match (default: *.py)
        """
        super().__init__()
        self.directories = [Path(d) for d in directories]
        self.pattern = pattern

    async def discover(self) -> list[dict[str, Any]]:
        """
        Discover plugins from directories.

        Returns:
            List of discovered plugin information
        """
        discovered = []

        for directory in self.directories:
            if not directory.exists():
                self.logger.warning(f"Plugin directory does not exist: {directory}")
                continue

            if not directory.is_dir():
                self.logger.warning(f"Plugin path is not a directory: {directory}")
                continue

            self.logger.debug(f"Scanning directory for plugins: {directory}")
            directory_plugins = await self._scan_directory(directory)
            discovered.extend(directory_plugins)

        self.logger.info(f"Discovered {len(discovered)} plugins from directories")
        return discovered

    async def _scan_directory(self, directory: Path) -> list[dict[str, Any]]:
        """
        Scan a single directory for plugins.

        Args:
            directory: Directory to scan

        Returns:
            List of discovered plugin information
        """
        discovered = []

        try:
            # Scan for Python files
            for plugin_file in directory.glob(self.pattern):
                if plugin_file.name.startswith("__"):
                    continue  # Skip __init__.py and __pycache__

                try:
                    plugin_info = await self._analyze_plugin_file(plugin_file)
                    if plugin_info:
                        discovered.append(plugin_info)
                except Exception as e:
                    self.logger.warning(
                        f"Error analyzing plugin file {plugin_file}: {e}"
                    )

            # Scan for package directories
            for plugin_dir in directory.iterdir():
                if (
                    plugin_dir.is_dir()
                    and not plugin_dir.name.startswith("__")
                    and (plugin_dir / "__init__.py").exists()
                ):
                    try:
                        plugin_info = await self._analyze_plugin_package(plugin_dir)
                        if plugin_info:
                            discovered.append(plugin_info)
                    except Exception as e:
                        self.logger.warning(
                            f"Error analyzing plugin package {plugin_dir}: {e}"
                        )

        except Exception as e:
            raise PluginDiscoveryError(
                f"Error scanning directory {directory}", str(directory)
            ) from e

        return discovered

    async def _analyze_plugin_file(self, plugin_file: Path) -> dict[str, Any] | None:
        """
        Analyze a Python file for plugin classes.

        Args:
            plugin_file: Path to Python file

        Returns:
            Plugin information if found, None otherwise
        """
        module_name = plugin_file.stem

        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin classes
            plugin_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, IPlugin)
                    and attr != IPlugin
                    and hasattr(attr, "_plugin_metadata")
                ):
                    plugin_classes.append(attr)

            if plugin_classes:
                # Take the first plugin class found
                plugin_class = plugin_classes[0]
                if len(plugin_classes) > 1:
                    self.logger.warning(
                        f"Multiple plugin classes found in {plugin_file}, using {plugin_class.__name__}"
                    )

                return {
                    "type": "file",
                    "path": str(plugin_file),
                    "module_name": module_name,
                    "class_name": plugin_class.__name__,
                    "metadata": plugin_class._plugin_metadata,
                    "module": module,
                }

        except Exception as e:
            self.logger.debug(f"Error loading plugin file {plugin_file}: {e}")

        return None

    async def _analyze_plugin_package(self, plugin_dir: Path) -> dict[str, Any] | None:
        """
        Analyze a Python package for plugin classes.

        Args:
            plugin_dir: Path to plugin package directory

        Returns:
            Plugin information if found, None otherwise
        """
        package_name = plugin_dir.name

        try:
            # Add parent directory to sys.path temporarily
            parent_dir = str(plugin_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                path_added = True
            else:
                path_added = False

            try:
                # Import the package
                module = importlib.import_module(package_name)

                # Find plugin classes in the package
                plugin_classes = []
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, IPlugin)
                        and attr != IPlugin
                        and hasattr(attr, "_plugin_metadata")
                    ):
                        plugin_classes.append(attr)

                if plugin_classes:
                    # Take the first plugin class found
                    plugin_class = plugin_classes[0]
                    if len(plugin_classes) > 1:
                        self.logger.warning(
                            f"Multiple plugin classes found in {plugin_dir}, using {plugin_class.__name__}"
                        )

                    return {
                        "type": "package",
                        "path": str(plugin_dir),
                        "module_name": package_name,
                        "class_name": plugin_class.__name__,
                        "metadata": plugin_class._plugin_metadata,
                        "module": module,
                    }

            finally:
                # Remove from sys.path if we added it
                if path_added and parent_dir in sys.path:
                    sys.path.remove(parent_dir)

        except Exception as e:
            self.logger.debug(f"Error loading plugin package {plugin_dir}: {e}")

        return None


class EntryPointDiscoverer(PluginDiscoverer):
    """
    Discovers plugins using Python entry points.

    Uses the setuptools entry_points mechanism to discover
    plugins that have been installed as packages.
    """

    def __init__(self, group: str = "marty.plugins"):
        """
        Initialize entry point-based plugin discoverer.

        Args:
            group: Entry point group to search
        """
        super().__init__()
        self.group = group

    async def discover(self) -> list[dict[str, Any]]:
        """
        Discover plugins from entry points.

        Returns:
            List of discovered plugin information
        """
        discovered = []

        try:
            # Get entry points for our group
            eps = entry_points()
            if hasattr(eps, "select"):
                # New style (Python 3.10+)
                plugin_entries = eps.select(group=self.group)
            else:
                # Old style (Python 3.8-3.9)
                plugin_entries = eps.get(self.group, []) if hasattr(eps, "get") else []

            for entry_point in plugin_entries:
                try:
                    plugin_info = await self._analyze_entry_point(entry_point)
                    if plugin_info:
                        discovered.append(plugin_info)
                except Exception as e:
                    self.logger.warning(
                        f"Error analyzing entry point {entry_point.name}: {e}"
                    )

        except Exception as e:
            raise PluginDiscoveryError(
                f"Error discovering entry points for group {self.group}"
            ) from e

        self.logger.info(f"Discovered {len(discovered)} plugins from entry points")
        return discovered

    async def _analyze_entry_point(self, entry_point) -> dict[str, Any] | None:
        """
        Analyze an entry point for plugin information.

        Args:
            entry_point: Entry point to analyze

        Returns:
            Plugin information if valid, None otherwise
        """
        try:
            # Load the entry point
            plugin_class = entry_point.load()

            # Verify it's a plugin class
            if (
                isinstance(plugin_class, type)
                and issubclass(plugin_class, IPlugin)
                and hasattr(plugin_class, "_plugin_metadata")
            ):
                return {
                    "type": "entry_point",
                    "name": entry_point.name,
                    "module_name": entry_point.module,
                    "class_name": plugin_class.__name__,
                    "metadata": getattr(plugin_class, "_plugin_metadata", None),
                    "entry_point": entry_point,
                    "plugin_class": plugin_class,
                }

        except Exception as e:
            self.logger.debug(f"Error loading entry point {entry_point.name}: {e}")

        return None


class CompositePluginDiscoverer(PluginDiscoverer):
    """
    Composite plugin discoverer that combines multiple discovery strategies.

    Allows using multiple discovery mechanisms simultaneously
    and merges the results.
    """

    def __init__(self, discoverers: list[PluginDiscoverer]):
        """
        Initialize composite plugin discoverer.

        Args:
            discoverers: List of plugin discoverers to use
        """
        super().__init__()
        self.discoverers = discoverers

    async def discover(self) -> list[dict[str, Any]]:
        """
        Discover plugins using all configured discoverers.

        Returns:
            Combined list of discovered plugin information
        """
        all_discovered = []

        for discoverer in self.discoverers:
            try:
                discovered = await discoverer.discover()
                all_discovered.extend(discovered)
            except Exception as e:
                self.logger.error(
                    f"Error in discoverer {discoverer.__class__.__name__}: {e}"
                )

        # Remove duplicates based on plugin name
        unique_plugins = {}
        for plugin_info in all_discovered:
            plugin_name = plugin_info["metadata"].name
            if plugin_name not in unique_plugins:
                unique_plugins[plugin_name] = plugin_info
            else:
                self.logger.warning(
                    f"Duplicate plugin found: {plugin_name}, keeping first occurrence"
                )

        result = list(unique_plugins.values())
        self.logger.info(
            f"Discovered {len(result)} unique plugins using composite discoverer"
        )
        return result
