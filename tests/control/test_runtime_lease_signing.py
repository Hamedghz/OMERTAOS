from __future__ import annotations

import base64

import pytest

from control.scheduling.lease_signing import LeaseSigner, LeaseSigningError


def test_lease_signing_is_deterministic_and_binds_every_dispatch_field() -> None:
    signer = LeaseSigner.from_encoded(base64.b64encode(b"k" * 32).decode())
    fields = {
        "tenant_id": "tenant-a",
        "task_id": "task-a",
        "attempt_id": "task-a:0",
        "node_id": "runtime-a",
        "generation": 7,
        "expires_at_ms": 2_000_000_000_000,
        "nonce": bytes(range(32)),
    }

    token = signer.sign(**fields)

    assert token == signer.sign(**fields)
    assert len(token.split(".")) == 2
    for field, replacement in (
        ("tenant_id", "tenant-b"),
        ("task_id", "task-b"),
        ("attempt_id", "task-a:1"),
        ("node_id", "runtime-b"),
        ("generation", 8),
        ("expires_at_ms", 2_000_000_000_001),
        ("nonce", bytes(reversed(range(32)))),
    ):
        changed = fields | {field: replacement}
        assert signer.sign(**changed) != token


def test_lease_signer_rejects_missing_or_invalid_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMERTA_RUNTIME_LEASE_HMAC_KEY", raising=False)
    with pytest.raises(LeaseSigningError, match="is required"):
        LeaseSigner.from_env()
    with pytest.raises(LeaseSigningError, match="valid base64"):
        LeaseSigner.from_encoded("not-base64")
    with pytest.raises(LeaseSigningError, match="32-64 bytes"):
        LeaseSigner.from_encoded(base64.b64encode(b"short").decode())


def test_unreleased_aion_draft_name_is_not_a_lease_key_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OMERTA_RUNTIME_LEASE_HMAC_KEY", raising=False)
    monkeypatch.setenv(
        "AION_RUNTIME_LEASE_HMAC_KEY",
        base64.b64encode(b"legacy-draft-key-material-32-byte").decode(),
    )

    with pytest.raises(LeaseSigningError, match="OMERTA_RUNTIME_LEASE_HMAC_KEY"):
        LeaseSigner.from_env()


def test_lease_signer_repr_redacts_key() -> None:
    encoded = base64.b64encode(b"sensitive-runtime-lease-key-12345").decode()

    rendered = repr(LeaseSigner.from_encoded(encoded))

    assert "sensitive-runtime-lease-key" not in rendered
    assert encoded not in rendered
