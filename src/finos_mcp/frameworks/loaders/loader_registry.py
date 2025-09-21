"""Framework loader registry for dynamic loader registration.

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This module provides a registry for framework loaders following the
singleton pattern similar to ContentServiceManager.
"""

import asyncio
from typing import Optional

from ...logging import get_logger
from .base_loader import BaseFrameworkLoader

logger = get_logger("loader_registry")


class FrameworkLoaderRegistry:
    """Registry for framework loaders following ContentService patterns."""

    def __init__(self) -> None:
        """Initialize loader registry."""
        self._loaders: dict[str, BaseFrameworkLoader] = {}
        self._loader_classes: dict[str, type[BaseFrameworkLoader]] = {}
        self.logger = get_logger("loader_registry")

    def register_loader(
        self, framework_name: str, loader_class: type[BaseFrameworkLoader]
    ) -> None:
        """Register a framework loader class.

        Args:
            framework_name: Name of the framework (e.g., "iso42001")
            loader_class: Loader class to register
        """
        self._loader_classes[framework_name] = loader_class
        self.logger.info(f"Registered framework loader: {framework_name}")

    async def get_loader(self, framework_name: str) -> BaseFrameworkLoader | None:
        """Get framework loader instance with lazy initialization.

        Args:
            framework_name: Name of the framework

        Returns:
            Framework loader instance or None if not registered
        """
        # Return existing instance if available
        if framework_name in self._loaders:
            return self._loaders[framework_name]

        # Get loader class
        loader_class = self._loader_classes.get(framework_name)
        if not loader_class:
            self.logger.warning(f"No loader registered for framework: {framework_name}")
            return None

        try:
            # Create and cache loader instance
            loader = loader_class(framework_name)
            self._loaders[framework_name] = loader
            self.logger.info(f"Created loader instance for: {framework_name}")
            return loader

        except Exception as e:
            self.logger.error(
                f"Failed to create loader for {framework_name}: {e}",
                extra={
                    "framework": framework_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None

    def get_registered_frameworks(self) -> list[str]:
        """Get list of registered framework names.

        Returns:
            List of framework names
        """
        return list(self._loader_classes.keys())

    async def load_framework(self, framework_name: str, **kwargs) -> dict | None:
        """Load framework data using registered loader.

        Args:
            framework_name: Name of the framework
            **kwargs: Additional arguments passed to loader

        Returns:
            Framework data or None if failed
        """
        loader = await self.get_loader(framework_name)
        if not loader:
            return None

        try:
            return await loader.load_framework(**kwargs)
        except Exception as e:
            self.logger.error(
                f"Failed to load framework {framework_name}: {e}",
                extra={
                    "framework": framework_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None

    async def health_check_all(self) -> dict[str, dict]:
        """Perform health check on all registered loaders.

        Returns:
            Health check results for all loaders
        """
        results = {}

        # Get all loader instances
        loaders = []
        for framework_name in self._loader_classes:
            loader = await self.get_loader(framework_name)
            if loader:
                loaders.append((framework_name, loader))

        if not loaders:
            return {"healthy": True, "frameworks": {}}

        # Run health checks concurrently
        tasks = [loader.health_check() for _, loader in loaders]
        framework_names = [name for name, _ in loaders]

        try:
            health_results = await asyncio.gather(*tasks, return_exceptions=True)

            for framework_name, result in zip(
                framework_names, health_results, strict=False
            ):
                if isinstance(result, Exception):
                    results[framework_name] = {
                        "healthy": False,
                        "error": str(result),
                        "error_type": type(result).__name__,
                    }
                else:
                    results[framework_name] = result

        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "frameworks": results,
            }

        # Determine overall health
        overall_healthy = all(
            result.get("healthy", False) for result in results.values()
        )

        return {
            "healthy": overall_healthy,
            "total_frameworks": len(results),
            "healthy_frameworks": sum(
                1 for result in results.values() if result.get("healthy", False)
            ),
            "frameworks": results,
        }

    async def close_all(self) -> None:
        """Close all loaders and cleanup resources."""
        self.logger.info("Shutting down all framework loaders")

        # Close all loader instances
        for framework_name, loader in self._loaders.items():
            try:
                await loader.close()
            except Exception as e:
                self.logger.warning(
                    f"Error closing loader {framework_name}: {e}",
                    extra={
                        "framework": framework_name,
                        "error": str(e),
                    },
                )

        # Clear instances
        self._loaders.clear()
        self.logger.info("All framework loaders closed")


class FrameworkLoaderRegistryManager:
    """Singleton manager for the global loader registry."""

    _instance: Optional["FrameworkLoaderRegistryManager"] = None
    _registry: FrameworkLoaderRegistry | None = None

    def __new__(cls) -> "FrameworkLoaderRegistryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_registry(self) -> FrameworkLoaderRegistry:
        """Get global loader registry instance.

        Returns:
            Global FrameworkLoaderRegistry instance
        """
        if self._registry is None:
            self._registry = FrameworkLoaderRegistry()
            await self._register_default_loaders()
            logger.info("Global framework loader registry initialized")

        return self._registry

    async def _register_default_loaders(self) -> None:
        """Register default framework loaders."""
        # Import here to avoid circular imports
        try:
            from .iso42001 import ISO42001Loader

            self._registry.register_loader("iso42001", ISO42001Loader)
        except ImportError as e:
            logger.warning(f"Failed to register ISO42001 loader: {e}")

        try:
            from .ffiec import FFIECLoader

            self._registry.register_loader("ffiec", FFIECLoader)
        except ImportError as e:
            logger.warning(f"Failed to register FFIEC loader: {e}")

        try:
            from .gdpr import GDPRLoader

            self._registry.register_loader("gdpr", GDPRLoader)
        except ImportError as e:
            logger.warning(f"Failed to register GDPR loader: {e}")

        try:
            from .ccpa import CCPALoader

            self._registry.register_loader("ccpa", CCPALoader)
        except ImportError as e:
            logger.warning(f"Failed to register CCPA loader: {e}")

    async def close_registry(self) -> None:
        """Close and cleanup global registry."""
        if self._registry is not None:
            try:
                await self._registry.close_all()
            except Exception as e:
                logger.warning(f"Error during registry shutdown: {e}")
            finally:
                self._registry = None
                logger.info("Global framework loader registry closed")


# Global registry manager instance
_loader_registry_manager = FrameworkLoaderRegistryManager()


async def get_loader_registry() -> FrameworkLoaderRegistry:
    """Get global loader registry instance.

    Returns:
        Global FrameworkLoaderRegistry instance
    """
    return await _loader_registry_manager.get_registry()


async def close_loader_registry() -> None:
    """Close and cleanup global loader registry."""
    await _loader_registry_manager.close_registry()
