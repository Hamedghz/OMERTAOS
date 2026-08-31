from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from control.app.network.migrate import apply_schema, missing_tables
from control.scheduling import (
    NodeState,
    RuntimeNodeHeartbeat,
    RuntimeNodeRegistration,
    RuntimeScheduler,
    SchedulingRequest,
)
from control.scheduling.models import (
    RuntimeNode,
    RuntimeExecutionLease,
    RuntimeResourceLease,
    SchedulingDecision,
    TaskAttempt,
)
from control.scheduling.lease_signing import LeaseSigningError


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    apply_schema(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _register(
    scheduler: RuntimeScheduler,
    db: Session,
    node_id: str,
    *,
    tenants: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = ("terminal.execute",),
    active_leases: int = 0,
    available_cpu: int = 1000,
    available_memory: int = 512,
) -> RuntimeNode:
    node = scheduler.register_node(
        db,
        RuntimeNodeRegistration(
            node_id=node_id,
            endpoint=f"{node_id}:50051",
            tenant_ids=tenants,
            capabilities=capabilities,
            total_cpu_millis=1000,
            total_memory_mb=512,
            available_cpu_millis=available_cpu,
            available_memory_mb=available_memory,
        ),
    )
    node.active_leases = active_leases
    db.commit()
    return node


def test_runtime_scheduler_migration_is_additive_and_idempotent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cluster.db'}")

    assert missing_tables(engine) == {
        "control_configuration",
        "proxy_profiles",
        "runtime_audit_events",
        "runtime_execution_leases",
        "runtime_nodes",
        "runtime_resource_leases",
        "scheduling_decisions",
        "task_attempts",
    }
    apply_schema(engine)
    apply_schema(engine)
    assert missing_tables(engine) == set()


def test_round_robin_scheduler_is_capability_and_tenant_aware(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a", tenants=("tenant-a",))
    _register(scheduler, db, "node-b", tenants=("tenant-a",))
    _register(scheduler, db, "node-c", tenants=("tenant-b",))

    first = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            required_capabilities=("terminal.execute",),
            strategy="round_robin",
        ),
    )
    second = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-2",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            required_capabilities=("terminal.execute",),
            strategy="round_robin",
        ),
    )

    assert first.selected_node_id == "node-a"
    assert second.selected_node_id == "node-b"
    assert first.rejected_nodes == {"node-c": "tenant"}


def test_least_loaded_scheduler_prefers_capacity_and_health(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(
        scheduler, db, "busy", active_leases=3, available_cpu=900, available_memory=500
    )
    _register(
        scheduler,
        db,
        "degraded",
        active_leases=0,
        available_cpu=900,
        available_memory=500,
    )
    _register(
        scheduler, db, "idle", active_leases=0, available_cpu=900, available_memory=500
    )
    scheduler.record_heartbeat(
        db,
        "degraded",
        RuntimeNodeHeartbeat(
            available_cpu_millis=900,
            available_memory_mb=500,
            state=NodeState.degraded,
        ),
    )

    result = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            required_capabilities=("terminal.execute",),
            strategy="least_loaded",
        ),
    )

    assert result.selected_node_id == "idle"


def test_scheduler_rejects_draining_stale_and_over_budget_nodes(db: Session) -> None:
    scheduler = RuntimeScheduler(heartbeat_timeout_seconds=5)
    _register(scheduler, db, "draining")
    _register(scheduler, db, "stale")
    _register(scheduler, db, "small", available_cpu=10, available_memory=10)
    scheduler.mark_draining(db, "draining")
    stale = db.get(RuntimeNode, "stale")
    assert stale is not None
    stale.last_heartbeat_at = datetime.now(UTC) - timedelta(seconds=10)
    db.commit()

    result = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            required_capabilities=("terminal.execute",),
            cpu_millis=100,
            memory_mb=128,
        ),
    )

    assert result.decision == "rejected"
    assert result.rejected_nodes == {
        "draining": "state:draining",
        "small": "capacity",
        "stale": "state:unreachable",
    }


