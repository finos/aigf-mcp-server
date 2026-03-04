"""Canonical status normalization for internal OpenEMCP compatibility."""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OpenEMCPValidationStatus(str, Enum):
    """Canonical OpenEMCP validation decisions."""

    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


_STATUS_MAP: dict[str, OpenEMCPValidationStatus] = {
    "approved": OpenEMCPValidationStatus.APPROVED,
    "approve": OpenEMCPValidationStatus.APPROVED,
    "accepted": OpenEMCPValidationStatus.APPROVED,
    "accept": OpenEMCPValidationStatus.APPROVED,
    "ok": OpenEMCPValidationStatus.APPROVED,
    "pass": OpenEMCPValidationStatus.APPROVED,
    "allowed": OpenEMCPValidationStatus.APPROVED,
    "rejected": OpenEMCPValidationStatus.REJECTED,
    "reject": OpenEMCPValidationStatus.REJECTED,
    "denied": OpenEMCPValidationStatus.REJECTED,
    "deny": OpenEMCPValidationStatus.REJECTED,
    "blocked": OpenEMCPValidationStatus.REJECTED,
    "fail": OpenEMCPValidationStatus.REJECTED,
    "modified": OpenEMCPValidationStatus.MODIFIED,
    "countered": OpenEMCPValidationStatus.MODIFIED,
    "needs_changes": OpenEMCPValidationStatus.MODIFIED,
    "amended": OpenEMCPValidationStatus.MODIFIED,
}


def normalize_validation_status(
    raw_status: str | None,
) -> OpenEMCPValidationStatus:
    """Normalize free-form status into the canonical OpenEMCP enum."""
    if not raw_status:
        return OpenEMCPValidationStatus.MODIFIED

    normalized = _STATUS_MAP.get(raw_status.strip().lower())
    if normalized is None:
        logger.warning(
            "Unknown validation status '%s'; defaulting to 'modified'",
            raw_status,
        )
        return OpenEMCPValidationStatus.MODIFIED

    return normalized
