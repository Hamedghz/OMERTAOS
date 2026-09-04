from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from control.app.main import app
from control.orchestration.runtime_dispatch import (
    RUNTIME_ECHO_INTENT,
    RuntimeDispatchRequest,
    RuntimeDispatchResult,
)
from control.transports import GrpcAdapter, GrpcTransportUnavailable
from control.transports.tasks_grpc import AionTasksGenericHandler, TaskId, TaskRequest
from control.transports import tasks_grpc as tasks_grpc_module
from shared.config.environment import EnvironmentConflictError


@dataclass(frozen=True)
class _MetadataItem:
    key: str
    value: str


class _FakeContext:
    def invocation_metadata(self) -> list[_MetadataItem]:
        return [
            _MetadataItem("tenant-id", "tenant-a"),
            _MetadataItem("x-request-id", "req-a"),
            _MetadataItem("x-correlation-id", "correlation-a"),
            _MetadataItem("traceparent", "00-trace-a-span-a-01"),
            _MetadataItem("idempotency-key", "idem-a"),
        ]

    def abort(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("abort should not be called for unary task adapters")


class _FakeDispatcher:
    def __init__(self) -> None:
        self.requests: list[RuntimeDispatchRequest] = []

    def supports(self, intent: str) -> bool:
        return intent == RUNTIME_ECHO_INTENT

    def dispatch(self, request: RuntimeDispatchRequest) -> RuntimeDispatchResult:
        self.requests.append(request)
        return RuntimeDispatchResult(
            status="OK",
            reason="allowlisted command executed by selected Runtime node",
            attempt_id="task-a:0",
            selected_node_id="node-a",
            exit_code=0,
            stdout="hello runtime\n",
            retry_count=0,
            latency_ms=2.5,
        )


def test_all_control_health_aliases_share_canonical_payload() -> None:
    client = TestClient(app)
    expected = {"status": "ok", "service": "control"}

    for path in ("/health", "/healthz", "/v1/health", "/v1/healthz"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == expected


@pytest.mark.asyncio
async def test_grpc_adapter_fails_closed_without_server_factory() -> None:
    with pytest.raises(GrpcTransportUnavailable, match="no-op adapter"):
        await GrpcAdapter("0.0.0.0:50051").serve()


@pytest.mark.asyncio
async def test_grpc_adapter_delegates_to_server_factory() -> None:
    endpoints: list[str] = []

    async def serve(endpoint: str) -> None:
        endpoints.append(endpoint)

    await GrpcAdapter("0.0.0.0:50051", server_factory=serve).serve()

    assert endpoints == ["0.0.0.0:50051"]


def test_minimal_control_grpc_submit_fails_closed_without_runtime_transport() -> None:
    request = TaskRequest()
    request.schema_version = "1.0"
    request.task_id = "task-a"
    request.intent = "capo.r4.health_probe"
    request.metadata["agent_id"] = "agent-a"

    response = AionTasksGenericHandler().submit(request, _FakeContext())

    assert response.task_id == "task-a"
    assert response.intent == "capo.r4.health_probe"
    assert response.status == "ERROR"
    assert response.engine.route == "runtime"
    assert response.engine.chosen_by == "control"
    assert response.error.code == "RUNTIME_TRANSPORT_UNAVAILABLE"
    assert "synthetic success" in response.error.message
    assert response.metadata["tenant_id"] == "tenant-a"
    assert response.metadata["request_id"] == "correlation-a"


def test_control_grpc_submit_dispatches_allowlisted_runtime_intent() -> None:
    request = TaskRequest()
    request.schema_version = "1.0"
    request.task_id = "task-a"
    request.intent = RUNTIME_ECHO_INTENT
    request.params["message"] = "hello runtime"
    request.metadata["agent_id"] = "agent-a"
    dispatcher = _FakeDispatcher()

    response = AionTasksGenericHandler(dispatcher=dispatcher).submit(
        request, _FakeContext()
    )

    assert response.status == "OK"
    assert response.result["stdout"] == "hello runtime\n"
    assert response.result["exit_code"] == "0"
    assert response.metadata["runtime_node_id"] == "node-a"
    assert response.metadata["request_id"] == "correlation-a"
    assert response.metadata["trace_id"] == "00-trace-a-span-a-01"
    assert dispatcher.requests == [
        RuntimeDispatchRequest(
            task_id="task-a",
            intent=RUNTIME_ECHO_INTENT,
            tenant_id="tenant-a",
            agent_id="agent-a",
            message="hello runtime",
            request_id="correlation-a",
            trace_id="00-trace-a-span-a-01",
            idempotency_key="idem-a",
        )
    ]


def test_control_grpc_submit_rejects_invalid_runtime_request() -> None:
    request = TaskRequest()
    request.schema_version = "1.0"
    request.task_id = "task-a"
    request.intent = RUNTIME_ECHO_INTENT
    request.metadata["agent_id"] = "agent-a"
    dispatcher = _FakeDispatcher()

    response = AionTasksGenericHandler(dispatcher=dispatcher).submit(
        request, _FakeContext()
    )

    assert response.status == "ERROR"
    assert response.error.code == "RUNTIME_REQUEST_INVALID"
    assert dispatcher.requests == []


def test_control_grpc_server_reads_canonical_bind_and_rejects_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeServer:
        def __init__(self) -> None:
            self.endpoints: list[str] = []
            self.started = False

        def add_insecure_port(self, endpoint: str) -> int:
            self.endpoints.append(endpoint)
            return 50051

        def start(self) -> None:
            self.started = True

    server = FakeServer()
    monkeypatch.delenv("AION_CONTROL_GRPC_BIND", raising=False)
    monkeypatch.setenv("OMERTA_CONTROL_GRPC_BIND", "127.0.0.1:50051")
    monkeypatch.setattr(tasks_grpc_module, "create_server", lambda: server)

    assert tasks_grpc_module.serve() is server
    assert server.endpoints == ["127.0.0.1:50051"]
    assert server.started is True

    monkeypatch.setenv("AION_CONTROL_GRPC_BIND", "0.0.0.0:50051")
    with pytest.raises(EnvironmentConflictError):
        tasks_grpc_module.serve()


def test_minimal_control_grpc_status_fails_closed_without_storage() -> None:
    request = TaskId()
    request.task_id = "task-a"

    response = AionTasksGenericHandler().status_by_id(request, _FakeContext())

    assert response.task_id == "task-a"
    assert response.status == "ERROR"
    assert response.error.code == "TASK_STATUS_UNAVAILABLE"
