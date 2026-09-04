from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from control.app.network.migrate import apply_schema
from control.audit.models import RuntimeAuditEvent
from control.clients.runtime import (
    RuntimeEnvelope,
    RuntimeExecutionRejected,
    RuntimeTransportUnavailable,
)
from control.orchestration.runtime_dispatch import (
    RUNTIME_ECHO_INTENT,
    RuntimeDispatchRequest,
    RuntimeTaskDispatcher,
)
from control.scheduling import (
    NodeState,
    RuntimeNodeRegistration,
    RuntimeScheduler,
    SchedulingRequest,
)
from control.scheduling.models import RuntimeExecutionLease, RuntimeNode
from shared.config.environment import EnvironmentConflictError


class RecordingExecutor:
    def __init__(self, response: dict[str, object] | BaseException) -> None:
        self.response = response
        self.calls: list[RuntimeEnvelope] = []

    async def execute(self, envelope: RuntimeEnvelope) -> dict[str, object]:
        self.calls.append(envelope)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class ReclaimingExecutor:
    def __init__(
        self,
        scheduler: RuntimeScheduler,
        session_factory: Callable[[], Session],
    ) -> None:
        self.scheduler = scheduler
        self.session_factory = session_factory

    async def execute(self, envelope: RuntimeEnvelope) -> dict[str, object]:
        db = self.session_factory()
        try:
            execution_lease = db.get(
                RuntimeExecutionLease, envelope.lease_generation
            )
            assert execution_lease is not None
            execution_lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            assert self.scheduler.reclaim_expired_leases(db) == 1
        finally:
            db.close()
        return {"ok": True, "stdout": "stale\n", "stderr": "", "code": 0}


@pytest.fixture()
def session_factory() -> Callable[[], Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    apply_schema(engine)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )


def _register(
    session_factory: Callable[[], Session],
    scheduler: RuntimeScheduler,
    node_id: str,
    *,
    capabilities: tuple[str, ...] = ("terminal.execute",),
    tenant_ids: tuple[str, ...] = ("tenant-a",),
) -> None:
    db = session_factory()
    try:
        scheduler.register_node(
            db,
            RuntimeNodeRegistration(
                node_id=node_id,
                endpoint=f"{node_id}:50051",
                capabilities=capabilities,
                tenant_ids=tenant_ids,
            ),
        )
    finally:
        db.close()


def _request(task_id: str = "task-a") -> RuntimeDispatchRequest:
    return RuntimeDispatchRequest(
        task_id=task_id,
        intent=RUNTIME_ECHO_INTENT,
        tenant_id="tenant-a",
        agent_id="agent-a",
        message="hello runtime",
        request_id="request-a",
        trace_id="00-trace-a-span-a-01",
        idempotency_key="idempotency-a",
    )


def _dispatcher(
    session_factory: Callable[[], Session],
    scheduler: RuntimeScheduler,
    clients: dict[str, RecordingExecutor],
    *,
    max_retries: int = 0,
) -> RuntimeTaskDispatcher:
    return RuntimeTaskDispatcher(
        scheduler=scheduler,
        session_factory=session_factory,
        schema_initializer=lambda: None,
        client_factory=lambda endpoint: clients[endpoint],
        timeout_seconds=0.5,
        max_retries=max_retries,
    )


def test_dispatcher_reads_canonical_runtime_limits_and_rejects_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMERTA_RUNTIME_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("OMERTA_RUNTIME_MAX_RETRIES", "0")
    dispatcher = RuntimeTaskDispatcher()
    assert dispatcher.timeout_seconds == 4.0
    assert dispatcher.max_retries == 0

    monkeypatch.setenv("AION_RUNTIME_TIMEOUT_SECONDS", "3")
    with pytest.raises(EnvironmentConflictError) as raised:
        RuntimeTaskDispatcher()
    rendered = str(raised.value)
    assert "OMERTA_RUNTIME_TIMEOUT_SECONDS" in rendered
    assert "AION_RUNTIME_TIMEOUT_SECONDS" in rendered
    assert "4" not in rendered
    assert "3" not in rendered


