from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from control.audit import append_runtime_audit_event
from shared.config.environment import integer_parser, resolve_environment
from shared.telemetry.audit import emit_audit

from .models import (
    RuntimeExecutionLease,
    RuntimeNode,
    RuntimeResourceLease,
    SchedulingDecision,
    TaskAttempt,
)
from .lease_signing import LeaseSigner

LEASE_TTL_ENV = "OMERTA_RUNTIME_LEASE_TTL_SECONDS"
LEGACY_LEASE_TTL_ENV = "AION_RUNTIME_LEASE_TTL_SECONDS"


class NodeState(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    unreachable = "unreachable"
    draining = "draining"


@dataclass(frozen=True, slots=True)
class RuntimeNodeRegistration:
    node_id: str
    endpoint: str
    capabilities: tuple[str, ...] = ()
    total_cpu_millis: int = 1000
    total_memory_mb: int = 512
    available_cpu_millis: int | None = None
    available_memory_mb: int | None = None
    tenant_ids: tuple[str, ...] = ()
    software_version: str = "unknown"
    contract_version: str = "runtime.v1"
    trust_zone: str = "local"
    labels: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.node_id, "node_id")
        _require_text(self.endpoint, "endpoint")
        _require_positive(self.total_cpu_millis, "total_cpu_millis")
        _require_positive(self.total_memory_mb, "total_memory_mb")
        if self.available_cpu_millis is not None and self.available_cpu_millis < 0:
            raise ValueError("available_cpu_millis must be non-negative")
        if self.available_memory_mb is not None and self.available_memory_mb < 0:
            raise ValueError("available_memory_mb must be non-negative")


@dataclass(frozen=True, slots=True)
class RuntimeNodeHeartbeat:
    available_cpu_millis: int
    available_memory_mb: int
    active_leases: int | None = None
    state: NodeState = NodeState.healthy
    capabilities: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.available_cpu_millis < 0:
            raise ValueError("available_cpu_millis must be non-negative")
        if self.available_memory_mb < 0:
            raise ValueError("available_memory_mb must be non-negative")
        if self.active_leases is not None and self.active_leases < 0:
            raise ValueError("active_leases must be non-negative")


