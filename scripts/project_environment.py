#!/usr/bin/env python3
"""Does the resolved interpreter hold what ``pyproject.toml`` declares?

``scripts/project-python.sh`` resolves the interpreter every gate runs on. This
module answers the second half of the question: whether that interpreter's
installed distributions actually satisfy the declared dependency set. It runs
*inside* the resolved interpreter, because the only environment worth measuring
is the one about to run the tool.

The check exists because of what it would have caught. ``pyproject.toml`` moved
to ``fastmcp>=3.4.7,<4`` in PR #34. The project virtualenv on the maintainer's
machine stayed at ``fastmcp 2.14.5`` for the next six months, and pip-audit,
mypy and pylint all kept running against it without a word -- pip-audit
reporting advisories for a version the project forbids, mypy type-checking
against an API that is no longer the one it ships. Nothing compared the
interpreter to the declaration, so nothing noticed. See #89.

A missing distribution counts as a violation for the same reason: ``[dev]``
declares ``detect-secrets>=1.5.0`` precisely so the pre-commit hook and the
control test in ``tests/unit/test_secrets_scanning.py`` both have it, and that
same virtualenv did not have it installed at all.

Offline by construction -- ``importlib.metadata`` reads what is on disk and
``packaging`` parses what is declared. Nothing here reaches the network, so it
is cheap enough to run in front of every hook invocation.

This file is build tooling and deliberately lives outside ``src/`` so it never
ships in the wheel.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

__all__ = [
    "DeclarationError",
    "Violation",
    "declared_requirements",
    "find_violations",
    "format_report",
]

# The extras a gate needs. Runtime dependencies are always checked; these are
# the tables holding the tools the gates themselves run.
_DEFAULT_EXTRAS = ("dev", "security")


class DeclarationError(ValueError):
    """``pyproject.toml`` is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class Violation:
    """One declared requirement the resolved interpreter does not satisfy."""

    name: str
    declared: str
    installed: str | None
    origin: str

    def describe(self) -> str:
        """Render this violation the way the shell wrapper reports it."""
        where = f"[{self.origin}]"
        if self.installed is None:
            return f"  {self.name} is not installed (declared {self.declared}) {where}"
        return (
            f"  {self.name} {self.installed} does not satisfy {self.declared} {where}"
        )


def _requirement_type() -> type:
    """Return ``packaging.requirements.Requirement``, or explain its absence.

    ``packaging`` is not in the standard library. It is present in every
    environment this check is meant to run in -- pip, setuptools and pip-audit
    all depend on it -- so its absence means the interpreter is not a working
    project environment at all, which is worth saying plainly rather than
    letting an ImportError traceback stand in for the diagnosis.
    """
    try:
        from packaging.requirements import Requirement
    except ModuleNotFoundError as exc:  # pragma: no cover - environment defect
        raise DeclarationError(
            f"{sys.executable} cannot import `packaging`, so the declared "
            "dependency set cannot be parsed. That interpreter is not a "
            "working project environment; recreate it with "
            "`pip install -e '.[security,dev]'`."
        ) from exc
    return Requirement


def _read_pyproject(pyproject: Path) -> dict:
    try:
        raw = pyproject.read_bytes()
    except OSError as exc:
        raise DeclarationError(f"cannot read {pyproject}: {exc}") from exc
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise DeclarationError(f"{pyproject} is not valid TOML: {exc}") from exc


