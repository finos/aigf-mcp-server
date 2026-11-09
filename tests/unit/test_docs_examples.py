"""Guards that what the documentation tells a reader to type can be typed.

``test_docs_truth.py`` closes the names and counts of the tool surface. #47
also asked for the commands, the paths and the arguments, and those stayed open
while the defects it listed were corrected by hand. Corrected by hand in one
place: the README's Quick Start was repaired, and the same three lines in
``docs/api/integration-guide.md`` went on cloning into one directory, changing
into another and then asking the server for a help text it does not have.

These tests assert five invariants over the same corpus (``README.md``,
``CONTRIBUTING.md`` and everything under ``docs/``):

1. **A clone and the ``cd`` after it agree.** ``git clone <url>`` makes a
   directory named after the repository; the next ``cd`` must enter that one,
   or the one the clone was told to make.
2. **The server is started without arguments.** ``finos-mcp`` reads no
   command line, so ``finos-mcp --help`` starts a server that waits on stdin.
   The rule is read from the entry point's module: when that module parses
   arguments, the test that says it does not fails first.
3. **A repository path the docs name exists.** A word of a shell line, or a
   name in backticks, that starts with one of the repository's top-level
   directories is a tracked file or directory. A ``.py`` or ``.sh`` name in
   backticks is exactly one file of the repository, or one a script writes.
4. **A call example passes arguments the tool accepts.** The tool exists,
   every required parameter is there and nothing else is, whether the example
   is written as
   ``call_tool("name", {...})``, as a JSON request, or as ``name("value")``.
   This is the invariant that would have caught ``{"framework": ...}`` after
   the parameter became ``framework_id``.
5. **No count of the upstream documents without a date.** How many risks,
   mitigations and frameworks there are is decided in another repository. Five
   lines stated four different numbers, none of them the current one, two under
   the words "may grow over time".

What this does not close: whether a command does what the sentence beside it
says, an argument of the right name with a value the tool rejects, a path
named without backticks or inside a block that is not shell, a clone and its
``cd`` in two separate blocks, and the arguments of prompts and resources. The
Python examples are not run.
"""

from __future__ import annotations

import ast
import re
import shlex
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from test_docs_truth import _live_docs, _tracked  # type: ignore[import-not-found]
    from test_published_surface import (  # type: ignore[import-not-found]
        PUBLISHED_TOOL_PARAMETERS,
        PUBLISHED_TOOLS,
    )
finally:
    sys.path.pop(0)

pytestmark = pytest.mark.unit

_ENTRY_POINT = "finos-mcp"
_ENTRY_MODULE = "finos_mcp.fastmcp_main"
#: An unlabelled fence is read too: a command is often pasted into one.
_SHELLS = {"", "bash", "sh", "shell", "zsh", "console"}
#: Words that run the command after them and leave its arguments alone.
_LAUNCHERS = {"env", "exec", "nohup", "time", "sudo", "uv", "run"}

#: A fence line. Whatever follows the language word is an info string.
_FENCE = re.compile(r"^\s*`{3,}\s*([\w-]*)(.*)$")
_SPAN = re.compile(r"`([^`\n]+)`")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
#: Where one command of a shell line ends and the next begins.
_COMMAND_BREAK = re.compile(r"\|\||&&|[|;]")
#: A redirection or ``&``: from here on the words are not arguments.
_REDIRECTION = re.compile(r"^(?:\d*[<>]|&$)")
_CLONE_SOURCE = re.compile(r"://|^git@|\.git$")
_SOURCE_FILE = re.compile(r"(?<![\w-])(?:\.{1,2}/)*([\w.-]+(?:/[\w.-]+)*\.(?:py|sh))\b")
_SLASHED_PATH = re.compile(r"(?<![\w/.-])(?:\./)?([\w.-]+(?:/[\w.-]+)+)")
_LINE_SUFFIX = re.compile(r":\d+$")
_LAUNCH_ARGS = re.compile(
    r"\"command\"\s*:\s*\"[^\"]*" + re.escape(_ENTRY_POINT) + r"\"\s*,\s*"
    r"\"args\"\s*:\s*\[\s*([^\]\s][^\]]*)\]"
)

