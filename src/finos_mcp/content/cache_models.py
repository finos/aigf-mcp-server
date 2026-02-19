"""
Secure cache data models using Pydantic validation.

Replaces pickle serialization with secure JSON + Pydantic validation
to prevent RCE vulnerabilities while maintaining type safety.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CacheDataType(str, Enum):
    """Supported cache data types for validation."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    NONE = "none"


class CacheEntryMetadata(BaseModel):
    """Metadata for cache entries with security validation."""

    entry_type: CacheDataType = Field(..., description="Type of cached data")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_size: int = Field(..., ge=0, description="Size of data in bytes")
    compression_used: bool = Field(default=False, description="Was compression applied")
    integrity_hash: str | None = Field(None, description="Data integrity hash")

    @field_validator("data_size")
    @classmethod
    def validate_data_size(cls, v: int) -> int:
        """Validate data size limits for security.

        Aligned with cache.MAX_OBJECT_SIZE (10 MB) so that an object that
        passes the serialisation-layer size check will also pass Pydantic
        model validation. Previously this cap was 1 MB while the cache layer
        allowed 10 MB, producing inconsistent rejections.
        """
        max_size = 10_000_000  # 10 MB — must match cache.MAX_OBJECT_SIZE
        if v > max_size:
            raise ValueError(f"Data size {v} exceeds maximum allowed {max_size} bytes")
        return v

    @field_validator("integrity_hash")
    @classmethod
    def validate_integrity_hash(cls, v: str | None) -> str | None:
        """Validate integrity hash format."""
        if v is not None and (not isinstance(v, str) or len(v) != 64):
            raise ValueError("Integrity hash must be a 64-character SHA-256 hex string")
        return v


