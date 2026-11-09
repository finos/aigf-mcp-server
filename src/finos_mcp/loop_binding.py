#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Rebinding a loop-bound singleton, with the discard on the record.

``HTTPClientManager`` holds a resource bound to the event loop that created
it. Called from another loop, it drops what it holds and rebuilds on the new
one, because the old object cannot be used from here. ``CacheManager`` held
one too until #302 and was the other caller.
``must_rebind()`` is the one test of that condition, and it writes the record
of the discard itself: the test and the report are one call, so a caller
cannot take the rebind branch silently. Three closers and two getters had each
done so in turn (#101, #109, #116) before this module existed.

Nothing is torn down here. Against a closed loop it cannot be done, against a
running one it would close a resource that loop may be serving with, and
against a stopped one the cancel is accepted and never runs. The abandoned
resource is dropped with its cost named, and its fate belongs to whoever tore
the creating loop down.

Since #181 the server has one loop, so the discard branch is latent there: it
fires only for a test suite or an embedding program that uses these singletons
from more than one loop (#196). The empty first access, with nothing to
discard, happens on every cold start and is deliberately silent.

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

from __future__ import annotations

import asyncio
import logging

__all__ = ["must_rebind"]


def _provenance(bound_loop: asyncio.AbstractEventLoop | None) -> str:
    """Why the rebind is happening, as observed rather than as assumed.

    The condition in ``must_rebind()`` fires on four materially different
    states and no single sentence is true of all of them, which is the mistake
    ``CacheManager._discard_reason()``, since removed, was written to correct:
    the line it replaced asserted the closed-loop case at every one of them.

    ``is_closed()`` alone does not separate the last two. A loop that has
    stopped but not yet been closed reports ``is_closed() == False`` exactly as
    a running one does. Measured::

        never run  -> is_closed: False  is_running: False
        running    -> is_closed: False  is_running: True
        stopped    -> is_closed: False  is_running: False
        closed     -> is_closed: True   is_running: False
    """
    if bound_loop is None:
        return (
            "the event loop that created it was never recorded, so whether "
            "anything bound to that loop can still be reached is unknown"
        )
    if bound_loop.is_closed():
        return (
            "it was created on an event loop that is now closed, so nothing "
            "bound to that loop can be reached from here"
        )
    if bound_loop.is_running():
        return (
            "it was created on a different event loop that is still running, "
            "so it may still be in use there and is not torn down from here"
        )
    return (
        "it was created on a different event loop that has stopped without "
        "being closed, so work scheduled from here would sit in that loop's "
        "queue unrun"
    )


def must_rebind(
    *,
    bound_loop: asyncio.AbstractEventLoop | None,
    current_loop: asyncio.AbstractEventLoop,
    resource: object | None,
    resource_name: str,
    cost: str,
    logger: logging.Logger,
) -> bool:
    """Whether ``resource`` must be dropped because the loop changed.

    Returns ``True`` when the caller should clear its resource, rebind its
    ``_loop`` to ``current_loop`` and rebuild any loop-bound primitives; the
    record of the discard has been written by then. The line is keyed on
    ``resource``, never on the branch: the branch is also taken on every first
    access, when ``bound_loop`` is ``None`` and there is nothing to discard,
    and a line there would announce a discard that did not happen. It is
    written once per loop change, at INFO, the level the closers' own discard
    lines use, so one transcript reads alike. ``cost`` is required so a new
    call site cannot register a resource without saying what dropping it
    leaves behind.

    Args:
        bound_loop: The loop the resource was created on, or ``None`` if the
            manager has never been bound.
        current_loop: The running loop, from ``asyncio.get_running_loop()``.
        resource: What the caller is holding, or ``None`` if it holds nothing.
        resource_name: How the resource is named in the log line, lower case
            and matching the closers' wording ("cache", "HTTP client").
        cost: One sentence naming the close that will not run and what that
            leaves behind. Ends up after the provenance in the same line.
        logger: The caller's own logger, so the record is attributed to the
            module that owns the resource rather than to this one.

    Returns:
        ``True`` if the caller must drop and rebuild, ``False`` if its existing
        binding is still valid for the running loop.

    """
    if (
        bound_loop is not None
        and not bound_loop.is_closed()
        and bound_loop is current_loop
    ):
        return False

    if resource is not None:
        logger.info(
            "Discarding %s without closing it: %s. %s",
            resource_name,
            _provenance(bound_loop),
            cost,
        )

    return True
