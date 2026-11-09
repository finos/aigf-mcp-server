#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Access to the shared :class:`ContentService`.

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
"""

from .content.discovery import (
    DiscoveryServiceManager,
)
from .content.service import (
    ContentService,
    get_content_service,
)

# Module-level DiscoveryServiceManager singleton.
# Tool handlers previously called DiscoveryServiceManager() on every
# invocation, constructing a new Python wrapper object each time even though
# the underlying singleton state is held in class variables.  A module-level
# instance avoids the unnecessary allocation on every call.
_discovery_manager = DiscoveryServiceManager()


async def get_service() -> ContentService:
    """Get the content service, from the one manager that holds it.

    A one-line re-export of ``get_content_service()``, and the thinness is the
    fix. This used to run through ``AsyncServiceManager``, which memoised what
    ``ContentServiceManager`` already held -- the *same instance*, by identity
    -- so the process kept two singletons for one object and only the second
    was reachable from ``cleanup_resources()`` (#114).

    What that cost is not the stale reference #114's title describes. The two
    singletons disagreed after a shutdown, and the second shutdown then closed
    nothing while reporting success. Measured on ``main`` at 7fb5c2f::

        shutdown 1 closed:                      [<the service>]
        still serving the same instance:        True
        ContentServiceManager singleton empty:  True
        shutdown 2 closed:                      NOTHING
        ...while the service is still live:     True

    The deleted manager's three assets each had a measurement against them, so
    none was carried over:

    - Its ``asyncio.Lock`` and double-checked locking guarded a critical
      section containing only ``await get_content_service()`` -- which cannot
      double-construct, because that function assigns
      ``self._content_service`` *before* its only ``await`` and so has no
      suspension point between the check and the act. Probed with 20
      concurrent callers against a fresh manager: 1 construction, with and
      without the lock. That lock was also what forced ``close_service()``'s
      empty return to leave ``_lock`` bound, a constraint documented in
      ``close_cache()`` and now removed with the thing that imposed it.
    - Its ``_loop`` and ``must_rebind()`` emitted a discard line for a discard
      that did not happen: ``_ensure_loop_context()`` nulled ``_service``, and
      ``get_service()`` then re-fetched the identical object from
      ``ContentServiceManager``, which nothing had cleared. Same object id
      before and after, measured. That is the "a false record is read and
      believed" failure ``loop_binding``'s own docstring exists to prevent,
      one layer up. The true records are the two managers', which name the
      resource each actually drops; the service has memoised neither
      component since #313.
    - ``close_service()`` had no caller anywhere in ``src/``.

    **What this does not do is give the surviving manager loop-awareness, and
    that is deliberate.** ``ContentServiceManager`` holds nothing loop-bound: a
    ``ContentService`` asks the cache and HTTP client managers on each use and
    keeps no copy (#313), so a ``must_rebind()`` here would report a discard
    costing nothing -- re-creating, in the survivor, the exact line this change
    removes.
    """
    return await get_content_service()
