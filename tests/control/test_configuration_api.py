from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from control.app.main import app
from shared.config.environment import EnvironmentConflictError


def admin_headers() -> dict[str, str]:
    return {
        "authorization": "Bearer test-admin-token",
        "x-aion-roles": "admin",
        "x-aion-user-id": "config-test",
    }


def test_configuration_propose_apply_and_revert(monkeypatch):
    monkeypatch.delenv("AION_GATEWAY_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("AION_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("OMERTA_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    local_provider = f"local-{uuid4()}"

    with TestClient(app) as client:
        initial = client.get("/v1/config/status", headers=admin_headers())
        assert initial.status_code == 200
        initial_effective = initial.json()["effective"]

        proposal = client.post(
            "/v1/config/propose",
            headers=admin_headers(),
            json={
                "router": {
                    "mode": "local",
                    "local_provider": local_provider,
                    "api_provider": None,
                }
            },
        )
        assert proposal.status_code == 200
        assert proposal.json()["has_pending"] is True
        assert proposal.json()["proposed"]["router"]["local_provider"] == local_provider

        applied = client.post("/v1/config/apply", headers=admin_headers())
        assert applied.status_code == 200
        assert applied.json()["has_pending"] is False
        assert applied.json()["effective"]["router"]["local_provider"] == local_provider

        reverted = client.post("/v1/config/revert", headers=admin_headers())
        assert reverted.status_code == 200
        assert reverted.json()["effective"] == initial_effective


def test_configuration_requires_trusted_gateway_token(monkeypatch):
    monkeypatch.delenv("OMERTA_GATEWAY_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("AION_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("AION_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    with TestClient(app) as client:
        user_role = client.get(
            "/v1/config/status",
            headers={"x-aion-roles": "user"},
        )
        forged_admin = client.get(
            "/v1/config/status",
            headers={"x-aion-roles": "admin"},
        )
        wrong_token = client.get(
            "/v1/config/status",
            headers={
                "authorization": "Bearer wrong-token",
                "x-aion-roles": "admin",
            },
        )
        raw_token = client.get(
            "/v1/config/status",
            headers={"authorization": "test-admin-token"},
        )

    assert user_role.status_code == 403
    assert forged_admin.status_code == 403
    assert wrong_token.status_code == 403
    assert raw_token.status_code == 403


def test_configuration_rejects_conflicting_gateway_tokens(monkeypatch):
    canonical_value = "canonical-test-token"
    legacy_value = "legacy-test-token"
    monkeypatch.setenv("OMERTA_GATEWAY_ADMIN_TOKEN", canonical_value)
    monkeypatch.setenv("AION_GATEWAY_ADMIN_TOKEN", legacy_value)
    monkeypatch.delenv("AION_ADMIN_TOKEN", raising=False)

    with TestClient(app) as client:
        with pytest.raises(EnvironmentConflictError) as raised:
            client.get("/v1/config/status", headers=admin_headers())

    rendered = str(raised.value)
    assert "OMERTA_GATEWAY_ADMIN_TOKEN" in rendered
    assert "AION_GATEWAY_ADMIN_TOKEN" in rendered
    assert canonical_value not in rendered
    assert legacy_value not in rendered
