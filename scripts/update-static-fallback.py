#!/usr/bin/env python3
"""Script to update static fallback file lists from GitHub API.

This ensures the static fallback matches the actual repository content.
Run this script periodically to keep the fallback data synchronized.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from finos_mcp.content.discovery import DiscoveryServiceManager


async def get_current_files():
    """Fetch current file lists from GitHub API."""
    print("Fetching current file lists from GitHub API...")

    discovery_manager = DiscoveryServiceManager()
    discovery_service = await discovery_manager.get_discovery_service()
    discovery_result = await discovery_service.discover_content()

    if discovery_result.source != "github_api":
        print(f"WARNING: Using {discovery_result.source} instead of github_api")
        print("Make sure GitHub API is accessible!")
        return None

    # Sort files for consistent ordering
    mitigation_files = sorted([f.filename for f in discovery_result.mitigation_files])
    risk_files = sorted([f.filename for f in discovery_result.risk_files])
    framework_files = sorted([f.filename for f in discovery_result.framework_files])

    print(f"\n✓ Found {len(mitigation_files)} mitigation files")
    print(f"✓ Found {len(risk_files)} risk files")
    print(f"✓ Found {len(framework_files)} framework files")

    return {
        "mitigations": mitigation_files,
        "risks": risk_files,
        "frameworks": framework_files,
    }


def format_python_list(files, indent=4):
    """Format file list as Python code."""
    indent_str = " " * indent
    lines = ["["]
    for filename in files:
        lines.append(f'{indent_str}"{filename}",')
    lines.append("]")
    return "\n".join(lines)


def generate_updated_code(files):
    """Generate the updated Python code for discovery.py."""
    code = f'''# Static fallback file lists (auto-generated - do not edit manually)
# To update: python scripts/update-static-fallback.py

STATIC_MITIGATION_FILES = {format_python_list(files["mitigations"])}

STATIC_RISK_FILES = {format_python_list(files["risks"])}

STATIC_FRAMEWORK_FILES = {format_python_list(files["frameworks"])}
'''
    return code


async def main():
    """Main function."""
    files = await get_current_files()

    if not files:
        print("\n✗ Failed to fetch files from GitHub API")
        return 1

    # Generate updated code
    updated_code = generate_updated_code(files)

    print("\n" + "=" * 80)
    print("GENERATED CODE (copy to discovery.py lines 27-67):")
    print("=" * 80)
    print(updated_code)
    print("=" * 80)

    # Also save to a file
    output_file = Path(__file__).parent.parent / "static_fallback_lists.py"
    output_file.write_text(updated_code)
    print(f"\n✓ Also saved to: {output_file}")

    print("\nTo apply the update:")
    print("1. Review the generated code above")
    print("2. Replace lines 27-67 in src/finos_mcp/content/discovery.py")
    print("3. Or run: python scripts/apply-static-fallback-update.py")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
