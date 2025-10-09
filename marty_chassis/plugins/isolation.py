"""
Plugin isolation and sandboxing for secure plugin execution.

This module provides isolation mechanisms to ensure plugins
cannot interfere with each other or the core framework.
"""

import asyncio
import logging
import sys
import threading
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..logger import get_logger
from .exceptions import PluginError
from .interfaces import IPlugin, PluginState


class PluginIsolationError(PluginError):
    """Exception raised when plugin isolation is violated."""

    pass


class ResourceLimits:
    """Resource limits for plugin execution."""

    def __init__(
        self,
        max_memory_mb: Optional[int] = None,
        max_cpu_time_seconds: Optional[float] = None,
        max_threads: Optional[int] = None,
        max_file_handles: Optional[int] = None,
        allowed_modules: Optional[Set[str]] = None,
        blocked_modules: Optional[Set[str]] = None,
    ):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_time_seconds = max_cpu_time_seconds
        self.max_threads = max_threads
        self.max_file_handles = max_file_handles
        self.allowed_modules = allowed_modules or set()
        self.blocked_modules = blocked_modules or {
            "os",
            "subprocess",
            "multiprocessing",
            "ctypes",
            "importlib",
            "sys",
            "__builtin__",
            "builtins",
        }


class PluginSandbox:
    """
    Sandbox environment for plugin execution.

    Provides isolation mechanisms including:
    - Module import restrictions
    - Resource monitoring
    - Exception containment
    - Namespace isolation
    """

    def __init__(self, plugin_name: str, limits: Optional[ResourceLimits] = None):
        self.plugin_name = plugin_name
        self.limits = limits or ResourceLimits()
        self.logger = get_logger(f"Sandbox.{plugin_name}")

        # Resource tracking
        self._thread_count = 0
        self._file_handles: Set[Any] = set()
        self._original_modules: Dict[str, Any] = {}

        # Isolation state
        self._isolated = False
        self._lock = threading.RLock()

    @contextmanager
    def isolated_execution(self):
        """
        Context manager for isolated plugin execution.

        Usage:
            with sandbox.isolated_execution():
                await plugin.some_method()
        """
        try:
            self._enter_isolation()
            yield
        except Exception as e:
            self.logger.error(
                f"Error in isolated execution for {self.plugin_name}: {e}"
            )
            raise PluginIsolationError(f"Isolation error: {e}", self.plugin_name) from e
        finally:
            self._exit_isolation()

    def _enter_isolation(self):
        """Enter isolation mode."""
        with self._lock:
            if self._isolated:
                return

            self.logger.debug(f"Entering isolation for plugin: {self.plugin_name}")

            # Store original modules for restoration
            self._original_modules = dict(sys.modules)

            # Install import hook
            self._install_import_hook()

            self._isolated = True

    def _exit_isolation(self):
        """Exit isolation mode."""
        with self._lock:
            if not self._isolated:
                return

            self.logger.debug(f"Exiting isolation for plugin: {self.plugin_name}")

            # Remove import hook
            self._remove_import_hook()

            # Cleanup any new modules loaded during isolation
            self._cleanup_modules()

            self._isolated = False

    def _install_import_hook(self):
        """Install import hook to restrict module access."""
        # Store original import function
        if not hasattr(sys.modules["builtins"], "_marty_original_import"):
            sys.modules["builtins"]._marty_original_import = sys.modules[
                "builtins"
            ].__import__

        def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Restricted import function."""
            # Check if module is blocked
            if name in self.limits.blocked_modules:
                raise ImportError(
                    f"Module '{name}' is blocked for plugin '{self.plugin_name}'"
                )

            # Check if module is in allowed list (if specified)
            if self.limits.allowed_modules and name not in self.limits.allowed_modules:
                # Allow marty_chassis modules
                if not name.startswith("marty_chassis"):
                    raise ImportError(
                        f"Module '{name}' is not in allowed list for plugin '{self.plugin_name}'"
                    )

            # Use original import
            return sys.modules["builtins"]._marty_original_import(
                name, globals, locals, fromlist, level
            )

        # Replace import function
        sys.modules["builtins"].__import__ = restricted_import

    def _remove_import_hook(self):
        """Remove import hook and restore original import."""
        if hasattr(sys.modules["builtins"], "_marty_original_import"):
            sys.modules["builtins"].__import__ = sys.modules[
                "builtins"
            ]._marty_original_import

    def _cleanup_modules(self):
        """Remove modules loaded during isolation."""
        current_modules = set(sys.modules.keys())
        original_modules = set(self._original_modules.keys())
        new_modules = current_modules - original_modules

        for module_name in new_modules:
            # Don't remove marty_chassis modules or system modules
            if (
                not module_name.startswith("marty_chassis")
                and not module_name.startswith("_")
                and module_name not in {"typing", "collections", "functools"}
            ):
                try:
                    del sys.modules[module_name]
                    self.logger.debug(
                        f"Removed module loaded during isolation: {module_name}"
                    )
                except KeyError:
                    pass  # Module already removed

    def track_thread(self, thread_id: int) -> None:
        """Track a thread created by the plugin."""
        with self._lock:
            self._thread_count += 1
            if self.limits.max_threads and self._thread_count > self.limits.max_threads:
                raise PluginIsolationError(
                    f"Thread limit exceeded: {self._thread_count} > {self.limits.max_threads}",
                    self.plugin_name,
                )

    def untrack_thread(self, thread_id: int) -> None:
        """Untrack a thread when it finishes."""
        with self._lock:
            self._thread_count = max(0, self._thread_count - 1)

    def track_file_handle(self, handle: Any) -> None:
        """Track a file handle opened by the plugin."""
        with self._lock:
            self._file_handles.add(handle)
            if (
                self.limits.max_file_handles
                and len(self._file_handles) > self.limits.max_file_handles
            ):
                raise PluginIsolationError(
                    f"File handle limit exceeded: {len(self._file_handles)} > {self.limits.max_file_handles}",
                    self.plugin_name,
                )

    def untrack_file_handle(self, handle: Any) -> None:
        """Untrack a file handle when it's closed."""
        with self._lock:
            self._file_handles.discard(handle)

    def cleanup(self) -> None:
        """Clean up sandbox resources."""
        with self._lock:
            self.logger.debug(f"Cleaning up sandbox for plugin: {self.plugin_name}")

            # Close any remaining file handles
            for handle in list(self._file_handles):
                try:
                    if hasattr(handle, "close"):
                        handle.close()
                except Exception:
                    pass  # Best effort cleanup

            self._file_handles.clear()
            self._thread_count = 0

            if self._isolated:
                self._exit_isolation()


