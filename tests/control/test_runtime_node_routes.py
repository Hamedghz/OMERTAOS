from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from control.app.main import app
from control.app.runtime_nodes.routes import get_db
from control.app.network.migrate import apply_schema


def test_runtime_node_routes_register_heartbeat_and_schedule(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AION_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    apply_schema(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        headers = {
            "authorization": "Bearer test-admin-token",
            "x-aion-roles": "admin",
            "tenant-id": "tenant-a",
            "x-request-id": "req-a",
            "x-correlation-id": "correlation-a",
            "traceparent": "00-trace-a-span-a-01",
        }
        registration = client.post(
            "/v1/runtime/nodes",
            headers=headers,
            json={
                "node_id": "runtime-a",
                "endpoint": "runtime-a:50051",
                "capabilities": ["terminal.execute"],
                "tenant_ids": ["tenant-a"],
                "total_cpu_millis": 1000,
                "total_memory_mb": 512,
            },
        )
        assert registration.status_code == 201
        assert registration.json()["state"] == "healthy"

        heartbeat = client.post(
            "/v1/runtime/nodes/runtime-a/heartbeat",
            headers=headers,
            json={
                "available_cpu_millis": 900,
                "available_memory_mb": 400,
                "active_leases": 0,
            },
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["available_memory_mb"] == 400

        decision = client.post(
            "/v1/runtime/schedule",
            headers=headers,
            json={
                "task_id": "task-a",
                "attempt_id": "attempt-a",
                "tenant_id": "tenant-a",
                "required_capabilities": ["terminal.execute"],
                "strategy": "least_loaded",
            },
        )
        assert decision.status_code == 200
        assert decision.json()["selected_node_id"] == "runtime-a"
        assert "lease_token" not in decision.json()
        assert "lease_generation" not in decision.json()

        trail = client.get("/v1/runtime/audit/task-a", headers=headers)
        assert trail.status_code == 200
        assert trail.json()["tenant_id"] == "tenant-a"
        assert trail.json()["truncated"] is False
        assert trail.json()["next_cursor"] is None
        assert [item["action"] for item in trail.json()["items"]] == [
            "runtime.schedule"
        ]
        assert trail.json()["items"][0]["request_id"] == "correlation-a"
        assert trail.json()["items"][0]["trace_id"] == "00-trace-a-span-a-01"

        other_tenant = client.get(
            "/v1/runtime/audit/task-a",
            headers={**headers, "tenant-id": "tenant-b"},
        )
        assert other_tenant.status_code == 200
        assert other_tenant.json()["items"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_runtime_node_routes_require_admin(monkeypatch) -> None:
    monkeypatch.setenv("AION_GATEWAY_ADMIN_TOKEN", "test-admin-token")
    client = TestClient(app)

    response = client.get("/v1/runtime/nodes")

    assert response.status_code == 403
    assert client.get("/v1/runtime/audit/task-a").status_code == 403
    assert (
        client.get(
            "/v1/runtime/nodes",
            headers={"x-aion-roles": "admin"},
        ).status_code
        == 403
    )