def test_dispatch_executes_allowlisted_command_once_and_replays_cached_result(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a")
    executor = RecordingExecutor(
        {"ok": True, "stdout": "hello runtime\n", "stderr": "", "code": 0}
    )
    audit_actions: list[str] = []
    monkeypatch.setattr(
        "control.orchestration.runtime_dispatch.emit_audit",
        lambda action, _actor, _tenant: audit_actions.append(action),
    )
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
    )

    first = dispatcher.dispatch(_request())
    replay = dispatcher.dispatch(_request())

    assert first.status == "OK"
    assert first.stdout == "hello runtime\n"
    assert first.selected_node_id == "node-a"
    assert replay.status == "OK"
    assert replay.idempotent_replay is True
    assert len(executor.calls) == 1
    assert executor.calls[0].argv == (
        "/usr/bin/printf",
        "%s\\n",
        "hello runtime",
    )
    assert executor.calls[0].task_id == "task-a"
    assert executor.calls[0].trace_id == "00-trace-a-span-a-01"
    assert executor.calls[0].node_id == "node-a"
    assert executor.calls[0].lease_token
    assert executor.calls[0].lease_generation > 0
    assert executor.calls[0].lease_expires_at_ms > 0
    assert executor.calls[0].lease_token not in repr(executor.calls[0])
    assert audit_actions == ["runtime.dispatch.start", "runtime.dispatch.success"]

    db = session_factory()
    try:
        attempt = scheduler.get_attempt(db, "task-a", "task-a:0", "tenant-a")
        node = db.get(RuntimeNode, "node-a")
        assert attempt is not None and attempt.status == "completed"
        assert node is not None and node.active_leases == 0
        execution_lease = db.scalar(select(RuntimeExecutionLease))
        assert execution_lease is not None
        assert execution_lease.status == "released"
        events = list(
            db.scalars(
                select(RuntimeAuditEvent)
                .where(RuntimeAuditEvent.task_id == "task-a")
                .order_by(RuntimeAuditEvent.id)
            ).all()
        )
        assert [event.action for event in events] == [
            "runtime.schedule",
            "runtime.dispatch.start",
            "runtime.dispatch.success",
            "runtime.dispatch.cache_replay",
        ]
        assert events[1].request_id == "request-a"
        assert events[1].trace_id == "00-trace-a-span-a-01"
        assert events[2].outcome == "completed"
        assert events[2].actor == "agent-a"
    finally:
        db.close()


@pytest.mark.parametrize(
    ("capabilities", "draining", "expected_code"),
    [
        ((), False, "RUNTIME_CAPABILITY_UNAVAILABLE"),
        (("terminal.execute",), True, "RUNTIME_NODE_DRAINING"),
    ],
)
def test_dispatch_rejects_ineligible_nodes_without_contacting_runtime(
    session_factory: Callable[[], Session],
    capabilities: tuple[str, ...],
    draining: bool,
    expected_code: str,
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a", capabilities=capabilities)
    if draining:
        db = session_factory()
        try:
            scheduler.mark_draining(db, "node-a")
        finally:
            db.close()
    executor = RecordingExecutor(
        {"ok": True, "stdout": "unexpected", "stderr": "", "code": 0}
    )
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
    )

    result = dispatcher.dispatch(_request())

    assert result.status == "ERROR"
    assert result.error_code == expected_code
    assert executor.calls == []


def test_dispatch_retries_transport_failure_on_another_eligible_node(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a")
    _register(session_factory, scheduler, "node-b")
    unavailable = RecordingExecutor(RuntimeTransportUnavailable("unavailable"))
    healthy = RecordingExecutor(
        {"ok": True, "stdout": "hello runtime\n", "stderr": "", "code": 0}
    )
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {
            "node-a:50051": unavailable,
            "node-b:50051": healthy,
        },
        max_retries=1,
    )

    result = dispatcher.dispatch(_request())

    assert result.status == "OK"
    assert result.selected_node_id == "node-b"
    assert result.retry_count == 1
    assert len(unavailable.calls) == 1
    assert len(healthy.calls) == 1
    db = session_factory()
    try:
        node_a = db.get(RuntimeNode, "node-a")
        node_b = db.get(RuntimeNode, "node-b")
        assert node_a is not None and node_a.state == NodeState.unreachable.value
        assert node_a.active_leases == 0
        assert node_b is not None and node_b.active_leases == 0
        events = list(
            db.scalars(
                select(RuntimeAuditEvent)
                .where(RuntimeAuditEvent.task_id == "task-a")
                .order_by(RuntimeAuditEvent.id)
            ).all()
        )
        assert [event.action for event in events] == [
            "runtime.schedule",
            "runtime.dispatch.start",
            "runtime.dispatch.unavailable",
            "runtime.schedule",
            "runtime.dispatch.start",
            "runtime.dispatch.success",
        ]
        assert [event.retry_count for event in events] == [0, 0, 0, 1, 1, 1]
    finally:
        db.close()