class PluginIsolationManager:
    """
    Manages isolation for all plugins.

    Provides centralized management of plugin sandboxes
    and enforces isolation policies.
    """

    def __init__(self, default_limits: Optional[ResourceLimits] = None):
        self.default_limits = default_limits or ResourceLimits()
        self.sandboxes: Dict[str, PluginSandbox] = {}
        self.logger = get_logger(self.__class__.__name__)

        # Global isolation settings
        self._global_isolation_enabled = True
        self._plugin_limits: Dict[str, ResourceLimits] = {}

    def create_sandbox(
        self, plugin_name: str, limits: Optional[ResourceLimits] = None
    ) -> PluginSandbox:
        """
        Create a sandbox for a plugin.

        Args:
            plugin_name: Name of the plugin
            limits: Optional custom resource limits

        Returns:
            Plugin sandbox instance
        """
        if plugin_name in self.sandboxes:
            self.logger.warning(f"Sandbox already exists for plugin: {plugin_name}")
            return self.sandboxes[plugin_name]

        # Use custom limits, plugin-specific limits, or default limits
        effective_limits = (
            limits or self._plugin_limits.get(plugin_name) or self.default_limits
        )

        sandbox = PluginSandbox(plugin_name, effective_limits)
        self.sandboxes[plugin_name] = sandbox

        self.logger.info(f"Created sandbox for plugin: {plugin_name}")
        return sandbox

    def get_sandbox(self, plugin_name: str) -> Optional[PluginSandbox]:
        """Get sandbox for a plugin."""
        return self.sandboxes.get(plugin_name)

    def remove_sandbox(self, plugin_name: str) -> None:
        """Remove sandbox for a plugin."""
        if plugin_name in self.sandboxes:
            sandbox = self.sandboxes[plugin_name]
            sandbox.cleanup()
            del self.sandboxes[plugin_name]
            self.logger.info(f"Removed sandbox for plugin: {plugin_name}")

    def set_plugin_limits(self, plugin_name: str, limits: ResourceLimits) -> None:
        """Set custom limits for a specific plugin."""
        self._plugin_limits[plugin_name] = limits
        self.logger.info(f"Set custom limits for plugin: {plugin_name}")

    async def execute_isolated(
        self, plugin: IPlugin, method_name: str, *args, **kwargs
    ) -> Any:
        """
        Execute a plugin method in isolation.

        Args:
            plugin: Plugin instance
            method_name: Name of method to execute
            *args: Method arguments
            **kwargs: Method keyword arguments

        Returns:
            Method result
        """
        if not self._global_isolation_enabled:
            # Execute without isolation
            method = getattr(plugin, method_name)
            return (
                await method(*args, **kwargs)
                if asyncio.iscoroutinefunction(method)
                else method(*args, **kwargs)
            )

        plugin_name = plugin.plugin_metadata.name
        sandbox = self.get_sandbox(plugin_name)

        if not sandbox:
            sandbox = self.create_sandbox(plugin_name)

        try:
            with sandbox.isolated_execution():
                method = getattr(plugin, method_name)

                if asyncio.iscoroutinefunction(method):
                    return await method(*args, **kwargs)
                else:
                    return method(*args, **kwargs)

        except Exception as e:
            self.logger.error(
                f"Error executing {method_name} for plugin {plugin_name}: {e}"
            )
            # Mark plugin as errored
            plugin.state = PluginState.ERROR
            raise PluginIsolationError(
                f"Isolated execution failed for {method_name}: {str(e)}", plugin_name
            ) from e

    def enable_global_isolation(self, enabled: bool = True) -> None:
        """Enable or disable global plugin isolation."""
        self._global_isolation_enabled = enabled
        self.logger.info(
            f"Global plugin isolation {'enabled' if enabled else 'disabled'}"
        )

    def get_isolation_status(self) -> Dict[str, Any]:
        """Get status of plugin isolation."""
        return {
            "global_isolation_enabled": self._global_isolation_enabled,
            "active_sandboxes": list(self.sandboxes.keys()),
            "sandbox_count": len(self.sandboxes),
            "plugin_limits": {
                name: {
                    "max_memory_mb": limits.max_memory_mb,
                    "max_cpu_time_seconds": limits.max_cpu_time_seconds,
                    "max_threads": limits.max_threads,
                    "max_file_handles": limits.max_file_handles,
                    "blocked_modules": list(limits.blocked_modules),
                }
                for name, limits in self._plugin_limits.items()
            },
        }

    async def cleanup_all_sandboxes(self) -> None:
        """Clean up all sandboxes."""
        self.logger.info("Cleaning up all plugin sandboxes")

        for plugin_name in list(self.sandboxes.keys()):
            self.remove_sandbox(plugin_name)

        self.logger.info("All plugin sandboxes cleaned up")


# Global isolation manager instance
_isolation_manager: Optional[PluginIsolationManager] = None


def get_isolation_manager() -> PluginIsolationManager:
    """Get or create the global isolation manager."""
    global _isolation_manager
    if _isolation_manager is None:
        _isolation_manager = PluginIsolationManager()
    return _isolation_manager


def reset_isolation_manager() -> None:
    """Reset the global isolation manager."""
    global _isolation_manager
    if _isolation_manager:
        asyncio.create_task(_isolation_manager.cleanup_all_sandboxes())
    _isolation_manager = None
