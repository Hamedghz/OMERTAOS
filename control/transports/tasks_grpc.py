from __future__ import annotations

import logging
from concurrent import futures
from typing import Iterable
from uuid import uuid4

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import Message

from control.orchestration.runtime_dispatch import (
    RuntimeDispatchRequest,
    RuntimeDispatchResult,
    RuntimeTaskDispatcher,
)
from shared.config.environment import resolve_environment

LOGGER = logging.getLogger(__name__)


def _field(
    name: str,
    number: int,
    field_type: int,
    *,
    type_name: str | None = None,
    label: int = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
) -> descriptor_pb2.FieldDescriptorProto:
    field = descriptor_pb2.FieldDescriptorProto()
    field.name = name
    field.number = number
    field.label = label
    field.type = field_type
    if type_name:
        field.type_name = type_name
    return field


def _message(
    name: str,
    fields: Iterable[descriptor_pb2.FieldDescriptorProto],
    *,
    nested: Iterable[descriptor_pb2.DescriptorProto] = (),
    map_entry: bool = False,
) -> descriptor_pb2.DescriptorProto:
    descriptor = descriptor_pb2.DescriptorProto()
    descriptor.name = name
    descriptor.field.extend(fields)
    descriptor.nested_type.extend(nested)
    descriptor.options.map_entry = map_entry
    return descriptor


