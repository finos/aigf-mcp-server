"""The filename-to-identifier derivations, extracted from twelve inlined copies.

Issue #87 calls this the cheap, safe first step, and names one derivation. There
are three, which is why the duplication survived: they look alike and are not
the same. The document id strips a ``ri-``/``mi-`` prefix, the display name does
not and lowercases nothing, and the title fallback strips neither.

These tests **characterise** rather than specify. The extraction was required to
preserve today's behaviour character-for-character, so the quirks below are
asserted deliberately, not overlooked:

* both replaces are **unanchored** -- ``"ri-"`` is removed wherever it occurs,
  not only as a prefix. No filename in the 46-file corpus contains an inner
  ``ri-`` or ``mi-``, so nothing observable depends on it today. It is asserted
  here so that the day a filename does, the change is a failing test rather
  than a silently altered id.
* the display name keeps the prefix and the numeric separator, so
  ``ri-10_prompt-injection.md`` renders as ``Ri 10_Prompt Injection``. That is
  what callers see in every ``list_*`` response today.

Changing either is a user-visible change to the published surface and belongs in
its own issue, where the display-name contract is the subject rather than a side
effect of a refactor.
"""

from __future__ import annotations

import pytest

from finos_mcp.content.parse import (
    document_id_from_filename,
    document_name_from_filename,
    filename_stem,
)
from finos_mcp.content.static_catalog import STATIC_MITIGATION_FILES, STATIC_RISK_FILES

#: Modules that bind ``get_service`` in their own namespace. Since #87 split the
#: server, patching the aggregator rebinds a name no caller reads.
_GET_SERVICE_BINDERS = (
    "finos_mcp.documents.tools",
    "finos_mcp.documents.format",
    "finos_mcp.health_tools",
)


def _patch_get_service(monkeypatch, value, **kwargs) -> None:
    """Patch ``get_service`` in every module that binds it."""
    import importlib

    for dotted in _GET_SERVICE_BINDERS:
        monkeypatch.setattr(
            importlib.import_module(dotted), "get_service", value, **kwargs
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "prefix", "expected"),
    [
        ("ri-10_prompt-injection.md", "ri-", "10_prompt-injection"),
        ("mi-4_ai-firewall.md", "mi-", "4_ai-firewall"),
        # No prefix present: the strip is a no-op rather than an error.
        ("plain-document.md", "ri-", "plain-document"),
        # Unanchored, and asserted as such: an inner occurrence is removed too.
        ("ai-ri-nested.md", "ri-", "ai-nested"),
    ],
)
def test_document_id_strips_the_suffix_and_the_prefix(
    filename: str, prefix: str, expected: str
) -> None:
    assert document_id_from_filename(filename, prefix) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        # The prefix survives and the underscore does not become a space.
        ("ri-10_prompt-injection.md", "Ri 10_Prompt Injection"),
        ("mi-4_ai-firewall.md", "Mi 4_Ai Firewall"),
    ],
)
def test_document_name_is_title_cased_with_the_prefix_intact(
    filename: str, expected: str
) -> None:
    """This helper's contract, which #121 did not change -- only its audience.

    Rewritten rather than deleted, so the change is visible. It landed in #117
    to pin what ``list_*`` published, and the comment above these cases used to
    read "this is what every list_* response shows today". That is no longer
    true: a listing now publishes the title the document declares, and this
    value is what it falls back to when a document cannot be read or declares
    no usable title.

    So the assertions stand exactly as they were -- the derived name must keep
    its shape, or a degraded listing degrades into something unrecognisable --
    while the claim about the published surface moves to the test that actually
    covers it, ``test_listings_publish_the_frontmatter_title_as_the_name`` in
    tests/unit/test_document_titles.py.
    """
    assert document_name_from_filename(filename) == expected


@pytest.mark.unit
def test_filename_stem_strips_only_the_extension() -> None:
    """The title fallback: no prefix handling, no case change."""
    assert filename_stem("ri-10_prompt-injection.md") == "ri-10_prompt-injection"


