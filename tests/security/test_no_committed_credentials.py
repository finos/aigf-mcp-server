"""Guard against a credential-shaped literal reaching a tracked file.

The defect this covers: `scripts/run-local-with-token.sh` carried a real GitHub
PAT in cleartext and was kept out of the index by `.git/info/exclude` alone --
a per-clone file that is never committed, does not exist for a teammate, and is
absent from a CI checkout. One re-clone and `git add -A` would have staged it.

`.pre-commit-config.yaml` already declares a detect-secrets hook, but hooks are
installed per clone too; `.git/hooks/` was empty when this was written, so that
control was running for nobody. This test runs wherever pytest runs.

The check is deliberately *shape*-based rather than path-based. A guard that
looked for `scripts/run-local-with-token.sh` would start passing the moment
that file became clean, and would then never fail again.

`# pragma: allowlist secret` is honoured only under `tests/` and in
`.env.example`. Everywhere else a trailing comment cannot silence a finding --
that is precisely the route a real leaked credential would take.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The same prefixes the settings validator accepts (src/finos_mcp/config.py),
# so the guard and the validator cannot drift apart.
TOKEN_PATTERN = re.compile(
    r"(?:ghp_|gho_|ghu_|ghs_|ghr_|ghv_|github_pat_)[A-Za-z0-9_]{20,}"
)

ALLOWLIST_PRAGMA = "pragma: allowlist secret"

# Where a pragma is allowed to silence a finding.
PRAGMA_HONOURED_PREFIXES = ("tests/",)
PRAGMA_HONOURED_FILES = (".env.example",)

# Floors that prove the sweep actually looked at something. Without them, a
# broken `git ls-files` or a read that silently yields nothing would leave the
# violation list empty and the guard would pass while measuring nothing --
# indistinguishable from a clean tree.
#
# Deliberately loose. An exact placeholder count would fail the build whenever
# someone legitimately deleted one, which is a maintenance tax with no security
# value; one match is enough to show the matching path fires on real content.
MIN_TRACKED_FILES = 50
MIN_PLACEHOLDER_LINES = 1


def pragma_is_honoured(path: str) -> bool:
    """Whether an allowlist pragma may silence a finding in this file."""
    return path in PRAGMA_HONOURED_FILES or path.startswith(PRAGMA_HONOURED_PREFIXES)


def find_token_lines(text: str) -> list[int]:
    """Return the 1-indexed lines holding a credential-shaped literal."""
    return [
        lineno
        for lineno, line in enumerate(text.splitlines(), start=1)
        if TOKEN_PATTERN.search(line)
    ]


def scan_text(path: str, text: str) -> list[str]:
    """Return "path:line" for each credential-shaped literal not legitimately allowed."""
    violations: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not TOKEN_PATTERN.search(line):
            continue
        if ALLOWLIST_PRAGMA in line and pragma_is_honoured(path):
            continue
        violations.append(f"{path}:{lineno}")
    return violations


def tracked_files() -> list[str]:
    """Every path in the index.

    Deliberately no try/except: if git is missing or fails, this test errors
    rather than skipping. A guard that can quietly opt out of running is not a
    guard (see tests/unit/test_ci_config_drift.py, invariant 10).
    """
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    return [path for path in completed.stdout.decode("utf-8").split("\0") if path]


def read_tracked(path: str) -> str | None:
    """Text of a tracked file, or None when it is binary or absent."""
    try:
        return (REPO_ROOT / path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return None


class TestScannerBehaviour:
    """The detector itself, exercised on synthetic input."""

    LIVE_SHAPE = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"  # pragma: allowlist secret

    def test_flags_a_token_in_source(self) -> None:
        """A bare credential shape under src/ is a violation."""
        assert scan_text("src/finos_mcp/config.py", self.LIVE_SHAPE) == [
            "src/finos_mcp/config.py:1"
        ]

    def test_pragma_does_not_silence_outside_the_honoured_paths(self) -> None:
        """A trailing comment must not buy an exemption for src/ or scripts/."""
        line = f"{self.LIVE_SHAPE}  # {ALLOWLIST_PRAGMA}"

        assert scan_text("src/finos_mcp/config.py", line) == [
            "src/finos_mcp/config.py:1"
        ]
        assert scan_text("scripts/run-local-with-token.sh", line) == [
            "scripts/run-local-with-token.sh:1"
        ]

    def test_pragma_silences_under_tests_and_env_example(self) -> None:
        """Where placeholders legitimately live, the pragma is honoured."""
        line = f"{self.LIVE_SHAPE}  # {ALLOWLIST_PRAGMA}"

        assert not scan_text("tests/unit/test_structured_logging.py", line)
        assert not scan_text(".env.example", line)

    def test_an_unmarked_token_under_tests_is_still_flagged(self) -> None:
        """Being under tests/ is not itself an exemption; the pragma is."""
        assert scan_text("tests/unit/test_structured_logging.py", self.LIVE_SHAPE) == [
            "tests/unit/test_structured_logging.py:1"
        ]

    def test_a_bare_prefix_is_not_a_token(self) -> None:
        """The wrapper names the prefixes in prose; that must not self-trip."""
        assert not scan_text("scripts/run-local-with-token.sh", "ghp_ gho_ github_pat_")

    def test_reports_the_line_number(self) -> None:
        """A finding must point at the offending line, not just the file."""
        text = "\n".join(["clean", "clean", self.LIVE_SHAPE])

        assert scan_text("src/finos_mcp/config.py", text) == [
            "src/finos_mcp/config.py:3"
        ]


class TestTrackedTree:
    """The real index."""

    def test_the_scanner_reaches_real_content(self) -> None:
        """Fail if the sweep read nothing, rather than reporting a clean tree.

        An empty violation list has two causes -- a clean index, or a sweep
        that never looked. These assertions separate them.
        """
        tracked = tracked_files()
        assert len(tracked) >= MIN_TRACKED_FILES, (
            f"git ls-files returned {len(tracked)} paths; the sweep has no "
            "index to scan"
        )

        readable = 0
        seen = 0
        for path in tracked:
            text = read_tracked(path)
            if text is None:
                continue
            readable += 1
            seen += len(find_token_lines(text))

        assert readable >= MIN_TRACKED_FILES, (
            f"only {readable} of {len(tracked)} tracked files could be read; "
            "the sweep is not reaching file content"
        )
        assert seen >= MIN_PLACEHOLDER_LINES, (
            "found no credential-shaped line anywhere in the index. The "
            "allowlist path is therefore untested against real data -- either "
            "the placeholders were removed, or the pattern no longer matches"
        )

    def test_no_unallowed_credential_in_a_tracked_file(self) -> None:
        """The guard itself: nothing in the index carries a live credential."""
        violations: list[str] = []
        for path in tracked_files():
            text = read_tracked(path)
            if text is not None:
                violations.extend(scan_text(path, text))

        assert not violations, (
            "credential-shaped literal in tracked file(s): "
            + ", ".join(violations)
            + ". Move the secret out of the repository. A "
            f"'# {ALLOWLIST_PRAGMA}' comment only silences this under "
            "tests/ or in .env.example."
        )