def _map_entry(name: str, value_type: int) -> descriptor_pb2.DescriptorProto:
    return _message(
        name,
        [
            _field("key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
            _field("value", 2, value_type),
        ],
        map_entry=True,
    )


def _build_pool() -> descriptor_pool.DescriptorPool:
    file_descriptor = descriptor_pb2.FileDescriptorProto()
    file_descriptor.name = "aion/v1/tasks.proto"
    file_descriptor.package = "aion.v1"
    file_descriptor.syntax = "proto3"

    file_descriptor.message_type.extend(
        [
            _message(
                "TaskRequest",
                [
                    _field("schema_version", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("task_id", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("intent", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field(
                        "params",
                        4,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.TaskRequest.ParamsEntry",
                        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ),
                    _field("preferred_engine", 5, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("priority", 6, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field(
                        "sla",
                        7,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.SLA",
                    ),
                    _field(
                        "metadata",
                        8,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.TaskRequest.MetadataEntry",
                        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ),
                    _field("request_id", 9, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
                nested=[
                    _map_entry("ParamsEntry", descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _map_entry("MetadataEntry", descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "SLA",
                [
                    _field("budget_usd", 1, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE),
                    _field("p95_ms", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT64),
                    _field("privacy", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message("TaskId", [_field("task_id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)]),
            _message(
                "TaskResult",
                [
                    _field("schema_version", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("task_id", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("intent", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("status", 4, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field(
                        "engine",
                        5,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.EngineDecision",
                    ),
                    _field(
                        "result",
                        6,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.TaskResult.ResultEntry",
                        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ),
                    _field(
                        "usage",
                        7,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.Usage",
                    ),
                    _field(
                        "error",
                        8,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.Error",
                    ),
                    _field(
                        "metadata",
                        9,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.TaskResult.MetadataEntry",
                        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
                    ),
                ],
                nested=[
                    _map_entry("ResultEntry", descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _map_entry("MetadataEntry", descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "EngineDecision",
                [
                    _field("route", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("chosen_by", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("reason", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("tier", 4, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "Usage",
                [
                    _field("latency_ms", 1, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE),
                    _field("tokens", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT64),
                    _field("cost_usd", 3, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE),
                ],
            ),
            _message(
                "Error",
                [
                    _field("code", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("message", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "StreamChunk",
                [
                    _field(
                        "result",
                        1,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.TaskResult",
                    ),
                    _field(
                        "control",
                        2,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.StreamControl",
                    ),
                ],
            ),
            _message(
                "StreamControl",
                [
                    _field("cursor", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("final", 2, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                    _field("requires_ack", 3, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                    _field(
                        "retry",
                        4,
                        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                        type_name=".aion.v1.RetryMarker",
                    ),
                    _field("backpressure_hint", 5, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "RetryMarker",
                [
                    _field("reason", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("attempt", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT32),
                    _field("max_attempts", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT32),
                    _field("retry_after_ms", 4, descriptor_pb2.FieldDescriptorProto.TYPE_INT64),
                ],
            ),
            _message(
                "StreamAck",
                [
                    _field("task_id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("cursor", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                    _field("consumer_id", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
            _message(
                "AckResponse",
                [
                    _field("accepted", 1, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL),
                    _field("cursor", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
                ],
            ),
        ]
    )

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_descriptor)
    return pool


_POOL = _build_pool()
TaskRequest = message_factory.GetMessageClass(_POOL.FindMessageTypeByName("aion.v1.TaskRequest"))
TaskId = message_factory.GetMessageClass(_POOL.FindMessageTypeByName("aion.v1.TaskId"))
TaskResult = message_factory.GetMessageClass(_POOL.FindMessageTypeByName("aion.v1.TaskResult"))
StreamAck = message_factory.GetMessageClass(_POOL.FindMessageTypeByName("aion.v1.StreamAck"))
AckResponse = message_factory.GetMessageClass(_POOL.FindMessageTypeByName("aion.v1.AckResponse"))


def _metadata_value(context: grpc.ServicerContext, key: str) -> str:
    for item in context.invocation_metadata():
        if item.key == key:
            return str(item.value)
    return ""


def _error_result(
    *,
    task_id: str,
    intent: str,
    schema_version: str,
    code: str,
    message: str,
    tenant_id: str = "",
    request_id: str = "",
) -> Message:
    result = TaskResult()
    result.schema_version = schema_version or "1.0"
    result.task_id = task_id or str(uuid4())
    result.intent = intent
    result.status = "ERROR"
    result.engine.route = "runtime"
    result.engine.chosen_by = "control"
    result.engine.reason = message
    result.error.code = code
    result.error.message = message
    if tenant_id:
        result.metadata["tenant_id"] = tenant_id
    if request_id:
        result.metadata["request_id"] = request_id
    return result


def _dispatch_result(
    *,
    request: Message,
    dispatched: RuntimeDispatchResult,
    tenant_id: str,
    request_id: str,
    trace_id: str,
) -> Message:
    result = TaskResult()
    result.schema_version = request.schema_version or "1.0"
    result.task_id = request.task_id
    result.intent = request.intent
    result.status = dispatched.status
    result.engine.route = "runtime"
    result.engine.chosen_by = "control"
    result.engine.reason = dispatched.reason
    if dispatched.selected_node_id:
        result.engine.tier = dispatched.selected_node_id
        result.metadata["runtime_node_id"] = dispatched.selected_node_id
    if dispatched.attempt_id:
        result.metadata["attempt_id"] = dispatched.attempt_id
    result.metadata["tenant_id"] = tenant_id
    result.metadata["retry_count"] = str(dispatched.retry_count)
    result.metadata["idempotent_replay"] = str(
        dispatched.idempotent_replay
    ).lower()
    if request_id:
        result.metadata["request_id"] = request_id
    if trace_id:
        result.metadata["trace_id"] = trace_id
    result.usage.latency_ms = dispatched.latency_ms
    if dispatched.exit_code is not None:
        result.result["exit_code"] = str(dispatched.exit_code)
    if dispatched.stdout:
        result.result["stdout"] = dispatched.stdout
    if dispatched.stderr:
        result.result["stderr"] = dispatched.stderr
    if dispatched.error_code:
        result.error.code = dispatched.error_code
        result.error.message = dispatched.error_message or "Runtime dispatch failed"
    return result


class AionTasksGenericHandler(grpc.GenericRpcHandler):
    def __init__(self, dispatcher: RuntimeTaskDispatcher | None = None) -> None:
        self.dispatcher = dispatcher or RuntimeTaskDispatcher()

    def service(self, handler_call_details: grpc.HandlerCallDetails) -> grpc.RpcMethodHandler | None:
        methods = {
            "/aion.v1.AionTasks/Submit": grpc.unary_unary_rpc_method_handler(
                self.submit,
                request_deserializer=TaskRequest.FromString,
                response_serializer=TaskResult.SerializeToString,
            ),
            "/aion.v1.AionTasks/StatusById": grpc.unary_unary_rpc_method_handler(
                self.status_by_id,
                request_deserializer=TaskId.FromString,
                response_serializer=TaskResult.SerializeToString,
            ),
            "/aion.v1.AionTasks/Stream": grpc.unary_stream_rpc_method_handler(
                self.stream,
                request_deserializer=TaskRequest.FromString,
                response_serializer=TaskResult.SerializeToString,
            ),
            "/aion.v1.AionTasks/AckStream": grpc.unary_unary_rpc_method_handler(
                self.ack_stream,
                request_deserializer=StreamAck.FromString,
                response_serializer=AckResponse.SerializeToString,
            ),
        }
        return methods.get(handler_call_details.method)

    def submit(self, request: Message, context: grpc.ServicerContext) -> Message:
        if self.dispatcher.supports(request.intent):
            tenant_id = request.metadata.get("tenant_id") or _metadata_value(
                context, "tenant-id"
            )
            request_id = (
                request.request_id
                or _metadata_value(context, "x-correlation-id")
                or _metadata_value(context, "x-request-id")
            )
            trace_id = _metadata_value(context, "traceparent")
            try:
                dispatch_request = RuntimeDispatchRequest(
                    task_id=request.task_id,
                    intent=request.intent,
                    tenant_id=tenant_id,
                    agent_id=request.metadata.get("agent_id") or "",
                    message=request.params.get("message") or "",
                    request_id=request_id,
                    trace_id=trace_id,
                    idempotency_key=_metadata_value(context, "idempotency-key")
                    or None,
                )
            except ValueError as error:
                return _error_result(
                    task_id=request.task_id,
                    intent=request.intent,
                    schema_version=request.schema_version,
                    code="RUNTIME_REQUEST_INVALID",
                    message=str(error),
                    tenant_id=tenant_id,
                    request_id=request_id,
                )
            dispatched = self.dispatcher.dispatch(dispatch_request)
            return _dispatch_result(
                request=request,
                dispatched=dispatched,
                tenant_id=tenant_id,
                request_id=request_id,
                trace_id=trace_id,
            )

        reason = "Runtime transport is not configured; refusing to report synthetic success"
        return _error_result(
            task_id=request.task_id,
            intent=request.intent,
            schema_version=request.schema_version,
            code="RUNTIME_TRANSPORT_UNAVAILABLE",
            message=reason,
            tenant_id=request.metadata.get("tenant_id") or _metadata_value(context, "tenant-id"),
            request_id=request.request_id
            or _metadata_value(context, "x-correlation-id")
            or _metadata_value(context, "x-request-id"),
        )

    def status_by_id(self, request: Message, context: grpc.ServicerContext) -> Message:
        return _error_result(
            task_id=request.task_id,
            intent="status",
            schema_version="1.0",
            code="TASK_STATUS_UNAVAILABLE",
            message="Durable task status storage is not configured for the minimal Control gRPC adapter",
            request_id=_metadata_value(context, "x-request-id"),
        )

    def stream(self, request: Message, context: grpc.ServicerContext) -> Iterable[Message]:
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Task streaming is not implemented in the minimal Control gRPC adapter")
        yield from ()

    def ack_stream(self, request: Message, context: grpc.ServicerContext) -> Message:
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Task stream acknowledgements are not implemented")


def create_server(max_workers: int = 2) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    server.add_generic_rpc_handlers((AionTasksGenericHandler(),))
    return server


def serve(endpoint: str | None = None) -> grpc.Server:
    configured_endpoint = resolve_environment(
        "OMERTA_CONTROL_GRPC_BIND",
        aliases=("AION_CONTROL_GRPC_BIND",),
        default="0.0.0.0:50051",
    )
    assert isinstance(configured_endpoint, str)
    bind_endpoint = endpoint or configured_endpoint
    server = create_server()
    bound_port = server.add_insecure_port(bind_endpoint)
    if bound_port == 0:
        raise RuntimeError(f"Control gRPC server failed to bind {bind_endpoint}")
    server.start()
    LOGGER.info("Control gRPC server listening on %s", bind_endpoint)
    return server
