from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from shared.config.environment import EnvironmentConflictError


PROVIDER_MODULES = ("shared.secret_store.provider", "policies.provider")
VAULT_ENVIRONMENT_NAMES = (
    "VAULT_ADDR",
    "AION_VAULT_ADDR",
    "VAULT_AUTH_METHOD",
    "AION_VAULT_AUTH_METHOD",
    "VAULT_NAMESPACE",
    "AION_VAULT_NAMESPACE",
    "VAULT_KV_MOUNT",
    "AION_VAULT_KV_MOUNT",
    "VAULT_TOKEN",
    "AION_VAULT_TOKEN",
    "VAULT_APPROLE_ROLE_ID",
    "AION_VAULT_APPROLE_ROLE_ID",
    "VAULT_APPROLE_SECRET_ID",
    "AION_VAULT_APPROLE_SECRET_ID",
)


class FakeVaultClient:
    def __init__(self, *, url: str, namespace: str | None) -> None:
        self.url = url
        self.namespace = namespace
        self.token: str | None = None


def _clear_vault_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VAULT_ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("module_name", PROVIDER_MODULES)
def test_secret_provider_reads_standard_vault_environment(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(module_name)
    _clear_vault_environment(monkeypatch)
    monkeypatch.setenv("VAULT_ADDR", "https://vault.test")
    monkeypatch.setenv("VAULT_TOKEN", "canonical-test-token")
    monkeypatch.setattr(module, "hvac", SimpleNamespace(Client=FakeVaultClient))

    provider = module.SecretProvider()

    assert provider._url == "https://vault.test"
    assert provider._token == "canonical-test-token"


@pytest.mark.parametrize("module_name", PROVIDER_MODULES)
def test_secret_provider_rejects_conflicting_token_aliases_without_values(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(module_name)
    _clear_vault_environment(monkeypatch)
    canonical_value = "canonical-test-token"
    legacy_value = "legacy-test-token"
    monkeypatch.setenv("VAULT_ADDR", "https://vault.test")
    monkeypatch.setenv("VAULT_TOKEN", canonical_value)
    monkeypatch.setenv("AION_VAULT_TOKEN", legacy_value)
    monkeypatch.setattr(module, "hvac", SimpleNamespace(Client=FakeVaultClient))

    with pytest.raises(EnvironmentConflictError) as raised:
        module.SecretProvider()

    rendered = str(raised.value)
    assert "VAULT_TOKEN" in rendered
    assert "AION_VAULT_TOKEN" in rendered
    assert canonical_value not in rendered
    assert legacy_value not in rendered
