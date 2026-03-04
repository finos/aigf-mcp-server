"""Unit tests for OpenEMCP status normalization."""

import pytest

from finos_mcp.openemcp.status import (
    OpenEMCPValidationStatus,
    normalize_validation_status,
)


@pytest.mark.unit
class TestOpenEMCPStatusNormalization:
    """Validate canonical status normalization rules."""

    @pytest.mark.parametrize(
        ("raw_status", "expected"),
        [
            ("approved", OpenEMCPValidationStatus.APPROVED),
            ("accept", OpenEMCPValidationStatus.APPROVED),
            ("pass", OpenEMCPValidationStatus.APPROVED),
            ("reject", OpenEMCPValidationStatus.REJECTED),
            ("blocked", OpenEMCPValidationStatus.REJECTED),
            ("fail", OpenEMCPValidationStatus.REJECTED),
            ("modified", OpenEMCPValidationStatus.MODIFIED),
            ("countered", OpenEMCPValidationStatus.MODIFIED),
            ("needs_changes", OpenEMCPValidationStatus.MODIFIED),
        ],
    )
    def test_maps_known_statuses(self, raw_status, expected):
        assert normalize_validation_status(raw_status) == expected

    def test_unknown_value_defaults_to_modified(self):
        assert (
            normalize_validation_status("pending_manual_review")
            == OpenEMCPValidationStatus.MODIFIED
        )

    def test_missing_value_defaults_to_modified(self):
        assert normalize_validation_status(None) == OpenEMCPValidationStatus.MODIFIED
        assert normalize_validation_status("") == OpenEMCPValidationStatus.MODIFIED
