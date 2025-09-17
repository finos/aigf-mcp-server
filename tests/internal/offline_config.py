"""
Offline development mode configuration.
Provides utilities for running tests without external dependencies.
"""

import json
import os
from pathlib import Path
from typing import Any


class OfflineConfig:
    """Configuration for offline development mode."""

    def __init__(self):
        self.fixtures_dir = Path("tests/fixtures")
        self.responses_dir = self.fixtures_dir / "responses"
        self.mock_data_dir = self.fixtures_dir / "mock_data"

    def is_offline_mode(self) -> bool:
        """Check if offline mode is enabled."""
        return os.getenv("FINOS_MCP_OFFLINE_MODE", "false").lower() == "true"

    def get_mock_response(self, response_type: str) -> dict[str, Any]:
        """Get mock response data for testing."""
        response_file = self.responses_dir / f"{response_type}.json"
        if response_file.exists():
            with open(response_file) as f:
                return json.load(f)
        return {}

    def get_mock_file_list(self, list_type: str) -> list[str]:
        """Get mock file list for testing."""
        list_file = self.mock_data_dir / f"{list_type}_files.json"
        if list_file.exists():
            with open(list_file) as f:
                return json.load(f)
        return []


# Global instance
offline_config = OfflineConfig()
