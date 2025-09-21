"""Framework loaders for dynamic content loading.

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

This module provides dynamic framework content loading capabilities that extend
the existing ContentService patterns for additional governance frameworks.
"""

from .base_loader import BaseFrameworkLoader, FrameworkLoaderError
from .loader_registry import FrameworkLoaderRegistry, get_loader_registry

__all__ = [
    "BaseFrameworkLoader",
    "FrameworkLoaderError",
    "FrameworkLoaderRegistry",
    "get_loader_registry",
]