def test_scheduler_replays_existing_attempt_and_bounds_retry(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")
    request = SchedulingRequest(
        task_id="task-1",
        attempt_id="attempt-1",
        tenant_id="tenant-a",
        required_capabilities=("terminal.execute",),
        retry_count=0,
        max_retries=1,
    )

    first = scheduler.schedule(db, request)
    replay = scheduler.schedule(db, request)
    rejected = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-2",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            retry_count=2,
            max_retries=1,
        ),
    )

    assert first.selected_node_id == "node-a"
    assert replay.selected_node_id == "node-a"
    assert replay.idempotent_replay is True
    assert rejected.decision == "rejected"
    assert rejected.reason == "retry budget exhausted"


def test_scheduler_rejects_cross_tenant_attempt_identity_replay(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a", tenants=("tenant-a", "tenant-b"))
    first = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-shared",
            attempt_id="attempt-shared",
            tenant_id="tenant-a",
        ),
    )

    collision = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-shared",
            attempt_id="attempt-shared",
            tenant_id="tenant-b",
        ),
    )

    assert first.selected_node_id == "node-a"
    assert collision.decision == "rejected"
    assert collision.selected_node_id is None
    assert collision.idempotent_replay is False
    assert collision.reason == "attempt identity is not available"
    assert scheduler.get_attempt(
        db,
        "task-shared",
        "attempt-shared",
        "tenant-b",
    ) is None


def test_scheduler_finishes_attempt_and_releases_node_lease(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")
    scheduling = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            required_capabilities=("terminal.execute",),
        ),
    )
    node = db.get(RuntimeNode, "node-a")
    lease = db.scalar(select(RuntimeResourceLease))

    assert node is not None
    assert node.active_leases == 1
    assert node.available_cpu_millis == 900
    assert node.available_memory_mb == 384
    assert lease is not None and lease.status == "active"

    finished = scheduler.finish_attempt(
        db,
        "task-1",
        "attempt-1",
        tenant_id="tenant-a",
        status="transport_error",
        node_state=NodeState.unreachable,
        lease_generation=scheduling.lease_generation,
    )
    replay = scheduler.finish_attempt(
        db,
        "task-1",
        "attempt-1",
        tenant_id="tenant-a",
        status="transport_error",
        node_state=NodeState.unreachable,
    )
    db.expire_all()
    node = db.get(RuntimeNode, "node-a")
    lease = db.scalar(select(RuntimeResourceLease))

    assert finished.status == "transport_error"
    assert replay.status == "transport_error"
    assert node is not None and node.active_leases == 0
    assert node.available_cpu_millis == 1000
    assert node.available_memory_mb == 512
    assert node.state == NodeState.unreachable.value
    assert lease is not None and lease.status == "released"
    assert lease.released_at is not None


def test_scheduler_persists_only_execution_lease_token_hash(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")

    result = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-token",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
        ),
    )
    execution_lease = db.scalar(select(RuntimeExecutionLease))

    assert result.lease_token is not None
    assert result.lease_generation is not None
    assert result.lease_expires_at is not None
    assert execution_lease is not None
    assert execution_lease.id == result.lease_generation
    assert execution_lease.token_hash == hashlib.sha256(
        result.lease_token.encode()
    ).hexdigest()
    assert result.lease_token not in repr(result)


