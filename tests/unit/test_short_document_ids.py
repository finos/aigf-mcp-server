"""The get tools accept the short ids the corpus uses to cross-reference (#337).

The documents refer to each other as ``ri-10``, ``mi-13`` and ``ct-15`` (the
mitigations' older prefix), and the filenames carry the same number, so a
client that has read one document knows the number of the next and nothing
else. ``get_risk("ri-10")`` was refused with "No risk has the id 'ri-10'", so
a model had to list every document and match the number itself. The number
now resolves to the one document that carries it; the published ids and the
refusal for a number no document has are unchanged.
"""

from __future__ import annotations

import pytest
from test_listing_descriptions import (  # type: ignore[import-not-found]
    _stub_catalog,
)

from finos_mcp.documents.tools import get_mitigation, get_risk
from finos_mcp.exceptions import UnknownDocumentError

_CATALOG: dict[str, dict[str, object] | None] = {
    "ri-10_prompt-injection.md": {
        "content": "## Summary\n\nText.\n",
        "metadata": {"title": "Prompt Injection"},
    },
    "ri-1_information-leaked-to-hosted-model.md": {
        "content": "## Summary\n\nText.\n",
        "metadata": {"title": "Information Leaked To Hosted Model"},
    },
    "mi-13_providing-citations.md": {
        "content": "## Purpose\n\nText.\n",
        "metadata": {"title": "Providing Citations"},
    },
}


@pytest.mark.unit
@pytest.mark.parametrize(
    "requested",
    [
        "10_prompt-injection",
        "ri-10",
        "RI-10",
        "10",
        "ri-10_prompt-injection",
        " ri-10 ",
    ],
)
async def test_every_form_of_a_risk_id_serves_the_same_document(
    monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    _stub_catalog(monkeypatch, _CATALOG)

    served = await get_risk(requested)

    assert served.title == "Prompt Injection"
    # The record names the document by its published id, so a client that
    # asked by number learns the id the listing uses.
    assert served.document_id == "10_prompt-injection"


@pytest.mark.unit
@pytest.mark.parametrize("requested", ["mi-13", "ct-13", "CT-13", "13"])
async def test_a_mitigation_is_found_by_either_prefix_or_the_number_alone(
    monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    _stub_catalog(monkeypatch, _CATALOG)

    served = await get_mitigation(requested)

    assert served.document_id == "13_providing-citations"


@pytest.mark.unit
async def test_a_number_matches_whole_so_one_is_not_ten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_catalog(monkeypatch, _CATALOG)

    served = await get_risk("ri-1")

    assert served.document_id == "1_information-leaked-to-hosted-model"


@pytest.mark.unit
@pytest.mark.parametrize("requested", ["ri-99", "99", "mi-10", "prompt-injection"])
async def test_a_form_no_document_carries_is_still_refused(
    monkeypatch: pytest.MonkeyPatch, requested: str
) -> None:
    """A mitigation prefix on a risk tool, or a number no risk has, is unknown."""
    _stub_catalog(monkeypatch, _CATALOG)

    with pytest.raises(UnknownDocumentError) as refused:
        await get_risk(requested)

    assert "list_risks" in str(refused.value)


@pytest.mark.unit
async def test_a_short_id_two_documents_share_is_refused_naming_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two files with one number: the short id names neither (#349).

    The first in listing order used to be served, and that order can change
    between listings. A full id still names one document.
    """
    revised = "ri-10_prompt-injection-v2.md"
    _stub_catalog(
        monkeypatch, {**_CATALOG, revised: _CATALOG["ri-10_prompt-injection.md"]}
    )

    with pytest.raises(UnknownDocumentError) as refused:
        await get_risk("ri-10")

    message = str(refused.value)
    assert "10_prompt-injection," in message
    assert "10_prompt-injection-v2" in message
    served = await get_risk("10_prompt-injection-v2")
    assert served.document_id == "10_prompt-injection-v2"
