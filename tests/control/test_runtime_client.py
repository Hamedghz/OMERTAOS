from __future__ import annotations

import asyncio
from importlib import import_module
from types import SimpleNamespace

import grpc
import pytest

from control.clients.runtime import (
    RuntimeDaemonClient,
    RuntimeEnvelope,
    RuntimeExecutionRejected,
    RuntimeLeaseRejected,
    RuntimeTransportUnavailable,
)
from control.clients.runtime import grpc_transport as grpc_transport_module
from control.clients.runtime.grpc_transport import GrpcRuntimeTransport
from shared.config.environment import EnvironmentConflictError


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, RuntimeEnvelope, float]] = []

    async def execute(
        self,
        endpoint: str,
        envelope: RuntimeEnvelope,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append((endpoint, envelope, timeout_seconds))
        return {"ok": True, "agent_id": envelope.agent_id}


class SlowTransport:
    async def execute(
        self,
        endpoint: str,
        envelope: RuntimeEnvelope,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        await asyncio.sleep(timeout_seconds * 10)
        return {"ok": True}


class ErrorTransport:
    def __init__(self, status: grpc.StatusCode) -> None:
        self.status = status

    async def execute(
        self,
        endpoint: str,
        envelope: RuntimeEnvelope,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        raise FakeRpcError(self.status)


class FakeRpcError(grpc.RpcError):
    def __init__(self, status: grpc.StatusCode) -> None:
        super().__init__()
        self.status = status

    def code(self) -> grpc.StatusCode:
        return self.status


class FakeExecuteCommand:
    def __init__(self) -> None:
        self.request = None
        self.timeout = None
        self.metadata = None

    async def __call__(self, request, *, timeout, metadata):
        self.request = request
        self.timeout = timeout
        self.metadata = metadata
        return SimpleNamespace(ok=True, stdout="ok\n", stderr="", code=0)


class FakeChannel:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_runtime_envelope_requires_identity_and_command() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        RuntimeEnvelope(tenant_id="", agent_id="agent-1", argv=("echo",))
    with pytest.raises(ValueError, match="agent_id"):
        RuntimeEnvelope(tenant_id="tenant-1", agent_id="", argv=("echo",))
    with pytest.raises(ValueError, match="argv"):
        RuntimeEnvelope(tenant_id="tenant-1", agent_id="agent-1", argv=())


def test_runtime_envelope_normalizes_legacy_argument_lists() -> None:
    envelope = RuntimeEnvelope(tenant_id="tenant-1", agent_id="agent-1", argv=["echo", "ok"])

    assert envelope.argv == ("echo", "ok")


def test_runtime_envelope_rejects_empty_capabilities_and_oversized_metadata() -> None:
    with pytest.raises(ValueError, match="capabilities"):
        RuntimeEnvelope("tenant-1", "agent-1", ("echo",), capabilities=())
    with pytest.raises(ValueError, match="task_id"):
        RuntimeEnvelope(
            "tenant-1",
            "agent-1",
            ("echo",),
            task_id="x" * 256,
        )


def test_runtime_client_reads_canonical_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AION_RUNTIME_ENDPOINT", raising=False)
    monkeypatch.setenv("OMERTA_RUNTIME_ENDPOINT", "runtime-canonical:50051")

    client = RuntimeDaemonClient()

    assert client.endpoint == "runtime-canonical:50051"


def test_runtime_client_rejects_conflicting_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_value = "runtime-canonical:50051"
    legacy_value = "runtime-legacy:50051"
    monkeypatch.setenv("OMERTA_RUNTIME_ENDPOINT", canonical_value)
    monkeypatch.setenv("AION_RUNTIME_ENDPOINT", legacy_value)

    with pytest.raises(EnvironmentConflictError) as raised:
        RuntimeDaemonClient()

    rendered = str(raised.value)
    assert "OMERTA_RUNTIME_ENDPOINT" in rendered
    assert "AION_RUNTIME_ENDPOINT" in rendered
    assert canonical_value not in rendered
    assert legacy_value not in rendered


@pytest.mark.asyncio
async def test_runtime_client_fails_closed_without_transport() -> None:
    client = RuntimeDaemonClient(endpoint="runtime:50051")
    envelope = RuntimeEnvelope("tenant-1", "agent-1", ("echo", "ok"))

    with pytest.raises(RuntimeTransportUnavailable, match="synthetic success"):
        await client.execute(envelope)


@pytest.mark.asyncio
async def test_runtime_client_delegates_to_bounded_transport() -> None:
    transport = RecordingTransport()
    client = RuntimeDaemonClient(
        endpoint="runtime:50051",
        transport=transport,
        timeout_seconds=0.5,
    )
    envelope = RuntimeEnvelope("tenant-1", "agent-1", ("echo", "ok"))

    assert await client.execute(envelope) == {"ok": True, "agent_id": "agent-1"}
    assert transport.calls == [("runtime:50051", envelope, 0.5)]


@pytest.mark.asyncio
async def test_runtime_client_enforces_timeout() -> None:
    client = RuntimeDaemonClient(
        endpoint="runtime:50051",
        transport=SlowTransport(),
        timeout_seconds=0.01,
    )

    with pytest.raises(TimeoutError):
        await client.execute(RuntimeEnvelope("tenant-1", "agent-1", ("sleep",)))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (grpc.StatusCode.UNAVAILABLE, RuntimeTransportUnavailable),
        (grpc.StatusCode.FAILED_PRECONDITION, RuntimeLeaseRejected),
        (grpc.StatusCode.PERMISSION_DENIED, RuntimeExecutionRejected),
    ],
)
async def test_runtime_client_distinguishes_outage_from_policy_rejection(
    status: grpc.StatusCode,
    expected_error: type[RuntimeError],
) -> None:
    client = RuntimeDaemonClient(
        endpoint="runtime:50051",
        transport=ErrorTransport(status),
        timeout_seconds=0.5,
    )

    with pytest.raises(expected_error):
        await client.execute(RuntimeEnvelope("tenant-1", "agent-1", ("echo",)))


@pytest.mark.asyncio
async def test_grpc_transport_propagates_execution_context_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = FakeChannel()
    execute_command = FakeExecuteCommand()
    stub = SimpleNamespace(ExecuteCommand=execute_command)
    monkeypatch.setattr(
        grpc_transport_module.grpc.aio,
        "insecure_channel",
        lambda endpoint: channel,
    )
    monkeypatch.setattr(
        grpc_transport_module.runtime_pb2_grpc,
        "RuntimeServiceStub",
        lambda _channel: stub,
    )
    envelope = RuntimeEnvelope(
        tenant_id="tenant-1",
        agent_id="agent-1",
        argv=("/usr/bin/printf", "%s\\n", "ok"),
        task_id="task-1",
        attempt_id="task-1:0",
        request_id="request-1",
        trace_id="00-trace-1-span-1-01",
        capabilities=("terminal.execute",),
        node_id="runtime-1",
        lease_token="abcdefghijklmnopqrstuvwxyzABCDEFG_1234567890",
        lease_generation=7,
        lease_expires_at_ms=2_000_000_000_000,
    )

    result = await GrpcRuntimeTransport().execute(
        "runtime:50051",
        envelope,
        timeout_seconds=0.5,
    )

    assert result == {"ok": True, "stdout": "ok\n", "stderr": "", "code": 0}
    assert execute_command.request.context.tenant_id == "tenant-1"
    assert execute_command.request.context.agent_id == "agent-1"
    assert list(execute_command.request.context.capabilities) == ["terminal.execute"]
    assert execute_command.timeout == 0.5
    assert execute_command.metadata == (
        ("tenant-id", "tenant-1"),
        ("x-aion-task-id", "task-1"),
        ("x-aion-attempt-id", "task-1:0"),
        ("x-request-id", "request-1"),
        ("traceparent", "00-trace-1-span-1-01"),
        ("x-aion-node-id", "runtime-1"),
        (
            "x-aion-lease-token",
            "abcdefghijklmnopqrstuvwxyzABCDEFG_1234567890",
        ),
        ("x-aion-lease-generation", "7"),
        ("x-aion-lease-expires-at-ms", "2000000000000"),
    )
    assert envelope.lease_token not in repr(envelope)
    assert channel.closed is True


def test_execution_contract_is_retired() -> None:
    with pytest.raises(ModuleNotFoundError):
        import_module("execution.runtime_contract")
