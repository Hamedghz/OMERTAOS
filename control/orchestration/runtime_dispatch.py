from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from time import perf_counter

from sqlalchemy.orm import Session

from control.audit import append_runtime_audit_event
from control.app.network.models import SessionLocal, init_db
from control.clients.runtime import (
    RuntimeDaemonClient,
    RuntimeEnvelope,
    RuntimeExecutionRejected,
    RuntimeExecutor,
    RuntimeLeaseRejected,
    RuntimeTransportUnavailable,
)
from control.scheduling import NodeState, RuntimeScheduler, SchedulingRequest
from control.scheduling.models import RuntimeNode
from shared.config.environment import integer_parser, resolve_environment
from shared.telemetry.audit import emit_audit

RUNTIME_ECHO_INTENT = "runtime.echo.v1"
RUNTIME_EXECUTE_CAPABILITY = "terminal.execute"
MAX_ECHO_MESSAGE_LENGTH = 1024
MAX_RESULT_TEXT_LENGTH = 64 * 1024
RESULT_CACHE_SIZE = 256


@dataclass(frozen=True, slots=True)
class RuntimeDispatchRequest:
    task_id: str
    intent: str
    tenant_id: str
    agent_id: str
    message: str
    request_id: str = ""
    trace_id: str = ""
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        for value, name, limit in (
            (self.task_id, "task_id", 120),
            (self.intent, "intent", 120),
            (self.tenant_id, "tenant_id", 120),
            (self.agent_id, "agent_id", 120),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
            if len(value) > limit:
                raise ValueError(f"{name} exceeds {limit} characters")
        if self.intent != RUNTIME_ECHO_INTENT:
            raise ValueError("unsupported runtime intent")
        if not self.message:
            raise ValueError("message is required")
        if len(self.message) > MAX_ECHO_MESSAGE_LENGTH:
            raise ValueError(
                f"message exceeds {MAX_ECHO_MESSAGE_LENGTH} characters"
            )
        if "\x00" in self.message:
            raise ValueError("message contains a null byte")
        for value, name in (
            (self.request_id, "request_id"),
            (self.trace_id, "trace_id"),
            (self.idempotency_key or "", "idempotency_key"),
        ):
            if len(value) > 255:
                raise ValueError(f"{name} exceeds 255 characters")


@dataclass(frozen=True, slots=True)
class RuntimeDispatchResult:
    status: str
    reason: str
    attempt_id: str = ""
    selected_node_id: str | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    idempotent_replay: bool = False
    latency_ms: float = 0.0


RuntimeClientFactory = Callable[[str], RuntimeExecutor]
SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class _KeyLockEntry:
    lock: threading.Lock
    users: int = 0


class RuntimeTaskDispatcher:
    """Schedule and dispatch the single allowlisted R5 execution intent."""

    def __init__(
        self,
        *,
        scheduler: RuntimeScheduler | None = None,
        session_factory: SessionFactory = SessionLocal,
        schema_initializer: Callable[[], None] = init_db,
        client_factory: RuntimeClientFactory | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        resolved_timeout = timeout_seconds
        if resolved_timeout is None:
            resolved_timeout = resolve_environment(
                "OMERTA_RUNTIME_TIMEOUT_SECONDS",
                aliases=("AION_RUNTIME_TIMEOUT_SECONDS",),
                default="5",
                parser=float,
            )
            assert isinstance(resolved_timeout, float)
        if resolved_timeout <= 0 or resolved_timeout > 30:
            raise ValueError("Runtime timeout must be between 0 and 30 seconds")

        resolved_retries = max_retries
        if resolved_retries is None:
            resolved_retries = resolve_environment(
                "OMERTA_RUNTIME_MAX_RETRIES",
                aliases=("AION_RUNTIME_MAX_RETRIES",),
                default="1",
                parser=integer_parser(),
            )
            assert isinstance(resolved_retries, int)
        if resolved_retries < 0 or resolved_retries > 1:
            raise ValueError("Runtime retries must be between 0 and 1")

        self.scheduler = scheduler or RuntimeScheduler()
        if self.scheduler.lease_ttl.total_seconds() <= resolved_timeout:
            raise ValueError("Runtime lease TTL must exceed the execution timeout")
        self._session_factory = session_factory
        self._schema_initializer = schema_initializer
        self._client_factory = client_factory or (
            lambda endpoint: RuntimeDaemonClient(
                endpoint=endpoint,
                timeout_seconds=resolved_timeout,
            )
        )
        self.timeout_seconds = resolved_timeout
        self.max_retries = resolved_retries
        self._schema_ready = False
        self._schema_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._result_cache: OrderedDict[
            str, tuple[str, RuntimeDispatchResult]
        ] = OrderedDict()
        self._key_locks_guard = threading.Lock()
        self._key_locks: dict[str, _KeyLockEntry] = {}

    @staticmethod
    def supports(intent: str) -> bool:
        return intent == RUNTIME_ECHO_INTENT

    def dispatch(self, request: RuntimeDispatchRequest) -> RuntimeDispatchResult:
        started = perf_counter()
        cache_key = f"{request.tenant_id}:{request.task_id}"
        digest = _request_digest(request)
        key_lock = self._acquire_key_lock(cache_key)
        try:
            cached = self._cached(cache_key)
            if cached is not None:
                cached_digest, cached_result = cached
                if cached_digest != digest:
                    self._record_cached_audit(
                        request,
                        cached_result,
                        action="runtime.dispatch.idempotency_conflict",
                        outcome="rejected",
                        reason="runtime request identity conflict",
                    )
                    return _with_latency(
                        _error_result(
                            code="RUNTIME_IDEMPOTENCY_CONFLICT",
                            message="Task identity was reused with a different runtime request",
                            reason="runtime request identity conflict",
                        ),
                        started,
                    )
                self._record_cached_audit(
                    request,
                    cached_result,
                    action="runtime.dispatch.cache_replay",
                    outcome="replayed",
                    reason="runtime result replayed from bounded process cache",
                )
                return _with_latency(
                    replace(cached_result, idempotent_replay=True),
                    started,
                )

            self._ensure_schema()
            db = self._session_factory()
            try:
                result, cacheable = self._dispatch_with_session(db, request)
            finally:
                db.close()
            result = _with_latency(result, started)
            if cacheable:
                self._remember(cache_key, digest, result)
            return result
        finally:
            self._release_key_lock(cache_key, key_lock)

    def _dispatch_with_session(
        self,
        db: Session,
        request: RuntimeDispatchRequest,
    ) -> tuple[RuntimeDispatchResult, bool]:
        for retry_count in range(self.max_retries + 1):
            attempt_id = f"{request.task_id}:{retry_count}"
            scheduling = self.scheduler.schedule(
                db,
                SchedulingRequest(
                    task_id=request.task_id,
                    attempt_id=attempt_id,
                    tenant_id=request.tenant_id,
                    required_capabilities=(RUNTIME_EXECUTE_CAPABILITY,),
                    strategy="round_robin",
                    idempotency_key=request.idempotency_key,
                    retry_count=retry_count,
                    max_retries=self.max_retries,
                    trace_id=request.trace_id or request.request_id or None,
                ),
                actor=request.agent_id,
            )
            if scheduling.idempotent_replay:
                attempt = self.scheduler.get_attempt(
                    db, request.task_id, attempt_id, request.tenant_id
                )
                status = attempt.status if attempt is not None else "unknown"
                if status == "expired" and retry_count < self.max_retries:
                    append_runtime_audit_event(
                        db,
                        action="runtime.dispatch.reclaimed_retry",
                        actor=request.agent_id,
                        tenant_id=request.tenant_id,
                        task_id=request.task_id,
                        attempt_id=attempt_id,
                        node_id=scheduling.selected_node_id,
                        request_id=request.request_id,
                        trace_id=request.trace_id,
                        outcome="retrying",
                        reason="expired runtime lease was reclaimed",
                        retry_count=retry_count,
                    )
                    db.commit()
                    continue
                append_runtime_audit_event(
                    db,
                    action="runtime.dispatch.replay_blocked",
                    actor=request.agent_id,
                    tenant_id=request.tenant_id,
                    task_id=request.task_id,
                    attempt_id=attempt_id,
                    node_id=scheduling.selected_node_id,
                    request_id=request.request_id,
                    trace_id=request.trace_id,
                    outcome="rejected",
                    reason="durable runtime result replay is unavailable",
                    retry_count=retry_count,
                )
                db.commit()
                return (
                    _error_result(
                        code="RUNTIME_RESULT_REPLAY_UNAVAILABLE",
                        message=(
                            "Runtime attempt was already dispatched; durable result replay "
                            "is not available"
                        ),
                        reason=f"runtime attempt replay blocked ({status})",
                        attempt_id=attempt_id,
                        selected_node_id=scheduling.selected_node_id,
                        retry_count=retry_count,
                        idempotent_replay=True,
                    ),
                    False,
                )
            if scheduling.selected_node_id is None:
                code, message = _scheduling_error(scheduling.rejected_nodes)
                return (
                    _error_result(
                        code=code,
                        message=message,
                        reason=scheduling.reason,
                        attempt_id=attempt_id,
                        retry_count=retry_count,
                    ),
                    False,
                )

            node = db.get(RuntimeNode, scheduling.selected_node_id)
            if node is None:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="transport_error",
                    node_state=NodeState.unreachable,
                    audit_action="runtime.dispatch.unavailable",
                    reason="selected runtime node disappeared before dispatch",
                    lease_generation=scheduling.lease_generation,
                )
                if retry_count < self.max_retries:
                    continue
                return (
                    _error_result(
                        code="RUNTIME_NODE_UNAVAILABLE",
                        message="Selected Runtime node is no longer registered",
                        reason="selected runtime node disappeared before dispatch",
                        attempt_id=attempt_id,
                        selected_node_id=scheduling.selected_node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )

            append_runtime_audit_event(
                db,
                action="runtime.dispatch.start",
                actor=request.agent_id,
                tenant_id=request.tenant_id,
                task_id=request.task_id,
                attempt_id=attempt_id,
                node_id=node.node_id,
                request_id=request.request_id,
                trace_id=request.trace_id,
                outcome="started",
                reason="runtime execution started",
                retry_count=retry_count,
            )
            db.commit()
            emit_audit("runtime.dispatch.start", request.agent_id, request.tenant_id)
            envelope = RuntimeEnvelope(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                argv=("/usr/bin/printf", "%s\\n", request.message),
                task_id=request.task_id,
                attempt_id=attempt_id,
                request_id=request.request_id,
                trace_id=request.trace_id,
                capabilities=(RUNTIME_EXECUTE_CAPABILITY,),
                node_id=node.node_id,
                lease_token=scheduling.lease_token or "",
                lease_generation=scheduling.lease_generation or 0,
                lease_expires_at_ms=(
                    int(scheduling.lease_expires_at.timestamp() * 1000)
                    if scheduling.lease_expires_at is not None
                    else 0
                ),
            )
            try:
                response = asyncio.run(self._client_factory(node.endpoint).execute(envelope))
            except TimeoutError:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="timeout",
                    node_state=NodeState.degraded,
                    audit_action="runtime.dispatch.timeout",
                    reason="runtime execution timed out",
                    lease_generation=scheduling.lease_generation,
                )
                emit_audit("runtime.dispatch.timeout", request.agent_id, request.tenant_id)
                if retry_count < self.max_retries:
                    continue
                return (
                    _error_result(
                        code="RUNTIME_TIMEOUT",
                        message="Runtime execution exceeded the bounded deadline",
                        reason="runtime execution timed out",
                        status="TIMEOUT",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )
            except RuntimeTransportUnavailable:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="transport_error",
                    node_state=NodeState.unreachable,
                    audit_action="runtime.dispatch.unavailable",
                    reason="runtime transport failed closed",
                    lease_generation=scheduling.lease_generation,
                )
                emit_audit(
                    "runtime.dispatch.unavailable", request.agent_id, request.tenant_id
                )
                if retry_count < self.max_retries:
                    continue
                return (
                    _error_result(
                        code="RUNTIME_TRANSPORT_UNAVAILABLE",
                        message="Runtime transport is unavailable",
                        reason="runtime transport failed closed",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )
            except RuntimeLeaseRejected:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="fenced",
                    audit_action="runtime.dispatch.fenced",
                    reason="runtime rejected an expired or fenced execution lease",
                    lease_generation=scheduling.lease_generation,
                )
                emit_audit("runtime.dispatch.fenced", request.agent_id, request.tenant_id)
                if retry_count < self.max_retries:
                    continue
                return (
                    _error_result(
                        code="RUNTIME_LEASE_REJECTED",
                        message="Runtime rejected the execution lease",
                        reason="runtime lease was expired or fenced",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )
            except RuntimeExecutionRejected:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="rejected",
                    audit_action="runtime.dispatch.rejected",
                    reason="runtime capability or execution policy rejected the request",
                    lease_generation=scheduling.lease_generation,
                )
                emit_audit("runtime.dispatch.rejected", request.agent_id, request.tenant_id)
                return (
                    _error_result(
                        code="RUNTIME_EXECUTION_REJECTED",
                        message="Runtime rejected the execution request",
                        reason="runtime capability or execution policy rejected the request",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )
            except Exception:
                self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="failed",
                    audit_action="runtime.dispatch.failed",
                    reason="unexpected runtime dispatch failure",
                    lease_generation=scheduling.lease_generation,
                )
                emit_audit("runtime.dispatch.failed", request.agent_id, request.tenant_id)
                return (
                    _error_result(
                        code="RUNTIME_DISPATCH_FAILED",
                        message="Runtime dispatch failed without exposing internal details",
                        reason="unexpected runtime dispatch failure",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )

            parsed = _parse_runtime_response(response)
            if parsed.error_code is not None:
                finished = self._finish_attempt(
                    db,
                    request,
                    attempt_id,
                    status="failed",
                    audit_action="runtime.dispatch.failed",
                    reason="runtime returned an execution error",
                    lease_generation=scheduling.lease_generation,
                )
                if not finished:
                    return (
                        _error_result(
                            code="RUNTIME_LEASE_REJECTED",
                            message="Runtime result arrived after its lease was fenced",
                            reason="stale runtime result was rejected",
                            attempt_id=attempt_id,
                            selected_node_id=node.node_id,
                            retry_count=retry_count,
                        ),
                        True,
                    )
                emit_audit("runtime.dispatch.failed", request.agent_id, request.tenant_id)
                return (
                    replace(
                        parsed,
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )

            finished = self._finish_attempt(
                db,
                request,
                attempt_id,
                status="completed",
                audit_action="runtime.dispatch.success",
                reason="runtime execution completed",
                lease_generation=scheduling.lease_generation,
            )
            if not finished:
                return (
                    _error_result(
                        code="RUNTIME_LEASE_REJECTED",
                        message="Runtime result arrived after its lease was fenced",
                        reason="stale runtime result was rejected",
                        attempt_id=attempt_id,
                        selected_node_id=node.node_id,
                        retry_count=retry_count,
                    ),
                    True,
                )
            emit_audit("runtime.dispatch.success", request.agent_id, request.tenant_id)
            return (
                replace(
                    parsed,
                    attempt_id=attempt_id,
                    selected_node_id=node.node_id,
                    retry_count=retry_count,
                ),
                True,
            )

        raise AssertionError("bounded Runtime retry loop did not return")

    def _finish_attempt(
        self,
        db: Session,
        request: RuntimeDispatchRequest,
        attempt_id: str,
        *,
        status: str,
        audit_action: str,
        reason: str,
        node_state: NodeState | None = None,
        lease_generation: int | None = None,
    ) -> bool:
        attempt = self.scheduler.finish_attempt(
            db,
            request.task_id,
            attempt_id,
            tenant_id=request.tenant_id,
            status=status,
            node_state=node_state,
            actor=request.agent_id,
            audit_action=audit_action,
            request_id=request.request_id,
            trace_id=request.trace_id,
            reason=reason,
            lease_generation=lease_generation,
        )
        return attempt.status == status

    def _record_cached_audit(
        self,
        request: RuntimeDispatchRequest,
        result: RuntimeDispatchResult,
        *,
        action: str,
        outcome: str,
        reason: str,
    ) -> None:
        self._ensure_schema()
        db = self._session_factory()
        try:
            append_runtime_audit_event(
                db,
                action=action,
                actor=request.agent_id,
                tenant_id=request.tenant_id,
                task_id=request.task_id,
                attempt_id=result.attempt_id or None,
                node_id=result.selected_node_id,
                request_id=request.request_id,
                trace_id=request.trace_id,
                outcome=outcome,
                reason=reason,
                retry_count=result.retry_count,
            )
            db.commit()
        finally:
            db.close()

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if not self._schema_ready:
                self._schema_initializer()
                self._schema_ready = True

    def _cached(self, key: str) -> tuple[str, RuntimeDispatchResult] | None:
        with self._cache_lock:
            cached = self._result_cache.get(key)
            if cached is not None:
                self._result_cache.move_to_end(key)
            return cached

    def _remember(
        self,
        key: str,
        digest: str,
        result: RuntimeDispatchResult,
    ) -> None:
        with self._cache_lock:
            self._result_cache[key] = (digest, result)
            self._result_cache.move_to_end(key)
            while len(self._result_cache) > RESULT_CACHE_SIZE:
                self._result_cache.popitem(last=False)

    def _acquire_key_lock(self, key: str) -> threading.Lock:
        with self._key_locks_guard:
            entry = self._key_locks.get(key)
            if entry is None:
                entry = _KeyLockEntry(threading.Lock())
                self._key_locks[key] = entry
            entry.users += 1
            lock = entry.lock
        lock.acquire()
        return lock

    def _release_key_lock(self, key: str, lock: threading.Lock) -> None:
        lock.release()
        with self._key_locks_guard:
            entry = self._key_locks[key]
            entry.users -= 1
            if entry.users == 0:
                del self._key_locks[key]


def _request_digest(request: RuntimeDispatchRequest) -> str:
    payload = "\x1f".join(
        (
            request.intent,
            request.tenant_id,
            request.agent_id,
            request.message,
            request.idempotency_key or "",
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_runtime_response(response: dict[str, object]) -> RuntimeDispatchResult:
    code = response.get("code")
    ok = response.get("ok")
    if not isinstance(code, int) or not isinstance(ok, bool):
        return _error_result(
            code="RUNTIME_PROTOCOL_ERROR",
            message="Runtime returned an invalid execution response",
            reason="runtime response contract validation failed",
        )
    stdout = _bounded_text(response.get("stdout"))
    stderr = _bounded_text(response.get("stderr"))
    if not ok or code != 0:
        return RuntimeDispatchResult(
            status="ERROR",
            reason="runtime command returned a non-zero exit code",
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            error_code="RUNTIME_COMMAND_FAILED",
            error_message="Runtime command failed",
        )
    return RuntimeDispatchResult(
        status="OK",
        reason="allowlisted command executed by selected Runtime node",
        exit_code=code,
        stdout=stdout,
        stderr=stderr,
    )


def _bounded_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if len(value) <= MAX_RESULT_TEXT_LENGTH:
        return value
    return value[:MAX_RESULT_TEXT_LENGTH]


def _scheduling_error(rejected_nodes: dict[str, str]) -> tuple[str, str]:
    reasons = set(rejected_nodes.values())
    if "capability" in reasons:
        return (
            "RUNTIME_CAPABILITY_UNAVAILABLE",
            "No Runtime node advertises the required capability",
        )
    if reasons and reasons <= {"state:draining"}:
        return "RUNTIME_NODE_DRAINING", "All eligible Runtime nodes are draining"
    return "RUNTIME_NODE_UNAVAILABLE", "No eligible Runtime node is available"


def _error_result(
    *,
    code: str,
    message: str,
    reason: str,
    status: str = "ERROR",
    attempt_id: str = "",
    selected_node_id: str | None = None,
    retry_count: int = 0,
    idempotent_replay: bool = False,
) -> RuntimeDispatchResult:
    return RuntimeDispatchResult(
        status=status,
        reason=reason,
        attempt_id=attempt_id,
        selected_node_id=selected_node_id,
        error_code=code,
        error_message=message,
        retry_count=retry_count,
        idempotent_replay=idempotent_replay,
    )


def _with_latency(
    result: RuntimeDispatchResult,
    started: float,
) -> RuntimeDispatchResult:
    return replace(result, latency_ms=(perf_counter() - started) * 1000)
