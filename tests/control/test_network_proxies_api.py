from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from control.app.main import app


def admin_headers() -> dict[str, str]:
    return {
        "authorization": "Bearer test-admin-token",
        "x-aion-roles": "admin",
        "x-aion-user-id": "admin-test",
    }


def test_proxy_profile_crud_masks_secrets(monkeypatch):
    monkeypatch.setenv("OMERTA_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("OMERTA_CONTROL_DISABLE_SECRETS", "1")
    monkeypatch.setenv(
        "OMERTA_CONTROL_LOCAL_SECRET_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
    name = f"test-http-{uuid4()}"

    with TestClient(app) as client:
        create = client.post(
            "/v1/network/proxies",
            headers=admin_headers(),
            json={
                "name": name,
                "type": "http",
                "scope": "ai_providers",
                "host": "proxy.local",
                "port": 8080,
                "enabled": True,
                "secrets": {"password": "do-not-return"},
            },
        )
        assert create.status_code == 201
        payload = create.json()
        assert payload["has_secrets"] is True
        assert "password" not in payload

        profile_id = payload["id"]
        read = client.get(f"/v1/network/proxies/{profile_id}", headers=admin_headers())
        assert read.status_code == 200
        assert read.json()["name"] == name
        assert "do-not-return" not in read.text

        update = client.put(
            f"/v1/network/proxies/{profile_id}",
            headers=admin_headers(),
            json={"port": 8081, "fallback_direct": True},
        )
        assert update.status_code == 200
        assert update.json()["port"] == 8081
        assert update.json()["fallback_direct"] is True

        delete = client.delete(
            f"/v1/network/proxies/{profile_id}", headers=admin_headers()
        )
        assert delete.status_code == 204


def test_proxy_profile_mutations_are_admin_only(monkeypatch):
    monkeypatch.setenv("OMERTA_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    with TestClient(app) as client:
        user_role = client.post(
            "/v1/network/proxies",
            headers={"x-aion-roles": "user"},
            json={"name": "blocked", "type": "direct", "scope": "global"},
        )
        forged_admin = client.post(
            "/v1/network/proxies",
            headers={"x-aion-roles": "admin"},
            json={"name": "blocked-admin", "type": "direct", "scope": "global"},
        )

    assert user_role.status_code == 403
    assert forged_admin.status_code == 403


def test_proxy_profile_views_require_token_before_trusting_roles(monkeypatch):
    monkeypatch.setenv("OMERTA_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    enabled_name = f"enabled-{uuid4()}"
    disabled_name = f"disabled-{uuid4()}"

    with TestClient(app) as client:
        enabled = client.post(
            "/v1/network/proxies",
            headers=admin_headers(),
            json={
                "name": enabled_name,
                "type": "direct",
                "scope": "global",
                "enabled": True,
            },
        )
        disabled = client.post(
            "/v1/network/proxies",
            headers=admin_headers(),
            json={
                "name": disabled_name,
                "type": "direct",
                "scope": "global",
                "enabled": False,
            },
        )
        assert enabled.status_code == 201
        assert disabled.status_code == 201

        forged = client.get(
            "/v1/network/proxies",
            headers={"x-aion-roles": "admin"},
        )
        user = client.get(
            "/v1/network/proxies",
            headers={
                "authorization": "Bearer test-admin-token",
                "x-aion-roles": "user",
            },
        )
        admin = client.get("/v1/network/proxies", headers=admin_headers())
        monkeypatch.setenv("OMERTA_NETWORK_PROXY_STATUS_PUBLIC", "1")
        public = client.get(
            "/v1/network/proxies",
            headers={"x-aion-roles": "admin"},
        )

        client.delete(
            f"/v1/network/proxies/{enabled.json()['id']}",
            headers=admin_headers(),
        )
        client.delete(
            f"/v1/network/proxies/{disabled.json()['id']}",
            headers=admin_headers(),
        )

    assert forged.status_code == 403
    assert user.status_code == 200
    assert enabled_name in {item["name"] for item in user.json()["items"]}
    assert disabled_name not in {item["name"] for item in user.json()["items"]}
    assert admin.status_code == 200
    assert {enabled_name, disabled_name}.issubset(
        {item["name"] for item in admin.json()["items"]}
    )
    assert public.status_code == 200
    assert enabled_name in {item["name"] for item in public.json()["items"]}
    assert disabled_name not in {item["name"] for item in public.json()["items"]}