@dataclass(frozen=True, slots=True)
class SchedulingRequest:
    task_id: str
    attempt_id: str
    tenant_id: str
    required_capabilities: tuple[str, ...] = ()
    cpu_millis: int = 100
    memory_mb: int = 128
    strategy: str = "round_robin"
    idempotency_key: str | None = None
    retry_count: int = 0
    max_retries: int = 0
    trace_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.task_id, "task_id")
        _require_text(self.attempt_id, "attempt_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_positive(self.cpu_millis, "cpu_millis")
        _require_positive(self.memory_mb, "memory_mb")
        if self.strategy not in {"round_robin", "least_loaded"}:
            raise ValueError("strategy must be round_robin or least_loaded")
        if self.retry_count < 0 or self.max_retries < 0:
            raise ValueError("retry counts must be non-negative")


@dataclass(frozen=True, slots=True)
class SchedulingResult:
    task_id: str
    attempt_id: str
    tenant_id: str
    strategy: str
    decision: str
    selected_node_id: str | None
    reason: str
    eligible_nodes: tuple[str, ...]
    rejected_nodes: dict[str, str]
    idempotent_replay: bool = False
    lease_token: str | None = field(default=None, repr=False)
    lease_generation: int | None = None
    lease_expires_at: datetime | None = None


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _now() -> datetime:
    return datetime.now(UTC)


def _json_list(values: tuple[str, ...] | list[str]) -> str:
    normalized = sorted({value.strip() for value in values if value.strip()})
    return json.dumps(normalized, separators=(",", ":"))


def _json_map(values: dict[str, str]) -> str:
    normalized = {key: values[key] for key in sorted(values)}
    return json.dumps(normalized, separators=(",", ":"))


def _list(raw: str) -> set[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, list):
        return set()
    return {str(item) for item in parsed if str(item).strip()}


def _state(node: RuntimeNode) -> NodeState:
    try:
        return NodeState(node.state)
    except ValueError:
        return NodeState.unreachable


class RuntimeScheduler:
    def __init__(
        self,
        *,
        heartbeat_timeout_seconds: int = 30,
        lease_ttl_seconds: int | None = None,
        lease_signing_key: str | None = None,
    ) -> None:
        if heartbeat_timeout_seconds <= 0:
            raise ValueError("heartbeat_timeout_seconds must be positive")
        resolved_lease_ttl = lease_ttl_seconds
        if resolved_lease_ttl is None:
            resolved_lease_ttl = resolve_environment(
                LEASE_TTL_ENV,
                aliases=(LEGACY_LEASE_TTL_ENV,),
                default="45",
                parser=integer_parser(minimum=5, maximum=120),
            )
            assert isinstance(resolved_lease_ttl, int)
        if resolved_lease_ttl < 5 or resolved_lease_ttl > 120:
            raise ValueError("lease_ttl_seconds must be between 5 and 120")
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self.lease_ttl = timedelta(seconds=resolved_lease_ttl)
        self._lease_signer = (
            LeaseSigner.from_encoded(lease_signing_key)
            if lease_signing_key is not None
            else None
        )

    def register_node(
        self,
        db: Session,
        registration: RuntimeNodeRegistration,
        *,
        actor: str = "system",
    ) -> RuntimeNode:
        available_cpu = registration.available_cpu_millis
        available_memory = registration.available_memory_mb
        node = db.scalars(
            select(RuntimeNode)
            .where(RuntimeNode.node_id == registration.node_id)
            .with_for_update()
        ).first()
        if node is None:
            node = RuntimeNode(node_id=registration.node_id, endpoint=registration.endpoint)
            db.add(node)
        node.endpoint = registration.endpoint
        node.state = NodeState.healthy.value
        node.software_version = registration.software_version
        node.contract_version = registration.contract_version
        node.trust_zone = registration.trust_zone
        node.capabilities_json = _json_list(registration.capabilities)
        node.tenant_ids_json = _json_list(registration.tenant_ids)
        node.labels_json = _json_map(registration.labels)
        node.total_cpu_millis = registration.total_cpu_millis
        node.total_memory_mb = registration.total_memory_mb
        reserved_cpu, reserved_memory, active_leases = self._active_reservations(
            db, registration.node_id
        )
        reported_cpu = (
            available_cpu if available_cpu is not None else registration.total_cpu_millis
        )
        reported_memory = (
            available_memory
            if available_memory is not None
            else registration.total_memory_mb
        )
        node.available_cpu_millis = max(
            min(reported_cpu, registration.total_cpu_millis) - reserved_cpu, 0
        )
        node.available_memory_mb = max(
            min(reported_memory, registration.total_memory_mb) - reserved_memory, 0
        )
        node.active_leases = max(node.active_leases or 0, active_leases)
        node.drain_requested = False
        node.last_heartbeat_at = _now()
        node.updated_at = _now()
        db.commit()
        db.refresh(node)
        emit_audit("runtime.node.register", actor, "system")
        return node

    def record_heartbeat(
        self,
        db: Session,
        node_id: str,
        heartbeat: RuntimeNodeHeartbeat,
        *,
        actor: str = "system",
    ) -> RuntimeNode:
        node = db.scalars(
            select(RuntimeNode)
            .where(RuntimeNode.node_id == node_id)
            .with_for_update()
        ).first()
        if node is None:
            raise ValueError("runtime node is not registered")
        if node.drain_requested or heartbeat.state is NodeState.draining:
            node.state = NodeState.draining.value
            node.drain_requested = True
        else:
            node.state = heartbeat.state.value
        reserved_cpu, reserved_memory, active_leases = self._active_reservations(
            db, node_id
        )
        node.available_cpu_millis = max(
            min(heartbeat.available_cpu_millis, node.total_cpu_millis)
            - reserved_cpu,
            0,
        )
        node.available_memory_mb = max(
            min(heartbeat.available_memory_mb, node.total_memory_mb)
            - reserved_memory,
            0,
        )
        if heartbeat.active_leases is not None:
            node.active_leases = max(heartbeat.active_leases, active_leases)
        else:
            node.active_leases = max(node.active_leases, active_leases)
        if heartbeat.capabilities is not None:
            node.capabilities_json = _json_list(heartbeat.capabilities)
        node.last_heartbeat_at = _now()
        node.updated_at = _now()
        db.commit()
        db.refresh(node)
        emit_audit("runtime.node.heartbeat", actor, "system")
        return node

    def mark_draining(self, db: Session, node_id: str, *, actor: str = "system") -> RuntimeNode:
        node = db.get(RuntimeNode, node_id)
        if node is None:
            raise ValueError("runtime node is not registered")
        node.state = NodeState.draining.value
        node.drain_requested = True
        node.updated_at = _now()
        db.commit()
        db.refresh(node)
        emit_audit("runtime.node.drain", actor, "system")
        return node

    def refresh_unreachable(self, db: Session, *, at: datetime | None = None) -> int:
        checked_at = at or _now()
        changed = self._refresh_node_states(
            db.scalars(select(RuntimeNode)).all(), checked_at
        )
        if changed:
            db.commit()
        return changed

    def discover_workers(self, db: Session, tenant_id: str) -> list[RuntimeNode]:
        self.refresh_unreachable(db)
        nodes = db.scalars(select(RuntimeNode).order_by(RuntimeNode.node_id)).all()
        return [node for node in nodes if self._tenant_allowed(node, tenant_id)]

    def get_attempt(
        self,
        db: Session,
        task_id: str,
        attempt_id: str,
        tenant_id: str,
    ) -> TaskAttempt | None:
        return db.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id == task_id)
            .where(TaskAttempt.attempt_id == attempt_id)
            .where(TaskAttempt.tenant_id == tenant_id)
        ).first()

    def _get_attempt_by_identity(
        self,
        db: Session,
        task_id: str,
        attempt_id: str,
    ) -> TaskAttempt | None:
        return db.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id == task_id)
            .where(TaskAttempt.attempt_id == attempt_id)
        ).first()

    def finish_attempt(
        self,
        db: Session,
        task_id: str,
        attempt_id: str,
        *,
        tenant_id: str,
        status: str,
        node_state: NodeState | None = None,
        actor: str = "system",
        audit_action: str = "runtime.attempt.finish",
        request_id: str | None = None,
        trace_id: str | None = None,
        reason: str = "runtime attempt finished",
        lease_generation: int | None = None,
    ) -> TaskAttempt:
        _require_text(status, "status")
        self._lock_attempt_identity(db, task_id, attempt_id)
        attempt = db.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.task_id == task_id)
            .where(TaskAttempt.attempt_id == attempt_id)
            .where(TaskAttempt.tenant_id == tenant_id)
            .with_for_update()
        ).first()
        if attempt is None:
            raise ValueError("runtime attempt is not registered")
        node = None
        if attempt.selected_node_id is not None:
            node = db.scalars(
                select(RuntimeNode)
                .where(RuntimeNode.node_id == attempt.selected_node_id)
                .with_for_update()
            ).first()
        lease = db.scalars(
            select(RuntimeResourceLease)
            .where(RuntimeResourceLease.task_attempt_id == attempt.id)
            .with_for_update()
        ).first()
        execution_lease = None
        if lease is not None:
            execution_lease = db.scalars(
                select(RuntimeExecutionLease)
                .where(RuntimeExecutionLease.resource_lease_id == lease.id)
                .with_for_update()
            ).first()
        finished_at = _now()
        if attempt.status == status:
            db.commit()
            db.refresh(attempt)
            return attempt
        lease_is_current = (
            attempt.status == "leased"
            and lease is not None
            and lease.status == "active"
            and (
                execution_lease is None
                or (
                    execution_lease.status == "active"
                    and lease_generation == execution_lease.id
                    and _as_aware(execution_lease.expires_at) > finished_at
                )
            )
        )
        if not lease_is_current:
            if (
                attempt.status == "leased"
                and lease is not None
                and lease.status == "active"
                and execution_lease is not None
                and execution_lease.status == "active"
                and _as_aware(execution_lease.expires_at) <= finished_at
            ):
                self._release_resources(node, lease, finished_at, status="expired")
                execution_lease.status = "expired"
                execution_lease.finished_at = finished_at
                attempt.status = "expired"
                attempt.updated_at = finished_at
                append_runtime_audit_event(
                    db,
                    action="runtime.lease.expired",
                    actor=actor,
                    tenant_id=attempt.tenant_id,
                    task_id=attempt.task_id,
                    attempt_id=attempt.attempt_id,
                    node_id=attempt.selected_node_id,
                    request_id=request_id,
                    trace_id=trace_id,
                    outcome="expired",
                    reason="runtime execution lease expired before completion",
                    retry_count=attempt.retry_count,
                )
            append_runtime_audit_event(
                db,
                action="runtime.attempt.finish_fenced",
                actor=actor,
                tenant_id=attempt.tenant_id,
                task_id=attempt.task_id,
                attempt_id=attempt.attempt_id,
                node_id=attempt.selected_node_id,
                request_id=request_id,
                trace_id=trace_id,
                outcome="rejected",
                reason="runtime attempt lease is no longer current",
                retry_count=attempt.retry_count,
            )
            db.commit()
            db.refresh(attempt)
            emit_audit("runtime.attempt.finish_fenced", actor, attempt.tenant_id)
            return attempt
        if attempt.status == "leased" and lease is not None:
            self._release_resources(node, lease, finished_at, status="released")
        if execution_lease is not None:
            execution_lease.status = "released"
            execution_lease.finished_at = finished_at
        attempt.status = status
        attempt.updated_at = finished_at
        if (
            node is not None
            and node_state is not None
            and _state(node) is not NodeState.draining
        ):
            node.state = node_state.value
            node.updated_at = _now()
        append_runtime_audit_event(
            db,
            action=audit_action,
            actor=actor,
            tenant_id=attempt.tenant_id,
            task_id=attempt.task_id,
            attempt_id=attempt.attempt_id,
            node_id=attempt.selected_node_id,
            request_id=request_id,
            trace_id=trace_id,
            outcome=status,
            reason=reason,
            retry_count=attempt.retry_count,
        )
        db.commit()
        db.refresh(attempt)
        emit_audit("runtime.attempt.finish", actor, attempt.tenant_id)
        return attempt

    def schedule(self, db: Session, request: SchedulingRequest, *, actor: str = "system") -> SchedulingResult:
        signer = self._lease_signer or LeaseSigner.from_env()
        self.reclaim_expired_leases(db, actor=actor)
        self._lock_attempt_identity(db, request.task_id, request.attempt_id)
        existing = self._get_attempt_by_identity(db, request.task_id, request.attempt_id)
        if existing and existing.tenant_id != request.tenant_id:
            return self._record_decision(
                db,
                request,
                "rejected",
                None,
                "attempt identity is not available",
                (),
                {},
                actor,
            )
        if existing and existing.selected_node_id:
            return self._record_decision(
                db,
                request,
                "selected",
                existing.selected_node_id,
                "idempotent scheduling replay",
                (existing.selected_node_id,),
                {},
                actor,
                idempotent_replay=True,
            )

        if request.retry_count > request.max_retries:
            return self._record_decision(
                db,
                request,
                "rejected",
                None,
                "retry budget exhausted",
                (),
                {},
                actor,
            )

        attempt = existing or TaskAttempt(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            tenant_id=request.tenant_id,
        )
        attempt.idempotency_key = request.idempotency_key
        attempt.required_capabilities_json = _json_list(request.required_capabilities)
        attempt.retry_count = request.retry_count
        attempt.max_retries = request.max_retries
        if existing is None:
            db.add(attempt)

        eligible, rejected = self._eligible_nodes(db, request)
        if not eligible:
            attempt.status = "pending"
            db.flush()
            return self._record_decision(
                db,
                request,
                "rejected",
                None,
                "no eligible runtime node",
                (),
                rejected,
                actor,
            )

        selected = self._select_node(db, request.strategy, eligible, request.tenant_id)
        selected.active_leases += 1
        selected.available_cpu_millis -= request.cpu_millis
        selected.available_memory_mb -= request.memory_mb
        attempt.selected_node_id = selected.node_id
        attempt.status = "leased"
        attempt.updated_at = _now()
        db.flush()
        resource_lease = RuntimeResourceLease(
            task_attempt_id=attempt.id,
            node_id=selected.node_id,
            cpu_millis=request.cpu_millis,
            memory_mb=request.memory_mb,
        )
        db.add(resource_lease)
        db.flush()
        lease_expires_at = _now() + self.lease_ttl
        execution_lease = RuntimeExecutionLease(
            resource_lease_id=resource_lease.id,
            token_hash="0" * 64,
            expires_at=lease_expires_at,
        )
        db.add(execution_lease)
        db.flush()
        lease_expires_at_ms = int(lease_expires_at.timestamp() * 1000)
        lease_token = signer.sign(
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            node_id=selected.node_id,
            generation=execution_lease.id,
            expires_at_ms=lease_expires_at_ms,
        )
        execution_lease.token_hash = hashlib.sha256(lease_token.encode()).hexdigest()
        return self._record_decision(
            db,
            request,
            "selected",
            selected.node_id,
            "eligible runtime node selected",
            tuple(node.node_id for node in eligible),
            rejected,
            actor,
            lease_token=lease_token,
            lease_generation=execution_lease.id,
            lease_expires_at=lease_expires_at,
        )

    def reclaim_expired_leases(
        self,
        db: Session,
        *,
        at: datetime | None = None,
        limit: int = 100,
        actor: str = "runtime-lifecycle",
    ) -> int:
        if limit <= 0 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        checked_at = at or _now()
        candidates = db.execute(
            select(
                TaskAttempt.task_id,
                TaskAttempt.attempt_id,
                TaskAttempt.tenant_id,
            )
            .join(
                RuntimeResourceLease,
                RuntimeResourceLease.task_attempt_id == TaskAttempt.id,
            )
            .join(
                RuntimeExecutionLease,
                RuntimeExecutionLease.resource_lease_id
                == RuntimeResourceLease.id,
            )
            .where(TaskAttempt.status == "leased")
            .where(RuntimeResourceLease.status == "active")
            .where(RuntimeExecutionLease.status == "active")
            .where(RuntimeExecutionLease.expires_at <= checked_at)
            .order_by(RuntimeExecutionLease.expires_at, RuntimeExecutionLease.id)
            .limit(limit)
        ).all()
        reclaimed_tenants: list[str] = []
        for task_id, attempt_id, tenant_id in candidates:
            self._lock_attempt_identity(db, task_id, attempt_id)
            attempt = db.scalars(
                select(TaskAttempt)
                .where(TaskAttempt.task_id == task_id)
                .where(TaskAttempt.attempt_id == attempt_id)
                .where(TaskAttempt.tenant_id == tenant_id)
                .with_for_update()
            ).first()
            if attempt is None or attempt.status != "leased":
                continue
            node = db.scalars(
                select(RuntimeNode)
                .where(RuntimeNode.node_id == attempt.selected_node_id)
                .with_for_update()
            ).first()
            lease = db.scalars(
                select(RuntimeResourceLease)
                .where(RuntimeResourceLease.task_attempt_id == attempt.id)
                .with_for_update()
            ).first()
            if lease is None or lease.status != "active":
                continue
            execution_lease = db.scalars(
                select(RuntimeExecutionLease)
                .where(RuntimeExecutionLease.resource_lease_id == lease.id)
                .with_for_update()
            ).first()
            if (
                execution_lease is None
                or execution_lease.status != "active"
                or _as_aware(execution_lease.expires_at) > checked_at
            ):
                continue
            self._release_resources(node, lease, checked_at, status="expired")
            execution_lease.status = "expired"
            execution_lease.finished_at = checked_at
            attempt.status = "expired"
            attempt.updated_at = checked_at
            append_runtime_audit_event(
                db,
                action="runtime.lease.expired",
                actor=actor,
                tenant_id=attempt.tenant_id,
                task_id=attempt.task_id,
                attempt_id=attempt.attempt_id,
                node_id=attempt.selected_node_id,
                outcome="expired",
                reason="runtime execution lease expired and capacity was reclaimed",
                retry_count=attempt.retry_count,
            )
            reclaimed_tenants.append(attempt.tenant_id)
        if reclaimed_tenants:
            db.commit()
            for tenant_id in reclaimed_tenants:
                emit_audit("runtime.lease.expired", actor, tenant_id)
        return len(reclaimed_tenants)

    def _eligible_nodes(self, db: Session, request: SchedulingRequest) -> tuple[list[RuntimeNode], dict[str, str]]:
        nodes = db.scalars(
            select(RuntimeNode).order_by(RuntimeNode.node_id).with_for_update()
        ).all()
        self._refresh_node_states(nodes, _now())
        required = set(request.required_capabilities)
        eligible: list[RuntimeNode] = []
        rejected: dict[str, str] = {}
        for node in nodes:
            state = _state(node)
            if state in {NodeState.unreachable, NodeState.draining}:
                rejected[node.node_id] = f"state:{state.value}"
                continue
            if not self._tenant_allowed(node, request.tenant_id):
                rejected[node.node_id] = "tenant"
                continue
            node_capabilities = _list(node.capabilities_json)
            if not required.issubset(node_capabilities):
                rejected[node.node_id] = "capability"
                continue
            if node.available_cpu_millis < request.cpu_millis or node.available_memory_mb < request.memory_mb:
                rejected[node.node_id] = "capacity"
                continue
            eligible.append(node)
        return eligible, rejected

    def _active_reservations(self, db: Session, node_id: str) -> tuple[int, int, int]:
        cpu, memory, leases = db.execute(
            select(
                func.coalesce(func.sum(RuntimeResourceLease.cpu_millis), 0),
                func.coalesce(func.sum(RuntimeResourceLease.memory_mb), 0),
                func.count(RuntimeResourceLease.id),
            )
            .where(RuntimeResourceLease.node_id == node_id)
            .where(RuntimeResourceLease.status == "active")
        ).one()
        return int(cpu), int(memory), int(leases)

    def _release_resources(
        self,
        node: RuntimeNode | None,
        lease: RuntimeResourceLease,
        released_at: datetime,
        *,
        status: str,
    ) -> None:
        if node is not None:
            node.active_leases = max(node.active_leases - 1, 0)
            node.available_cpu_millis = min(
                node.available_cpu_millis + lease.cpu_millis,
                node.total_cpu_millis,
            )
            node.available_memory_mb = min(
                node.available_memory_mb + lease.memory_mb,
                node.total_memory_mb,
            )
            node.updated_at = released_at
        lease.status = status
        lease.released_at = released_at

    def _lock_attempt_identity(
        self, db: Session, task_id: str, attempt_id: str
    ) -> None:
        if db.get_bind().dialect.name != "postgresql":
            return
        identity = f"{task_id}\0{attempt_id}".encode()
        lock_id = int.from_bytes(
            hashlib.blake2b(identity, digest_size=8).digest(), signed=True
        )
        db.execute(select(func.pg_advisory_xact_lock(lock_id)))

    def _refresh_node_states(
        self, nodes: list[RuntimeNode], checked_at: datetime
    ) -> int:
        changed = 0
        for node in nodes:
            if _state(node) is NodeState.draining:
                continue
            if (
                node.last_heartbeat_at is None
                or checked_at - _as_aware(node.last_heartbeat_at)
                > self.heartbeat_timeout
            ) and node.state != NodeState.unreachable.value:
                node.state = NodeState.unreachable.value
                node.updated_at = checked_at
                changed += 1
        return changed

    def _select_node(
        self,
        db: Session,
        strategy: str,
        eligible: list[RuntimeNode],
        tenant_id: str,
    ) -> RuntimeNode:
        if strategy == "least_loaded":
            return min(
                eligible,
                key=lambda node: (
                    _state(node) is NodeState.degraded,
                    node.active_leases,
                    _utilization(node),
                    node.node_id,
                ),
            )

        ordered = sorted(eligible, key=lambda node: (_state(node) is NodeState.degraded, node.node_id))
        previous = db.scalars(
            select(SchedulingDecision)
            .where(SchedulingDecision.tenant_id == tenant_id)
            .where(SchedulingDecision.strategy == "round_robin")
            .where(SchedulingDecision.selected_node_id.is_not(None))
            .order_by(desc(SchedulingDecision.created_at), desc(SchedulingDecision.id))
        ).first()
        if not previous or previous.selected_node_id not in {node.node_id for node in ordered}:
            return ordered[0]
        previous_index = [node.node_id for node in ordered].index(previous.selected_node_id)
        return ordered[(previous_index + 1) % len(ordered)]

    def _tenant_allowed(self, node: RuntimeNode, tenant_id: str) -> bool:
        tenants = _list(node.tenant_ids_json)
        return not tenants or tenant_id in tenants

    def _record_decision(
        self,
        db: Session,
        request: SchedulingRequest,
        decision: str,
        selected_node_id: str | None,
        reason: str,
        eligible_nodes: tuple[str, ...],
        rejected_nodes: dict[str, str],
        actor: str,
        *,
        idempotent_replay: bool = False,
        lease_token: str | None = None,
        lease_generation: int | None = None,
        lease_expires_at: datetime | None = None,
    ) -> SchedulingResult:
        row = SchedulingDecision(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            tenant_id=request.tenant_id,
            strategy=request.strategy,
            decision=decision,
            selected_node_id=selected_node_id,
            reason=reason,
            eligible_nodes_json=_json_list(eligible_nodes),
            rejected_nodes_json=_json_map(rejected_nodes),
            required_capabilities_json=_json_list(request.required_capabilities),
            trace_id=request.trace_id,
        )
        db.add(row)
        append_runtime_audit_event(
            db,
            action="runtime.schedule",
            actor=actor,
            tenant_id=request.tenant_id,
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            node_id=selected_node_id,
            trace_id=request.trace_id,
            outcome=decision,
            reason=reason,
            retry_count=request.retry_count,
        )
        db.commit()
        emit_audit("runtime.schedule", actor, request.tenant_id)
        return SchedulingResult(
            task_id=request.task_id,
            attempt_id=request.attempt_id,
            tenant_id=request.tenant_id,
            strategy=request.strategy,
            decision=decision,
            selected_node_id=selected_node_id,
            reason=reason,
            eligible_nodes=eligible_nodes,
            rejected_nodes=rejected_nodes,
            idempotent_replay=idempotent_replay,
            lease_token=lease_token,
            lease_generation=lease_generation,
            lease_expires_at=lease_expires_at,
        )


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _utilization(node: RuntimeNode) -> float:
    cpu_total = max(node.total_cpu_millis, 1)
    mem_total = max(node.total_memory_mb, 1)
    cpu_used = max(node.total_cpu_millis - node.available_cpu_millis, 0) / cpu_total
    mem_used = max(node.total_memory_mb - node.available_memory_mb, 0) / mem_total
    return max(cpu_used, mem_used)
