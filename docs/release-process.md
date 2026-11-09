# Release Process

What a release of this project is, how the version number is produced, what
`.github/workflows/release.yml` does, and how to cut a release.

Checked on 2026-10-11. The build commands and `scripts/check-release-tag.py`
were run in a clean clone. The statements about the workflow come from reading
it and from the logs of its past runs; the workflow itself was not run for
this page, so the two steps that call the script have not run on a runner.

## State of releases

- **No release exists.** The repository has no release and no tag.
  `CHANGELOG.md` has an `[Unreleased]` section and a `[0.1.0]` section dated
  2024-12-06; the `v0.1.0` tag was removed from the repository.
- **`main` is what is deployed.** Organisations install from a clone; see the
  [deployment guide](deployment.md).
- **The tag path of the workflow has never completed here.** The two tag pushes
  in its history (2025-09-16 and 2026-02-18) both failed, in jobs that have
  since been changed. The two runs that succeeded (2026-10-01 and 2026-10-03)
  were started by hand, a path that attached wrongly named files and has been
  removed; see [A release cannot be started by hand](#a-release-cannot-be-started-by-hand).

So the first real release is also the first complete run of the tag path. Do
the [rehearsal](#rehearse-first) before it.

## Version scheme

The version is not written in any file. `setuptools_scm` derives it from git
when the package is built or installed (`[tool.setuptools_scm]` in
`pyproject.toml`), and writes it into a generated module of the package that
git does not track. The server reports that version in the MCP `initialize` answer, in
`get_service_health` and in the `User-Agent` of its requests to GitHub.

Measured with `python -m build` in a clean clone:

| State of the checkout | Version built |
|---|---|
| No tag reachable from the commit | `0.1.dev312` (the number is the count of commits) |
| The commit carries tag `v9.9.9` | `9.9.9` |
| The commit carries tag `v9.9.10-rc.1` | `9.9.10rc1` |
| One commit after tag `v9.9.10-rc.1` | `9.9.10rc2.dev1` |

Two consequences:

- A tag must be on the commit that is built. One commit later is already a
  different, development version.
- Until the first tag exists, every install reports `0.1.dev` followed by a
  commit count. Two different branches can have the same count, so identify a
  deployed build by its commit, not by this number.

## What the workflow does

`release.yml` starts on a pushed tag that begins with `v`, and on nothing
else. It has three jobs, each needing the one before.

1. **Validate Release** (Python 3.11): checks the tag name with
   `scripts/check-release-tag.py`, installs the project with its `security`
   and `dev` extras, then runs bandit, semgrep, pylint and the test suite with
   its coverage floor. It does not run ruff, mypy or pip-audit; those run in
   the main pipeline on every push to `main`.
2. **Build Distribution**: `python -m build`, producing a source archive and a
   wheel, named from the git-derived version. The same script then requires
   exactly those two files, both carrying the version of the pushed tag. The
   job then attests the two files (`actions/attest-build-provenance`): GitHub
   stores a signed statement, keyed on each file's digest, that this workflow
   run on this commit built it.
   Only then are the files handed to the next job. **GitHub makes attestations
   for a private repository only on an Enterprise Cloud plan**, so on a private
   repository without one the step fails and no release is created; see
   [Verify a downloaded file](#verify-a-downloaded-file).
3. **Create GitHub Release**: creates a GitHub release named for the tag, with
   fixed notes and the two built files. The release is marked as a prerelease
   when the version is an alpha, beta, release candidate or development
   version, or a post-release of one (`v1.2.3-rc1.post2`). The validate job's
   script decides that from the version, not from the spelling of the tag:
   `v1.2.3-rc.1` and `v1.2.3.rc1` are both the prerelease `1.2.3rc1`, and
   `v1.2.3-1` is `1.2.3.post1`, which is not one.
   The release job marks a prerelease unless the script's answer is `false`,
   so if the answer does not reach it, a full release is published as a
   prerelease too; clear the mark on the release page if that happens.

### Tag names

A tag is `vX.Y.Z`, optionally followed by `-suffix` or `.suffix`, and the part
after the `v` has to be a version Python can parse, because that is what
`setuptools_scm` requires of it. Run the check before tagging:

```bash
python scripts/check-release-tag.py v0.2.0-rc.1
```

It prints `v0.2.0-rc.1 is version 0.2.0rc1` and exits 0, or prints the reason
and exits 1.

| Tag | Result |
|---|---|
| `v1.2.3` | version `1.2.3` |
| `v1.2.3-rc.1` | version `1.2.3rc1` |
| `v1.2.3.post1` | version `1.2.3.post1` |
| `1.2.3`, `v1.2`, `v1.2.3rc1` | refused: not `vX.Y.Z` with a separated suffix |
| `v0.0.0-ci.3`, `v1.2.3.x` | refused: not a version the build can parse |

The workflow's own pattern accepts `v0.0.0-ci.3`. In a clean clone,
`python -m build` and `pip install -e .` on a commit carrying that tag both
stop with `Can't parse version from tag 'v0.0.0-ci.3'`, and so does every
later build and install from that branch while the tag exists. The
script is therefore the first command of the run, before the install. If a
refused tag has already been pushed, delete it on both sides:

```bash
git push origin --delete v0.0.0-ci.3
git tag -d v0.0.0-ci.3
```

The `git push` line has not been run.

Put one version tag on a commit. When a commit carries two, `setuptools_scm`
chooses between them itself, and the run started by the other tag stops in the
build job, because the files do not carry its version. Measured with two
annotated tags on one commit, `v9.9.10-rc.1` made first and `v9.9.10` second:
the files were named `9.9.10`, and the check refused them for `v9.9.10-rc.1`.

GitHub reads the workflow from the tagged commit. A tag pushed on a commit
older than these checks runs the workflow as it was then, without them.

Nothing is published to PyPI and no container image is built.

The release notes are fixed text inside the workflow. They state how many
tools, resources and prompts the server has; check that text when the
published surface changes.

## A release cannot be started by hand

The workflow could once be started by hand (`workflow_dispatch`) with a
`version` input. It then built the branch it was started on, with no tag on
it, and named the release from the input, so the files carried the git-derived
version and not the one typed in.

From the log of the run on 2026-10-03: the input was `v0.0.0-ci.2`, the release
was created as `v0.0.0-ci.2`, and the files attached to it were
`finos_ai_governance_mcp_server-0.1.1rc2.dev113.tar.gz` and
`finos_ai_governance_mcp_server-0.1.1rc2.dev113-py3-none-any.whl`. The run on
2026-10-01 did the same with `v0.0.0-ci.1` and `0.1.1rc2.dev109`.

That trigger and its input are removed. The only way to start a release, or to
rehearse one, is to push a tag.

## Cut a release

The `git tag` commands below were run in a scratch clone. The pushes and the
`gh release` commands have not been run, because no release has been cut.

1. **`main` is green**, and the go-live gate passes locally:

   ```bash
   ./scripts/go-live-gate.sh
   ```

   Run it on `main` after the last merge. It needs a clean working tree, the
   development install in `venv/`, `gh` signed in to an account that can read
   the repository, and a commit that is already pushed. The CODEOWNERS gate
   asks GitHub about the commit, and failed on an unpushed branch when it was
   run for this page, after every gate before it had passed. The gate after
   it asks GitHub whether the private reporting form is available.

2. **Move the changelog.** In `CHANGELOG.md`, rename `[Unreleased]` to the
   version and date, add an empty `[Unreleased]` above it, and merge that
   through a pull request like any other change.

3. **Tag the merged commit and push that one tag.**

   ```bash
   git switch main
   git pull --ff-only origin main
   git tag -a v0.2.0 -m "v0.2.0"
   git push origin v0.2.0
   ```

   Push the tag by name. `git push --tags` pushes every local tag, including
   old ones that were deleted from the remote on purpose.

4. **Watch the run**, then check the release page: the two files must carry the
   same version as the tag (`v0.2.0` gives `...-0.2.0.tar.gz` and
   `...-0.2.0-py3-none-any.whl`).

   ```bash
   gh run list --workflow release.yml --repo finos/aigf-mcp-server --limit 1
   gh release view v0.2.0 --repo finos/aigf-mcp-server
   ```

5. **Verify one attached file** as a deployer would; the commands are in the
   next section.

A pushed tag is a published ref. Gate 9 of the go-live gate reads every
published ref for development-only files, so a tag on a commit that carries
them fails the gate from then on.

## Verify a downloaded file

Each file attached to a release carries a build provenance attestation: a
statement signed in the workflow run that built it, stored by GitHub under
the file's digest. A deployer who installs from a downloaded file can check
that the file is the one `release.yml` built from the tagged commit of this
repository, and was not changed since. The check needs `gh` 2.49 or newer
(the one used for this page is 2.86.0), signed in to an account that can read
the repository; for a public repository, any account.

```bash
gh release download v0.2.0 --repo finos/aigf-mcp-server --pattern '*.whl'
gh attestation verify finos_ai_governance_mcp_server-0.2.0-py3-none-any.whl --repo finos/aigf-mcp-server
```

`gh attestation verify` fetches the attestations GitHub holds for the file's
digest, checks the signature, and checks that the signing workflow belongs to
the named repository. It exits 0 for a file it has verified (`--format json`
prints the attestation), and exits 1 with `Error: HTTP 404: Not Found` naming
the file's digest for a file no attestation matches: a file built elsewhere,
or one changed after the build. Both exit codes were measured on 2026-10-12,
the 0 on another repository's attested release file and the 1 on a file of
this repository that was never released. `--repo` accepts a statement from any
workflow of the repository;
`--signer-workflow finos/aigf-mcp-server/.github/workflows/release.yml`
narrows it to this one.

The two commands above have not been run as written, because no release has
been cut. The attestation step itself has not run on a runner either. GitHub
makes attestations for a private repository only on an Enterprise Cloud plan,
so **on a private repository without one, every release run stops at the
attestation step** in the build job, and no release is created. The step is
not made conditional on the visibility, so that a release can never carry
files without a statement. Cut and rehearse releases on a public repository.

## Rehearse first

Because the tag path has not completed on this repository, run it once with a
throwaway prerelease tag before the first real release, then remove what it made:

```bash
git tag -a v0.0.0-rc.1 -m "release rehearsal"
git push origin v0.0.0-rc.1
```

A local build from that tag produces `finos_ai_governance_mcp_server-0.0.0rc1.tar.gz`
and `finos_ai_governance_mcp_server-0.0.0rc1-py3-none-any.whl`. On a private
repository the run stops at the attestation step, so rehearse once the
repository is public. When the run is green and the release carries those two
files, verify one of them as described above, then delete the release and the
tag:

```bash
gh release delete v0.0.0-rc.1 --repo finos/aigf-mcp-server --cleanup-tag --yes
git tag -d v0.0.0-rc.1
```

The rehearsal has not been done yet.