def test_dispatch_timeout_degrades_node_and_does_not_leak_lease(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a")
    executor = RecordingExecutor(TimeoutError())
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
    )

    result = dispatcher.dispatch(_request())

    assert result.status == "TIMEOUT"
    assert result.error_code == "RUNTIME_TIMEOUT"
    db = session_factory()
    try:
        node = db.get(RuntimeNode, "node-a")
        assert node is not None and node.state == NodeState.degraded.value
        assert node.active_leases == 0
    finally:
        db.close()


def test_dispatch_does_not_retry_runtime_policy_rejection(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a")
    executor = RecordingExecutor(RuntimeExecutionRejected("denied"))
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
        max_retries=1,
    )

    result = dispatcher.dispatch(_request())

    assert result.status == "ERROR"
    assert result.error_code == "RUNTIME_EXECUTION_REJECTED"
    assert len(executor.calls) == 1


def test_new_dispatcher_blocks_completed_attempt_without_durable_result_replay(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler()
    _register(session_factory, scheduler, "node-a")
    executor = RecordingExecutor(
        {"ok": True, "stdout": "hello runtime\n", "stderr": "", "code": 0}
    )
    first_dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
    )
    assert first_dispatcher.dispatch(_request()).status == "OK"

    replacement_executor = RecordingExecutor(
        {"ok": True, "stdout": "duplicate", "stderr": "", "code": 0}
    )
    replacement = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": replacement_executor},
    )

    replay = replacement.dispatch(_request())

    assert replay.status == "ERROR"
    assert replay.error_code == "RUNTIME_RESULT_REPLAY_UNAVAILABLE"
    assert replay.idempotent_replay is True
    assert replacement_executor.calls == []
    db = session_factory()
    try:
        actions = list(
            db.scalars(
                select(RuntimeAuditEvent.action)
                .where(RuntimeAuditEvent.task_id == "task-a")
                .order_by(RuntimeAuditEvent.id)
            ).all()
        )
        assert actions[-2:] == [
            "runtime.schedule",
            "runtime.dispatch.replay_blocked",
        ]
    finally:
        db.close()


def test_dispatcher_retries_after_expired_lease_reclamation(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler(lease_ttl_seconds=5)
    _register(session_factory, scheduler, "node-a")
    db = session_factory()
    try:
        stale = scheduler.schedule(
            db,
            SchedulingRequest(
                task_id="task-a",
                attempt_id="task-a:0",
                tenant_id="tenant-a",
                required_capabilities=("terminal.execute",),
                max_retries=1,
            ),
        )
        execution_lease = db.get(RuntimeExecutionLease, stale.lease_generation)
        assert execution_lease is not None
        execution_lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()
    executor = RecordingExecutor(
        {"ok": True, "stdout": "recovered\n", "stderr": "", "code": 0}
    )
    dispatcher = _dispatcher(
        session_factory,
        scheduler,
        {"node-a:50051": executor},
        max_retries=1,
    )

    result = dispatcher.dispatch(_request())

    assert result.status == "OK"
    assert result.retry_count == 1
    assert result.attempt_id == "task-a:1"
    assert len(executor.calls) == 1


def test_dispatcher_rejects_result_reclaimed_during_execution(
    session_factory: Callable[[], Session],
) -> None:
    scheduler = RuntimeScheduler(lease_ttl_seconds=5)
    _register(session_factory, scheduler, "node-a")
    executor = ReclaimingExecutor(scheduler, session_factory)
    dispatcher = RuntimeTaskDispatcher(
        scheduler=scheduler,
        session_factory=session_factory,
        schema_initializer=lambda: None,
        client_factory=lambda _endpoint: executor,
        timeout_seconds=0.5,
        max_retries=0,
    )

    result = dispatcher.dispatch(_request("task-stale-result"))

    assert result.status == "ERROR"
    assert result.error_code == "RUNTIME_LEASE_REJECTED"
    assert result.stdout == ""
