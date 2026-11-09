"""Guards that the issue chooser offers each template once.

``.github/ISSUE_TEMPLATE/`` carried a Markdown template and an issue form for
both "Bug Report" and "Feature Request". GitHub lists Markdown templates and
forms alike, so the chooser showed each twice, and the two copies named
different labels (#69). The Markdown copies were deleted and the forms kept.

Whether a form is well formed is not checked here: the ``check-issue-forms``
and ``check-issue-config`` pre-commit hooks validate these files against the
schemas check-jsonschema vendors for them. This module checks what a schema
cannot see. It also allows one spelling, ``<name>.yml`` directly inside the
directory: GitHub reads ``.yaml`` too, but a second spelling is a second file
the hooks and the chooser config would each have to be taught about. What it cannot
close: GitHub drops a template label the repository does not have without
saying so, and a unit test cannot ask GitHub which labels exist, so the
allowlist below has to be kept true by hand.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest
import yaml

_TEMPLATES = ".github/ISSUE_TEMPLATE"
_CHOOSER_CONFIG = "config.yml"
_THIS_REPOSITORY = "finos/aigf-mcp-server"
# Where GitHub looks for a security policy.
_SECURITY_POLICY_LOCATIONS = ("SECURITY.md", ".github/SECURITY.md", "docs/SECURITY.md")

# Labels a form may apply. Each existed in the repository when this was written
# (`gh label list`); add one here only after creating it there.
_LABELS_THE_REPOSITORY_HAS = {"bug", "enhancement", "question"}


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.rootpath))


def _tracked(root: Path, *pathspec: str) -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", *pathspec],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    return [path.decode("utf-8") for path in listed.split(b"\0") if path]


def _load_yaml(path: Path) -> dict[Any, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} is not a YAML mapping"
    return loaded


def _issue_forms(root: Path) -> dict[str, dict[Any, Any]]:
    """The tracked issue forms, keyed by file name.

    Refuses any other tracked file in the directory first, so a file this does
    not read as a form cannot sit there unexamined.
    """
    names = [path.removeprefix(f"{_TEMPLATES}/") for path in _tracked(root, _TEMPLATES)]
    unexpected = sorted(
        name for name in names if "/" in name or not name.endswith(".yml")
    )
    assert not unexpected, (
        f"{_TEMPLATES} may hold only <name>.yml issue forms and "
        f"{_CHOOSER_CONFIG}, but tracks {unexpected}. A Markdown template beside "
        "a form puts a second entry in the chooser (#69)."
    )
    forms = {
        name: _load_yaml(root / _TEMPLATES / name)
        for name in names
        if name != _CHOOSER_CONFIG
    }
    # Three forms when this guard was written: bug, feature request, question.
    assert len(forms) >= 3, (
        f"read only {sorted(forms)} from {_TEMPLATES}; if a form was really "
        "removed lower this floor, otherwise the listing has stopped reading them"
    )
    return forms


def test_each_template_appears_once_in_the_chooser(
    pytestconfig: pytest.Config,
) -> None:
    """The chooser lists a template by its ``name``, so no two forms may share one."""
    forms = _issue_forms(_repo_root(pytestconfig))
    by_name: dict[str, list[str]] = {}
    for file_name, form in forms.items():
        shown_as = " ".join(str(form.get("name", "")).split()).casefold()
        by_name.setdefault(shown_as, []).append(file_name)
    shared = {name: files for name, files in by_name.items() if len(files) > 1}
    assert not shared, f"forms share a chooser name: {shared}"


def test_every_form_label_exists_in_the_repository(
    pytestconfig: pytest.Config,
) -> None:
    """A label the repository lacks is dropped silently when the issue is filed."""
    unknown: dict[str, list[str]] = {}
    for file_name, form in _issue_forms(_repo_root(pytestconfig)).items():
        labels = form.get("labels") or []
        if isinstance(labels, str):
            labels = [label.strip() for label in labels.split(",")]
        missing = sorted(set(labels) - _LABELS_THE_REPOSITORY_HAS)
        if missing:
            unknown[file_name] = missing
    assert not unknown, (
        f"forms apply labels the repository does not have: {unknown}. Create "
        "the label first, then add it to _LABELS_THE_REPOSITORY_HAS."
    )


def test_no_contact_link_repeats_the_security_policy_row(
    pytestconfig: pytest.Config,
) -> None:
    """A contact link to the security policy is a second row for it in the chooser.

    With ``SECURITY.md`` tracked and no contact links, the rendered chooser showed
    a "Report a security vulnerability" row of GitHub's own; the contact link #69
    added to the same file made it two (#171). That is an observation of the page
    on 2026-10-05, not something GitHub documents, and nothing here can ask GitHub
    what it renders. This closes the one route seen: a link into this repository's
    policy file or its ``/security`` pages. A link to a copy of the policy kept
    somewhere else would still pass.
    """
    root = _repo_root(pytestconfig)
    policies = _tracked(root, *_SECURITY_POLICY_LOCATIONS)
    assert policies, (
        f"no security policy is tracked at any of {_SECURITY_POLICY_LOCATIONS}, "
        "so the chooser has nothing that tells a reporter how to report privately"
    )
    config_path = f"{_TEMPLATES}/{_CHOOSER_CONFIG}"
    if not _tracked(root, config_path):
        return
    links = _load_yaml(root / config_path).get("contact_links") or []
    repeated = [
        link.get("url")
        for link in links
        if _points_at_the_security_policy(str(link.get("url")))
    ]
    assert not repeated, (
        f"{_CHOOSER_CONFIG} links to {repeated}, which the chooser already "
        f"offers in its own row for {policies[0]} (#171)"
    )


def _points_at_the_security_policy(url: str) -> bool:
    spelled = unquote(url).casefold()
    repository = f"github.com/{_THIS_REPOSITORY}".casefold()
    return repository in spelled and (
        "security.md" in spelled or f"{repository}/security" in spelled
    )
