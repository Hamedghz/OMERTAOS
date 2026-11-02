from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from control.audit import (
    MAX_AUDIT_EVENTS_PER_TASK,
    RuntimeAuditEvent,
    list_runtime_audit_events,
)
from control.app.network.models import get_db
from control.app.service_auth import require_gateway_service_token
from control.scheduling import (
    NodeState,
    RuntimeNodeHeartbeat,
    RuntimeNodeRegistration,
    RuntimeScheduler,
    SchedulingRequest,
)
from control.scheduling.models import RuntimeNode

from .schemas import (
    RuntimeNodeHeartbeatIn,
    RuntimeNodeList,
    RuntimeNodeOut,
    RuntimeNodeRegistrationIn,
    RuntimeAuditEventOut,
    RuntimeAuditTrailOut,
    SchedulingRequestIn,
    SchedulingResultOut,
)

router = APIRouter(prefix="/v1/runtime", tags=["runtime-nodes"])
scheduler = RuntimeScheduler()


def _actor(request: Request) -> str:
    return (
        request.headers.get("x-aion-user-id")
        or request.headers.get("x-request-id")
        or "system"
    )


def _tenant(request: Request) -> str:
    return (
        request.headers.get("tenant-id")
        or request.headers.get("x-tenant-id")
        or "default"
    )


def require_admin(request: Request) -> None:
    require_gateway_service_token(request)


def _load_json_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(value) for value in parsed] if isinstance(parsed, list) else []


def _load_json_map(raw: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _node_out(node: RuntimeNode) -> RuntimeNodeOut:
    return RuntimeNodeOut(
        node_id=node.node_id,
        endpoint=node.endpoint,
        state=node.state,
        software_version=node.software_version,
        contract_version=node.contract_version,
        trust_zone=node.trust_zone,
        capabilities=_load_json_list(node.capabilities_json),
        tenant_ids=_load_json_list(node.tenant_ids_json),
        labels=_load_json_map(node.labels_json),
        total_cpu_millis=node.total_cpu_millis,
        total_memory_mb=node.total_memory_mb,
        available_cpu_millis=node.available_cpu_millis,
        available_memory_mb=node.available_memory_mb,
        active_leases=node.active_leases,
        drain_requested=node.drain_requested,
        last_heartbeat_at=node.last_heartbeat_at,
    )


def _audit_out(event: RuntimeAuditEvent) -> RuntimeAuditEventOut:
    return RuntimeAuditEventOut(
        event_id=event.event_id,
        action=event.action,
        actor=event.actor,
        tenant_id=event.tenant_id,
        task_id=event.task_id,
        attempt_id=event.attempt_id,
        node_id=event.node_id,
        request_id=event.request_id,
        trace_id=event.trace_id,
        outcome=event.outcome,
        reason=event.reason,
        retry_count=event.retry_count,
        created_at=event.created_at,
    )


@router.post(
    "/nodes", response_model=RuntimeNodeOut, status_code=status.HTTP_201_CREATED
)
def register_runtime_node(
    payload: RuntimeNodeRegistrationIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> RuntimeNodeOut:
    registration = RuntimeNodeRegistration(
        node_id=payload.node_id,
        endpoint=payload.endpoint,
        capabilities=tuple(payload.capabilities),
        total_cpu_millis=payload.total_cpu_millis,
        total_memory_mb=payload.total_memory_mb,
        available_cpu_millis=payload.available_cpu_millis,
        available_memory_mb=payload.available_memory_mb,
        tenant_ids=tuple(payload.tenant_ids),
        software_version=payload.software_version,
        contract_version=payload.contract_version,
        trust_zone=payload.trust_zone,
        labels=payload.labels,
    )
    return _node_out(scheduler.register_node(db, registration, actor=_actor(request)))


@router.post("/nodes/{node_id}/heartbeat", response_model=RuntimeNodeOut)
def heartbeat_runtime_node(
    node_id: str,
    payload: RuntimeNodeHeartbeatIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> RuntimeNodeOut:
    heartbeat = RuntimeNodeHeartbeat(
        available_cpu_millis=payload.available_cpu_millis,
        available_memory_mb=payload.available_memory_mb,
        active_leases=payload.active_leases,
        state=NodeState(payload.state.value),
        capabilities=tuple(payload.capabilities)
        if payload.capabilities is not None
        else None,
    )
    try:
        node = scheduler.record_heartbeat(db, node_id, heartbeat, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _node_out(node)


@router.post("/nodes/{node_id}/drain", response_model=RuntimeNodeOut)
def drain_runtime_node(
    node_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> RuntimeNodeOut:
    try:
        node = scheduler.mark_draining(db, node_id, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _node_out(node)


@router.get("/nodes", response_model=RuntimeNodeList)
def list_runtime_nodes(
    request: Request,
    tenant_id: str | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> RuntimeNodeList:
    resolved_tenant = tenant_id or _tenant(request)
    return RuntimeNodeList(
        items=[
            _node_out(node) for node in scheduler.discover_workers(db, resolved_tenant)
        ]
    )


@router.get("/audit/{task_id}", response_model=RuntimeAuditTrailOut)
def get_runtime_audit_trail(
    request: Request,
    task_id: str = Path(min_length=1, max_length=120),
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(
        default=MAX_AUDIT_EVENTS_PER_TASK, ge=1, le=MAX_AUDIT_EVENTS_PER_TASK
    ),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> RuntimeAuditTrailOut:
    tenant_id = _tenant(request)
    page = list_runtime_audit_events(
        db,
        task_id=task_id,
        tenant_id=tenant_id,
        cursor=cursor,
        limit=limit,
    )
    return RuntimeAuditTrailOut(
        task_id=task_id,
        tenant_id=tenant_id,
        items=[_audit_out(event) for event in page.items],
        next_cursor=page.next_cursor,
        truncated=page.truncated,
    )


@router.post("/schedule", response_model=SchedulingResultOut)
def schedule_runtime_attempt(
    payload: SchedulingRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> SchedulingResultOut:
    scheduling_request = SchedulingRequest(
        task_id=payload.task_id,
        attempt_id=payload.attempt_id,
        tenant_id=payload.tenant_id,
        required_capabilities=tuple(payload.required_capabilities),
        cpu_millis=payload.cpu_millis,
        memory_mb=payload.memory_mb,
        strategy=payload.strategy,
        idempotency_key=payload.idempotency_key,
        retry_count=payload.retry_count,
        max_retries=payload.max_retries,
        trace_id=request.headers.get("traceparent")
        or request.headers.get("x-correlation-id"),
        request_id=request.headers.get("x-correlation-id")
        or request.headers.get("x-request-id"),
    )
    result = scheduler.schedule(db, scheduling_request, actor=_actor(request))
    return SchedulingResultOut(
        task_id=result.task_id,
        attempt_id=result.attempt_id,
        tenant_id=result.tenant_id,
        strategy=result.strategy,
        decision=result.decision,
        selected_node_id=result.selected_node_id,
        reason=result.reason,
        eligible_nodes=list(result.eligible_nodes),
        rejected_nodes=result.rejected_nodes,
        idempotent_replay=result.idempotent_replay,
    )