def declared_requirements(
    pyproject: Path,
    extras: Sequence[str] = _DEFAULT_EXTRAS,
) -> list[tuple[object, str]]:
    """Parse the runtime dependencies plus the named extras.

    Returns ``(Requirement, origin)`` pairs, where ``origin`` names the table
    the requirement came from so a violation can say where the declaration
    lives rather than leaving the reader to grep for it.

    A named extra that does not exist is an error, not an empty list: silently
    checking nothing is the failure mode this whole module exists to remove.
    """
    requirement = _requirement_type()
    document = _read_pyproject(pyproject)
    project = document.get("project")
    if not isinstance(project, dict):
        raise DeclarationError(f"{pyproject} declares no [project] table")

    tables: list[tuple[str, object]] = [
        ("project.dependencies", project.get("dependencies", []))
    ]
    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        optional = {}
    for extra in extras:
        if extra not in optional:
            raise DeclarationError(
                f"{pyproject} declares no [project.optional-dependencies.{extra}] "
                f"table, but it was requested. Known extras: "
                f"{sorted(optional) or 'none'}."
            )
        tables.append((f"project.optional-dependencies.{extra}", optional[extra]))

    parsed: list[tuple[object, str]] = []
    seen: set[tuple[str, str]] = set()
    for origin, entries in tables:
        if not isinstance(entries, list):
            raise DeclarationError(f"{origin} in {pyproject} is not a list")
        for entry in entries:
            if not isinstance(entry, str):
                raise DeclarationError(f"{origin} in {pyproject} holds a non-string")
            try:
                req = requirement(entry)
            except Exception as exc:  # packaging raises InvalidRequirement
                raise DeclarationError(
                    f"{origin} in {pyproject} holds an unparseable "
                    f"requirement {entry!r}: {exc}"
                ) from exc
            # The same distribution may be declared in several extras (pytest
            # is in both [dev] and [test]). Check each distinct specifier once.
            key = (req.name.lower(), str(req.specifier))
            if key in seen:
                continue
            seen.add(key)
            parsed.append((req, origin))

    if not parsed:
        raise DeclarationError(
            f"{pyproject} declares no dependencies at all. An empty set makes "
            "this check pass vacuously, which is not a check."
        )
    return parsed


def find_violations(requirements: Iterable[tuple[object, str]]) -> list[Violation]:
    """Return every declared requirement this interpreter does not satisfy."""
    violations: list[Violation] = []
    for req, origin in requirements:
        # An environment marker that does not apply to this interpreter means
        # the requirement is not declared *here* -- skipping it is correct, and
        # reporting it would be a false failure on some other Python version.
        marker = getattr(req, "marker", None)
        if marker is not None and not marker.evaluate():
            continue

        name = req.name
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            violations.append(Violation(name, str(req.specifier), None, origin))
            continue

        # An unconstrained requirement is satisfied by any installed version.
        if not req.specifier:
            continue
        # Pre-releases count: a venv holding 4.0.0rc1 against `<4` is exactly
        # the kind of mismatch this is here to surface, not to wave through.
        if not req.specifier.contains(installed, prereleases=True):
            violations.append(Violation(name, str(req.specifier), installed, origin))
    return violations


def format_report(violations: Sequence[Violation], pyproject: Path) -> str:
    """Render violations as the message the developer has to act on."""
    lines = [
        f"project-python: {sys.executable} does not satisfy the dependency set "
        f"declared in {pyproject}:",
        *(violation.describe() for violation in violations),
        "",
        "The gate you just ran would have measured that environment rather "
        "than the one this project declares.",
        "Recreate it:",
        "    rm -rf venv && python3.12 -m venv venv",
        "    venv/bin/pip install -e '.[security,dev,test]'",
        "",
        "Set ALLOW_INSECURE_INTERPRETER_MISMATCH=1 to downgrade this to a "
        "warning if you know why the mismatch is there.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Report declared-vs-installed drift for the running interpreter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyproject", required=True, type=Path)
    parser.add_argument(
        "--extras",
        default=",".join(_DEFAULT_EXTRAS),
        help="comma-separated extras to check alongside the runtime dependencies",
    )
    args = parser.parse_args(argv)

    extras = tuple(part.strip() for part in args.extras.split(",") if part.strip())
    try:
        requirements = declared_requirements(args.pyproject, extras)
    except DeclarationError as exc:
        print(f"project-python: {exc}", file=sys.stderr)
        return 2

    violations = find_violations(requirements)
    if violations:
        print(format_report(violations, args.pyproject), file=sys.stderr)
        return 1

    print(
        f"project-python: {sys.executable} satisfies "
        f"{len(requirements)} declared requirement(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
