"""Backward-compatible re-exports for OpenEMCP envelope primitives."""

from ..compat.openemcp_envelope import OpenEMCPEnvelope, OpenEMCPPhase, create_envelope

__all__ = ["OpenEMCPEnvelope", "OpenEMCPPhase", "create_envelope"]
