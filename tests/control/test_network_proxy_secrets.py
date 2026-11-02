from __future__ import annotations

import json
import os
import stat

import pytest

from control.app.network.service import LocalSecretProvider
from shared.secret_store.provider import SecretProviderError


LOCAL_AES_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture(autouse=True)
def isolated_secret_environment(monkeypatch):
    for prefix in ("OMERTA", "AION"):
        for suffix in ("CONTROL_SECRET_DIR", "CONTROL_LOCAL_SECRET_KEY"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)


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


@pytest.fixture
def private_provider(monkeypatch, tmp_path):
    monkeypatch.delenv("AION_CONTROL_SECRET_DIR", raising=False)
    monkeypatch.delenv("AION_CONTROL_LOCAL_SECRET_KEY", raising=False)
    monkeypatch.setenv("OMERTA_CONTROL_SECRET_DIR", str(tmp_path / "secrets"))
    monkeypatch.setenv("OMERTA_CONTROL_LOCAL_SECRET_KEY", LOCAL_AES_KEY)
    return LocalSecretProvider()


def test_private_modes_even_with_permissive_umask(private_provider):
    previous = os.umask(0)
    try:
        private_provider.set_secret("profile", {"password": "test-only"})
    finally:
        os.umask(previous)
    assert stat.S_IMODE(private_provider.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(private_provider._file("profile").stat().st_mode) == 0o600


@pytest.mark.parametrize("mode", [0o777, 0o770, 0o755, 0o705])
def test_insecure_directory_is_rejected(private_provider, mode):
    private_provider.root.chmod(mode)
    try:
        with pytest.raises(SecretProviderError, match="owner-controlled"):
            private_provider.set_secret("profile", {"password": "test-only"})
    finally:
        private_provider.root.chmod(0o700)


def test_group_readable_native_directory_remains_supported(private_provider):
    private_provider.root.chmod(0o750)
    private_provider.set_secret("profile", {"password": "test-only"})
    assert private_provider.get_secret("profile") == {"password": "test-only"}


def test_directory_symlink_is_rejected(private_provider, tmp_path):
    link = tmp_path / "linked"
    link.symlink_to(private_provider.root, target_is_directory=True)
    private_provider.root = link
    with pytest.raises(SecretProviderError, match="private or accessible"):
        private_provider.set_secret("profile", {"password": "test-only"})


def test_secret_symlink_cannot_read_or_overwrite_target(private_provider, tmp_path):
    target = tmp_path / "untouched"
    target.write_bytes(b"unrelated-data")
    private_provider._file("profile").symlink_to(target)
    with pytest.raises(SecretProviderError, match="private or accessible"):
        private_provider.get_secret("profile")
    private_provider.set_secret("profile", {"password": "test-only"})
    assert target.read_bytes() == b"unrelated-data"
    assert not private_provider._file("profile").is_symlink()


def test_permission_failure_preserves_previous_ciphertext(private_provider, monkeypatch):
    private_provider.set_secret("profile", {"password": "original-test-only"})
    before = private_provider._file("profile").read_bytes()

    def deny(*args):
        raise PermissionError("synthetic failure; must not escape")

    monkeypatch.setattr(os, "fchmod", deny)
    with pytest.raises(SecretProviderError, match="private or accessible"):
        private_provider.set_secret("profile", {"password": "replacement-test-only"})
    assert private_provider._file("profile").read_bytes() == before
    assert list(private_provider.root.iterdir()) == [private_provider._file("profile")]
