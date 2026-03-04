"""Internal OpenEMCP compatibility primitives."""

from .compat import OpenEMCPEnvelope, OpenEMCPPhase, create_envelope
from .status import OpenEMCPValidationStatus, normalize_validation_status

__all__ = [
    "OpenEMCPEnvelope",
    "OpenEMCPPhase",
    "OpenEMCPValidationStatus",
    "create_envelope",
    "normalize_validation_status",
]
