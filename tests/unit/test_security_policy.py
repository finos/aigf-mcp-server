"""The repository's vulnerability-disclosure policy is a contract, asserted here.

Issue #79 filed the absence: this project ships a network-facing MCP server with
SSRF protection on JWKS fetching (#35), DoS and rate-limiting middleware (#33)
and prompt-injection boundaries (#22), behind a bandit gate set to zero high and
zero medium findings -- and had nowhere for a reporter to send a finding.

**Why the assertions read content rather than presence.** A ``SECURITY.md``
containing the word TODO satisfies ``path.is_file()``. Every route this policy
claims is asserted by the text that makes it work, because the failure this file
exists to catch is a policy that *looks* published while routing a reporter
nowhere.

**What this file does not catch, stated so it is not mistaken for more.** It
cannot verify that the mailbox is monitored, that a report sent there is
answered, or that the disclosure timeline is honoured. Those are commitments,
not properties of the tree. It asserts only that the document names a route
which exists, and does not name one which does not.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.helpers import load_module


def _repo_root(pytestconfig: pytest.Config) -> Path:
    """Return the repository root as pytest resolved it."""
    return Path(pytestconfig.rootpath)


def _policy_path(pytestconfig: pytest.Config) -> Path:
    """Return the path GitHub reads the disclosure policy from.

    GitHub surfaces the policy from the repository root, ``docs/`` or
    ``.github/``. The root is the location this project publishes at, so it is
    the only one asserted -- a policy that moved to ``.github/`` would still be
    surfaced by GitHub but would no longer be where this repository says it is.
    """
    return _repo_root(pytestconfig) / "SECURITY.md"


def _paragraphs(pytestconfig: pytest.Config) -> list[str]:
    """Return the policy split into markdown paragraphs, each newline-free.

    Markdown prose is soft-wrapped, so a proximity assertion bounded to a line
    rejects a correct document purely for where its clause happened to break.
    The paragraph is the syntactic block that carries one statement, so it is
    the unit these assertions are bounded to.
    """
    text = _policy_path(pytestconfig).read_text(encoding="utf-8")
    return [
        " ".join(block.split()) for block in re.split(r"\n\s*\n", text) if block.strip()
    ]


def test_security_policy_exists_at_repo_root(pytestconfig: pytest.Config) -> None:
    """GitHub routes reports from the file at the repository root."""
    path = _policy_path(pytestconfig)
    assert path.is_file(), (
        f"{path.name} must exist at the repository root: it is the file GitHub "
        "surfaces in the Security tab and in the new-issue flow, and so the "
        "only one that actually routes a report."
    )


#: The mailbox a report actually reaches. It is the ``authors`` contact in
#: ``pyproject.toml``, and is asserted as a literal rather than read from there:
#: a test that derives its expectation the way the document would cannot
#: disagree with the document.
MAINTAINER_CONTACT = "security@finos.org"


def test_policy_names_a_working_contact_route(pytestconfig: pytest.Config) -> None:
    """A policy without a reachable address routes nothing.

    GitHub private vulnerability reporting -- the route the FINOS blueprint
    prefers -- is not enabled on this repository, and does not exist on a
    private one. Email is therefore the primary route, and it has to be present
    in the text.
    """
    policy = _policy_path(pytestconfig).read_text(encoding="utf-8")
    assert MAINTAINER_CONTACT in policy, (
        f"the policy must name {MAINTAINER_CONTACT} as the reporting address; "
        "while private vulnerability reporting is not available, that mailbox "
        "is the only route a reporter has."
    )


def test_policy_forbids_public_issue_disclosure(pytestconfig: pytest.Config) -> None:
    """Naming a private route is not the same as closing the public one.

    A reporter's default action on a GitHub repository is to open an issue, and
    an issue about an unpatched vulnerability discloses it to everyone the
    moment it is filed. The instruction not to has to be explicit; #79 named it
    as the first requirement for that reason.
    """
    # Bounded to a single paragraph. Three substrings matched anywhere in the
    # file would be satisfied by a document that says "do not" about something
    # else, mentions "public" in a licence note and "issue" in a changelog link.
    # The bound is the paragraph rather than the line because markdown prose is
    # soft-wrapped: the first draft of this assertion used ``[^\n]*`` and failed
    # against a correct document whose sentence happened to wrap mid-clause.
    prohibition = re.compile(
        r"do\s+not\b.*?\bpublic\b.*?\bissue", re.IGNORECASE | re.DOTALL
    )
    assert any(
        prohibition.search(paragraph) for paragraph in _paragraphs(pytestconfig)
    ), (
        "the policy must tell reporters explicitly not to open a public issue, "
        "in one sentence rather than as words scattered through the document; "
        "offering a private route without forbidding the public one leaves the "
        "reporter's default action unchanged."
    )


def _route_module(pytestconfig: pytest.Config) -> ModuleType:
    """Import ``scripts/security_policy_route.py`` by path.

    ``scripts/`` is build tooling outside ``src/``, so it cannot be imported by
    name. Go-live Gate 11 runs the same file, so the test and the gate cannot
    hold two definitions of the document's two forms.
    """
    path = _repo_root(pytestconfig) / "scripts" / "security_policy_route.py"
    return load_module(path, "security_policy_route")


#: The bullet a public repository's policy carries in place of the "not
#: currently available" one. Used to build the public form of the real document.
_PUBLIC_ROUTE = (
    "- **GitHub private vulnerability reporting (preferred):** use the\n"
    "  [Report a vulnerability](https://github.com/finos/aigf-mcp-server/security/advisories/new)\n"
    "  form under the **Security** tab.\n"
)


def _with_reporting_bullet(pytestconfig: pytest.Config, replacement: str) -> str:
    """Return the real policy with its private-reporting bullet replaced."""
    text = _policy_path(pytestconfig).read_text(encoding="utf-8")
    bullet = re.compile(
        r"^- \*\*GitHub private vulnerability reporting.*?(?=^\S|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    assert len(bullet.findall(text)) == 1, (
        "the policy must carry exactly one 'GitHub private vulnerability "
        "reporting' bullet for these tests to rewrite"
    )
    return bullet.sub(lambda _: replacement + "\n", text)


def test_policy_is_in_exactly_one_reporting_form(pytestconfig: pytest.Config) -> None:
    """The document says the route is unavailable, or links it, and never both.

    GitHub's private vulnerability reporting -- the "Report a vulnerability"
    button under the Security tab -- exists only on a public repository with
    reporting enabled. Where it does not, the document must say the route is
    not available; where it does, the document must link the form. A unit test
    cannot know which, so it asserts that the document is in exactly one of the
    two forms, and go-live Gate 11 compares that form with what GitHub reports
    (#138, #389).
    """
    route = _route_module(pytestconfig)
    policy = _policy_path(pytestconfig).read_text(encoding="utf-8")
    assert route.policy_state(policy) in route.STATES


def test_each_reporting_form_is_wrong_for_the_other_visibility(
    pytestconfig: pytest.Config,
) -> None:
    """The gate fails in both directions, and names the direction.

    Both forms are built from the real document, so the test follows it when
    its wording changes.
    """
    route = _route_module(pytestconfig)
    private_form = _with_reporting_bullet(
        pytestconfig,
        "- **GitHub private vulnerability reporting:** not currently available.\n",
    )
    public_form = _with_reporting_bullet(pytestconfig, _PUBLIC_ROUTE)

    assert route.policy_state(private_form) == "private"
    assert route.policy_state(public_form) == "public"
    assert route.check(private_form, "private") is None
    assert route.check(public_form, "public") is None

    went_public = route.check(private_form, "public")
    assert went_public is not None and "still says" in went_public, went_public
    linked_early = route.check(public_form, "private")
    assert linked_early is not None and "not enabled" in linked_early, linked_early


def test_a_policy_in_both_forms_or_neither_is_refused(
    pytestconfig: pytest.Config,
) -> None:
    """A document that satisfies both visibilities is correct for neither."""
    route = _route_module(pytestconfig)
    both = _with_reporting_bullet(
        pytestconfig,
        "- **GitHub private vulnerability reporting:** not currently available.\n"
        "  The form will be at /security/advisories/new.\n",
    )
    with pytest.raises(ValueError, match="one or the other"):
        route.policy_state(both)

    unqualified = _with_reporting_bullet(
        pytestconfig,
        "- **GitHub private vulnerability reporting:** use the Security tab.\n",
    )
    with pytest.raises(ValueError, match="without saying"):
        route.policy_state(unqualified)

    with pytest.raises(ValueError, match="does not mention"):
        route.policy_state(_with_reporting_bullet(pytestconfig, ""))

    for text in (both, unqualified):
        for visibility in route.STATES:
            assert route.check(text, visibility) is not None


def test_the_go_live_gate_checks_the_policy_against_the_visibility(
    pytestconfig: pytest.Config,
) -> None:
    """Something has to ask GitHub, and the go-live gate is what does.

    Comments are stripped, so prose that names the script is not a call.
    """
    root = _repo_root(pytestconfig)
    check = "scripts/check-security-policy.sh"
    comment = re.compile(r"(?m)^\s*#.*$")
    gate = comment.sub("", (root / "scripts/go-live-gate.sh").read_text("utf-8"))
    assert "./" + check in gate, f"scripts/go-live-gate.sh does not run {check}"
    body = comment.sub("", (root / check).read_text("utf-8"))
    assert "security_policy_route.py" in body, (
        f"{check} does not run scripts/security_policy_route.py, so the gate "
        "and this file would hold two definitions of the document's forms."
    )


#: A stand-in for ``gh``: answers the two API reads Gate 11 makes from
#: FAKE_PRIVATE and FAKE_ENABLED, and fails on anything else.
_FAKE_GH = """#!/usr/bin/env bash
case "$*" in
  "api repos/o/r --jq .private") echo "$FAKE_PRIVATE" ;;
  "api repos/o/r/private-vulnerability-reporting --jq .enabled") echo "$FAKE_ENABLED" ;;
  *) echo "unexpected gh call: $*" >&2; exit 9 ;;
