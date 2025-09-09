#!/usr/bin/env python3
"""
Simple functionality test for the FINOS MCP Server.

This basic test ensures core functionality works correctly.
Used by other test suites to validate system stability.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    import finos_mcp
    import finos_mcp.server
    from finos_mcp.config import get_settings
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


async def test_basic_functionality() -> bool:
    """Test basic functionality of the MCP server."""
    try:
        # Test 1: Package imports correctly
        print("🧪 Testing package import...")
        assert hasattr(finos_mcp, "__version__")
        print(f"✅ Package version: {finos_mcp.__version__}")

        # Test 2: Configuration loads
        print("🧪 Testing configuration...")
        settings = get_settings()
        assert settings is not None
        print("✅ Configuration loaded")

        # Test 3: Server can be imported
        print("🧪 Testing server import...")
        assert hasattr(finos_mcp.server, "get_mitigation_files")
        assert hasattr(finos_mcp.server, "get_risk_files")
        print("✅ Server module imported")

        # Test 4: Basic data structures exist
        print("🧪 Testing data structures...")
        mitigation_files = await finos_mcp.server.get_mitigation_files()
        risk_files = await finos_mcp.server.get_risk_files()
        assert len(mitigation_files) > 0
        assert len(risk_files) > 0
        print(f"✅ Found {len(mitigation_files)} mitigations, {len(risk_files)} risks")

        print("🎉 All basic functionality tests passed!")
        return True

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def main() -> None:
    """Main test function."""
    print("🚀 Running simple functionality test...")

    try:
        success = asyncio.run(test_basic_functionality())
        if success:
            print("✅ Simple test completed successfully")
            sys.exit(0)
        else:
            print("❌ Simple test failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
