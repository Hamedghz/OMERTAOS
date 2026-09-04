from __future__ import annotations

import json

import pytest

from control.app.network.service import LocalSecretProvider
from shared.secret_store.provider import SecretProviderError


LOCAL_AES_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


def test_local_proxy_secrets_are_encrypted_at_rest(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AION_CONTROL_SECRET_DIR", raising=False)
    monkeypatch.delenv("AION_CONTROL_LOCAL_SECRET_KEY", raising=False)
    monkeypatch.setenv("OMERTA_CONTROL_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("OMERTA_CONTROL_LOCAL_SECRET_KEY", LOCAL_AES_KEY)
    provider = LocalSecretProvider()

    provider.set_secret("network/profile-1", {"password": "do-not-store-in-plaintext"})

    stored = provider._file("network/profile-1").read_bytes()
    assert b"do-not-store-in-plaintext" not in stored
    assert provider.get_secret("network/profile-1") == {"password": "do-not-store-in-plaintext"}


def test_legacy_plaintext_proxy_secret_is_migrated_on_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AION_CONTROL_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("AION_CONTROL_LOCAL_SECRET_KEY", LOCAL_AES_KEY)
    provider = LocalSecretProvider()
    secret_file = provider._file("network/profile-legacy")
    secret_file.write_text(json.dumps({"password": "legacy-secret"}), encoding="utf-8")

    assert provider.get_secret("network/profile-legacy") == {"password": "legacy-secret"}
    assert b"legacy-secret" not in secret_file.read_bytes()


def test_local_proxy_secret_provider_fails_closed_without_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AION_CONTROL_SECRET_DIR", str(tmp_path))
    monkeypatch.delenv("AION_CONTROL_LOCAL_SECRET_KEY", raising=False)

    with pytest.raises(SecretProviderError, match="base64 AES key"):
        LocalSecretProvider()
