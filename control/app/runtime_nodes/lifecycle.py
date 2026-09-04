from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Awaitable, Callable

import grpc
from sqlalchemy.orm import Session

from control.app.network.models import SessionLocal, init_db
from control.scheduling import (
    NodeState,
    RuntimeNodeHeartbeat,
    RuntimeNodeRegistration,
    RuntimeScheduler,
)
from control.scheduling.models import RuntimeNode
from shared.config.environment import integer_parser, resolve_environment
from shared.generated.python.runtime import runtime_pb2, runtime_pb2_grpc

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
RuntimeProbe = Callable[[str, float], Awaitable[bool]]
MAX_MANAGED_RUNTIME_NODES = 32
_NODE_CONFIG_KEYS = {
    "node_id",
    "endpoint",
    "capabilities",
    "tenant_ids",
    "total_cpu_millis",
    "total_memory_mb",
}


def _csv(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def _positive_int(
    env: Mapping[str, str], canonical_name: str, legacy_name: str, default: int
) -> int:
    value = resolve_environment(
        canonical_name,
        aliases=(legacy_name,),
        default=str(default),
        parser=integer_parser(minimum=1),
        environ=env,
    )
    assert isinstance(value, int)
    return value


def _positive_float(
    env: Mapping[str, str], canonical_name: str, legacy_name: str, default: float
) -> float:
    def parse_positive_float(raw_value: str) -> float:
        parsed = float(raw_value)
        if parsed <= 0:
            raise ValueError("not positive")
        return parsed

    value = resolve_environment(
        canonical_name,
        aliases=(legacy_name,),
        default=str(default),
        parser=parse_positive_float,
        environ=env,
    )
    assert isinstance(value, float)
    return value


def _string_setting(
    env: Mapping[str, str],
    canonical_name: str,
    legacy_name: str,
    default: str,
) -> str:
    value = resolve_environment(
        canonical_name,
        aliases=(legacy_name,),
        default=default,
        environ=env,
    )
    assert isinstance(value, str)
    return value


@dataclass(frozen=True, slots=True)
class RuntimeLifecycleConfig:
    enabled: bool
    node_id: str
    endpoint: str
    capabilities: tuple[str, ...]
    tenant_ids: tuple[str, ...]
    total_cpu_millis: int
    total_memory_mb: int
    heartbeat_interval_seconds: float
    probe_timeout_seconds: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RuntimeLifecycleConfig":
        source = os.environ if env is None else env
        enabled_value = resolve_environment(
            "OMERTA_RUNTIME_AUTO_REGISTER",
            aliases=("AION_RUNTIME_AUTO_REGISTER",),
            default="false",
            environ=source,
        )
        assert isinstance(enabled_value, str)
        enabled_value = enabled_value.strip().lower()
        if enabled_value not in {"true", "false", "1", "0"}:
            raise ValueError("OMERTA_RUNTIME_AUTO_REGISTER must be true or false")

        node_id = _string_setting(
            source,
            "OMERTA_RUNTIME_NODE_ID",
            "AION_RUNTIME_NODE_ID",
            "runtime-quickstart-1",
        ).strip()
        endpoint = _string_setting(
            source,
            "OMERTA_RUNTIME_ENDPOINT",
            "AION_RUNTIME_ENDPOINT",
            "runtime:50051",
        ).strip()
        capabilities = _csv(
            _string_setting(
                source,
                "OMERTA_RUNTIME_CAPABILITIES",
                "AION_RUNTIME_CAPABILITIES",
                "terminal.execute",
            )
        )
        interval = _positive_float(
            source,
            "OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS",
            "AION_RUNTIME_HEARTBEAT_INTERVAL_SECONDS",
            10.0,
        )
        timeout = _positive_float(
            source,
            "OMERTA_RUNTIME_PROBE_TIMEOUT_SECONDS",
            "AION_RUNTIME_PROBE_TIMEOUT_SECONDS",
            3.0,
        )

        if not node_id or len(node_id) > 120:
            raise ValueError("OMERTA_RUNTIME_NODE_ID must contain 1 to 120 characters")
        if not endpoint or len(endpoint) > 255:
            raise ValueError("OMERTA_RUNTIME_ENDPOINT must contain 1 to 255 characters")
        if not capabilities:
            raise ValueError("OMERTA_RUNTIME_CAPABILITIES must not be empty")
        if interval > 20:
            raise ValueError(
                "OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS must not exceed 20"
            )
        if timeout > interval:
            raise ValueError(
                "OMERTA_RUNTIME_PROBE_TIMEOUT_SECONDS must not exceed the heartbeat interval"
            )

        return cls(
            enabled=enabled_value in {"true", "1"},
            node_id=node_id,
            endpoint=endpoint,
            capabilities=capabilities,
            tenant_ids=_csv(
                _string_setting(
                    source,
                    "OMERTA_RUNTIME_TENANT_IDS",
                    "AION_RUNTIME_TENANT_IDS",
                    "",
                )
            ),
            total_cpu_millis=_positive_int(
                source,
                "OMERTA_RUNTIME_TOTAL_CPU_MILLIS",
                "AION_RUNTIME_TOTAL_CPU_MILLIS",
                1000,
            ),
            total_memory_mb=_positive_int(
                source,
                "OMERTA_RUNTIME_TOTAL_MEMORY_MB",
                "AION_RUNTIME_TOTAL_MEMORY_MB",
                512,
            ),
            heartbeat_interval_seconds=interval,
            probe_timeout_seconds=timeout,
        )

    @classmethod
    def all_from_env(
        cls, env: Mapping[str, str] | None = None
    ) -> tuple["RuntimeLifecycleConfig", ...]:
        source = os.environ if env is None else env
        fallback = cls.from_env(source)
        if not fallback.enabled:
            return ()

        raw = _string_setting(
            source,
            "OMERTA_RUNTIME_NODES_JSON",
            "AION_RUNTIME_NODES_JSON",
            "",
        ).strip()
        if not raw:
            return (fallback,)
        try:
            nodes = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("OMERTA_RUNTIME_NODES_JSON must be valid JSON") from exc
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("OMERTA_RUNTIME_NODES_JSON must be a non-empty array")

        limit = _positive_int(
            source,
            "OMERTA_RUNTIME_MANAGED_NODE_LIMIT",
            "AION_RUNTIME_MANAGED_NODE_LIMIT",
            2,
        )
        if limit > MAX_MANAGED_RUNTIME_NODES:
            raise ValueError(
                f"OMERTA_RUNTIME_MANAGED_NODE_LIMIT must not exceed {MAX_MANAGED_RUNTIME_NODES}"
            )
        if len(nodes) > limit:
            raise ValueError("OMERTA_RUNTIME_NODES_JSON exceeds the managed node limit")

        configs = tuple(
            cls._from_node_config(source, node, index)
            for index, node in enumerate(nodes)
        )
        if len({config.node_id for config in configs}) != len(configs):
            raise ValueError("OMERTA_RUNTIME_NODES_JSON contains duplicate node ids")
        if len({config.endpoint for config in configs}) != len(configs):
            raise ValueError("OMERTA_RUNTIME_NODES_JSON contains duplicate endpoints")
        return configs

    @classmethod
    def _from_node_config(
        cls,
        env: Mapping[str, str],
        node: object,
        index: int,
    ) -> "RuntimeLifecycleConfig":
        if not isinstance(node, dict):
            raise ValueError(f"Runtime node entry {index} must be an object")
        unknown = set(node) - _NODE_CONFIG_KEYS
        if unknown:
            raise ValueError(
                f"Runtime node entry {index} contains unsupported fields: "
                + ", ".join(sorted(unknown))
            )

        node_id = node.get("node_id")
        endpoint = node.get("endpoint")
        if not isinstance(node_id, str) or not isinstance(endpoint, str):
            raise ValueError(
                f"Runtime node entry {index} requires string node_id and endpoint"
            )

        derived = dict(env)
        for canonical_name, legacy_name, value in (
            ("OMERTA_RUNTIME_NODE_ID", "AION_RUNTIME_NODE_ID", node_id),
            ("OMERTA_RUNTIME_ENDPOINT", "AION_RUNTIME_ENDPOINT", endpoint),
        ):
            derived.pop(legacy_name, None)
            derived[canonical_name] = value
        for field, canonical_name, legacy_name in (
            ("capabilities", "OMERTA_RUNTIME_CAPABILITIES", "AION_RUNTIME_CAPABILITIES"),
            ("tenant_ids", "OMERTA_RUNTIME_TENANT_IDS", "AION_RUNTIME_TENANT_IDS"),
        ):
            if field not in node:
                continue
            items = node[field]
            if not isinstance(items, list) or any(
                not isinstance(item, str) or not item.strip() for item in items
            ):
                raise ValueError(
                    f"Runtime node entry {index} field {field} must be a string array"
                )
            derived.pop(legacy_name, None)
            derived[canonical_name] = ",".join(items)

        for field, canonical_name, legacy_name in (
            (
                "total_cpu_millis",
                "OMERTA_RUNTIME_TOTAL_CPU_MILLIS",
                "AION_RUNTIME_TOTAL_CPU_MILLIS",
            ),
            (
                "total_memory_mb",
                "OMERTA_RUNTIME_TOTAL_MEMORY_MB",
                "AION_RUNTIME_TOTAL_MEMORY_MB",
            ),
        ):
            if field not in node:
                continue
            value = node[field]
            if type(value) is not int:
                raise ValueError(
                    f"Runtime node entry {index} field {field} must be an integer"
                )
            derived.pop(legacy_name, None)
            derived[canonical_name] = str(value)

        return cls.from_env(derived)


async def probe_runtime(endpoint: str, timeout_seconds: float) -> bool:
    channel = grpc.aio.insecure_channel(endpoint)
    try:
        stub = runtime_pb2_grpc.RuntimeServiceStub(channel)
        response = await stub.QueryMetrics(
            runtime_pb2.MetricsRequest(tenant_id="system"),
            timeout=timeout_seconds,
        )
        if not response.ok:
            return False
        payload = json.loads(response.json)
        return payload.get("status") == "ready"
    except (grpc.RpcError, json.JSONDecodeError, TypeError):
        return False
    finally:
        await channel.close()


class RuntimeNodeLifecycle:
    def __init__(
        self,
        config: RuntimeLifecycleConfig,
        *,
        scheduler: RuntimeScheduler | None = None,
        session_factory: SessionFactory = SessionLocal,
        probe: RuntimeProbe = probe_runtime,
        schema_initializer: Callable[[], None] = init_db,
    ) -> None:
        self.config = config
        self.scheduler = scheduler or RuntimeScheduler()
        self.session_factory = session_factory
        self.probe = probe
        self.schema_initializer = schema_initializer
        self._reachable: bool | None = None
        self._schema_ready = False

    async def sync_once(self) -> bool:
        reachable = bool(
            await self.probe(
                self.config.endpoint,
                self.config.probe_timeout_seconds,
            )
        )
        if not reachable:
            self._log_reachability(False)
            return False

        if not self._schema_ready:
            self.schema_initializer()
            self._schema_ready = True
        with self.session_factory() as db:
            self.scheduler.reclaim_expired_leases(
                db, actor="runtime-lifecycle"
            )
            node = db.get(RuntimeNode, self.config.node_id)
            if node is None:
                self.scheduler.register_node(
                    db,
                    RuntimeNodeRegistration(
                        node_id=self.config.node_id,
                        endpoint=self.config.endpoint,
                        capabilities=self.config.capabilities,
                        tenant_ids=self.config.tenant_ids,
                        total_cpu_millis=self.config.total_cpu_millis,
                        total_memory_mb=self.config.total_memory_mb,
                        available_cpu_millis=self.config.total_cpu_millis,
                        available_memory_mb=self.config.total_memory_mb,
                        software_version="quickstart",
                        contract_version="runtime.v1",
                        trust_zone="local-quickstart",
                        labels={"managed_by": "control-runtime-lifecycle"},
                    ),
                    actor="runtime-lifecycle",
                )
            elif node.endpoint != self.config.endpoint:
                logger.error(
                    "Runtime lifecycle endpoint differs from the persisted node; refusing heartbeat"
                )
                return False
            else:
                node.capabilities_json = json.dumps(
                    list(self.config.capabilities), separators=(",", ":")
                )
                node.tenant_ids_json = json.dumps(
                    list(self.config.tenant_ids), separators=(",", ":")
                )
                node.total_cpu_millis = self.config.total_cpu_millis
                node.total_memory_mb = self.config.total_memory_mb
                node.software_version = "quickstart"
                node.contract_version = "runtime.v1"
                node.trust_zone = "local-quickstart"
                node.labels_json = '{"managed_by":"control-runtime-lifecycle"}'

            self.scheduler.record_heartbeat(
                db,
                self.config.node_id,
                RuntimeNodeHeartbeat(
                    available_cpu_millis=self.config.total_cpu_millis,
                    available_memory_mb=self.config.total_memory_mb,
                    state=NodeState.healthy,
                    capabilities=self.config.capabilities,
                ),
                actor="runtime-lifecycle",
            )

        self._log_reachability(True)
        return True

    async def run(self) -> None:
        while True:
            try:
                await self.sync_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Runtime lifecycle synchronization failed")
            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    def _log_reachability(self, reachable: bool) -> None:
        if self._reachable is reachable:
            return
        self._reachable = reachable
        log = logger.info if reachable else logger.warning
        log(
            "Runtime lifecycle reachability changed: node=%s reachable=%s",
            self.config.node_id,
            reachable,
        )


class RuntimeLifecycleManager:
    def __init__(
        self,
        configs: tuple[RuntimeLifecycleConfig, ...],
        *,
        scheduler: RuntimeScheduler | None = None,
        session_factory: SessionFactory = SessionLocal,
        probe: RuntimeProbe = probe_runtime,
        schema_initializer: Callable[[], None] = init_db,
    ) -> None:
        if not configs:
            raise ValueError("at least one Runtime lifecycle config is required")
        shared_scheduler = scheduler or RuntimeScheduler()
        self.lifecycles = tuple(
            RuntimeNodeLifecycle(
                config,
                scheduler=shared_scheduler,
                session_factory=session_factory,
                probe=probe,
                schema_initializer=schema_initializer,
            )
            for config in configs
        )
        self.interval_seconds = min(
            config.heartbeat_interval_seconds for config in configs
        )

    async def sync_once(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for lifecycle in self.lifecycles:
            try:
                results[lifecycle.config.node_id] = await lifecycle.sync_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Runtime lifecycle synchronization failed: node=%s",
                    lifecycle.config.node_id,
                )
                results[lifecycle.config.node_id] = False
        return results

    async def run(self) -> None:
        while True:
            await self.sync_once()
            await asyncio.sleep(self.interval_seconds)
