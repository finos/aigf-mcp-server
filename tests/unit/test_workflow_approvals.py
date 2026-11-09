"""Guards that no workflow approves a pull request.

``dependabot-security-validation.yml`` had a ``dependabot-auto-approve`` job
that POSTed an ``APPROVE`` review with ``curl`` and no ``--fail``. On the first
Dependabot pull request it ever ran on (#161, run 36609524542) GitHub answered
``422 "GitHub Actions is not permitted to approve pull requests."``, the job
reported success, and the pull request had no review (#159).

It could not have succeeded. The repository has
``can_approve_pull_request_reviews: false``, and a ``pull_request`` run that
Dependabot triggers gets a read-only ``GITHUB_TOKEN`` whatever the workflow's
``permissions:`` block asks for, so enabling the setting would not have been
enough either. Only a personal access token stored as a Dependabot secret could
approve, and that was declined: it puts a write credential into runs that
execute Dependabot's code, to buy an approval that gates nothing, because this
plan has no branch protection. The job was deleted instead, and with it every
write scope the workflow requested. Merging a Dependabot pull request stays a
human decision.

The guard below refuses the approval routes a workflow can spell inline, not
only the one that was deleted: any call to the REST reviews endpoint, ``gh pr
review --approve``, the review mutations of the REST client and GraphQL
(``createReview``, ``submitReview``, ``addPullRequestReview``,
``submitPullRequestReview``), and an action whose name says it approves. The
endpoint is refused whatever the method, reads included: telling a GET from a
POST across ``curl`` and ``gh api`` spellings would be a prefilter an approval
could slip past, and no workflow here reads reviews. It reads parsed YAML, so
a YAML comment never matches. What it cannot close: an approval made from a
script file the workflow runs, or by an action whose name does not mention
approving; a reviewer still has to ask what a new ``uses:`` or script does.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

_WORKFLOWS = ".github/workflows"

_REST_ROUTE = "REST pull-request reviews endpoint"
_GH_CLI_ROUTE = "gh pr review --approve"
_REVIEW_MUTATION_ROUTE = "review mutation (REST client or GraphQL)"
_ACTION_ROUTE = "approval action"

# `pulls/<number>/reviews`, where the number may be an expression with spaces
# inside `${{ }}`, a shell variable, or github-script's `{pull_number}`.
_REVIEWS_ENDPOINT = re.compile(r"\bpulls/(?:\$\{\{[^}]*\}\}|[^\s/]+)/reviews\b")
# `gh pr review` up to the end of its command, then an approving flag. Matched
# with quoted arguments removed, so a review body that mentions `-a` is not one.
_GH_APPROVE = re.compile(r"\bgh\s+pr\s+review\b[^\n;&|]*?(?:--approve\b|\s-a\b)")
_QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")
_REVIEW_MUTATION = re.compile(
    r"\b(?:createReview|submitReview|addPullRequestReview|submitPullRequestReview)\b"
)


def _code(step: dict[str, Any]) -> str:
    """The shell and script text a step executes, with line continuations joined."""
    parts = [step.get("run")]
    inputs = step.get("with")
    if isinstance(inputs, dict):
        parts.append(inputs.get("script"))
    text = "\n".join(str(part) for part in parts if part is not None)
    return re.sub(r"\\\n\s*", " ", text)


def _approval_routes(workflow: dict[Any, Any]) -> tuple[list[str], int]:
    """Each place *workflow* can approve a pull request, and how many steps were read."""
    found: list[str] = []
    steps_read = 0
    for job_id, job in (workflow.get("jobs") or {}).items():
        if "approve" in str(job.get("uses", "")).lower():
            found.append(f"job {job_id}: {_ACTION_ROUTE} {job['uses']}")
        for index, step in enumerate(job.get("steps") or []):
            steps_read += 1
            where = f"job {job_id} step {index} ({step.get('name', 'unnamed')})"
            if "approve" in str(step.get("uses", "")).lower():
                found.append(f"{where}: {_ACTION_ROUTE} {step['uses']}")
            code = _code(step)
            if _REVIEWS_ENDPOINT.search(code):
                found.append(f"{where}: {_REST_ROUTE}")
            if _GH_APPROVE.search(_QUOTED.sub("''", code)):
                found.append(f"{where}: {_GH_CLI_ROUTE}")
            if _REVIEW_MUTATION.search(code):
                found.append(f"{where}: {_REVIEW_MUTATION_ROUTE}")
    return found, steps_read


def test_no_workflow_approves_a_pull_request(pytestconfig: pytest.Config) -> None:
    """An approval from Actions is refused here, and would gate nothing if it were not."""
    offenders: dict[str, list[str]] = {}
    steps_read = 0
    for path in sorted((Path(str(pytestconfig.rootpath)) / _WORKFLOWS).glob("*.y*ml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict), f"{path} is not a YAML mapping"
        found, read = _approval_routes(loaded)
        steps_read += read
        if found:
            offenders[path.name] = found

    # Measured at 67 when this guard was written; a much lower count means the
    # walk stopped reading steps, not that the workflows shrank.
    assert steps_read >= 30, (
        f"read only {steps_read} workflow steps; if the workflows really shrank, "
        "lower this floor to the new count, otherwise the walk has stopped reading them"
    )
    assert not offenders, (
        f"workflows approve pull requests: {offenders}. GitHub refuses approvals "
        "from Actions in this repository, and an approval gates nothing without "
        "branch protection; see this module's docstring (#159)."
    )


def _workflow(**step: Any) -> dict[str, Any]:
    return {"jobs": {"job": {"steps": [step]}}}


@pytest.mark.parametrize(
    ("workflow", "route"),
    [
        pytest.param(
            _workflow(
                run='curl -X POST \\\n  "https://api.github.com/repos/'
                "${{ github.repository }}/pulls/${{ github.event.pull_request.number }}"
                '/reviews" \\\n  -d \'{"event": "APPROVE"}\''
            ),
            _REST_ROUTE,
            id="deleted-curl",
        ),
        pytest.param(
            _workflow(
                run='gh api -X POST "repos/$REPO/pulls/$PR/reviews" -f event=APPROVE'
            ),
            _REST_ROUTE,
            id="gh-api",
        ),
        pytest.param(
            _workflow(run='gh pr review --approve "$PR_URL"'),
            _GH_CLI_ROUTE,
            id="gh-long-flag",
        ),
        pytest.param(
            _workflow(run='gh pr review "$PR_URL" \\\n  -a'),
            _GH_CLI_ROUTE,
            id="gh-short-flag-continued",
        ),
        pytest.param(
            _workflow(
                uses="actions/github-script@v7",
                **{
                    "with": {
                        "script": "await github.rest.pulls.createReview({event: 'APPROVE'})"
                    }
                },
            ),
            _REVIEW_MUTATION_ROUTE,
            id="github-script",
        ),
        pytest.param(
            _workflow(
                uses="actions/github-script@v7",
                **{"with": {"script": "await github.rest.pulls.submitReview({event})"}},
            ),
            _REVIEW_MUTATION_ROUTE,
            id="github-script-submit",
        ),
        pytest.param(
            _workflow(
                run="gh api graphql -f query='mutation { addPullRequestReview("
                'input: {pullRequestId: "$ID", event: APPROVE}) { clientMutationId } }\''
            ),
            _REVIEW_MUTATION_ROUTE,
            id="graphql",
        ),
        pytest.param(
            _workflow(run='gh api "repos/$REPO/pulls/$PR/reviews"'),
            _REST_ROUTE,
            id="rest-read-is-refused-too",
        ),
        pytest.param(
            _workflow(uses="hmarr/auto-approve-action@v4"),
            _ACTION_ROUTE,
            id="step-action",
        ),
        pytest.param(
            {
                "jobs": {
                    "job": {"uses": "org/workflows/.github/workflows/approve.yml@main"}
                }
            },
            _ACTION_ROUTE,
            id="reusable-workflow",
        ),
    ],
)
def test_each_approval_route_is_detected(workflow: dict[str, Any], route: str) -> None:
    """Every spelling the guard claims to refuse, each on its own."""
    found, _ = _approval_routes(workflow)
    assert any(route in finding for finding in found), (
        f"approval route not detected: {route}; found {found}"
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "jobs:\n  job:\n    steps:\n"
            "      # POST /repos/o/r/pulls/1/reviews with event APPROVE\n"
            "      - run: echo ok\n",
            id="yaml-comment",
        ),
        pytest.param(
            "jobs:\n  job:\n    steps:\n      - uses: actions/checkout@v4\n",
            id="unrelated-action",
        ),
        pytest.param(
            "jobs:\n  job:\n    steps:\n"
            '      - run: gh pr review "$PR" --comment -b "a note"\n'
            '      - run: gh api "repos/$REPO/pulls/$PR/files"\n'
            '      - run: gh pr review "$PR" --comment -b "see the -a flag"\n',
            id="non-approving-calls",
        ),
    ],
)
def test_workflows_that_do_not_approve_pass(text: str) -> None:
    """The guard accuses nothing that cannot approve."""
    found, read = _approval_routes(yaml.safe_load(text))
    assert read, "the control workflow had no steps to read"
    assert not found, f"a workflow that cannot approve was flagged: {found}"
