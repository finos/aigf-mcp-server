#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""FINOS AI Governance Framework MCP Server - the assembled server.

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This module used to hold the entire server: the models, every helper, all
eleven tools, three resources, three prompts, the auth construction and the DoS
plumbing -- 2,812 lines, 54% of the source tree (#87). It is now where those
pieces are assembled, and nothing else.

**Importing a domain module is what registers its tools.** Each decorates the
single ``mcp`` object built in :mod:`finos_mcp.app`, so the imports below are
not decorative: deleting one silently removes its tools from the published
surface. During this decomposition that failure happened for real -- an
extraction that dropped the ``@mcp.tool`` lines left every name importable and
every definition present, and registered nothing.
``tests/unit/test_published_surface.py`` pins every tool by name and
required parameter, and is what turns that silence into a failure.

**Why this module hands out ``mcp`` when :mod:`finos_mcp.app` defines it.**
``app.mcp`` is the same object, but reaching it there gets you the server
*before* the registrations: zero tools, no error, no log line. This module is
the only import that guarantees an assembled one, which is why it is the only
name re-exported here. ``tests/unit/test_server_assembly.py`` keeps that route
the only one there is.

The 43-name re-export that used to sit here was scaffolding for the move -- it
let a decomposition of that size land without also rewriting every importer.
The importers now name the module that owns each helper, so the scaffolding is
gone.
"""

# Imported for the registration side effect: each decorates ``mcp``.
from . import health_tools, http_health, prompts, resources  # noqa: F401
from .app import mcp
from .documents import tools as _document_tools  # noqa: F401
from .search import tools as _search_tools  # noqa: F401

__all__ = ["mcp"]
