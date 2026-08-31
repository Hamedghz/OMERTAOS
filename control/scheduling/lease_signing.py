from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
from dataclasses import dataclass, field
from pathlib import Path


LEASE_HMAC_ENV = "OMERTA_RUNTIME_LEASE_HMAC_KEY"
LEASE_HMAC_FILE_ENV = "OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE"
_DOMAIN = b"OMERTA_RUNTIME_LEASE_V1\x00"
_MIN_KEY_BYTES = 32
_MAX_KEY_BYTES = 64
_NONCE_BYTES = 32


class LeaseSigningError(RuntimeError):
    """Raised when execution-lease signing is unavailable or invalid."""


def _encoded_key_from_environment() -> str:
    encoded = os.getenv(LEASE_HMAC_ENV, "")
    key_file = os.getenv(LEASE_HMAC_FILE_ENV, "")
    if encoded and key_file:
        raise LeaseSigningError(
            f"set exactly one of {LEASE_HMAC_ENV} or {LEASE_HMAC_FILE_ENV}"
        )
    if encoded:
        return encoded
    if not key_file:
        raise LeaseSigningError(
            f"one of {LEASE_HMAC_ENV} or {LEASE_HMAC_FILE_ENV} is required"
        )
    try:
        raw = Path(key_file).read_bytes()
    except OSError as error:
        raise LeaseSigningError(f"{LEASE_HMAC_FILE_ENV} cannot be read") from error
    if len(raw) > 256:
        raise LeaseSigningError(f"{LEASE_HMAC_FILE_ENV} contains invalid key material")
    try:
        return raw.rstrip(b"\r\n").decode("ascii")
    except UnicodeDecodeError as error:
        raise LeaseSigningError(f"{LEASE_HMAC_FILE_ENV} must contain ASCII base64") from error


def _decode_key(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise LeaseSigningError(
            f"{LEASE_HMAC_ENV} must be valid base64"
        ) from error
    if not _MIN_KEY_BYTES <= len(key) <= _MAX_KEY_BYTES:
        raise LeaseSigningError(
            f"{LEASE_HMAC_ENV} must decode to {_MIN_KEY_BYTES}-{_MAX_KEY_BYTES} bytes"
        )
    return key


def _encode_part(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _payload(
    *,
    tenant_id: str,
    task_id: str,
    attempt_id: str,
    node_id: str,
    nonce: bytes,
    generation: int,
    expires_at_ms: int,
) -> bytes:
    if generation <= 0 or expires_at_ms <= 0:
        raise LeaseSigningError("lease generation and expiry must be positive")
    return b"".join(
        (
            _DOMAIN,
            _encode_part(tenant_id),
            _encode_part(task_id),
            _encode_part(attempt_id),
            _encode_part(node_id),
            struct.pack(">I", len(nonce)),
            nonce,
            struct.pack(">Q", generation),
            struct.pack(">Q", expires_at_ms),
        )
    )


def _urlsafe(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class LeaseSigner:
    _key: bytes = field(repr=False)

    @classmethod
    def from_env(cls) -> LeaseSigner:
        return cls(_decode_key(_encoded_key_from_environment()))

    @classmethod
    def from_encoded(cls, encoded: str) -> LeaseSigner:
        return cls(_decode_key(encoded))

    def sign(
        self,
        *,
        tenant_id: str,
        task_id: str,
        attempt_id: str,
        node_id: str,
        generation: int,
        expires_at_ms: int,
        nonce: bytes | None = None,
    ) -> str:
        resolved_nonce = nonce if nonce is not None else secrets.token_bytes(_NONCE_BYTES)
        if len(resolved_nonce) != _NONCE_BYTES:
            raise LeaseSigningError(f"lease nonce must be {_NONCE_BYTES} bytes")
        payload = _payload(
            tenant_id=tenant_id,
            task_id=task_id,
            attempt_id=attempt_id,
            node_id=node_id,
            nonce=resolved_nonce,
            generation=generation,
            expires_at_ms=expires_at_ms,
        )
        signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        return f"{_urlsafe(resolved_nonce)}.{_urlsafe(signature)}"