class SecureCacheEntry(BaseModel):
    """Secure cache entry with Pydantic validation."""

    key: str = Field(..., description="Cache key")
    data: str | int | float | bool | list[Any] | dict[str, Any] | None = Field(
        ..., description="Cached data (JSON-serializable only)"
    )
    metadata: CacheEntryMetadata = Field(..., description="Entry metadata")
    ttl: int = Field(..., ge=0, description="Time-to-live in seconds")
    created_timestamp: float = Field(..., description="Creation timestamp")

    @field_validator("key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        """Validate cache key format for security."""
        if not v or not isinstance(v, str):
            raise ValueError("Cache key must be a non-empty string")

        # Prevent path traversal in keys (allow colons for framework:filename format)
        if any(char in v for char in ["../", "/", "\\", "*", "?", "<", ">", "|"]):
            raise ValueError("Cache key contains invalid characters")

        if len(v) > 255:
            raise ValueError("Cache key too long (max 255 characters)")

        return v.strip()

    @field_validator("data")
    @classmethod
    def validate_data_security(
        cls, v: str | int | float | bool | list[Any] | dict[str, Any] | None
    ) -> str | int | float | bool | list[Any] | dict[str, Any] | None:
        """Validate data for security and JSON serializability."""
        # Check if data is JSON-serializable
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Data must be JSON-serializable: {e}") from e

        # Prevent dangerous data types
        if callable(v):  # Functions
            raise ValueError("Functions are not allowed in cache data")

        if hasattr(v, "__reduce__"):  # Objects with pickle methods
            # Allow basic types that have __reduce__ but are safe
            safe_types = (str, int, float, bool, list, dict, type(None))
            if not isinstance(v, safe_types):
                raise ValueError("Objects with __reduce__ method are not allowed")

        # Validate data size — aligned with cache.MAX_OBJECT_SIZE (10 MB)
        data_str = json.dumps(v)
        if len(data_str.encode("utf-8")) > 10_000_000:
            raise ValueError("Data size exceeds 10 MB limit")

        return v

    @field_validator("ttl")
    @classmethod
    def validate_ttl_range(cls, v: int) -> int:
        """Validate TTL is within reasonable bounds."""
        max_ttl = 86400 * 30  # 30 days max
        if v > max_ttl:
            raise ValueError(f"TTL {v} exceeds maximum {max_ttl} seconds")
        return v

    def calculate_integrity_hash(self, secret_key: str) -> str:
        """Calculate HMAC-SHA256 integrity hash for the data."""
        data_json = json.dumps(self.data, sort_keys=True, separators=(",", ":"))
        message = f"{self.key}:{data_json}:{self.ttl}:{self.created_timestamp}"
        return hmac.new(
            secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify_integrity(self, secret_key: str) -> bool:
        """Verify data integrity using HMAC."""
        if not self.metadata.integrity_hash:
            return False

        expected_hash = self.calculate_integrity_hash(secret_key)
        return hmac.compare_digest(self.metadata.integrity_hash, expected_hash)


class CacheValidationError(Exception):
    """Raised when cache data validation fails."""

    pass


class CacheSecurityError(Exception):
    """Raised when cache security validation fails."""

    pass


def determine_data_type(data: Any) -> CacheDataType:
    """Determine the cache data type for validation."""
    if data is None:
        return CacheDataType.NONE
    elif isinstance(data, bool):  # Check bool before int (bool is subclass of int)
        return CacheDataType.BOOLEAN
    elif isinstance(data, int):
        return CacheDataType.INTEGER
    elif isinstance(data, float):
        return CacheDataType.FLOAT
    elif isinstance(data, str):
        return CacheDataType.STRING
    elif isinstance(data, list):
        return CacheDataType.LIST
    elif isinstance(data, dict):
        return CacheDataType.DICT
    else:
        raise CacheValidationError(f"Unsupported data type: {type(data)}")


def validate_json_serializable(data: Any) -> bool:
    """Validate that data is JSON-serializable."""
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


def secure_cache_serializer(data: Any, key: str, ttl: int, secret_key: str) -> str:
    """Securely serialize cache data to JSON with validation."""
    import time

    # Determine data type
    data_type = determine_data_type(data)

    # Calculate data size
    data_json = json.dumps(data, separators=(",", ":"))
    data_size = len(data_json.encode("utf-8"))

    # Create timestamp
    timestamp = time.time()

    # Create cache entry
    entry = SecureCacheEntry(
        key=key,
        data=data,
        metadata=CacheEntryMetadata(
            entry_type=data_type,
            data_size=data_size,
            compression_used=False,
            integrity_hash=None,  # Will be set below
        ),
        ttl=ttl,
        created_timestamp=timestamp,
    )

    # Calculate and set integrity hash
    integrity_hash = entry.calculate_integrity_hash(secret_key)
    entry.metadata.integrity_hash = integrity_hash

    # Serialize to JSON
    return entry.model_dump_json()


def secure_cache_deserializer(serialized_data: str, secret_key: str) -> Any:
    """Securely deserialize cache data from JSON with validation."""
    try:
        # Parse JSON
        entry_dict = json.loads(serialized_data)

        # Validate with Pydantic
        entry = SecureCacheEntry.model_validate(entry_dict)

        # Verify integrity
        if not entry.verify_integrity(secret_key):
            raise CacheSecurityError("Cache entry integrity verification failed")

        # Return the actual data
        return entry.data

    except json.JSONDecodeError as e:
        raise CacheValidationError(f"Invalid JSON in cache data: {e}") from e
    except Exception as e:
        raise CacheValidationError(f"Cache data validation failed: {e}") from e


# Security configuration
class CacheSecurityConfig(BaseModel):
    """Configuration for cache security settings."""

    secret_key: str = Field(..., description="Secret key for HMAC integrity")
    max_entry_size: int = Field(
        default=1024 * 1024, description="Max entry size in bytes"
    )
    max_ttl: int = Field(default=86400 * 30, description="Max TTL in seconds")
    enable_integrity_check: bool = Field(
        default=True, description="Enable integrity checking"
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key strength."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        return v