esac
"""


@pytest.mark.parametrize(
    ("private", "enabled", "document", "exit_code"),
    [
        ("true", "", "private", 0),
        ("true", "", "public", 1),
        # Public with reporting off: the form does not exist, so the document
        # must say so (#389). Before #389 this case had no passing document.
        ("false", "false", "private", 0),
        ("false", "false", "public", 1),
        ("false", "true", "private", 1),
        ("false", "true", "public", 0),
    ],
)
def test_gate_11_expects_the_form_the_repository_offers(
    pytestconfig: pytest.Config,
    tmp_path: Path,
    private: str,
    enabled: str,
    document: str,
    exit_code: int,
) -> None:
    """Gate 11 compares the document with whether the form is available.

    Runs the real script against a fake ``gh``, so the visibility and the
    reporting setting are chosen here, not read from GitHub.
    """
    root = _repo_root(pytestconfig)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "check-security-policy.sh",
        "security_policy_route.py",
        "project-python.sh",
        "project_environment.py",
    ):
        shutil.copy2(root / "scripts" / name, scripts / name)
    shutil.copy2(root / "pyproject.toml", tmp_path / "pyproject.toml")
    forms = {
        "private": "- **GitHub private vulnerability reporting:** not currently available.\n",
        "public": _PUBLIC_ROUTE,
    }
    (tmp_path / "SECURITY.md").write_text(
        _with_reporting_bullet(pytestconfig, forms[document]), encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(_FAKE_GH, encoding="utf-8")
    fake_gh.chmod(0o755)
    env = {
        key: value for key, value in os.environ.items() if key != "GO_LIVE_VISIBILITY"
    }
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        PYTHON_BIN=sys.executable,
        FAKE_PRIVATE=private,
        FAKE_ENABLED=enabled,
    )

    result = subprocess.run(
        ["bash", str(scripts / "check-security-policy.sh"), "o/r"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )

    assert result.returncode == exit_code, (result.stdout, result.stderr)


#: The FINOS responsible-disclosure policy this project follows. Verified to
#: return HTTP 200 when this test was written; it is asserted as a literal so
#: the document cannot quietly drift to a different or broken link. The test
#: does not fetch it -- a unit test that reaches the network fails on a train.
FINOS_DISCLOSURE_POLICY_URL = "https://community.finos.org/docs/governance/software-projects/cve-responsible-disclosure"


def test_policy_links_the_finos_disclosure_policy(pytestconfig: pytest.Config) -> None:
    """The process this project follows is FINOS's, and is cited rather than restated.

    #79 asks for alignment with the foundation's disclosure process. Restating
    it here would create a second copy to drift; linking it means the timeline
    and CVE handling stay whatever FINOS currently publishes.
    """
    policy = _policy_path(pytestconfig).read_text(encoding="utf-8")
    assert FINOS_DISCLOSURE_POLICY_URL in policy, (
        "the policy must link the FINOS responsible-disclosure policy at "
        f"{FINOS_DISCLOSURE_POLICY_URL}; #79 asks for alignment with the "
        "foundation's process, and a link keeps this document from becoming a "
        "second copy of it that drifts."
    )


def test_policy_states_which_versions_are_supported(
    pytestconfig: pytest.Config,
) -> None:
    """A reporter needs to know whether the version they found it in is in scope.

    ``pyproject.toml`` declares ``Development Status :: 3 - Alpha`` and takes its
    version from ``setuptools_scm``, so there is no released, supported line to
    speak of -- ``main`` is the only thing this project maintains. Saying so is
    the honest answer, and it is one the document has to actually give.
    """
    policy = _policy_path(pytestconfig)
    headings = re.findall(
        r"^#{1,3}\s*(.+)$", policy.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert any(
        re.search(r"supported\s+versions", h, re.IGNORECASE) for h in headings
    ), (
        "the policy must carry a 'Supported Versions' section: it is the "
        "question a reporter asks first, and GitHub's own template leads with "
        f"it. Headings found: {headings}"
    )


def test_policy_commits_to_an_acknowledgement_timeline(
    pytestconfig: pytest.Config,
) -> None:
    """ "We will respond" with no interval is not a commitment a reporter can rely on.

    #79 asks for an expected acknowledgement and disclosure timeline. The test
    asserts a concrete number of days appears, because that is the part a vague
    policy leaves out.
    """
    paragraphs = _paragraphs(pytestconfig)
    acknowledgement = re.compile(r"\b\d+\s+(business\s+)?days?\b", re.IGNORECASE)
    assert any(acknowledgement.search(p) for p in paragraphs), (
        "the policy must state a concrete acknowledgement window in days; "
        "#79 asks for an expected timeline, and a policy that promises to "
        "respond without saying when commits to nothing a reporter can chase."
    )
