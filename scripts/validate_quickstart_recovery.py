#!/usr/bin/env python3
"""Explicit, bounded fresh-install and restart acceptance; never deletes volumes."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts import validate_quickstart_environment_parity as parity  # noqa: E402
from scripts.validate_environment_aliases import (  # noqa: E402
    load_alias_contract, parse_environment_file, validate_environment_aliases,
)

FRESH_PROJECT = "omerta-p3-fresh"


def recovery_config(rendered, groups, project, console_image, control_image, **images):
    parity.require(project == parity.PROJECT or re.fullmatch(r"omerta-p3-fresh(?:-[a-z0-9-]{1,20})?", project),
                   "unapproved recovery project")
    config, _ = parity.variant_config(rendered, groups, legacy=False,
                                     console_image=console_image, control_image=control_image, **images)
    config["name"] = project
    config["networks"]["default"]["name"] = f"{project}-net"
    config["volumes"] = {name: {"name": f"{project}_{name}"} for name in parity.VOLUMES}
    return config


def assert_fresh_absent(existing, project=FRESH_PROJECT):
    parity.require(not any(name.startswith(project + "_") for name in existing),
                   "fresh project has existing volumes; refusing to reuse them")


def assert_fenced(response):
    parity.require(response.get("code") == "FAILED_PRECONDITION"
                   and response.get("detail") == "runtime execution lease is missing, expired, or fenced",
                   "Runtime did not reject the duplicate lease with its public fail-closed status")


def assert_persisted_claim(state, lease, now_ms):
    parts = [lease[name].encode() for name in ("tenant_id", "task_id")]
    payload = b"".join(struct.pack(">I", len(part)) + part for part in parts)
    key = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
    parity.require(now_ms < lease["lease_expires_at_ms"], "restart probe lease expired")
    parity.require(state.get("version") == 1 and state.get("records", {}).get(key) == {
        "generation": lease["lease_generation"], "expires_at_ms": lease["lease_expires_at_ms"]},
        "Runtime did not persist the exact accepted claim")


def read_fence(runner, project, image, lease):
    _, raw, _ = runner.run("persisted accepted fence", ["docker", "run", "--rm", "--network", "none",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
        "--mount", f"type=volume,src={project}_runtime-state,dst=/state,readonly",
        image, "cat", "/state/lease-fence.json"])
    state = json.loads(raw)
    assert_persisted_claim(state, lease, int(time.time() * 1000))
    return state


def assert_restart_replay(response, task_id):
    parity.require(response.get("taskId") == task_id and response.get("status") == "ERROR"
                   and response.get("error", {}).get("code") == "RUNTIME_RESULT_REPLAY_UNAVAILABLE",
                   "post-restart replay did not fail closed with the documented result limitation")


LEASE_PROBE = r'''
import asyncio, json, os, sys, time, uuid
import grpc
from control.clients.runtime.client import RuntimeEnvelope
from control.clients.runtime.grpc_transport import GrpcRuntimeTransport
from control.scheduling.lease_signing import LeaseSigner
async def main():
    envelope = json.load(sys.stdin)
    ttl_ms = envelope.pop("_probe_ttl_ms", 90000)
    if not envelope.get("lease_token"):
        envelope.update(task_id="p3-" + uuid.uuid4().hex, attempt_id="p3:0",
            node_id=os.environ["OMERTA_RUNTIME_NODE_ID"], lease_generation=1,
            lease_expires_at_ms=int(time.time() * 1000) + ttl_ms)
        envelope["lease_token"] = LeaseSigner.from_env().sign(**{
            key: envelope[key] for key in ("tenant_id", "task_id", "attempt_id", "node_id")},
            generation=envelope["lease_generation"], expires_at_ms=envelope["lease_expires_at_ms"])
    try:
        result = await GrpcRuntimeTransport().execute(os.environ["OMERTA_RUNTIME_ENDPOINT"],
            RuntimeEnvelope(**envelope), timeout_seconds=10)
        assert result["ok"] and result["stdout"] == "p3-fence-ok\n"
        print(json.dumps({"code": "OK", "envelope": envelope}))
    except grpc.RpcError as exc:
        print(json.dumps({"code": exc.code().name, "detail": exc.details()}))
asyncio.run(main())
'''


# Only synthetic object contents are returned. Operational credentials stay in the container.
STORE_PROBE = r'''
import datetime, hashlib, hmac, json, os, sys
import requests
from sqlalchemy import text
from control.app.network.models import engine
p = json.load(sys.stdin)
with engine.connect() as db:
    migrations = list(db.execute(text('SELECT migration_name, checksum FROM _prisma_migrations '
                                     'WHERE finished_at IS NOT NULL ORDER BY migration_name')))
    users = db.execute(text('SELECT count(*) FROM "User" WHERE email=:email'),
                       {"email": p["email"]}).scalar_one()
    audit = list(db.execute(text('SELECT event_id FROM runtime_audit_events WHERE task_id=:task '
                                'AND tenant_id=:tenant ORDER BY id'), p))
assert users == 1 and migrations and audit
session = requests.Session()
session.trust_env = False
q = os.environ["OMERTA_CONTROL_QDRANT_URL"] + "/collections/p3_recovery_probe"
headers = {}
if os.environ.get("OMERTA_CONTROL_QDRANT_API_KEY"):
    headers["api-key"] = os.environ["OMERTA_CONTROL_QDRANT_API_KEY"]
if p["seed"]:
    response = session.get(q, headers=headers, timeout=10)
    if response.status_code == 404:
        session.put(q, json={"vectors": {"size": 2, "distance": "Cosine"}},
                    headers=headers, timeout=10).raise_for_status()
    session.put(q + "/points?wait=true", json={"points": [{"id": p["fixture"], "vector": [1., 0.],
        "payload": {"purpose": "p3-recovery"}}]}, headers=headers, timeout=10).raise_for_status()
response = session.get(q + "/points/" + p["fixture"], headers=headers, timeout=10)
response.raise_for_status()
assert response.json()["result"]["payload"] == {"purpose": "p3-recovery"}
endpoint = os.environ["OMERTA_CONTROL_MINIO_ENDPOINT"]
scheme = "https" if os.environ["OMERTA_CONTROL_MINIO_SECURE"].lower() == "true" else "http"
access = os.environ["OMERTA_CONTROL_MINIO_ACCESS_KEY"]
secret = os.environ["OMERTA_CONTROL_MINIO_SECRET_KEY"]
def s3(method, path, body=b""):
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    digest = hashlib.sha256(body).hexdigest()
    canonical_headers = f"host:{endpoint}\nx-amz-content-sha256:{digest}\nx-amz-date:{stamp}\n"
    names = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join((method, path, "", canonical_headers, names, digest))
    scope = date + "/us-east-1/s3/aws4_request"
    signing = ("AWS4" + secret).encode()
    for part in (date, "us-east-1", "s3", "aws4_request"):
        signing = hmac.new(signing, part.encode(), hashlib.sha256).digest()
    signature = hmac.new(signing, ("AWS4-HMAC-SHA256\n" + stamp + "\n" + scope + "\n" +
                         hashlib.sha256(canonical.encode()).hexdigest()).encode(), hashlib.sha256).hexdigest()
    return session.request(method, scheme + "://" + endpoint + path, data=body, timeout=10, headers={
        "x-amz-content-sha256": digest, "x-amz-date": stamp,
        "Authorization": "AWS4-HMAC-SHA256 Credential=" + access + "/" + scope +
                         ", SignedHeaders=" + names + ", Signature=" + signature})
path = "/omerta-p3-recovery/" + p["fixture"]
if p["seed"]:
    response = s3("PUT", "/omerta-p3-recovery")
    assert response.status_code in (200, 409)
    s3("PUT", path, b"p3-recovery-object\n").raise_for_status()
response = s3("GET", path)
response.raise_for_status()
assert response.content == b"p3-recovery-object\n"
print(json.dumps({"migration_digest": hashlib.sha256(json.dumps([list(r) for r in migrations]).encode()).hexdigest(),
                  "admin_count": users, "audit_ids": [r[0] for r in audit],
                  "qdrant": "passed", "minio": "passed"}))
'''

DISPATCH_COUNT = '''
import json, sys
from sqlalchemy import text
from control.app.network.models import engine
with engine.connect() as db:
    print(db.execute(text("SELECT count(*) FROM runtime_audit_events "
        "WHERE task_id=:task AND tenant_id=:tenant AND action='runtime.dispatch.start'"),
        json.load(sys.stdin)).scalar_one())
'''

CONTROL_REPLAY = '''
import json, os, sys
import grpc
from sqlalchemy import text
from control.app.network.models import engine
from control.transports.tasks_grpc import TaskRequest, TaskResult
p = json.load(sys.stdin)
with engine.connect() as db:
    actor = db.execute(text("SELECT actor FROM runtime_audit_events WHERE task_id=:task "
        "AND tenant_id=:tenant AND action='runtime.dispatch.start' ORDER BY id LIMIT 1"), p).scalar_one()
request = TaskRequest(schema_version="1.0", task_id=p["task"], intent="runtime.echo.v1",
                      params={"message": "m413-parity-ok"},
                      metadata={"agent_id": actor, "tenant_id": p["tenant"]},
                      request_id=p["headers"]["x-correlation-id"])
metadata = [(name, value) for name, value in p["headers"].items() if name != "Content-Type"]
metadata.append(("authorization", "Bearer " + os.environ["OMERTA_GATEWAY_ADMIN_TOKEN"]))
with grpc.insecure_channel("127.0.0.1:50051") as channel:
    call = channel.unary_unary("/aion.v1.AionTasks/Submit", request_serializer=TaskRequest.SerializeToString,
                              response_deserializer=TaskResult.FromString)
    result = call(request, metadata=metadata, timeout=10)
print(json.dumps({"taskId": result.task_id, "status": result.status, "error": {"code": result.error.code}}))
'''


def console_probe(runner, config):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = "http://localhost:23000"
    env = config["services"]["install"]["environment"]
    csrf = runner.http(opener, base, "/api/auth/csrf")
    body = urllib.parse.urlencode({"csrfToken": csrf["csrfToken"],
        "identifier": env["CONSOLE_ADMIN_EMAIL"], "password": env["CONSOLE_ADMIN_PASSWORD"],
        "callbackUrl": base + "/console", "json": "true"}).encode()
    runner.http(opener, base, "/api/auth/callback/credentials", body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    parity.require(runner.http(opener, base, "/api/auth/session").get("user", {}).get("role") == "ADMIN",
                   "administrator login failed")
    tenants = config["services"]["control"]["environment"].get("OMERTA_RUNTIME_TENANT_IDS", "")
    tenant = next((value.strip() for value in tenants.split(",") if value.strip()), "tenant-p3")
    nonce = uuid.uuid4().hex
    headers = {"Content-Type": "application/json", "tenant-id": tenant,
               "x-correlation-id": "p3-" + nonce, "idempotency-key": "p3-" + nonce,
               "traceparent": f"00-{nonce}-{uuid.uuid4().hex[:16]}-01"}
    payload = json.dumps({"intent": "runtime.echo.v1", "params": {"message": "m413-parity-ok"}}).encode()
    result = runner.http(opener, base, "/api/proxy/tasks", body=payload, headers=headers)
    parity.normalized_result(result)
    return opener, payload, headers, result["taskId"], tenant


def compose_command(project):
    return ["docker", "compose", "--parallel", "1", "--project-directory", str(ROOT),
            "--project-name", project, "-f", "-"]


def exec_probe(runner, project, service, code, payload, label):
    # Use container IDs, not Compose stdin, so probe data never shares a config stream.
    _, raw, _ = runner.run(label + ": container", ["docker", "ps", "-q", "--filter",
        f"label=com.docker.compose.project={project}", "--filter", f"label=com.docker.compose.service={service}"])
    ids = raw.decode().split()
    parity.require(len(ids) == 1, label + ": expected one running container")
    _, raw, _ = runner.run(label, ["docker", "exec", "-i", ids[0], "python", "-c", code],
                           data=json.dumps(payload).encode(), timeout=45)
    return json.loads(raw)


def volume_consumer_guard(runner, project):
    for name in parity.VOLUMES:
        _, raw, _ = runner.run("volume consumer guard: " + name, ["docker", "ps", "-aq", "--filter",
                                  f"volume={project}_{name}"])
        ids = raw.decode().split()
        if not ids:
            continue
        _, raw, _ = runner.run("volume consumer labels: " + name, ["docker", "inspect", *ids])
        records = json.loads(raw)
        parity.require(all(record["Config"].get("Labels", {}).get("com.docker.compose.project") == project
                           and not record["State"]["Running"] for record in records),
                       "volume is mounted by an active or foreign project container")


def run_project(runner, config, project):
    compose = compose_command(project)
    data = json.dumps(parity.compose_dollars(config, encode=True)).encode()
    runner.run(project + ": configuration", compose + ["config", "--quiet"], data=data)
    _, running, _ = runner.run(project + ": takeover guard", ["docker", "ps", "-q", "--filter",
                              f"label=com.docker.compose.project={project}"])
    parity.require(not running.strip(), "refusing to take over a running project")
    volume_consumer_guard(runner, project)
    try:
        runner.run(project + ": ready", compose + ["up", "-d", "--no-build", "--pull", "never",
            "--force-recreate", "--wait", "--wait-timeout", "180", "mongo", *parity.APPLICATIONS],
            data=data, timeout=300)
        parity.authenticated_echo(runner, config)
        opener, payload, headers, task, tenant = console_probe(runner, config)
        fixture = str(uuid.uuid4())
        probe = {"fixture": fixture, "seed": True, "task": task, "tenant": tenant,
                 "email": config["services"]["install"]["environment"]["CONSOLE_ADMIN_EMAIL"]}
        before = exec_probe(runner, project, "control", STORE_PROBE, probe, "seed and read stores")
        mongo = ["docker", "exec", "-i", f"{project}-mongo-1", "mongosh", "--quiet", "--eval"]
        runner.run("Mongo fixture seed", mongo + [
            f'db.getSiblingDB("omerta_p3_acceptance").probes.insertOne({{_id:{json.dumps(fixture)},purpose:"p3-recovery"}})'])
        ttl = int(config["services"]["runtime"]["environment"]["OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS"])
        envelope = {"tenant_id": tenant, "agent_id": "p3-acceptance", "argv": ["echo", "p3-fence-ok"],
                    "_probe_ttl_ms": min(ttl, 120) * 1000 - 5000}
        accepted = exec_probe(runner, project, "control", LEASE_PROBE, envelope, "Runtime signed claim")
        parity.require(accepted.get("code") == "OK", "initial signed lease failed")
        lease = accepted["envelope"]
        claimed_at = time.monotonic()
        state = read_fence(runner, project, config["services"]["runtime-lease-secret-init"]["image"], lease)
        assert_fenced(exec_probe(runner, project, "control", LEASE_PROBE, lease, "Runtime duplicate before restart"))
        runner.run("Runtime normal restart", compose + ["restart", "--timeout", "20", "runtime"], data=data)
        # Runtime healthcheck opens a real gRPC connection; no unbounded polling.
        for attempt in range(20):
            code, _, _ = runner.run("Runtime readiness", compose + ["exec", "-T", "runtime",
                "/usr/local/bin/runtime-daemon", "--healthcheck"], data=data, check=False, timeout=10)
            if code == 0:
                break
            time.sleep(1)
        parity.require(code == 0, "Runtime did not recover readiness")
        state_after = read_fence(runner, project, config["services"]["runtime-lease-secret-init"]["image"], lease)
        parity.require(state == state_after, "Runtime fence contents changed across normal restart")
        assert_fenced(exec_probe(runner, project, "control", LEASE_PROBE, lease, "Runtime duplicate after restart"))
        parity.require(time.time() * 1000 < lease["lease_expires_at_ms"], "lease expired during duplicate RPC")
        fence_seconds = round(time.monotonic() - claimed_at, 2)
        runner.run("normal stack stop", compose + ["stop", "--timeout", "30"], data=data,
                   timeout=120, guard=False)
        runner.run("normal stack start and installer reapply", compose + ["up", "-d", "--no-build", "--pull", "never",
            "--wait", "--wait-timeout", "180", "mongo", *parity.APPLICATIONS], data=data, timeout=300)
        probe["seed"] = False
        after = exec_probe(runner, project, "control", STORE_PROBE, probe, "read persisted stores")
        parity.require(before == after, "persistent stores or bootstrap identity changed after restart")
        runner.run("Mongo persisted fixture", mongo + [
            f'if(db.getSiblingDB("omerta_p3_acceptance").probes.countDocuments({{_id:{json.dumps(fixture)},purpose:"p3-recovery"}})!==1)quit(2)'])
        replay = runner.http(opener, "http://localhost:23000", "/api/proxy/tasks", body=payload, headers=headers)
        parity.require(replay.get("taskId") == task, "Gateway replay changed task identity")
        parity.normalized_result(replay)
        control_replay = exec_probe(runner, project, "control", CONTROL_REPLAY,
            {"task": task, "tenant": tenant, "headers": headers}, "Control gRPC replay after restart")
        assert_restart_replay(control_replay, task)
        audit_after = exec_probe(runner, project, "control", STORE_PROBE, probe, "read replay audit")
        parity.require(set(before["audit_ids"]).issubset(audit_after["audit_ids"]), "historical audit rows disappeared")
        _, raw, _ = runner.run("replay dispatch count", ["docker", "exec", "-i", f"{project}-control-1",
            "python", "-c", DISPATCH_COUNT],
            data=json.dumps({"task": task, "tenant": tenant}).encode())
        parity.require(raw.strip() == b"1", "post-restart replay dispatched additional work")
        parity.authenticated_echo(runner, config)
        return {"status": "passed", "postgres_migrations_digest": before["migration_digest"],
            "admin_count": before["admin_count"], "historical_audit_count": len(before["audit_ids"]),
            "postgres_mongo_qdrant_minio_persistence": "passed", "runtime_restart_stale_fence": "passed",
            "runtime_restart_probe_seconds": fence_seconds, "post_control_restart_replay": "fail-closed",
            "gateway_redis_replay_after_normal_restart": "passed",
            "durable_result_replay": "unavailable by design", "fresh_authenticated_echo_after_restart": "passed"}
    finally:
        runner.run(project + ": final normal stop", compose + ["stop", "--timeout", "30"], data=data,
                   timeout=120, guard=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--console-image", required=True)
    parser.add_argument("--control-image", required=True)
    parser.add_argument("--runtime-image", default="omertaos-runtime:m412-62fdfed")
    parser.add_argument("--gateway-image", default="omertaos-gateway:m412-62fdfed")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fresh-project", default=FRESH_PROJECT)
    parser.add_argument("--fresh-only", action="store_true",
                        help="Only fresh-install/restart checks; excludes existing data, backup and upgrade")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    parity.require(args.output.resolve().is_relative_to(ROOT / "artifacts"), "report must be under artifacts")
    runner = parity.Runner()
    runner.report.update(phase="P3", projects={}, blocked=[
        "encrypted backup and independent restore require an operator-approved encryption recipient",
        "older-release upgrade compatibility requires a separately restored clone; current-data reapply is not that gate"],
        skipped=["Redis durable queue recovery: canonical Quickstart has no named Redis volume; cache replay is separate",
                 "native/systemd, benchmarks and broader P4 security review are outside P3"])
    if args.fresh_only:
        runner.report.update(scope="fresh-install/restart only", blocked=[], skipped=[
            "existing-data reapply, encrypted backup/restore and historical upgrade are outside this invocation",
            "native/systemd, benchmarks and security scanning are outside this invocation"])
    try:
        runner.memory()
        parity.require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, "less than 5 GiB free disk")
        groups, unsupported = load_alias_contract()
        parity.require(not validate_environment_aliases(parse_environment_file(args.env_file), groups, unsupported).errors,
                       "environment preflight failed")
        _, raw, _ = runner.run("revision", ["git", "rev-parse", "HEAD"])
        runner.report["commit"] = raw.decode().strip()
        base = ["docker", "compose", "--project-directory", str(ROOT), "-p", parity.PROJECT,
                "--env-file", str(args.env_file.resolve()), "-f", str(ROOT / "deploy/docker/compose/quickstart.yml")]
        _, raw, _ = runner.run("canonical render", base + ["config", "--format", "json"])
        rendered = parity.compose_dollars(json.loads(raw), encode=False)
        _, raw, _ = runner.run("volume inventory", ["docker", "volume", "ls", "--format", "{{.Name}}"])
        existing = raw.decode().splitlines()
        assert_fresh_absent(existing, args.fresh_project)
        if not args.fresh_only:
            parity.require(all(f"{parity.PROJECT}_{name}" in existing for name in parity.VOLUMES), "source volumes missing")
        projects = (args.fresh_project,) if args.fresh_only else (args.fresh_project, parity.PROJECT)
        configs = {project: recovery_config(rendered, groups, project, args.console_image, args.control_image,
                   runtime_image=args.runtime_image, gateway_image=args.gateway_image) for project in projects}
        runner.report["images"] = {}
        for service in parity.APPLICATIONS:
            image = configs[args.fresh_project]["services"][service]["image"]
            _, raw, _ = runner.run(service + " image provenance", ["docker", "image", "inspect", "--format", "{{.Id}}", image])
            runner.report["images"][service] = {"tag": image, "id": raw.decode().strip()}
        for project, config in configs.items():
            data = json.dumps(parity.compose_dollars(config, encode=True)).encode()
            runner.run(project + ": render", compose_command(project) + ["config", "--quiet"], data=data)
        if not args.run:
            runner.report["status"] = "preflight-only"
            return 0
        for project, config in configs.items():
            runner.report["projects"][project] = run_project(runner, config, project)
            _, raw, _ = runner.run(project + ": stopped verification", ["docker", "ps", "-q", "--filter",
                                  f"label=com.docker.compose.project={project}"])
            parity.require(not raw.strip(), "project still running after final stop")
            runner.run(project + ": retained volumes", ["docker", "volume", "inspect",
                       *(f"{project}_{name}" for name in parity.VOLUMES)])
        runner.report["status"] = "passed-in-scope" if args.fresh_only else "partial-blocked"
        return 0 if args.fresh_only else 2
    except (Exception, KeyboardInterrupt) as exc:
        runner.report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        runner.report["error"] = str(exc) if isinstance(exc, parity.AcceptanceFailure) else type(exc).__name__
        print("Recovery acceptance: " + runner.report["error"], flush=True)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    finally:
        runner.report["minimum_available_ram_mib"] = (runner.minimum_ram or 0) // 1024
        runner.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(runner.report, indent=2) + "\n", encoding="utf-8")
        print("Report: " + str(args.output), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