def test_scheduler_without_signing_key_fails_before_reserving_capacity(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OMERTA_RUNTIME_LEASE_HMAC_KEY", raising=False)
    scheduler = RuntimeScheduler()
    node = _register(scheduler, db, "node-a")

    with pytest.raises(LeaseSigningError, match="is required"):
        scheduler.schedule(
            db,
            SchedulingRequest(
                task_id="task-no-signing-key",
                attempt_id="attempt-1",
                tenant_id="tenant-a",
            ),
        )

    db.refresh(node)
    assert node.active_leases == 0
    assert node.available_cpu_millis == node.total_cpu_millis
    assert node.available_memory_mb == node.total_memory_mb
    assert db.scalar(select(TaskAttempt)) is None
    assert db.scalar(select(RuntimeResourceLease)) is None
    assert db.scalar(select(RuntimeExecutionLease)) is None


def test_scheduler_reclaims_expired_execution_lease(db: Session) -> None:
    scheduler = RuntimeScheduler(lease_ttl_seconds=5)
    _register(scheduler, db, "node-a")
    result = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-expired",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            cpu_millis=250,
            memory_mb=128,
        ),
    )
    execution_lease = db.get(RuntimeExecutionLease, result.lease_generation)
    assert execution_lease is not None
    execution_lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert scheduler.reclaim_expired_leases(db) == 1

    attempt = scheduler.get_attempt(
        db, "task-expired", "attempt-1", "tenant-a"
    )
    node = db.get(RuntimeNode, "node-a")
    resource_lease = db.scalar(select(RuntimeResourceLease))
    db.refresh(execution_lease)
    assert attempt is not None and attempt.status == "expired"
    assert node is not None and node.active_leases == 0
    assert node.available_cpu_millis == 1000
    assert node.available_memory_mb == 512
    assert resource_lease is not None and resource_lease.status == "expired"
    assert execution_lease.status == "expired"
    assert execution_lease.finished_at is not None


def test_scheduler_fences_stale_completion_generation(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")
    result = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-fenced",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
        ),
    )
    assert result.lease_generation is not None

    fenced = scheduler.finish_attempt(
        db,
        "task-fenced",
        "attempt-1",
        tenant_id="tenant-a",
        status="completed",
        lease_generation=result.lease_generation + 1,
    )
    node = db.get(RuntimeNode, "node-a")
    assert fenced.status == "leased"
    assert node is not None and node.active_leases == 1

    completed = scheduler.finish_attempt(
        db,
        "task-fenced",
        "attempt-1",
        tenant_id="tenant-a",
        status="completed",
        lease_generation=result.lease_generation,
    )
    assert completed.status == "completed"


def test_scheduler_reserves_capacity_and_rejects_aggregate_overcommit(
    db: Session,
) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")

    first = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            cpu_millis=600,
            memory_mb=300,
        ),
    )
    second = scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-2",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            cpu_millis=600,
            memory_mb=300,
        ),
    )

    node = db.get(RuntimeNode, "node-a")
    assert first.decision == "selected"
    assert second.decision == "rejected"
    assert second.rejected_nodes == {"node-a": "capacity"}
    assert node is not None and node.active_leases == 1
    assert node.available_cpu_millis == 400
    assert node.available_memory_mb == 212


def test_heartbeat_preserves_scheduler_resource_reservations(db: Session) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")
    scheduler.schedule(
        db,
        SchedulingRequest(
            task_id="task-1",
            attempt_id="attempt-1",
            tenant_id="tenant-a",
            cpu_millis=250,
            memory_mb=128,
        ),
    )

    node = scheduler.record_heartbeat(
        db,
        "node-a",
        RuntimeNodeHeartbeat(
            available_cpu_millis=1000,
            available_memory_mb=512,
            active_leases=0,
        ),
    )

    assert node.active_leases == 1
    assert node.available_cpu_millis == 750
    assert node.available_memory_mb == 384


def test_schedule_rolls_back_attempt_when_audit_persistence_fails(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = RuntimeScheduler()
    _register(scheduler, db, "node-a")

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        "control.scheduling.service.append_runtime_audit_event",
        fail_audit,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        scheduler.schedule(
            db,
            SchedulingRequest(
                task_id="task-atomic",
                attempt_id="attempt-atomic",
                tenant_id="tenant-a",
                required_capabilities=("terminal.execute",),
            ),
        )
    db.rollback()

    node = db.get(RuntimeNode, "node-a")
    assert node is not None and node.active_leases == 0
    assert node.available_cpu_millis == 1000
    assert node.available_memory_mb == 512
    assert db.scalar(select(RuntimeResourceLease)) is None
    assert db.scalar(
        select(TaskAttempt).where(TaskAttempt.task_id == "task-atomic")
    ) is None
    assert db.scalar(
        select(SchedulingDecision).where(
            SchedulingDecision.task_id == "task-atomic"
        )
    ) is None
