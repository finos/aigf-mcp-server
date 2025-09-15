"""
Mock content service for fast test mode.
Provides minimal implementation for testing infrastructure.
"""

import asyncio
from typing import Any


class MockContentService:
    """Mock service for document retrieval during testing."""

    def __init__(self):
        self._cache = {}

    async def get_document(self, doc_type: str, filename: str) -> dict[str, Any] | None:
        """Get document by type and filename."""
        # Check if fast mode is active via global context
        try:
            from finos_mcp.internal.testing import _fast_mode_context

            fast_mode = _fast_mode_context
        except ImportError:
            fast_mode = None

        if fast_mode and fast_mode.is_active:
            # Fast mode: record cache hit
            fast_mode._record_cache_hit()
        else:
            # Simulate network delay in normal mode
            await asyncio.sleep(0.1)

        # Mock document data
        if doc_type == "mitigation":
            return {
                "filename": filename,
                "type": "mitigation",
                "content": f"# {filename}\n\nThis is a mock mitigation document.",
                "metadata": {"title": "Mock Mitigation"},
            }
        elif doc_type == "risk":
            return {
                "filename": filename,
                "type": "risk",
                "content": f"# {filename}\n\nThis is a mock risk document.",
                "metadata": {"title": "Mock Risk"},
            }

        return None


async def get_mock_content_service() -> MockContentService:
    """Get mock content service instance."""
    return MockContentService()