_DICT_CALL = re.compile(
    r"\w*call_tool\w*\(\s*[\"'](\w+)[\"']\s*,\s*(?:arguments\s*=\s*)?\{([^{}]*)\}"
)
_JSON_CALL = re.compile(
    r"[\"'](?:tool|name)[\"']\s*:\s*[\"'](\w+)[\"']\s*,\s*"
    r"[\"']arguments[\"']\s*:\s*\{([^{}]*)\}"
)
_KEY = re.compile(r"[\"'](\w+)[\"']\s*:")

#: A number, then the documents it counts, with up to two describing words
#: between them. The noun is plural or is followed by what it counts, so "the
#: ISO 42001 framework" and "3 risk categories" are not counts. "Top 10 risks"
#: is a title and "the first 5 frameworks" a limit. A word that is itself the
#: thing counted ("9 tools for frameworks") ends the reach.
_CORPUS_COUNT = re.compile(
    r"(?<![\w.-])(?<!top )(?<!first )(?<!up to )(?<!at most )(\d+)\+?\*{0,2}\s+"
    r"(?:(?!(?:tools?|prompts?|resources?|results?|categories|sections|references"
    r"|requests|of|for|in|to|across|and|or)\b)[a-z-]+\s+){0,2}?"
    r"(?:(?:risk|mitigation|framework)s\b"
    r"|(?:risk|mitigation|framework)\s+(?:documents|assessments|files)\b)",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _fences(text: str) -> list[tuple[str, list[tuple[int, str]]]]:
    """Each fenced block of ``text``: its language and ``(line number, line)`` pairs."""
    blocks: list[tuple[str, list[tuple[int, str]]]] = []
    inside = False
    for number, line in enumerate(text.splitlines(), 1):
        fence = _FENCE.match(line)
        if fence and not (inside and (fence.group(1) or fence.group(2).strip())):
            inside = not inside
            if inside:
                blocks.append((fence.group(1).lower(), []))
        elif inside:
            blocks[-1][1].append((number, line))
    return blocks


def _shell_lines(text: str) -> list[list[tuple[int, str]]]:
    """Each fenced shell block of ``text`` as its ``(line number, line)`` pairs."""
    return [lines for language, lines in _fences(text) if language in _SHELLS]


def _prose_spans(text: str) -> list[tuple[int, str]]:
    """``(line, text)`` for each backticked span outside the fenced blocks."""
    fenced = {number for _, lines in _fences(text) for number, _ in lines}
    return [
        (number, span.group(1))
        for number, line in enumerate(text.splitlines(), 1)
        if number not in fenced and not _FENCE.match(line)
        for span in _SPAN.finditer(line)
    ]


def _commands(line: str) -> list[list[str]]:
    """The commands on one shell line: their words, without assignments or redirections."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return []
    commands = []
    for part in _COMMAND_BREAK.split(stripped.removeprefix("$ ")):
        try:
            words = shlex.split(part, comments=True)
        except ValueError:
            words = part.split()
        while words and _ASSIGNMENT.match(words[0]):
            words.pop(0)
        for index, word in enumerate(words):
            if _REDIRECTION.match(word):
                del words[index:]
                break
        if words:
            commands.append(words)
    return commands


def _clone_pairs(text: str) -> list[tuple[int, str, str]]:
    """``(line of the cd, directory the clone makes, directory entered)``.

    Read within one fenced block: a clone in one block and the ``cd`` in the
    next are not paired.
    """
    pairs = []
    for block in _shell_lines(text):
        made: str | None = None
        for number, line in block:
            for words in _commands(line):
                if words[:2] == ["git", "clone"]:
                    made = None
                    for index, word in enumerate(words):
                        if index > 1 and _CLONE_SOURCE.search(word):
                            named = words[index + 1 : index + 2]
                            if named and not named[0].startswith("-"):
                                made = named[0].rstrip("/")
                            else:
                                made = word.rstrip("/").rsplit("/", 1)[-1]
                                made = made.removesuffix(".git")
                            break
                elif words[0] == "cd" and made is not None and len(words) > 1:
                    pairs.append((number, made, words[1]))
                    made = None
    return pairs


def _clone_mismatches(text: str) -> list[tuple[int, str, str]]:
    """The clone pairs where the ``cd`` does not start in the directory made."""
    return [
        (number, made, entered)
        for number, made, entered in _clone_pairs(text)
        if entered.removeprefix("./").split("/")[0] != made
    ]


def _started_with(words: list[str]) -> list[str] | None:
    """The arguments ``words`` start the server with, or None if they do not start it."""
    for index, word in enumerate(words):
        if word.rsplit("/", 1)[-1] == _ENTRY_POINT:
            return words[index + 1 :]
        if word == _ENTRY_MODULE and words[index - 1 : index] == ["-m"]:
            return words[index + 1 :]
        if (
            word not in _LAUNCHERS
            and not _ASSIGNMENT.match(word)
            and not (word == "-m" or word.rsplit("/", 1)[-1].startswith("python"))
        ):
            return None
    return None


def _server_starts(text: str) -> list[tuple[int, str]]:
    """``(line, arguments)`` for each place the document starts the server.

    A shell line in a fenced block, a backticked command in a sentence, and
    the ``args`` beside a ``"command"`` in a client's configuration.
    """
    lines = [pair for block in _shell_lines(text) for pair in block]
    starts = [
        (number, " ".join(arguments))
        for number, line in lines + _prose_spans(text)
        for words in _commands(line)
        if (arguments := _started_with(words)) is not None
    ]
    starts += [
        (text.count("\n", 0, match.start()) + 1, match.group(1).strip())
        for match in _LAUNCH_ARGS.finditer(text)
    ]
    return sorted(starts)


def _entry_point_arguments(text: str) -> list[tuple[int, str]]:
    """``(line, arguments)`` for each place the server is started with any."""
    return [(number, passed) for number, passed in _server_starts(text) if passed]


def _repository_paths(text: str, top_level: set[str]) -> list[tuple[int, str]]:
    """``(line, path)`` for each path of this repository the document names.

    In a shell command, any word, or the value after an ``=``. In a sentence,
    anything inside backticks. A glob or a shell variable is not a path.
    """
    lines = [pair for block in _shell_lines(text) for pair in block]
    words = [
        (number, word.rsplit("=", 1)[-1])
        for number, line in lines
        for command in _commands(line)
        for word in command
    ]
    words += [
        (number, word) for number, span in _prose_spans(text) for word in span.split()
    ]
    paths = []
    for number, word in words:
        if any(character in word for character in "*?{}$<>"):
            continue
        for match in _SLASHED_PATH.finditer(word.split("::")[0]):
            path = _LINE_SUFFIX.sub("", match.group(1)).rstrip("/.")
            if path.split("/")[0] in top_level and (number, path) not in paths:
                paths.append((number, path))
    return paths


def _source_files_named(text: str) -> list[tuple[int, str]]:
    """``(line, name)`` for each ``.py`` or ``.sh`` name inside backticks in the prose."""
    return [
        (number, match.group(1))
        for number, span in _prose_spans(text)
        for match in _SOURCE_FILE.finditer(span)
    ]


def _tracked_as(name: str, tracked: set[str]) -> list[str]:
    """The tracked paths ``name`` is, or is the tail of at a ``/``."""
    return sorted(path for path in tracked if path == name or path.endswith("/" + name))


def _written_by_a_script(root: Path, tracked: set[str]) -> set[str]:
    """Source files ``.gitignore`` names outright and a script in ``scripts/`` quotes."""
    ignored = {
        line.strip().removeprefix("/")
        for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    scripts = "".join(
        (root / path).read_text(encoding="utf-8", errors="replace")
        for path in tracked
        if path.startswith("scripts/")
    )
    return {
        name
        for name in ignored
        if name.endswith((".py", ".sh")) and f'"{name}"' in scripts
    }


def _positional_arguments(written: str) -> tuple[int, set[str]] | None:
    """How many positional values and which keywords a ``name(...)`` call passes.

    None when what stands between the parentheses is not a call's arguments:
    ``get_risk(id)`` in a signature, or a sentence.
    """
    try:
        call = ast.parse(f"f({written})", mode="eval").body
    except SyntaxError:
        return None
    assert isinstance(call, ast.Call)
    if not all(isinstance(value, ast.Constant) for value in call.args):
        return None
    return len(call.args), {keyword.arg for keyword in call.keywords if keyword.arg}


def _direct_calls(text: str, tools: set[str]) -> list[re.Match[str]]:
    """Each ``name(...)`` in ``text`` whose name is a tool's."""
    return list(
        re.finditer(rf"(?<![\w.\"'])({'|'.join(sorted(tools))})\(([^()\n]*)\)", text)
    )


def _call_defects(
    text: str, required: dict[str, set[str]], accepted: dict[str, set[str]]
) -> list[tuple[int, str, str]]:
    """``(line, tool, what is wrong)`` for each call example the server would refuse.

    ``get_risk()`` with nothing between the parentheses is how a sentence names
    a tool, so outside a fenced block it is not read as a call.
    """
    defects = []
    fenced = {number for _, lines in _fences(text) for number, _ in lines}

    def line_of(offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    def check(offset: int, tool: str, passed: set[str], positional: int = 0) -> None:
        unknown = passed - accepted[tool]
        if unknown:
            defects.append((line_of(offset), tool, f"passes {sorted(unknown)}"))
        missing = required[tool] - passed
        if positional > len(accepted[tool]):
            defects.append((line_of(offset), tool, f"passes {positional} values"))
        elif len(missing) > positional:
            defects.append((line_of(offset), tool, f"omits {sorted(missing)}"))

    for pattern in (_DICT_CALL, _JSON_CALL):
        for match in pattern.finditer(text):
            if match.group(1) in accepted:
                check(match.start(), match.group(1), set(_KEY.findall(match.group(2))))
            else:
                defects.append((line_of(match.start()), match.group(1), "is no tool"))

    for match in _direct_calls(text, set(accepted)):
        arguments = _positional_arguments(match.group(2))
        mention = not match.group(2).strip() and line_of(match.start()) not in fenced
        if arguments is not None and not mention:
            check(match.start(), match.group(1), arguments[1], arguments[0])
    return sorted(defects)


def _corpus_counts(text: str) -> list[tuple[int, str]]:
    """``(line, claim)`` for each undated count of the upstream documents."""
    return [
        (number, match.group(0))
        for number, line in enumerate(text.splitlines(), 1)
        if not _DATE.search(line)
        for match in _CORPUS_COUNT.finditer(line)
    ]


def _command_line_readers(source: str) -> list[str]:
    """What in ``source`` reads the command line: a parser it imports, or ``argv``."""
    parsers = {"argparse", "click", "typer", "optparse", "getopt", "fire", "cyclopts"}
    vectors = {"argv", "orig_argv"}
    readers = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            readers |= {a.name for a in node.names if a.name.split(".")[0] in parsers}
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in parsers:
                readers.add(node.module or "")
            readers |= {a.name for a in node.names if a.name in vectors}
        elif isinstance(node, ast.Attribute) and node.attr in vectors:
            readers.add(node.attr)
        elif isinstance(node, ast.Constant) and node.value in vectors:
            readers.add(str(node.value))
    return sorted(readers)


def _documents(pytestconfig: pytest.Config) -> dict[str, str]:
    root = Path(str(pytestconfig.rootpath))
    documents = {
        str(document.relative_to(root)): document.read_text(encoding="utf-8")
        for document in _live_docs(root)
    }
    assert len(documents) >= 10, f"only {len(documents)} live documents were read"
    return documents


def test_every_clone_is_followed_into_the_directory_it_makes(
    pytestconfig: pytest.Config,
) -> None:
    """``git clone`` then ``cd`` into a different name stops a reader at line two."""
    documents = _documents(pytestconfig)
    pairs = sum(len(_clone_pairs(text)) for text in documents.values())
    assert pairs >= 2, f"only {pairs} clone commands followed by a cd were read"

    offenders = {
        name: found
        for name, text in documents.items()
        if (found := _clone_mismatches(text))
    }
    assert not offenders, (
        "these clone commands make one directory and the next line enters "
        f"another, as (line, made, entered): {offenders}"
    )


def test_the_entry_point_reads_no_command_line(pytestconfig: pytest.Config) -> None:
    """The fact the next test rests on, read from the entry point's source.

    Closes the module the command is declared to run. Arguments parsed by a
    module it imports would not be seen here.
    """
    root = Path(str(pytestconfig.rootpath))
    scripts = (root / "pyproject.toml").read_text(encoding="utf-8")
    module, _, package = _ENTRY_MODULE.rpartition(".")[::-1]
    assert f'{_ENTRY_POINT} = "{_ENTRY_MODULE}:main"' in scripts, (
        f"pyproject.toml no longer declares {_ENTRY_POINT} as {_ENTRY_MODULE}:main"
    )

    source = root / "src" / package / f"{module}.py"
    readers = _command_line_readers(source.read_text(encoding="utf-8"))
    assert not readers, (
        f"{source.name} now reads the command line ({readers}). Say which "
        "arguments it takes in test_no_document_starts_the_server_with_arguments, "
        "which until now could refuse every one of them."
    )


def test_no_document_starts_the_server_with_arguments(
    pytestconfig: pytest.Config,
) -> None:
    """``finos-mcp --help`` prints no help: it starts a server and waits on stdin."""
    documents = _documents(pytestconfig)
    started = sum(len(_server_starts(text)) for text in documents.values())
    assert started >= 3, f"only {started} places starting the server were read"

    offenders = {
        name: found
        for name, text in documents.items()
        if (found := _entry_point_arguments(text))
    }
    assert not offenders, (
        f"these lines pass {_ENTRY_POINT} arguments it does not read, as "
        f"(line, arguments): {offenders}. It is configured by environment "
        "variables alone."
    )


def test_every_repository_path_the_docs_name_exists(
    pytestconfig: pytest.Config,
) -> None:
    """A path under one of the repository's directories is one it tracks."""
    root = Path(str(pytestconfig.rootpath))
    tracked = set(_tracked(root))
    directories = {str(parent) for path in tracked for parent in Path(path).parents} - {
        "."
    }
    top_level = {path.split("/")[0] for path in tracked if "/" in path}
    documents = _documents(pytestconfig)

    named = {
        name: found
        for name, text in documents.items()
        if (found := _repository_paths(text, top_level))
    }
    checked = sum(len(found) for found in named.values())
    assert checked >= 40, f"only {checked} repository paths were found in the docs"

    offenders = {
        name: missing
        for name, found in named.items()
        if (
            missing := [
                (line, path)
                for line, path in found
                if path not in tracked and path not in directories
            ]
        )
    }
    assert not offenders, (
        f"these documents name a path the repository does not track: {offenders}"
    )


def test_every_source_file_the_docs_name_exists(pytestconfig: pytest.Config) -> None:
    """A ``.py`` or ``.sh`` name in backticks is one tracked file, or the tail of one.

    The architecture page names modules as ``content/service.py``, relative to
    the package, so a name is accepted when exactly one tracked path ends with
    it at a directory boundary. A module that is deleted or renamed leaves no
    such path, and a name two files share does not say which is meant. A file
    a script writes is not tracked; it is accepted when ``.gitignore`` and a
    script under ``scripts/`` both name it.

    What this does not close: a sentence that says a file is gone and names it
    in backticks fails here. The live documents describe what exists; what was
    removed is recorded in ``CHANGELOG.md``.
    """
    root = Path(str(pytestconfig.rootpath))
    tracked = set(_tracked(root))
    written = _written_by_a_script(root, tracked)
    documents = _documents(pytestconfig)

    named = {
        name: found
        for name, text in documents.items()
        if (found := _source_files_named(text))
    }
    checked = sum(len(found) for found in named.values())
    assert checked >= 40, f"only {checked} source file names were found in the docs"

    offenders = {
        name: wrong
        for name, found in named.items()
        if (
            wrong := [
                (line, file, matches)
                for line, file in found
                if file not in written
                and len(matches := _tracked_as(file, tracked)) != 1
            ]
        )
    }
    assert not offenders, (
        "these documents name a source file that is not exactly one file of the "
        f"repository, as (line, name, files it could be): {offenders}"
    )


def test_every_call_example_passes_arguments_the_tool_accepts(
    pytestconfig: pytest.Config,
) -> None:
    """An example a reader copies is a call the server would not refuse."""
    documents = _documents(pytestconfig)
    examples = sum(
        len(_DICT_CALL.findall(text)) + len(_JSON_CALL.findall(text))
        for text in documents.values()
    )
    # The integration guide holds the two left since its copies went (#411,
    # #414); the floor notices a scanner that reads nothing.
    assert examples >= 2, f"only {examples} call examples with arguments were found"
    direct = sum(
        len(_direct_calls(text, set(PUBLISHED_TOOLS))) for text in documents.values()
    )
    # 14 since the user guide's and the integration guide's copies went (#411,
    # #414); the floor notices a scanner reading nothing, not copies.
    assert direct >= 10, f"only {direct} calls written as name(...) were found"

    offenders = {
        name: found
        for name, text in documents.items()
        if (found := _call_defects(text, PUBLISHED_TOOLS, PUBLISHED_TOOL_PARAMETERS))
    }
    assert not offenders, (
        "these call examples do not match what the server publishes, as "
        f"(line, tool, defect): {offenders}"
    )


def test_no_document_counts_the_upstream_documents_without_a_date(
    pytestconfig: pytest.Config,
) -> None:
    """The number of risks, mitigations and frameworks is not this repository's.

    The documents said 17 risks, 23 risks, 23 mitigations and 7 frameworks
    while the server listed 24, 25 and 13. A count is allowed on a line that
    says which day it was taken; ``total_count`` in a listing is the answer.

    What this does not close: a count split across two lines, one written as a
    word, and one in a table cell away from its noun.
    """
    offenders = {
        name: found
        for name, text in _documents(pytestconfig).items()
        if (found := _corpus_counts(text))
    }
    assert not offenders, (
        f"these lines count documents another repository holds: {offenders}. "
        "Remove the number or give the date it was counted on the same line."
    )


_SYNTHETIC_COMMANDS = """
```bash title="install"
git clone https://github.com/example/finos-mcp-server.git
cd aigf-mcp-server
git clone --depth 1 -b release/1.0 https://github.com/example/finos-mcp-server.git aigf && cd aigf/docs
git clone https://github.com/example/finos-mcp-server.git --depth 1
cd ./finos-mcp-server
FINOS_MCP_LOG_LEVEL=DEBUG finos-mcp 2> server.log &
finos-mcp --help
npx inspector --cli finos-mcp --method tools/list
# finos-mcp --version
./scripts/ci-local.sh && pytest tests/unit/test_gone.py::test_one -q --cov=src/gone
python scripts/removed.py:12 > docs/out.txt | tee venv/bin/log; ls scripts/*.sh
nohup ./venv/bin/finos-mcp --port 8000 &
python -m finos_mcp.fastmcp_main --transport http
```

Run `finos-mcp --version`, or `finos-mcp` alone; see `.github/workflows/test.yml`.

```json
{"command": "/usr/bin/finos-mcp", "args": ["--transport", "http"]}
{"command": "finos-mcp", "args": []}
```

```python
finos-mcp --verbose
cd elsewhere
```
"""

_SYNTHETIC_CALLS = """
```python
mcp_client.call_tool("get_framework", {"framework": "nist-ai-600-1"})
mcp_client.call_tool(
    "search_frameworks",
    {"query": topic, "limit": 10}
)
client.call_tool("search_frameworks", arguments={"limit": 5})
self.call_tool_cached("search_risks", {"query": "x"})
{"tool": "get_risk", "arguments": {}}
{"name": "get_risk", "arguments": {"risk_id": "10_prompt-injection"}}
Use: get_risk()
```
1. `get_risk("10_prompt-injection")` then `get_risk()` and `list_risks("all")`
2. `search_frameworks("risk management", 5)`, `search_frameworks(query="x", top=3)`
3. `get_mitigation(mitigation_id)` is a signature and `self.get_risk()` a method
"""

_SYNTHETIC_COUNTS = """
Returns: 17 AI governance risk documents
- **23 AI Governance Mitigations** (current repository snapshot)
The server provides access to **13** supported frameworks:
24 risks, 25 mitigations and 13 frameworks on 2026-10-07
OWASP ML Security Top 10 | Top 10 risks for machine learning systems
Returns the first 5 frameworks, in catalog order, or up to 20 frameworks
the server's 9 governance framework tools and 3 prompts for frameworks
the ISO 42001 framework, NIST SP 800-53 Rev 5 framework and 3 risk categories
200+ frameworks and 9 tools for frameworks
"""


def test_the_scanners_reject_synthetic_false_claims() -> None:
    """Each scanner is shown a document written to be wrong and must say so."""
    assert _clone_pairs(_SYNTHETIC_COMMANDS) == [
        (4, "finos-mcp-server", "aigf-mcp-server"),
        (5, "aigf", "aigf/docs"),
        (7, "finos-mcp-server", "./finos-mcp-server"),
    ], (
        "the clone scanner no longer reads the directory a clone makes: after "
        "options, under a fence with an info string, or named on the command"
    )
    assert _clone_mismatches(_SYNTHETIC_COMMANDS) == [
        (4, "finos-mcp-server", "aigf-mcp-server")
    ], "the clone scanner now accuses a cd into, or below, the directory made"

    assert _server_starts(_SYNTHETIC_COMMANDS) == [
        (8, ""),
        (9, "--help"),
        (14, "--port 8000"),
        (15, "--transport http"),
        (18, ""),
        (18, "--version"),
        (21, '"--transport", "http"'),
    ], (
        "the entry-point scanner no longer reads every way the server is "
        "started, or now reads an assignment, a redirection, another program's "
        "flags, a comment, empty args or a block that is not shell as one"
    )
    assert _entry_point_arguments(_SYNTHETIC_COMMANDS) == [
        (9, "--help"),
        (14, "--port 8000"),
        (15, "--transport http"),
        (18, "--version"),
        (21, '"--transport", "http"'),
    ]
    assert _repository_paths(
        _SYNTHETIC_COMMANDS, {"scripts", "tests", "src", ".github"}
    ) == [
        (12, "scripts/ci-local.sh"),
        (12, "tests/unit/test_gone.py"),
        (12, "src/gone"),
        (13, "scripts/removed.py"),
        (18, ".github/workflows/test.yml"),
    ], (
        "the path scanner no longer reads every repository path a document "
        "names, or now reads a glob, a redirection target or another tree's path"
    )

    assert _call_defects(
        _SYNTHETIC_CALLS, PUBLISHED_TOOLS, PUBLISHED_TOOL_PARAMETERS
    ) == [
        (3, "get_framework", "omits ['framework_id']"),
        (3, "get_framework", "passes ['framework']"),
        (8, "search_frameworks", "omits ['query']"),
        (9, "search_risks", "is no tool"),
        (10, "get_risk", "omits ['risk_id']"),
        (12, "get_risk", "omits ['risk_id']"),
        (14, "list_risks", "passes 1 values"),
        (15, "search_frameworks", "passes ['top']"),
    ], (
        "the call scanner no longer reads every way an example is written, or "
        "now accuses a correct call, a signature, a method of the same name or "
        "a tool named in a sentence with empty parentheses"
    )

    assert _source_files_named(
        "`python scripts/gone.py:42`, `../scripts/ci-local.sh --fast`, not `x.yml`"
    ) == [(1, "scripts/gone.py"), (1, "scripts/ci-local.sh")]
    tracked = {
        "src/finos_mcp/content/service.py",
        "src/finos_mcp/service.py",
        "scripts/ci-local.sh",
    }
    assert {
        name: len(_tracked_as(name, tracked))
        for name in ("content/service.py", "ci-local.sh", "service.py", "local.sh")
    } == {"content/service.py": 1, "ci-local.sh": 1, "service.py": 2, "local.sh": 0}, (
        "a name is no longer matched at a directory boundary"
    )

    assert _command_line_readers(
        "import sys, click.core\nfrom argparse import ArgumentParser\n"
        "from sys import argv\nx = sys.orig_argv\ny = getattr(sys, 'argv')\n"
    ) == ["argparse", "argv", "click.core", "orig_argv"], (
        "the entry-point reader no longer sees a parser imported by a dotted "
        "name or by its members, or an argument vector read under either name"
    )
    assert _command_line_readers("import sys\nsys.exit(0)\n") == []

    assert _corpus_counts(_SYNTHETIC_COUNTS) == [
        (2, "17 AI governance risk documents"),
        (3, "23 AI Governance Mitigations"),
        (4, "13** supported frameworks"),
        (10, "200+ frameworks"),
    ], (
        "the count scanner no longer reads a count of the upstream documents, "
        "or now accuses a dated count, a title, a limit, a standard's number "
        "or a count of something else"
    )


def test_a_generated_file_is_one_a_script_and_the_ignore_list_both_name(
    tmp_path: Path,
) -> None:
    """A comment in ``.gitignore``, or a name no script writes, excuses nothing."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "make.py").write_text(
        'Path("made.py").write_text("")  # "old.py" "made.log"\n', encoding="utf-8"
    )
    (tmp_path / ".gitignore").write_text(
        "# old.py\nmade.py\n/scratch.py\nmade.log\n", encoding="utf-8"
    )
    assert _written_by_a_script(tmp_path, {"scripts/make.py"}) == {"made.py"}


#: ``pip install`` run by a bare ``pip`` or ``python -m pip``, not a venv's own.
_BARE_PIP_INSTALL = re.compile(r"^(?:pip3?|python3?(?:\.\d+)?\s+-m\s+pip)\s+install\b")
_VENV_ACTIVATION = re.compile(r"\bvenv[/\\](?:bin|Scripts)[/\\]activate\b")
_CONFIG_COMMAND = re.compile(r'"command"\s*:\s*"([^"]*)"')


def test_every_pip_install_runs_inside_a_virtualenv(
    pytestconfig: pytest.Config,
) -> None:
    """A guide's install works on a current Python (#395).

    A ``pip install`` outside a virtualenv stops with
    ``externally-managed-environment`` on Homebrew Python and on Debian and
    Ubuntu system Python. A block may run the venv's own pip
    (``venv/bin/pip``), or activate the venv before a bare ``pip``.
    """
    outside: list[str] = []
    for name, text in _documents(pytestconfig).items():
        for lines in _shell_lines(text):
            activated = False
            for number, line in lines:
                command = line.strip()
                if command.startswith("#"):
                    continue
                activated = activated or bool(_VENV_ACTIVATION.search(command))
                if _BARE_PIP_INSTALL.match(command) and not activated:
                    outside.append(f"{name}:{number}: {command}")
    assert not outside, (
        "These install lines run pip outside a virtualenv, which a current "
        f"Python refuses: {outside}. Use venv/bin/pip, or activate the venv "
        "first in the same block."
    )


def test_every_client_config_names_the_server_by_absolute_path(
    pytestconfig: pytest.Config,
) -> None:
    """A desktop client can start the server the docs configure (#396).

    A client starts the server with its own PATH, which holds no activated
    virtualenv: measured, a bare ``finos-mcp`` connected nothing and the
    absolute path listed 13 frameworks.
    """
    bare: list[str] = []
    configs = 0
    for name, text in _documents(pytestconfig).items():
        for _language, lines in _fences(text):
            for number, line in lines:
                for command in _CONFIG_COMMAND.findall(line):
                    configs += 1
                    if not command.startswith("/"):
                        bare.append(f"{name}:{number}: {command}")
        for number, line in enumerate(text.splitlines(), 1):
            if "**Command**" in line and "finos-mcp" in line and "`/" not in line:
                bare.append(f"{name}:{number}: {line.strip()}")
    assert configs >= 4, f"only {configs} client configs were found"
    assert not bare, (
        f"These client configs start the server by a bare name: {bare}. Name "
        "the virtualenv's finos-mcp by its absolute path."
    )
