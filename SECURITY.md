# Security Policy

This project supports responsible disclosure of security vulnerabilities and
follows the [FINOS Security Vulnerabilities Responsible Disclosure Policy](https://community.finos.org/docs/governance/software-projects/cve-responsible-disclosure).
If you believe you have found a security vulnerability, we encourage and
appreciate your report. Please report it privately using the method below —
**do not** open a public GitHub issue, and do not otherwise disclose it
publicly, until a fix has been released.

## Reporting a Vulnerability

- **Email (primary):** [security@finos.org](mailto:security@finos.org)

  Please include the affected version or commit, a description of the issue, and
  the steps needed to reproduce it. A proof of concept is welcome but not
  required.

- **GitHub private vulnerability reporting:** not currently available. The
  "Report a vulnerability" button under the **Security** tab is not enabled on
  this repository, so email is the route. If it is enabled, this document will
  be updated to lead with it.

## Supported Versions

`pyproject.toml` declares this project `Development Status :: 3 - Alpha` and
derives its version from `setuptools_scm`. There is no maintained release line:
`main` is the only branch that receives fixes, and a report is in scope if it
reproduces there.

| Version | Supported |
| ------- | --------- |
| `main`  | ✅        |
| Any tag or older commit | ❌ — please re-check against `main` first |

## What to Expect

1. **Acknowledgement within 5 business days.** If you have not heard back by then,
   please send a follow-up — it means the mail went astray.
2. **Triage.** The report is confirmed or explained, and you are told which.
3. **Fix and release.** If confirmed, a fix is developed and released on `main`.
4. **Disclosure.** The vulnerability is disclosed publicly in accordance with the
   [FINOS Security Vulnerabilities Responsible Disclosure Policy](https://community.finos.org/docs/governance/software-projects/cve-responsible-disclosure),
   crediting you unless you ask otherwise.

## Scope

This server has a deliberate security surface, and findings against any of it
are in scope: SSRF protection on JWKS fetching, denial-of-service and
rate-limiting middleware, prompt-injection boundaries between fetched documents
and the model, and request and response size validation. Findings in the FINOS
AI Governance Framework *content* this server fetches belong upstream, at
[finos/ai-governance-framework](https://github.com/finos/ai-governance-framework).

Thank you for helping keep this project and its users secure.
