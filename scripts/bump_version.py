#!/usr/bin/env python3
"""
Version bumping script for semantic versioning
Supports: major, minor, patch, alpha, beta, rc releases
"""

import re
import sys
from pathlib import Path
from typing import Tuple


def get_current_version() -> str:
    """Extract current version from pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    content = pyproject_path.read_text()
    version_match = re.search(r'version = "([^"]+)"', content)

    if not version_match:
        raise ValueError("Version not found in pyproject.toml")

    return version_match.group(1)


def parse_version(version: str) -> Tuple[int, int, int, str]:
    """Parse semantic version into components"""
    # Remove 'v' prefix if present
    version = version.lstrip("v")

    # Handle prerelease versions (e.g., 1.0.0-alpha.1)
    if "-" in version:
        base_version, prerelease = version.split("-", 1)
    else:
        base_version, prerelease = version, ""

    # Parse major.minor.patch
    parts = base_version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    try:
        major, minor, patch = map(int, parts)
    except ValueError as e:
        raise ValueError(f"Invalid version format: {version}") from e

    return major, minor, patch, prerelease


def bump_version(current: str, bump_type: str) -> str:
    """Bump version according to semantic versioning rules"""
    major, minor, patch, prerelease = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "alpha":
        if prerelease.startswith("alpha"):
            # Bump alpha number
            alpha_match = re.match(r"alpha\.(\d+)", prerelease)
            if alpha_match:
                alpha_num = int(alpha_match.group(1)) + 1
            else:
                alpha_num = 1
            return f"{major}.{minor}.{patch}-alpha.{alpha_num}"
        else:
            # First alpha of next minor version
            return f"{major}.{minor + 1}.0-alpha.1"
    elif bump_type == "beta":
        if prerelease.startswith("beta"):
            # Bump beta number
            beta_match = re.match(r"beta\.(\d+)", prerelease)
            if beta_match:
                beta_num = int(beta_match.group(1)) + 1
            else:
                beta_num = 1
            return f"{major}.{minor}.{patch}-beta.{beta_num}"
        else:
            # First beta (from alpha or new)
            return f"{major}.{minor}.{patch}-beta.1"
    elif bump_type == "rc":
        if prerelease.startswith("rc"):
            # Bump rc number
            rc_match = re.match(r"rc\.(\d+)", prerelease)
            if rc_match:
                rc_num = int(rc_match.group(1)) + 1
            else:
                rc_num = 1
            return f"{major}.{minor}.{patch}-rc.{rc_num}"
        else:
            # First rc
            return f"{major}.{minor}.{patch}-rc.1"
    elif bump_type == "release":
        # Remove prerelease suffix for final release
        return f"{major}.{minor}.{patch}"
    else:
        raise ValueError(
            f"Invalid bump type: {bump_type}. Use: major, minor, patch, alpha, beta, rc, release"
        )


def update_version_files(new_version: str) -> None:
    """Update version in all relevant files"""
    # Update pyproject.toml
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content)
    pyproject_path.write_text(content)
    print(f"Updated pyproject.toml: {new_version}")

    # Update src/finos_mcp/__init__.py
    init_path = Path("src/finos_mcp/__init__.py")
    if init_path.exists():
        content = init_path.read_text()
        content = re.sub(
            r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content
        )
        init_path.write_text(content)
        print(f"Updated __init__.py: {new_version}")


def main():
    """Main version bumping logic"""
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py <bump_type>")
        print("Bump types: major, minor, patch, alpha, beta, rc, release")
        print()
        print("Examples:")
        print("  python scripts/bump_version.py patch    # 1.0.0 -> 1.0.1")
        print("  python scripts/bump_version.py minor    # 1.0.0 -> 1.1.0")
        print("  python scripts/bump_version.py major    # 1.0.0 -> 2.0.0")
        print("  python scripts/bump_version.py alpha    # 1.0.0 -> 1.1.0-alpha.1")
        print("  python scripts/bump_version.py release  # 1.1.0-rc.1 -> 1.1.0")
        sys.exit(1)

    bump_type = sys.argv[1]

    try:
        current_version = get_current_version()
        new_version = bump_version(current_version, bump_type)

        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")

        # Confirm before making changes
        response = input("Update version files? (y/N): ")
        if response.lower() == "y":
            update_version_files(new_version)
            print(f"\n✅ Version bumped from {current_version} to {new_version}")
            print("Next steps:")
            print("  1. git add .")
            print(f"  2. git commit -m 'chore: bump version to {new_version}'")
            print(f"  3. git tag v{new_version}")
            print("  4. git push origin main --tags")
        else:
            print("Version bump cancelled")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
