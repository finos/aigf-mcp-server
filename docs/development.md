# Development

How to work on this repository and what has to be green before anything merges.
For the contribution process and project governance -- including the CLA
requirement -- see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

`main` is the production branch. Everything below exists to keep it that way.

## Development install

```bash
git clone https://github.com/finos/aigf-mcp-server.git aigf-mcp-server
cd aigf-mcp-server
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -e ".[dev,security,test]"
venv/bin/pre-commit install
```

The pip upgrade matters: the dependency scan (`pip-audit`) checks the
virtual environment's own pip, and the one a new venv ships with can carry a
known vulnerability.

Python 3.11 or newer is required, as the [Quick Start](../README.md#quick-start)
explains. Every gate looks for the virtual environment in `venv/`.
`scripts/dev-setup.sh` makes `venv/`, installs the package with its `dev` and
`security` extras, installs the hooks and writes a development `.env`.

## The rule

**The functional gate must be green before anything merges into `main`.**

```bash
FINOS_RUN_LIVE_MCP_TEST=1 FINOS_RUN_AUTH_HTTP_TEST=1 pytest -q \
  tests/integration/test_live_mcp_server.py \
  tests/integration/test_auth_http_transport.py
```

The first suite spawns the real server as a subprocess, drives it over the MCP
protocol, and asserts on the **content** of every answer. The second starts the
server over HTTP with authentication on and checks the token, scope and JWKS
rules; it needs no network. Both run in three places:

| Where | When |
|---|---|
| `functional-gate` job in `.github/workflows/security-analysis.yml` | every push to `main`/`feature/*`, and every PR to `main` |
| `pre-push` hook (install it -- see below) | before a push leaves your machine |
| `scripts/ci-local.sh`, `scripts/ci-exact-simulation.sh` | when you run local CI |

**Honest limitation.** `main` has no branch protection, so a red check *cannot
physically block* a merge. It is advisory, and merging past it is a human
decision. The pre-push hook is the one
place enforcement actually happens, so install the hooks:

```bash
pre-commit install
```

`--no-verify` exists, and there are legitimate reasons to use it. Knowing why you
are using it is the requirement.

Nothing used to verify that you ran it, and an uninstalled hook looks exactly
like a passing one from the outside -- so the enforcement point this repository
names as its only one did not exist on a clean checkout. `scripts/ci-local.sh`
now refuses to run until the hook is installed.

## Which Python the gates run

One script decides: `scripts/project-python.sh`. Every `language: system`
pre-commit hook, `scripts/ci-local.sh` and `scripts/pip-audit-scan.sh` resolve
their interpreter through it. Of the scripts the gates run, two kinds do not:
`scripts/semgrep-isolated.sh` builds a separate environment from
`$SEMGREP_PYTHON`, or else the first of `python3.13`, `python3.12`,
`python3.11` and `python3` on `PATH` that is 3.11 or newer, and the two
transport test scripts use `$PYTHON_BIN` or else `venv/bin/python`. The
developer setup scripts (`scripts/dev-*.sh`) call `python3` or `python`
themselves.

It resolves `$PYTHON_BIN`, then `venv/bin/python`, then `$VIRTUAL_ENV/bin/python`
-- and stops there. There is deliberately no fallback to a system interpreter:
that fallback is what let a stale virtualenv become the audited artefact for six
months without a word. On macOS it would also be actively wrong, since
`/usr/bin/python3` is Python 3.9 and holds none of this project's tools.

Before running anything it checks that the resolved environment satisfies the
dependency set `pyproject.toml` declares, and refuses to run when it does not:

```
project-python: .../venv/bin/python does not satisfy the dependency set declared in pyproject.toml:
  fastmcp 2.14.5 does not satisfy <4,>=3.4.7 [project.dependencies]
```

That is not hypothetical -- it is what the project virtualenv reported after
`pyproject.toml` moved to `fastmcp>=3.4.7,<4` and nobody rebuilt it. Rebuild
with:

```bash
rm -rf venv && python3.12 -m venv venv
venv/bin/pip install -e '.[security,dev,test]'
```

`ALLOW_INSECURE_INTERPRETER_MISMATCH=1` downgrades the refusal to a warning when
you know why the mismatch is there.

## Why content assertions, not shape assertions

The suite used to contain these three checks, and all three passed while the
framework search returned nothing at all:

```python
assert frameworks["total_count"] > 0                     # 3 unrelated files satisfy this
assert isinstance(framework["content"], str)             # a Python dict repr satisfies this
assert isinstance(search_frameworks_payload["results"], list)   # an EMPTY list satisfies this
```

Assert what the answer *is*. A named framework must be present; a rendered
document must contain its own title; a multi-word search must return results; ids
from `search_frameworks` must work with `get_framework`.

The same rule applies to every test in this repository, and it is enforced.
`tests/unit/test_ci_config_drift.py` fails the build if a collected test file
contains no assertion, if a test function returns a value instead of asserting
(pytest scores that as a pass), or if a test catches an exception and returns
instead of failing. Three files in this repo were written that way, and they are
why a broken framework catalog, an unusable search and non-round-tripping ids all
reached `main`.

## Rate limits

The gate runs **unauthenticated** against GitHub's 60 requests/hour per-IP limit.
It fits because:

- document bodies come from `raw.githubusercontent.com`, which is not counted
  against the API limit;
- discovery lists three directories and caches the result for an hour;
- CI persists that cache with `actions/cache`.

A full run costs about **six** API requests. If you see the gate fail with
`source='static_fallback'` or `source='expired_cache'`, that is the budget
being spent, not a code defect — retry, or set `FINOS_MCP_GITHUB_TOKEN`. The gate deliberately **fails** rather
than skipping in that state: the built-in catalog ships the correct filenames even
when discovery is pointed at the wrong directory, so passing on fallback data
would verify nothing.

## The other gates

Run everything CI runs:

```bash
bash scripts/ci-local.sh
```

Order: bandit → semgrep → pylint → ruff → mypy → pytest (≥82% coverage) →
pip-audit → pre-commit → functional gate.

Two conventions that the drift tests enforce, so they are worth knowing before you
trip over them:

- **One source of truth per tool.** Every tool's configuration lives in
  `pyproject.toml` (the external `config/security/bandit.yml` and `config/security/semgrep.yml`
  rulesets are the exceptions). No call site may restate a rule — no
  `--fail-under`, no `--strict-*`, no `--ignore-vuln`. Only presentational flags.
- **Hooks run the project's own tools.** Every pre-commit hook for a tool this
  project declares is `repo: local` + `language: system`. An upstream hook builds
  its own environment from its own `rev`, which is a second version of the tool
  drifting on its own schedule. Every failure `.pre-commit-config.yaml` has had
  was that one failure.

One check runs by hand, because it needs Node and no job installs it: the
FINOS CALM schema check of `calm/architecture.json`. Run it from the
repository root, where the control requirement paths in the file resolve:

```bash
npx --yes @finos/calm-cli@1.62.0 validate -a calm/architecture.json --strict -f pretty
```

It prints `No issues found.` and exits 0, or lists each error and exits 1; a
warning is an error under `--strict`. Run it after changing the file. What the
file says about the code is checked without Node by
`tests/unit/test_calm_architecture.py`, which runs with the rest of the suite.

## Live transport tests

```bash
# End-to-end stdio MCP test
FINOS_RUN_LIVE_MCP_TEST=1 venv/bin/pytest -q tests/integration/test_live_mcp_server.py

# End-to-end HTTP MCP test (starts the server and probes /mcp)
./scripts/test-http-transport.sh

# End-to-end HTTP auth test: no token, a token without the required scope, a valid token
./scripts/test-auth-http-transport.sh
```

## Go-live gate

```bash
./scripts/go-live-gate.sh
```

It runs the release checks in one go: tracked-folder hygiene, a clean working
tree, linting and type checks, the test suite, the live stdio, HTTP and auth
transport checks, the dependency vulnerability scan, no branch or tag on the
remote publishing development-only files, and CODEOWNERS owners that GitHub
can resolve, and a `SECURITY.md` that describes the reporting route the
repository has. Both ask the GitHub API, and the CODEOWNERS check reads the
pushed file, so `HEAD` must be pushed.

## Adding a tool

1. Add a decorated async function in the module that owns the domain:
   `documents/tools.py`, `search/tools.py` or `health_tools.py`. A new module
   must also be imported from `fastmcp_server.py`, or nothing it defines is
   registered.
2. Use `@mcp.tool()` with type hints and a Pydantic return model.
3. Add tests in `tests/unit/`, and add the tool to
   `tests/unit/test_published_surface.py`, which pins the published surface.
4. Run `venv/bin/python scripts/generate-tool-table.py` to rewrite the tool
   table in the project README, and document the tool in
   [`docs/api/mcp-tools.md`](api/mcp-tools.md).

## Working on this repository

- Branch from `origin/main`. Use `security/*` for anything touching the
  security surface, so the Dependabot Security Validation workflow runs.
  `feature/security-*` is also matched, for branches created under the older
  convention. These are the only two, and a test keeps them in step with the
  workflow.
- Conventional commits. A pull request's title is checked: its scope, if it
  has one, must be one of `deps`, `security`, `config`, `tools`, `cache`,
  `http`, `logging`, `parser`, `service`, `tests`, `ci`. The commits inside a
  pull request are not checked; their scope names the module they change,
  such as `parse` or `discovery`, and a merge commit lands them on `main` as
  written.
- Update `CHANGELOG.md` under `[Unreleased]`.
- A pull request runs the gates on Python 3.12 only. Python 3.11 and 3.13 run
  on the push to `main` after the merge, weekly, and when you start the
  `Security Analysis & Code Quality` workflow by hand on your branch. Read the
  run on `main` after you merge. Pull requests that the Dependabot Security
  Validation workflow validates still run all three.
- Do not commit a file whose name contains `claude`, and do not write a literal
  dot-`claude` sequence into a tracked file. Two hooks block both, one matching
  on filename and one on content — which is also why this sentence spells the
  sequence out rather than showing it, and why the repository cannot contain a
  `CLAUDE.md`.

  The reason is to keep local tooling and session files out of the
  repository, not security: nothing exploitable is being prevented, so the
  hooks are not labelled as though there were. The word itself is fine
  in file *contents* — `docs/README.md` documents Claude Desktop setup by name.
  If a hook stops you, rename the file; you should never see it fire on a file
  you did not write, and if you do, that is a bug worth reporting rather than a
  reason to reach for `--no-verify`.
