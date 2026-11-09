"""``must_rebind()`` in isolation: the four provenance states and the two keys.

The cross-loop behaviour of the three managers that use this helper is covered
end to end in ``tests/integration/test_cross_loop_teardown.py``. What that file
cannot reach is the *provenance* wording, because a manager driven through a
real loop change only ever presents one of the four states -- the creating loop
closed. The other three were unexercised until this file existed, which
mutation-testing found: a helper that reported "now closed" at every state
passed the whole integration file.

The distinction is not decorative. ``is_closed()`` alone does not separate a
loop that has stopped from one that never ran or one still serving::

    never run  -> is_closed: False  is_running: False
    running    -> is_closed: False  is_running: True
    stopped    -> is_closed: False  is_running: False
    closed     -> is_closed: True   is_running: False

A line that says "which is now closed" about a loop that is still running
tells a reader the resource is unreachable when it is in fact still serving
requests -- the failure ``CacheManager._discard_reason()`` was written to fix in
the closers, reproduced one layer over.

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
from collections.abc import Iterator

import pytest

from finos_mcp.loop_binding import must_rebind

#: A logger of our own, so these tests read the records the helper emits
#: without depending on how the application's logger tree is configured.
LOGGER_NAME = "tests.loop_binding"

#: Stand-in for a resource. Any non-``None`` object will do; the helper never
#: looks at it beyond the ``is not None`` test.
SENTINEL = object()

COST = "Nothing.close() does not run."


@pytest.fixture
def logger() -> logging.Logger:
    """A propagating logger, so ``caplog``'s root handler sees the records.

    Unlike the application's loggers, whose parent sets ``propagate = False``
    -- the reason the integration tests must name the child in
    ``caplog.at_level()``.
    """
    log = logging.getLogger(LOGGER_NAME)
    log.propagate = True
    return log


def _call(
    bound_loop: asyncio.AbstractEventLoop | None,
    current_loop: asyncio.AbstractEventLoop,
    resource: object | None,
    logger: logging.Logger,
) -> bool:
    return must_rebind(
        bound_loop=bound_loop,
        current_loop=current_loop,
        resource=resource,
        resource_name="cache",
        cost=COST,
        logger=logger,
    )


@pytest.fixture
def spare_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """A loop that is neither running nor closed, and is closed afterwards.

    ``new_event_loop()`` alone would do, but running one iteration on it first
    makes it a loop that has genuinely *been* used and stopped, which is the
    state being distinguished rather than a never-started one.
    """
    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    try:
        yield loop
    finally:
        if not loop.is_closed():
            loop.close()


@pytest.mark.unit
async def test_the_same_loop_is_not_a_rebind_and_is_not_reported(
    logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """The overwhelmingly common call: nothing changed, so nothing is said."""
    running = asyncio.get_running_loop()
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        assert _call(running, running, SENTINEL, logger) is False
    assert caplog.records == [], [r.getMessage() for r in caplog.records]


@pytest.mark.unit
async def test_no_resource_means_no_record_however_the_loop_looks(
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
    spare_loop: asyncio.AbstractEventLoop,
) -> None:
    """The cold-start case, at all four provenances at once.

    ``bound_loop is None`` is the state of every manager on its first ever
    access, so this is the firing that actually happens in production. The
    other two are included because the key is the resource, not the loop:
    neither may produce a line either when there is nothing to drop.

    The fourth provenance -- a *different* loop that is still running -- is not
    reachable from here, because this test's own loop is the only running one
    and pairing it with itself is the same-loop case rather than a discard. It
    is covered in ``test_a_running_creating_loop_says_the_resource_may_still_be
    _in_use``, which drives a second loop to get at it.
    """
    running = asyncio.get_running_loop()
    closed = asyncio.new_event_loop()
    closed.close()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        for bound in (None, closed, spare_loop):
            assert _call(bound, running, None, logger) is True

    assert caplog.records == [], (
        "a discard record was emitted with no resource to discard; got "
        f"{[r.getMessage() for r in caplog.records]}"
    )


@pytest.mark.unit
async def test_an_unrecorded_loop_says_so_rather_than_guessing(
    logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """``_loop is None`` is not the same statement as "a different loop"."""
    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        assert _call(None, asyncio.get_running_loop(), SENTINEL, logger) is True

    message = _one_record(caplog).getMessage()
    assert "never recorded" in message, message
    assert "closed" not in message, (
        f"nothing is known about this loop, so the line must not assert it is "
        f"closed; got {message!r}"
    )


@pytest.mark.unit
async def test_a_closed_creating_loop_says_nothing_can_be_reached(
    logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """The only state the integration tests reach, pinned here as well."""
    closed = asyncio.new_event_loop()
    closed.close()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        assert _call(closed, asyncio.get_running_loop(), SENTINEL, logger) is True

    message = _one_record(caplog).getMessage()
    assert "now closed" in message, message
    assert "still running" not in message, message


@pytest.mark.unit
def test_a_running_creating_loop_says_the_resource_may_still_be_in_use(
    logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """The state where not closing is a *choice*, not an impossibility.

    Cancelling into a live loop is perfectly possible via
    ``call_soon_threadsafe``. We decline because that loop may still be serving
    through this very resource -- so the line must not claim unreachability,
    which would tell a reader the opposite of what is true.

    Synchronous, and the assertion runs *inside* the coroutine on purpose: the
    bound loop has to be observed while it is actually running, and by the time
    ``run_until_complete`` returns it is not.
    """
    captured: list[str] = []

    async def observe() -> None:
        running = asyncio.get_running_loop()
        assert running.is_running(), "precondition: the bound loop must be live"
        other = asyncio.new_event_loop()
        try:
            with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
                assert _call(running, other, SENTINEL, logger) is True
        finally:
            other.close()
        captured.extend(r.getMessage() for r in caplog.records)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(observe())
    finally:
        loop.close()

    assert len(captured) == 1, captured
    assert "still running" in captured[0], captured[0]
    assert "may still be in use there" in captured[0], captured[0]
    assert "now closed" not in captured[0], (
        f"this loop is alive; saying it is closed inverts what the reader "
        f"needs to know; got {captured[0]!r}"
    )


@pytest.mark.unit
async def test_a_stopped_but_unclosed_loop_is_its_own_answer(
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
    spare_loop: asyncio.AbstractEventLoop,
) -> None:
    """The state ``is_closed()`` cannot distinguish from a running one.

    A cancel scheduled here would be *accepted* and never run, which is the
    shape that looks like a successful teardown and is not. It reports as
    neither "closed" nor "still running", and this test exists because both of
    those would otherwise be plausible readings of the same ``is_closed() ==
    False``.
    """
    assert not spare_loop.is_closed() and not spare_loop.is_running(), (
        "precondition: the loop must be stopped but still open"
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        assert _call(spare_loop, asyncio.get_running_loop(), SENTINEL, logger) is True

    message = _one_record(caplog).getMessage()
    assert "stopped without being closed" in message, message
    assert "still running" not in message, message
    assert "now closed" not in message, message


@pytest.mark.unit
async def test_the_record_carries_the_caller_s_name_cost_and_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Three call sites share this helper, so the line must identify which.

    A shared helper that logged under its own module name would attribute every
    discard in the process to ``loop_binding``, which is the one module that
    does not own any of the resources.
    """
    closed = asyncio.new_event_loop()
    closed.close()
    other = logging.getLogger(f"{LOGGER_NAME}.http")
    other.propagate = True

    with caplog.at_level(logging.DEBUG, logger=other.name):
        must_rebind(
            bound_loop=closed,
            current_loop=asyncio.get_running_loop(),
            resource=SENTINEL,
            resource_name="HTTP client",
            cost="HTTPClient.close() does not run.",
            logger=other,
        )

    record = _one_record(caplog)
    assert record.name == other.name, (
        "the record must be attributed to the module that owns the resource, "
        f"not to loop_binding; got {record.name!r}"
    )
    assert record.levelno == logging.INFO
    message = record.getMessage()
    assert "Discarding HTTP client" in message, message
    assert "HTTPClient.close() does not run." in message, message


def _one_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    """The single record, or a failure naming what was actually emitted."""
    assert len(caplog.records) == 1, (
        f"expected exactly one record, got {[r.getMessage() for r in caplog.records]}"
    )
    return caplog.records[0]
