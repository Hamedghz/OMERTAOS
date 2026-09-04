from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

import grpc

from shared.config.environment import resolve_environment

from .grpc_transport import GrpcRuntimeTransport


class RuntimeTransportUnavailable(RuntimeError):
    """Raised when no versioned Runtime transport has been configured."""


class RuntimeExecutionRejected(RuntimeError):
    """Raised when Runtime rejects an otherwise reachable execution request."""


class RuntimeLeaseRejected(RuntimeError):
    """Raised when Runtime rejects a missing, expired, or fenced lease."""


@dataclass(frozen=True, slots=True)
class RuntimeEnvelope:
    tenant_id: str
    agent_id: str
    argv: tuple[str, ...]
    task_id: str = ""
    attempt_id: str = ""
    request_id: str = ""
    trace_id: str = ""
    capabilities: tuple[str, ...] = ("terminal.execute",)
    node_id: str = ""
    lease_token: str = field(default="", repr=False)
    lease_generation: int = 0
    lease_expires_at_ms: int = 0

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.agent_id.strip():
            raise ValueError("agent_id is required")
        normalized_argv = tuple(self.argv)
        if not normalized_argv or any(not value for value in normalized_argv):
            raise ValueError("argv must contain non-empty arguments")
        object.__setattr__(self, "argv", normalized_argv)
        normalized_capabilities = tuple(self.capabilities)
        if not normalized_capabilities or any(
            not value.strip() for value in normalized_capabilities
        ):
            raise ValueError("capabilities must contain non-empty values")
        object.__setattr__(self, "capabilities", normalized_capabilities)
        for value, name in (
            (self.task_id, "task_id"),
            (self.attempt_id, "attempt_id"),
            (self.request_id, "request_id"),
            (self.trace_id, "trace_id"),
            (self.node_id, "node_id"),
        ):
            if len(value) > 255:
                raise ValueError(f"{name} exceeds 255 characters")
        if len(self.lease_token) > 128:
            raise ValueError("lease_token exceeds 128 characters")
        if self.lease_generation < 0 or self.lease_expires_at_ms < 0:
            raise ValueError("lease metadata must be non-negative")


class RuntimeExecutor(Protocol):
    async def execute(self, envelope: RuntimeEnvelope) -> dict[str, object]: ...


class RuntimeTransport(Protocol):
    async def execute(
        self,
        endpoint: str,
        envelope: RuntimeEnvelope,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]: ...


class RuntimeDaemonClient:
    """Fail-closed facade for the versioned Control-to-Runtime transport."""

    def __init__(
        self,
        endpoint: str | None = None,
        *,
        transport: RuntimeTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        configured_endpoint = resolve_environment(
            "OMERTA_RUNTIME_ENDPOINT",
            aliases=("AION_RUNTIME_ENDPOINT",),
            default="127.0.0.1:50051",
        )
        assert isinstance(configured_endpoint, str)
        resolved_endpoint = endpoint or configured_endpoint
        if not resolved_endpoint.strip():
            raise ValueError("Runtime endpoint is required")
        if timeout_seconds <= 0:
            raise ValueError("Runtime timeout must be positive")
        self.endpoint = resolved_endpoint
        self._transport = transport or GrpcRuntimeTransport()
        self.timeout_seconds = timeout_seconds

    async def execute(self, envelope: RuntimeEnvelope) -> dict[str, object]:
        if self._transport is None:
            raise RuntimeTransportUnavailable(
                "Runtime transport is not configured; refusing to report synthetic success"
            )
        try:
            return await asyncio.wait_for(
                self._transport.execute(
                    self.endpoint,
                    envelope,
                    timeout_seconds=self.timeout_seconds,
                ),
                timeout=self.timeout_seconds,
            )
        except grpc.RpcError as error:
            if error.code() in {
                grpc.StatusCode.CANCELLED,
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.UNAVAILABLE,
            }:
                raise RuntimeTransportUnavailable(
                    "Runtime transport is unavailable; refusing to report synthetic success"
                ) from error
            if error.code() is grpc.StatusCode.FAILED_PRECONDITION:
                raise RuntimeLeaseRejected(
                    "Runtime rejected a missing, expired, or fenced execution lease"
                ) from error
            raise RuntimeExecutionRejected(
                "Runtime rejected execution; refusing to weaken capability enforcement"
            ) from error
