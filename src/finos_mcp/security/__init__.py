# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Security utilities for the FINOS MCP Server.

Import the module you need; this package re-exports nothing. A re-export is
an import edge every submodule pays for: the one that stood here made
``config`` import the DoS middleware to reach a pure dataclass (#329).
"""