@pytest.mark.unit
def test_every_shipped_filename_yields_a_usable_id() -> None:
    """Properties the id contract must hold across the whole shipped corpus.

    Deliberately not a comparison against the expression this helper replaced.
    That expression now lives only inside the helper, so asserting the two agree
    would compare the function to a copy of its own body -- it would pass by
    construction and could never disagree with the code. These are properties
    the ids must satisfy for the get_* tools to accept them, checked against
    every filename the server actually ships.
    """
    namespaces = {
        "risk": (STATIC_RISK_FILES, "ri-"),
        "mitigation": (STATIC_MITIGATION_FILES, "mi-"),
    }
    total = sum(len(files) for files, _ in namespaces.values())
    assert total >= 40, f"corpus looks empty: {total} filenames"

    for doc_type, (filenames, prefix) in namespaces.items():
        ids = [document_id_from_filename(name, prefix) for name in filenames]

        assert all(ids), f"a shipped {doc_type} filename derived an empty id"
        # Uniqueness is checked *within* a namespace, not across both. get_risk
        # scans risk filenames only and get_mitigation mitigation filenames
        # only, so a shared slug is not a collision -- each document is still
        # reachable through its own tool. Pooling them would fail the day
        # upstream adds mi-10_prompt-injection.md beside ri-10_prompt-injection
        # .md, and would report "unreachable" about two reachable documents.
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        assert not duplicates, (
            f"two shipped {doc_type} filenames derive the same id, so one "
            f"{doc_type} document is unreachable: {duplicates}"
        )
        assert not [i for i in ids if ".md" in i], (
            f"a {doc_type} id kept its file extension"
        )
        assert not [i for i in ids if i.startswith(("ri-", "mi-"))], (
            f"a {doc_type} id kept the prefix the get_* tools do not expect"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "discovery_works", [True, False], ids=["live-discovery", "static-fallback"]
)
@pytest.mark.parametrize(
    ("list_tool", "get_tool", "doc_type", "static_files"),
    [
        ("list_risks", "get_risk", "risk", STATIC_RISK_FILES),
        ("list_mitigations", "get_mitigation", "mitigation", STATIC_MITIGATION_FILES),
    ],
)
async def test_every_published_id_is_well_formed_and_resolves(
    list_tool: str,
    get_tool: str,
    doc_type: str,
    static_files: list[str],
    discovery_works: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every risk/mitigation call site the extraction touched, guarded offline.

    The extraction moved the risk from the *expression* -- identical at all
    twelve sites and hard to get wrong -- to two things that are now easy to get
    wrong, and this test covers both:

    * the ``prefix`` **argument** (six sites), the only thing separating a risk
      derivation from a mitigation one; and
    * the **choice of helper** (six sites), because
      ``document_name_from_filename`` and ``filename_stem`` share the signature
      ``(str) -> str`` and so are swappable by a one-identifier edit.

    Each site is reachable only under a particular combination of tool and
    discovery outcome, so the parametrization crosses both.

    **Two independent assertions are needed, because each is blind to what the
    other catches.**

    *The round trip alone is not enough.* ``list_*`` and ``get_*`` derive ids the
    same way, so a *uniform* fault is self-consistent: mutate every ``"mi-"`` to
    ``"ri-"`` and the published id still matches the one ``get_mitigation``
    computes. The round trip resolves happily while every id ships as
    ``mi-4_ai-firewall`` instead of ``4_ai-firewall``, contradicting every
    documented example. Only the published *form* reveals it.

    *The form alone is not enough either.* Mutate the prefix at the ``get_*``
    site only and every published id is still perfectly well-formed -- but no id
    matches any candidate filename, so **every** ``get_risk`` call returns "not
    found". Only the round trip reveals that.

    Measured: with only the form asserted on the fallback branch, single-site
    mutations at four of the six sites left all 666 offline tests green.
    """
    from finos_mcp.content.discovery import (
        DiscoveryResult,
        DiscoveryServiceManager,
        GitHubDiscoveryService,
        GitHubFileInfo,
    )
    from finos_mcp.documents import tools as doc_tools

    def _file_info(name: str) -> GitHubFileInfo:
        return GitHubFileInfo(filename=name)

    class _FakeDiscovery:
        async def discover_content(self) -> DiscoveryResult:
            # The offline branch is discovery's own static catalog: the tools
            # had a copy of it, taken on any exception, until #296.
            if not discovery_works:
                return GitHubDiscoveryService()._create_static_fallback()
            files = [_file_info(name) for name in static_files]
            return DiscoveryResult(
                mitigation_files=files if doc_type == "mitigation" else [],
                risk_files=files if doc_type == "risk" else [],
                framework_files=[],
                source="github_api",
            )

    async def _discovery(_self: object) -> _FakeDiscovery:
        return _FakeDiscovery()

    # Patched on the *class*, not on `server._discovery_manager`.
    # DiscoveryServiceManager.__new__ returns a process-wide singleton, so
    # setattr on the instance makes monkeypatch record the bound method and
    # write it back on teardown as a real instance attribute -- which then
    # permanently shadows any later class-level patch, silently disabling
    # another test's stub and sending it to the network while it still looks
    # green.
    monkeypatch.setattr(
        DiscoveryServiceManager, "get_discovery_service", _discovery, raising=True
    )

    fetched: list[str] = []

    class _FakeService:
        async def get_document(
            self, _doc_type: str, filename: str
        ) -> dict[str, object]:
            fetched.append(filename)
            return {"content": "stub body", "metadata": {}}

    async def _get_service() -> _FakeService:
        return _FakeService()

    _patch_get_service(monkeypatch, _get_service, raising=True)

    listing = await getattr(doc_tools, list_tool)()

    # Prove which branch ran. Without this the test could measure the live path
    # twice and report it as coverage of the offline one, or vice versa.
    expected_source = "github_api" if discovery_works else "static_fallback"
    assert listing.source == expected_source, (
        f"expected the {expected_source} branch, got {listing.source!r} -- the "
        "assertions below would be measuring the wrong call site"
    )
    assert listing.total_count == len(static_files)
    published = list(listing.documents)
    assert published, "the listing published no documents at all"

    # Assertion 1: the published form. A *property*, not a recomputation of the
    # derivation -- restating the expression here would compare the source to a
    # copy of itself and could never disagree with it.
    kept_prefix = [doc.id for doc in published if doc.id.startswith(("ri-", "mi-"))]
    assert not kept_prefix, (
        f"{list_tool} published ids that keep the filename prefix, which "
        f"{get_tool} does not accept and no documented example shows: "
        f"{kept_prefix}"
    )
    assert not [doc.id for doc in published if ".md" in doc.id], (
        f"{list_tool} published an id that kept its file extension"
    )

    # Assertion 2: every published id resolves through the matching get_* tool.
    # Checked for the whole catalog rather than documents[0], so a derivation
    # that happens to work for one filename cannot pass for all of them.
    for doc in published:
        # Assertion 3: the *name* is the display derivation, not one of its two
        # same-shaped siblings. The extraction left three helpers, and two of
        # them -- document_name_from_filename and filename_stem -- share the
        # signature (str) -> str, so they are substitutable by a one-identifier
        # edit at six call sites. Measured: swapping them at the four doc_name
        # sites leaves the whole offline suite green while every list_*
        # response ships name="ri-10_prompt-injection" instead of
        # "Ri 10_Prompt Injection". Nothing else reads this field -- the live
        # gate never touches documents[N]["name"] -- so this is the only guard.
        assert doc.name != filename_stem(doc.filename), (
            f"{list_tool} published name={doc.name!r}, which is the bare "
            "filename stem rather than the display name. filename_stem and "
            "document_name_from_filename have the same signature, so this is "
            "what calling the wrong one looks like"
        )
        assert doc.name[:1].isupper() and " " in doc.name, (
            f"{list_tool} published name={doc.name!r}, which is not the "
            "title-cased, space-separated form every list_* response has "
            "always shown"
        )

        fetched.clear()
        content = await getattr(doc_tools, get_tool)(doc.id)
        assert fetched == [doc.filename], (
            f"{get_tool}({doc.id!r}) did not resolve to {doc.filename!r} -- it "
            f"fetched {fetched!r}. The id {list_tool} published is not one "
            f"{get_tool} can find, so this document is unreachable"
        )
        # Assertion 4: the title fallback is the *other* helper -- the raw stem,
        # deliberately not title-cased. This is the second half of the
        # substitutable-helper gap.
        #
        # It does NOT exercise a "no frontmatter title" path, and an earlier
        # version of this comment wrongly claimed it did. The stub's metadata is
        # irrelevant here: get_risk reads `doc.get("title", ...)`, and
        # get_document never sets a top-level "title" key, so the fallback is
        # **unconditional** today. Measured: this assertion passes identically
        # with metadata={"title": "Prompt Injection"}. That is issue #118, and
        # this assertion does not pin it -- measured again with #118's fix
        # applied (reading doc["metadata"]["title"]), all 12 cases still pass,
        # because the stub supplies no frontmatter title to prefer.
        assert content.title == filename_stem(doc.filename), (
            f"{get_tool}({doc.id!r}) fell back to title={content.title!r}; with "
            f"no frontmatter title it must be the bare stem "
            f"{filename_stem(doc.filename)!r}"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "discovery_works", [True, False], ids=["live-discovery", "static-fallback"]
)
async def test_every_published_framework_id_resolves(
    discovery_works: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The framework list/get pair, which the extraction left inline.

    ``list_frameworks`` and ``get_framework`` still carry three inlined copies of
    ``.replace(".yml", "").replace(".yaml", "")`` (fastmcp_server.py:618, 640 and
    770). They are the same list/get pairing this file guards for risks and
    mitigations, and the same pair that carried the ``framework`` vs
    ``framework_id`` bug the surface contract exists to prevent recurring.

    Measured one site at a time against the whole offline suite:

    ==== ============================= ==============
    line branch                        result
    ==== ============================= ==============
    618  list_frameworks, live         caught
    640  list_frameworks, fallback     **survived**
    770  get_framework                 caught
    ==== ============================= ==============

    So two of the three were already covered incidentally by
    ``test_rate_limit_transparency.py``, and the static-fallback branch was
    covered by nothing -- the same hole, in the same shape, as the one the risk
    and mitigation tests above were written to close. The only framework round
    trip that existed is ``tests/test_id_mapping.py``, which is marked
    integration, needs the network, and skips when a body cannot be fetched.
    """
    from finos_mcp.content.discovery import (
        DiscoveryResult,
        DiscoveryServiceManager,
        GitHubDiscoveryService,
        GitHubFileInfo,
    )
    from finos_mcp.content.static_catalog import STATIC_FRAMEWORK_FILES
    from finos_mcp.documents import tools as doc_tools

    class _FakeDiscovery:
        async def discover_content(self) -> DiscoveryResult:
            if not discovery_works:
                return GitHubDiscoveryService()._create_static_fallback()
            return DiscoveryResult(
                mitigation_files=[],
                risk_files=[],
                framework_files=[
                    GitHubFileInfo(filename=name) for name in STATIC_FRAMEWORK_FILES
                ],
                source="github_api",
            )

    async def _discovery(_self: object) -> _FakeDiscovery:
        return _FakeDiscovery()

    monkeypatch.setattr(
        DiscoveryServiceManager, "get_discovery_service", _discovery, raising=True
    )

    fetched: list[str] = []

    class _FakeService:
        async def get_document(
            self, _doc_type: str, filename: str
        ) -> dict[str, object]:
            fetched.append(filename)
            return {"content": "stub: true\n", "metadata": {}}

    async def _get_service() -> _FakeService:
        return _FakeService()

    _patch_get_service(monkeypatch, _get_service, raising=True)

    listing = await doc_tools.list_frameworks()

    expected_source = "github_api" if discovery_works else "static_fallback"
    assert listing.source == expected_source, (
        f"expected the {expected_source} branch, got {listing.source!r} -- the "
        "assertions below would be measuring the wrong call site"
    )
    published = list(listing.frameworks)
    assert published, "the listing published no frameworks at all"

    shipped = set(STATIC_FRAMEWORK_FILES)
    for framework in published:
        # The published form, as a property rather than a recomputation: the id
        # must be a filename the server actually ships, minus its extension.
        # Stated this way it also catches a *uniform* fault, where every copy is
        # broken the same way and the round trip below still resolves happily.
        assert {f"{framework.id}.yml", f"{framework.id}.yaml"} & shipped, (
            f"list_frameworks published id={framework.id!r}, which is not any "
            "shipped filename minus its extension"
        )

        fetched.clear()
        await doc_tools.get_framework(framework.id)
        assert len(fetched) == 1 and fetched[0].startswith(framework.id), (
            f"get_framework({framework.id!r}) did not resolve to a document -- "
            f"it fetched {fetched!r}. The id list_frameworks published is not "
            "one get_framework can find, so this framework is unreachable"
        )
