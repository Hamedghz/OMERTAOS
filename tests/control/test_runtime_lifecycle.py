from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from control.app.network.migrate import apply_schema
from control.app.runtime_nodes.lifecycle import (
    RuntimeLifecycleConfig,
    RuntimeLifecycleManager,
    RuntimeNodeLifecycle,
    probe_runtime,
)
from control.app.runtime_nodes import lifecycle as lifecycle_module
from control.scheduling import RuntimeScheduler, SchedulingRequest
from control.scheduling.models import (
    RuntimeExecutionLease,
    RuntimeNode,
    RuntimeResourceLease,
    TaskAttempt,
)
from shared.config.environment import (
    DeprecatedEnvironmentAliasWarning,
    EnvironmentConflictError,
)


def _config(**overrides: str) -> RuntimeLifecycleConfig:
    values = {
        "OMERTA_RUNTIME_AUTO_REGISTER": "true",
        "OMERTA_RUNTIME_NODE_ID": "runtime-a",
        "OMERTA_RUNTIME_ENDPOINT": "runtime:50051",
        "OMERTA_RUNTIME_CAPABILITIES": "terminal.execute",
        "OMERTA_RUNTIME_TENANT_IDS": "tenant-a,tenant-b",
        "OMERTA_RUNTIME_TOTAL_CPU_MILLIS": "1000",
        "OMERTA_RUNTIME_TOTAL_MEMORY_MB": "512",
        "OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS": "10",
        "OMERTA_RUNTIME_PROBE_TIMEOUT_SECONDS": "3",
        **overrides,
    }
    return RuntimeLifecycleConfig.from_env(values)


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    apply_schema(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    engine.dispose()


def test_runtime_lifecycle_config_is_opt_in_and_bounded() -> None:
    assert RuntimeLifecycleConfig.from_env({}).enabled is False
    assert _config().tenant_ids == ("tenant-a", "tenant-b")

    with pytest.raises(ValueError, match="must not exceed 20"):
        _config(OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS="21")
    with pytest.raises(ValueError, match="must not exceed the heartbeat interval"):
        _config(OMERTA_RUNTIME_PROBE_TIMEOUT_SECONDS="11")


def test_runtime_lifecycle_accepts_deprecated_alias_and_rejects_conflict() -> None:
    with pytest.warns(
        DeprecatedEnvironmentAliasWarning,
        match="AION_RUNTIME_AUTO_REGISTER.*OMERTA_RUNTIME_AUTO_REGISTER",
    ):
        config = RuntimeLifecycleConfig.from_env(
            {"AION_RUNTIME_AUTO_REGISTER": "true"}
        )
    assert config.enabled is True

    with pytest.raises(EnvironmentConflictError) as error:
        RuntimeLifecycleConfig.from_env(
            {
                "OMERTA_RUNTIME_AUTO_REGISTER": "true",
                "AION_RUNTIME_AUTO_REGISTER": "false",
            }
        )
    assert "OMERTA_RUNTIME_AUTO_REGISTER" in str(error.value)
    assert "AION_RUNTIME_AUTO_REGISTER" in str(error.value)


def test_runtime_lifecycle_parses_two_unique_nodes() -> None:
    values = {
        "OMERTA_RUNTIME_AUTO_REGISTER": "true",
        "OMERTA_RUNTIME_MANAGED_NODE_LIMIT": "2",
        "OMERTA_RUNTIME_NODES_JSON": (
            '[{"node_id":"runtime-a","endpoint":"runtime-a:50051",'
            '"capabilities":["terminal.execute"],"tenant_ids":["tenant-a"]},'
            '{"node_id":"runtime-b","endpoint":"runtime-b:50051",'
            '"capabilities":["terminal.execute","resource.allocate"],'
            '"total_cpu_millis":2000,"total_memory_mb":1024}]'
        ),
    }

    configs = RuntimeLifecycleConfig.all_from_env(values)

    assert [config.node_id for config in configs] == ["runtime-a", "runtime-b"]
    assert configs[0].tenant_ids == ("tenant-a",)
    assert configs[1].capabilities == (
        "terminal.execute",
        "resource.allocate",
    )
    assert configs[1].total_memory_mb == 1024


@pytest.mark.parametrize(
    "nodes_json",
    [
        '[{"node_id":"runtime-a","endpoint":"runtime-a:50051"},'
        '{"node_id":"runtime-a","endpoint":"runtime-b:50051"}]',
        '[{"node_id":"runtime-a","endpoint":"runtime:50051"},'
        '{"node_id":"runtime-b","endpoint":"runtime:50051"}]',
    ],
)
def test_runtime_lifecycle_rejects_duplicate_identity_or_endpoint(
    nodes_json: str,
) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        RuntimeLifecycleConfig.all_from_env(
            {
                "OMERTA_RUNTIME_AUTO_REGISTER": "true",
                "OMERTA_RUNTIME_MANAGED_NODE_LIMIT": "2",
                "OMERTA_RUNTIME_NODES_JSON": nodes_json,
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('{"status":"ready"}', True),
        ("not-json", False),
    ],
)
async def test_runtime_probe_requires_ready_json_and_closes_channel(
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
    expected: bool,
) -> None:
    class FakeChannel:
        closed = False

        async def close(self) -> None:
            self.closed = True

    class QueryMetrics:
        async def __call__(self, request: object, *, timeout: float) -> object:
            assert getattr(request, "tenant_id") == "system"
            assert timeout == 2.0
            return SimpleNamespace(ok=True, json=payload)

    channel = FakeChannel()
    monkeypatch.setattr(
        lifecycle_module.grpc.aio,
        "insecure_channel",
        lambda endpoint: channel,
    )
    monkeypatch.setattr(
        lifecycle_module.runtime_pb2_grpc,
        "RuntimeServiceStub",
        lambda _channel: SimpleNamespace(QueryMetrics=QueryMetrics()),
    )

    assert await probe_runtime("runtime:50051", 2.0) is expected
    assert channel.closed is True


@pytest.mark.asyncio
async def test_reachable_runtime_is_registered_and_heartbeated(
    session_factory: sessionmaker[Session],
) -> None:
    calls: list[tuple[str, float]] = []

    async def reachable(endpoint: str, timeout: float) -> bool:
        calls.append((endpoint, timeout))
        return True

    lifecycle = RuntimeNodeLifecycle(
        _config(),
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )

    assert await lifecycle.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        assert node is not None
        assert node.endpoint == "runtime:50051"
        assert node.state == "healthy"
        assert node.tenant_ids_json == '["tenant-a","tenant-b"]'
        assert node.capabilities_json == '["terminal.execute"]'
        assert node.last_heartbeat_at is not None
    assert calls == [("runtime:50051", 3.0)]


@pytest.mark.asyncio
async def test_lifecycle_reconciles_trusted_config_without_resetting_leases(
    session_factory: sessionmaker[Session],
) -> None:
    async def reachable(_endpoint: str, _timeout: float) -> bool:
        return True

    initial = RuntimeNodeLifecycle(
        _config(),
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )
    updated = RuntimeNodeLifecycle(
        _config(
            OMERTA_RUNTIME_CAPABILITIES="terminal.execute,resource.allocate",
            OMERTA_RUNTIME_TENANT_IDS="tenant-c",
            OMERTA_RUNTIME_TOTAL_CPU_MILLIS="2000",
            OMERTA_RUNTIME_TOTAL_MEMORY_MB="1024",
        ),
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )

    assert await initial.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        assert node is not None
        node.active_leases = 2
        db.commit()

    assert await updated.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        assert node is not None
        assert set(json.loads(node.capabilities_json)) == {
            "terminal.execute",
            "resource.allocate",
        }
        assert json.loads(node.tenant_ids_json) == ["tenant-c"]
        assert node.total_cpu_millis == 2000
        assert node.available_cpu_millis == 2000
        assert node.total_memory_mb == 1024
        assert node.available_memory_mb == 1024
        assert node.active_leases == 2


@pytest.mark.asyncio
async def test_lifecycle_reclaims_expired_execution_lease(
    session_factory: sessionmaker[Session],
) -> None:
    async def reachable(_endpoint: str, _timeout: float) -> bool:
        return True

    scheduler = RuntimeScheduler(lease_ttl_seconds=5)
    lifecycle = RuntimeNodeLifecycle(
        _config(),
        scheduler=scheduler,
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )
    assert await lifecycle.sync_once() is True
    with session_factory() as db:
        scheduled = scheduler.schedule(
            db,
            SchedulingRequest(
                task_id="task-expired",
                attempt_id="attempt-1",
                tenant_id="tenant-a",
                cpu_millis=250,
                memory_mb=128,
            ),
        )
        execution_lease = db.get(
            RuntimeExecutionLease, scheduled.lease_generation
        )
        assert execution_lease is not None
        execution_lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    assert await lifecycle.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        attempt = db.scalar(
            select(TaskAttempt).where(TaskAttempt.task_id == "task-expired")
        )
        resource_lease = db.scalar(select(RuntimeResourceLease))
        assert node is not None and node.active_leases == 0
        assert node.available_cpu_millis == 1000
        assert node.available_memory_mb == 512
        assert attempt is not None and attempt.status == "expired"
        assert resource_lease is not None and resource_lease.status == "expired"


@pytest.mark.asyncio
async def test_unreachable_runtime_is_not_registered(
    session_factory: sessionmaker[Session],
) -> None:
    async def unreachable(_endpoint: str, _timeout: float) -> bool:
        return False

    lifecycle = RuntimeNodeLifecycle(
        _config(),
        session_factory=session_factory,
        probe=unreachable,
        schema_initializer=lambda: None,
    )

    assert await lifecycle.sync_once() is False
    with session_factory() as db:
        assert db.get(RuntimeNode, "runtime-a") is None


@pytest.mark.asyncio
async def test_lifecycle_preserves_operator_drain(
    session_factory: sessionmaker[Session],
) -> None:
    async def reachable(_endpoint: str, _timeout: float) -> bool:
        return True

    lifecycle = RuntimeNodeLifecycle(
        _config(),
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )
    assert await lifecycle.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        assert node is not None
        node.drain_requested = True
        node.state = "draining"
        db.commit()

    assert await lifecycle.sync_once() is True
    with session_factory() as db:
        node = db.get(RuntimeNode, "runtime-a")
        assert node is not None
        assert node.drain_requested is True
        assert node.state == "draining"


@pytest.mark.asyncio
async def test_lifecycle_manager_probes_nodes_sequentially(
    session_factory: sessionmaker[Session],
) -> None:
    calls: list[str] = []

    async def reachable(endpoint: str, _timeout: float) -> bool:
        calls.append(endpoint)
        return True

    configs = RuntimeLifecycleConfig.all_from_env(
        {
            "OMERTA_RUNTIME_AUTO_REGISTER": "true",
            "OMERTA_RUNTIME_MANAGED_NODE_LIMIT": "2",
            "OMERTA_RUNTIME_NODES_JSON": (
                '[{"node_id":"runtime-a","endpoint":"runtime-a:50051"},'
                '{"node_id":"runtime-b","endpoint":"runtime-b:50051"}]'
            ),
        }
    )
    manager = RuntimeLifecycleManager(
        configs,
        session_factory=session_factory,
        probe=reachable,
        schema_initializer=lambda: None,
    )

    assert await manager.sync_once() == {"runtime-a": True, "runtime-b": True}
    assert calls == ["runtime-a:50051", "runtime-b:50051"]
    with session_factory() as db:
        assert db.get(RuntimeNode, "runtime-a") is not None
        assert db.get(RuntimeNode, "runtime-b") is not None
