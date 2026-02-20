#!/usr/bin/env python3
"""FINOS MCP Server — End-to-End Smoke Test
============================================

Real-world scenario tests covering all 11 tools, 3 resource templates, and
3 prompts via the MCP Inspector CLI.  Each test case mirrors how a security
analyst agent would actually use the server.

Usage:
    python3 scripts/e2e_smoke_test.py [--config PATH] [--server NAME] [--timeout N]

Defaults:
    --config   /tmp/finos-inspector-config.json
    --server   finos
    --timeout  45  (seconds per test)

Output:
    - Coloured pass/fail console output
    - Markdown report written to  scripts/e2e_report_<YYYYMMDD_HHMMSS>.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# ── ANSI colours ────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW = "\033[93m"
CYAN  = "\033[96m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def _c(colour: str, text: str) -> str:
    """Wrap text in an ANSI colour if stdout is a TTY."""
    return f"{colour}{text}{RESET}" if sys.stdout.isatty() else text


# ── Data types ───────────────────────────────────────────────────────────────────
@dataclass
class Check:
    """A single assertion within a test case."""
    description: str
    fn: Any  # Callable[[Any], bool]


@dataclass
class TestCase:
    category: str
    name: str
    description: str
    cli_args: list[str]         # args appended to the base inspector command
    checks: list[Check]
    parse_path: str = "structured"  # "structured" | "resource" | "prompt" | "raw"


@dataclass
class TestResult:
    case: TestCase
    passed: bool
    failures: list[str]
    raw_output: str
    duration_ms: float
    skipped: bool = False
    skip_reason: str = ""


# ── Inspector runner ─────────────────────────────────────────────────────────────
BASE_CMD_TEMPLATE = [
    "npx", "@modelcontextprotocol/inspector",
    "--cli",
    "--config", "{config}",
    "--server", "{server}",
]


def _build_base(config: str, server: str) -> list[str]:
    return [
        "npx", "@modelcontextprotocol/inspector",
        "--cli",
        "--config", config,
        "--server", server,
    ]


def run_inspector(
    config: str,
    server: str,
    extra_args: list[str],
    timeout: int,
) -> tuple[bool, str, float]:
    """Run the inspector CLI.  Returns (ok, stdout, duration_ms)."""
    cmd = _build_base(config, server) + extra_args
    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.monotonic() - t0) * 1000
        output = proc.stdout.strip()
        if proc.returncode != 0 and not output:
            return False, proc.stderr.strip()[:400], elapsed
        return True, output, elapsed
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s", (time.monotonic() - t0) * 1000
    except Exception as exc:
        return False, f"Process error: {exc}", (time.monotonic() - t0) * 1000


# ── Response parsers ─────────────────────────────────────────────────────────────
def parse_response(raw: str, parse_path: str) -> tuple[bool, Any, str]:
    """Parse the raw JSON output depending on the endpoint type.

    Returns (ok, data, error_message).
    """
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, None, f"JSON parse error: {exc}"

    if parse_path == "structured":
        # tools/call → { structuredContent: {...}, isError: bool }
        if doc.get("isError"):
            inner = doc.get("content", [{}])
            msg = inner[0].get("text", "unknown error") if inner else "unknown error"
            return False, doc, f"Tool returned isError=true: {msg}"
        data = doc.get("structuredContent") or doc.get("content")
        return True, data, ""

    if parse_path == "resource":
        # resources/read → { contents: [{ text: "..." }] }
        contents = doc.get("contents", [])
        if not contents:
            return False, None, "resources/read returned empty contents"
        text = contents[0].get("text", "")
        return True, text, ""

    if parse_path == "prompt":
        # prompts/get → { messages: [{ role: "user", content: { text: "..." } }] }
        messages = doc.get("messages", [])
        if not messages:
            return False, None, "prompts/get returned no messages"
        text = messages[0].get("content", {}).get("text", "")
        return True, text, ""

    # raw — return the whole doc
    return True, doc, ""


# ── Test suite ────────────────────────────────────────────────────────────────────
def build_test_suite() -> list[TestCase]:
    """Return the ordered list of test cases."""

    # Shorthand builders
    def tool(name: str, args: list[str] | None = None) -> list[str]:
        base = ["--method", "tools/call", "--tool-name", name]
        for a in (args or []):
            base += ["--tool-arg", a]
        return base

    def resource(uri: str) -> list[str]:
        return ["--method", "resources/read", "--uri", uri]

    def prompt(name: str, args: list[str]) -> list[str]:
        return [*["--method", "prompts/get", "--prompt-name", name, "--prompt-args"], *args]

    return [

        # ── Category: Infrastructure ────────────────────────────────────────────
        TestCase(
            category="Infrastructure",
            name="TC-01 • Service health",
            description="get_service_health returns status=healthy with uptime > 0",
            cli_args=tool("get_service_health"),
            parse_path="structured",
            checks=[
                Check("status == 'healthy'",
                      lambda d: isinstance(d, dict) and d.get("status") == "healthy"),
                Check("uptime_seconds > 0",
                      lambda d: isinstance(d, dict) and d.get("uptime_seconds", 0) > 0),
                Check("version is non-empty string",
                      lambda d: isinstance(d, dict) and bool(d.get("version"))),
            ],
        ),

        TestCase(
            category="Infrastructure",
            name="TC-02 • Cache statistics",
            description="get_cache_stats returns numeric counters with hit_rate in [0, 1]",
            cli_args=tool("get_cache_stats"),
            parse_path="structured",
            checks=[
                Check("total_requests >= 0",
                      lambda d: isinstance(d, dict) and d.get("total_requests", -1) >= 0),
                Check("hit_rate in [0.0, 1.0]",
                      lambda d: isinstance(d, dict) and 0.0 <= d.get("hit_rate", -1) <= 1.0),
            ],
        ),

        # ── Category: Discovery (list tools) ────────────────────────────────────
        TestCase(
            category="Discovery",
            name="TC-03 • List frameworks",
            description="list_frameworks returns ≥ 1 framework; each has id, name, description",
            cli_args=tool("list_frameworks"),
            parse_path="structured",
            checks=[
                Check("total_count >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_count", 0) >= 1),
                Check("every framework has non-empty id, name, description",
                      lambda d: isinstance(d, dict) and all(
                          fw.get("id") and fw.get("name") and fw.get("description")
                          for fw in d.get("frameworks", [])
                      )),
                Check("returned count matches total_count",
                      lambda d: isinstance(d, dict) and
                          len(d.get("frameworks", [])) == d.get("total_count", -1)),
            ],
        ),

        TestCase(
            category="Discovery",
            name="TC-04 • List risks",
            description="list_risks returns ≥ 20 risk documents with valid ids",
            cli_args=tool("list_risks"),
            parse_path="structured",
            checks=[
                Check("total_count >= 20",
                      lambda d: isinstance(d, dict) and d.get("total_count", 0) >= 20),
                Check("document_type == 'risk'",
                      lambda d: isinstance(d, dict) and d.get("document_type") == "risk"),
                Check("every document has non-empty id and name",
                      lambda d: isinstance(d, dict) and all(
                          doc.get("id") and doc.get("name")
                          for doc in d.get("documents", [])
                      )),
            ],
        ),

        TestCase(
            category="Discovery",
            name="TC-05 • List mitigations",
            description="list_mitigations returns ≥ 20 mitigation documents",
            cli_args=tool("list_mitigations"),
            parse_path="structured",
            checks=[
                Check("total_count >= 20",
                      lambda d: isinstance(d, dict) and d.get("total_count", 0) >= 20),
                Check("document_type == 'mitigation'",
                      lambda d: isinstance(d, dict) and d.get("document_type") == "mitigation"),
                Check("every document has non-empty id and name",
                      lambda d: isinstance(d, dict) and all(
                          doc.get("id") and doc.get("name")
                          for doc in d.get("documents", [])
                      )),
            ],
        ),

        # ── Category: Document retrieval ─────────────────────────────────────────
        TestCase(
            category="Document retrieval",
            name="TC-06 • get_framework eu-ai-act",
            description="Fetches EU AI Act framework; content is non-empty and not an error message",
            cli_args=tool("get_framework", ["framework=eu-ai-act"]),
            parse_path="structured",
            checks=[
                Check("framework_id == 'eu-ai-act'",
                      lambda d: isinstance(d, dict) and d.get("framework_id") == "eu-ai-act"),
                Check("content length > 200 chars",
                      lambda d: isinstance(d, dict) and len(d.get("content", "")) > 200),
                Check("content does not start with 'Failed'",
                      lambda d: isinstance(d, dict) and
                          not d.get("content", "").startswith("Failed")),
            ],
        ),

        TestCase(
            category="Document retrieval",
            name="TC-07 • get_risk RI-9 title format (T6)",
            description="get_risk returns formatted title 'Data Poisoning (RI-9)' — not raw filename",
            cli_args=tool("get_risk", ["risk_id=9_data-poisoning"]),
            parse_path="structured",
            checks=[
                Check("title == 'Data Poisoning (RI-9)'",
                      lambda d: isinstance(d, dict) and d.get("title") == "Data Poisoning (RI-9)"),
                Check("content length > 100 chars",
                      lambda d: isinstance(d, dict) and len(d.get("content", "")) > 100),
                Check("sections is a list",
                      lambda d: isinstance(d, dict) and isinstance(d.get("sections"), list)),
            ],
        ),

        TestCase(
            category="Document retrieval",
            name="TC-08 • get_risk RI-1 title format (T6)",
            description="get_risk RI-1 title contains 'RI-1' and is not the raw filename",
            cli_args=tool("get_risk", ["risk_id=1_information-leaked-to-hosted-model"]),
            parse_path="structured",
            checks=[
                Check("title contains '(RI-1)'",
                      lambda d: isinstance(d, dict) and "(RI-1)" in d.get("title", "")),
                Check("title does not contain underscores (not raw filename)",
                      lambda d: isinstance(d, dict) and "_" not in d.get("title", "")),
                Check("content is non-empty",
                      lambda d: isinstance(d, dict) and len(d.get("content", "")) > 100),
            ],
        ),

        TestCase(
            category="Document retrieval",
            name="TC-09 • get_mitigation MI-1 title format (T6)",
            description="get_mitigation title is 'AI Data Leakage Prevention and Detection (MI-1)'",
            cli_args=tool("get_mitigation",
                          ["mitigation_id=1_ai-data-leakage-prevention-and-detection"]),
            parse_path="structured",
            checks=[
                Check("title == 'AI Data Leakage Prevention and Detection (MI-1)'",
                      lambda d: isinstance(d, dict) and
                          d.get("title") == "AI Data Leakage Prevention and Detection (MI-1)"),
                Check("content length > 100 chars",
                      lambda d: isinstance(d, dict) and len(d.get("content", "")) > 100),
            ],
        ),

        TestCase(
            category="Document retrieval",
            name="TC-10 • get_risk — invalid ID (graceful error)",
            description="get_risk with unknown ID returns a graceful 'not found' response without crashing",
            cli_args=tool("get_risk", ["risk_id=invalid-risk-xyz-99"]),
            parse_path="structured",
            checks=[
                Check("returns a DocumentContent (has 'title' key)",
                      lambda d: isinstance(d, dict) and "title" in d),
                Check("title or content indicates not-found (no crash)",
                      lambda d: isinstance(d, dict) and (
                          "not found" in d.get("title", "").lower() or
                          "not found" in d.get("content", "").lower()
                      )),
            ],
        ),

        # ── Category: Search ──────────────────────────────────────────────────────
        TestCase(
            category="Search",
            name="TC-11 • search_frameworks 'risk assessment'",
            description="Exact phrase search across frameworks returns ≥ 1 result",
            cli_args=tool("search_frameworks", ["query=risk assessment"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
                Check("results list is non-empty",
                      lambda d: isinstance(d, dict) and len(d.get("results", [])) >= 1),
                Check("every result has a content field",
                      lambda d: isinstance(d, dict) and all(
                          r.get("content") for r in d.get("results", [])
                      )),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-12 • search_risks 'data poisoning' (exact phrase + ranking)",
            description="Exact phrase match ranks first (T8): first result content contains the phrase",
            cli_args=tool("search_risks", ["query=data poisoning"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
                Check("first result content contains 'data poisoning' verbatim (exact match ranked first)",
                      lambda d: isinstance(d, dict) and d.get("results") and
                          "data poisoning" in d["results"][0].get("content", "").lower()),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-13 • search_risks 'customer data privacy' (T7 token fallback)",
            description="Multi-word phrase with no exact match; token fallback should find results",
            cli_args=tool("search_risks", ["query=customer data privacy"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1 (was 0 before T7)",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-14 • search_risks 'model training security'",
            description="Token fallback finds risks related to model training",
            cli_args=tool("search_risks", ["query=model training security"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-15 • search_risks stop-words only → 0 results",
            description="Query containing only stop words must return 0 results",
            cli_args=tool("search_risks", ["query=the is are"]),
            parse_path="structured",
            checks=[
                Check("total_found == 0",
                      lambda d: isinstance(d, dict) and d.get("total_found", -1) == 0),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-16 • search_mitigations 'data protection' (T7 token fallback)",
            description="Token fallback finds mitigations for natural-language query",
            cli_args=tool("search_mitigations", ["query=data protection"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-17 • search_mitigations 'encryption'",
            description="Single-token search returns at least one mitigation result",
            cli_args=tool("search_mitigations", ["query=encryption"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
                Check("every result has framework_id and content",
                      lambda d: isinstance(d, dict) and all(
                          r.get("framework_id") and r.get("content")
                          for r in d.get("results", [])
                      )),
            ],
        ),

        TestCase(
            category="Search",
            name="TC-24 • search_mitigations 'data leakage' (exact phrase + ranking)",
            description="Exact phrase match ranks first (T8): first result content contains the phrase",
            cli_args=tool("search_mitigations", ["query=data leakage"]),
            parse_path="structured",
            checks=[
                Check("total_found >= 1",
                      lambda d: isinstance(d, dict) and d.get("total_found", 0) >= 1),
                Check("first result content contains 'data leakage' verbatim (exact match ranked first)",
                      lambda d: isinstance(d, dict) and d.get("results") and
                          "data leakage" in d["results"][0].get("content", "").lower()),
            ],
        ),

        # ── Category: Resources ───────────────────────────────────────────────────
        TestCase(
            category="Resources",
            name="TC-18 • Resource finos://frameworks/eu-ai-act",
            description="Framework resource returns non-empty markdown content",
            cli_args=resource("finos://frameworks/eu-ai-act"),
            parse_path="resource",
            checks=[
                Check("content length > 100 chars",
                      lambda d: isinstance(d, str) and len(d) > 100),
                Check("content does not start with 'Error'",
                      lambda d: isinstance(d, str) and not d.startswith("Error")),
            ],
        ),

        TestCase(
            category="Resources",
            name="TC-19 • Resource finos://risks/9_data-poisoning",
            description="Risk resource returns markdown with 'poison' in content",
            cli_args=resource("finos://risks/9_data-poisoning"),
            parse_path="resource",
            checks=[
                Check("content length > 100 chars",
                      lambda d: isinstance(d, str) and len(d) > 100),
                Check("content contains 'poison'",
                      lambda d: isinstance(d, str) and "poison" in d.lower()),
            ],
        ),

        TestCase(
            category="Resources",
            name="TC-20 • Resource finos://mitigations/1_ai-data-leakage-prevention-and-detection",
            description="Mitigation resource returns non-empty markdown content",
            cli_args=resource(
                "finos://mitigations/1_ai-data-leakage-prevention-and-detection"
            ),
            parse_path="resource",
            checks=[
                Check("content length > 100 chars",
                      lambda d: isinstance(d, str) and len(d) > 100),
                Check("content contains 'leakage' or 'data'",
                      lambda d: isinstance(d, str) and (
                          "leakage" in d.lower() or "data" in d.lower()
                      )),
            ],
        ),

        # ── Category: Prompts ─────────────────────────────────────────────────────
        TestCase(
            category="Prompts",
            name="TC-21 • Prompt analyze_framework_compliance",
            description="Returns a rich compliance prompt including framework content",
            cli_args=prompt(
                "analyze_framework_compliance",
                ["framework=eu-ai-act",
                 "use_case=deploying a customer-facing LLM chatbot in financial services"],
            ),
            parse_path="prompt",
            checks=[
                Check("prompt text length > 200 chars",
                      lambda d: isinstance(d, str) and len(d) > 200),
                Check("prompt mentions the framework",
                      lambda d: isinstance(d, str) and "eu-ai-act" in d.lower()),
                Check("prompt contains compliance guidance keywords",
                      lambda d: isinstance(d, str) and any(
                          kw in d.lower() for kw in
                          ["compliance", "requirement", "risk", "implement"]
                      )),
            ],
        ),

        TestCase(
            category="Prompts",
            name="TC-22 • Prompt risk_assessment_analysis",
            description="Returns a risk assessment prompt with embedded FINOS risk documentation",
            cli_args=prompt(
                "risk_assessment_analysis",
                ["risk_category=data poisoning",
                 "context=a financial institution fine-tuning an LLM on proprietary trading data"],
            ),
            parse_path="prompt",
            checks=[
                Check("prompt text length > 300 chars",
                      lambda d: isinstance(d, str) and len(d) > 300),
                Check("prompt contains 'RISK CATEGORY'",
                      lambda d: isinstance(d, str) and "RISK CATEGORY" in d),
                Check("prompt contains embedded risk documentation",
                      lambda d: isinstance(d, str) and (
                          "RELEVANT RISK DOCUMENTATION" in d or "RI-" in d
                      )),
            ],
        ),

        TestCase(
            category="Prompts",
            name="TC-23 • Prompt mitigation_strategy_prompt",
            description="Returns a mitigation prompt with embedded FINOS mitigation strategies",
            cli_args=prompt(
                "mitigation_strategy_prompt",
                ["risk_type=privacy leakage",
                 "system_description=LLM assistant integrated with internal HR data and customer PII"],
            ),
            parse_path="prompt",
            checks=[
                Check("prompt text length > 300 chars",
                      lambda d: isinstance(d, str) and len(d) > 300),
                Check("prompt contains 'RISK TYPE'",
                      lambda d: isinstance(d, str) and "RISK TYPE" in d),
                Check("prompt contains mitigation strategies section",
                      lambda d: isinstance(d, str) and (
                          "AVAILABLE MITIGATION" in d or "MI-" in d
                      )),
            ],
        ),
    ]


# ── Runner ────────────────────────────────────────────────────────────────────────
def run_test(tc: TestCase, config: str, server: str, timeout: int) -> TestResult:
    ok, raw, elapsed = run_inspector(config, server, tc.cli_args, timeout)

    if not ok and not raw.startswith("{"):
        return TestResult(
            case=tc, passed=False,
            failures=[f"Inspector call failed: {raw}"],
            raw_output=raw, duration_ms=elapsed,
        )

    parse_ok, data, parse_err = parse_response(raw, tc.parse_path)

    failures: list[str] = []

    if not parse_ok:
        failures.append(parse_err)
    else:
        for check in tc.checks:
            try:
                result = check.fn(data)
                if not result:
                    failures.append(f"FAIL: {check.description}")
            except Exception as exc:
                failures.append(f"ERROR in check '{check.description}': {exc}")

    return TestResult(
        case=tc,
        passed=len(failures) == 0,
        failures=failures,
        raw_output=raw,
        duration_ms=elapsed,
    )


# ── Report generator ──────────────────────────────────────────────────────────────
def _badge(passed: bool) -> str:
    return "✅ PASS" if passed else "❌ FAIL"


def generate_markdown_report(
    results: list[TestResult],
    config: str,
    server: str,
    total_ms: float,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    categories: dict[str, list[TestResult]] = {}
    for r in results:
        categories.setdefault(r.case.category, []).append(r)

    lines: list[str] = []
    lines.append("# FINOS MCP Server — End-to-End Smoke Test Report")
    lines.append(f"\n**Date:** {now}  ")
    lines.append(f"**Config:** `{config}`  ")
    lines.append(f"**Server:** `{server}`  ")
    lines.append(f"**Total duration:** {total_ms / 1000:.1f}s\n")

    lines.append("## Summary\n")
    lines.append("| Result | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| ✅ Passed | **{passed}** |")
    lines.append(f"| ❌ Failed | **{failed}** |")
    lines.append(f"| Total  | **{len(results)}** |")

    overall = "✅ ALL TESTS PASSED" if failed == 0 else f"❌ {failed} TEST(S) FAILED"
    lines.append(f"\n**Overall: {overall}**\n")

    lines.append("---\n")
    lines.append("## Results by Category\n")

    for category, cat_results in categories.items():
        cat_pass = sum(1 for r in cat_results if r.passed)
        lines.append(f"### {category}  ({cat_pass}/{len(cat_results)} passed)\n")
        lines.append("| # | Test | Result | Duration | Details |")
        lines.append("|---|------|--------|----------|---------|")
        for r in cat_results:
            badge = _badge(r.passed)
            dur = f"{r.duration_ms:.0f} ms"
            if r.passed:
                detail = "All checks passed"
            else:
                detail = "; ".join(r.failures[:2])
                if len(r.failures) > 2:
                    detail += f" (+{len(r.failures) - 2} more)"
            # Escape pipes in detail
            detail = detail.replace("|", "\\|")
            lines.append(f"| {r.case.name[:6]} | {r.case.description} | {badge} | {dur} | {detail} |")
        lines.append("")

    # Failed test details
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        lines.append("---\n")
        lines.append("## Failed Test Details\n")
        for r in failed_results:
            lines.append(f"### {r.case.name}\n")
            lines.append(f"**Description:** {r.case.description}\n")
            lines.append("**Failures:**\n")
            for f in r.failures:
                lines.append(f"- {f}")
            lines.append("\n**Raw output (first 600 chars):**\n")
            lines.append("```json")
            lines.append(r.raw_output[:600])
            lines.append("```\n")

    lines.append("---\n")
    lines.append("## Test Case Reference\n")
    lines.append("| ID | Category | Name | CLI method |")
    lines.append("|----|----------|------|------------|")
    for r in results:
        method_flag = next(
            (r.case.cli_args[i + 1] for i, a in enumerate(r.case.cli_args)
             if a == "--method"),
            "?"
        )
        lines.append(
            f"| {r.case.name[:6]} | {r.case.category} | "
            f"{r.case.description[:60]} | `{method_flag}` |"
        )
    lines.append("")
    lines.append("---")
    lines.append("*Generated by `scripts/e2e_smoke_test.py`*")

    return "\n".join(lines)


# ── CLI entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="FINOS MCP Server end-to-end smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="/tmp/finos-inspector-config.json",  # noqa: S108
        help="Path to the MCP Inspector config file (default: /tmp/finos-inspector-config.json)",
    )
    parser.add_argument(
        "--server",
        default="finos",
        help="Server name inside the config file (default: finos)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Seconds to wait per test before timing out (default: 45)",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Only run tests whose name contains this string (case-insensitive)",
    )
    args = parser.parse_args()

    suite = build_test_suite()
    if args.filter:
        suite = [tc for tc in suite if args.filter.lower() in tc.name.lower()]
        if not suite:
            print(f"No tests match filter '{args.filter}'")
            sys.exit(1)

    # Header
    print()
    print(_c(BOLD, "=" * 60))
    print(_c(BOLD, "  FINOS MCP Server — End-to-End Smoke Test"))
    print(_c(BOLD, "=" * 60))
    print(f"  Config : {args.config}")
    print(f"  Server : {args.server}")
    print(f"  Tests  : {len(suite)}")
    print(f"  Timeout: {args.timeout}s per test")
    print()

    results: list[TestResult] = []
    current_category = ""
    wall_t0 = time.monotonic()

    for tc in suite:
        if tc.category != current_category:
            current_category = tc.category
            print(_c(CYAN, f"\n── {current_category} " + "─" * (44 - len(current_category))))

        print(f"  {tc.name} … ", end="", flush=True)
        result = run_test(tc, args.config, args.server, args.timeout)
        results.append(result)

        dur = f"{result.duration_ms:.0f}ms"
        if result.passed:
            print(_c(GREEN, "PASS") + f"  ({dur})")
        else:
            print(_c(RED, "FAIL") + f"  ({dur})")
            for failure in result.failures:
                print(f"    {_c(YELLOW, '→')} {failure}")

    total_ms = (time.monotonic() - wall_t0) * 1000
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    # Summary
    print()
    print(_c(BOLD, "=" * 60))
    if failed == 0:
        print(_c(GREEN, _c(BOLD, f"  ALL {passed} TESTS PASSED")))
    else:
        print(_c(RED, _c(BOLD, f"  {failed} FAILED, {passed} PASSED  ({len(results)} total)")))
    print(f"  Total time: {total_ms / 1000:.1f}s")
    print(_c(BOLD, "=" * 60))

    # Write report
    report_md = generate_markdown_report(results, args.config, args.server, total_ms)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"scripts/e2e_report_{ts}.md"
    with open(report_path, "w") as fh:
        fh.write(report_md)
    print(f"\n  Report written → {_c(CYAN, report_path)}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
