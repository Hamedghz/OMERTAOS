#!/usr/bin/env python3
"""Bounded, explicit live acceptance of the isolated Quickstart environment aliases."""

from __future__ import annotations

import argparse
import copy
import http.cookiejar
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts.validate_environment_aliases import (  # noqa: E402
    load_alias_contract,
    parse_environment_file,
    validate_environment_aliases,
)

PROJECT = "omerta-m4-validation"
APPLICATIONS = ("runtime", "control", "gateway", "console")
PORTS = {"runtime": (25051, 50051), "control": (28000, 8000),
         "gateway": (28080, 8080), "console": (23000, 3000)}
VOLUMES = ("postgres-data", "mongo-data", "minio-data", "qdrant-data",
           "runtime-state", "runtime-lease-secret")


class AcceptanceFailure(RuntimeError):
    """Only operator-safe messages may be supplied to this exception."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


def signal_process_group(child, sig):
    """A child can exit between a timeout/poll result and the signal."""
    try:
        os.killpg(child.pid, sig)
    except ProcessLookupError:
        pass


def compose_dollars(value, *, encode: bool):
    """Translate Compose's escaped config output to/from logical process strings."""
    if isinstance(value, str):
        return value.replace("$", "$$") if encode else value.replace("$$", "$")
    if isinstance(value, list):
        return [compose_dollars(item, encode=encode) for item in value]
    if isinstance(value, dict):
        return {key: compose_dollars(item, encode=encode) for key, item in value.items()}
    return value


def variant_config(rendered, groups, *, legacy: bool, console_image: str,
                   control_image: str = "omertaos-control:m412-62fdfed",
                   runtime_image: str = "omertaos-runtime:m412-62fdfed",
                   gateway_image: str = "omertaos-gateway:m412-62fdfed"):
    config = copy.deepcopy(rendered)
    config["name"] = PROJECT
    config["networks"]["default"]["name"] = f"{PROJECT}-net"
    coverage = {}
    image_overrides = {
        "runtime": runtime_image,
        "control": control_image,
        "gateway": gateway_image,
        "console": console_image,
        "install": console_image,
    }
    for name, image in image_overrides.items():
        service = config["services"][name]
        service["image"] = image
        service.pop("build", None)
    for name, (published, target) in PORTS.items():
        config["services"][name]["ports"] = [{
            "host_ip": "127.0.0.1", "published": str(published),
            "target": target, "protocol": "tcp",
        }]
    for name in ("console", "install"):
        env = config["services"][name]["environment"]
        env["NEXTAUTH_URL"] = "http://localhost:23000"
        # Exercise the product URL reader rather than its higher-priority override.
        env.pop("GATEWAY_URL", None)
    console_env = config["services"]["console"]["environment"]
    console_env["NEXT_PUBLIC_GATEWAY_URL"] = "http://localhost:28080"
    console_env.pop("DOCKER", None)
    config["services"]["gateway"]["environment"]["OMERTA_CORS_ORIGINS"] = (
        "http://localhost:23000"
    )
    for name in (*APPLICATIONS, "install"):
        env = config["services"][name]["environment"]
        coverage[name] = {}
        for group in groups:
            if group.canonical_name not in env:
                continue
            preferred = "AION_" + group.canonical_name.removeprefix("OMERTA_")
            alias = preferred if preferred in group.aliases else group.aliases[0]
            coverage[name][group.canonical_name] = alias
            require(not any(alias_key in env for alias_key in group.aliases),
                    f"unexpected legacy writer in {name}")
            if legacy:
                env[alias] = env.pop(group.canonical_name)
    return config, coverage


def conflicting_pairs(groups, coverage):
    configured = {key for pairs in coverage.values() for key in pairs}
    failures = 0
    for group in groups:
        if group.canonical_name not in configured:
            continue
        for alias in group.aliases:
            result = validate_environment_aliases(
                {group.canonical_name: "canonical-probe", alias: "legacy-probe"},
                (group,),
            )
            require(len(result.errors) == 1, "alias conflict preflight accepted a conflict")
            require("canonical-probe" not in result.errors[0]
                    and "legacy-probe" not in result.errors[0],
                    "alias conflict preflight disclosed a probe value")
            failures += 1
    return failures


def normalized_result(payload):
    require(payload.get("status") == "OK", "Runtime task did not succeed")
    require(payload.get("engine", {}).get("route") == "runtime", "task bypassed Runtime")
    result = payload.get("result", {})
    require(str(result.get("exit_code")) == "0", "Runtime echo exit code was not zero")
    require(result.get("stdout") == "m413-parity-ok\n", "Runtime echo output mismatch")
    return {"status": payload["status"], "route": "runtime",
            "exit_code": str(result["exit_code"]), "stdout": result["stdout"]}


class Runner:
    def __init__(self):
        self.report = {"phase": "M4.1.3", "started_at": datetime.now(timezone.utc).isoformat(),
                       "project": PROJECT, "gates": [], "variants": {},
                       "status": "running"}
        self.minimum_ram = None

    def memory(self):
        with open("/proc/meminfo", encoding="ascii") as handle:
            available = next(int(line.split()[1]) for line in handle
                             if line.startswith("MemAvailable:"))
        self.minimum_ram = min(self.minimum_ram or available, available)
        require(available >= 1024 * 1024, "available RAM below 1 GiB")

    def run(self, label, command, *, data=None, timeout=180, check=True, guard=True):
        started = time.monotonic()
        if guard:
            self.memory()
        child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        failure = None
        first = True
        try:
            while True:
                try:
                    out, err = child.communicate(input=data if first else None, timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    if guard:
                        self.memory()
                    require(time.monotonic() - started < timeout, f"{label}: timeout")
        except BaseException as exc:
            failure = exc
            signal_process_group(child, signal.SIGTERM)
            try:
                out, err = child.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                signal_process_group(child, signal.SIGKILL)
                out, err = child.communicate()
        self.report["gates"].append({"gate": label, "command": command,
                                     "exit_code": child.returncode,
                                     "duration_s": round(time.monotonic() - started, 2)})
        print(f"{label}: exit={child.returncode}", flush=True)
        if failure is not None:
            raise failure
        if check:
            require(child.returncode == 0, f"{label}: command failed (output withheld)")
        return child.returncode, out, err

    def http(self, opener, base, path, *, body=None, headers=None, expected=200):
        self.memory()
        request = urllib.request.Request(base + path, data=body, headers=headers or {})
        try:
            with opener.open(request, timeout=10) as response:
                code, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            code, raw = exc.code, exc.read()
        except (OSError, urllib.error.URLError) as exc:
            raise AcceptanceFailure(f"HTTP {path}: transport failed") from exc
        require(code == expected, f"HTTP {path}: expected {expected}, got {code}")
        self.report["gates"].append({"gate": f"HTTP {path}", "status_code": code})
        return json.loads(raw) if raw and raw.lstrip().startswith((b"{", b"[")) else raw


def verify_container_environment(runner, compose, stdin, config, coverage, legacy):
    for name in APPLICATIONS:
        _, raw, _ = runner.run(f"{name}: container id", compose + ["ps", "-q", name], data=stdin)
        ids = raw.decode().split()
        require(len(ids) == 1, f"{name}: expected exactly one container")
        _, raw, _ = runner.run(f"{name}: inspect", ["docker", "inspect", ids[0]])
        inspected = json.loads(raw)[0]
        actual = dict(item.split("=", 1) for item in inspected["Config"]["Env"])
        expected = config["services"][name]["environment"]
        require(all(actual.get(key) == str(value) for key, value in expected.items()),
                f"{name}: process environment differs from rendered variant")
        for canonical, alias in coverage[name].items():
            absent = canonical if legacy else alias
            require(absent not in actual, f"{name}: unexpected alias precedence")
        require(inspected["State"].get("Health", {}).get("Status") == "healthy",
                f"{name}: unhealthy")


def authenticated_echo(runner, config):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    console = "http://localhost:23000"
    for base, path in ((console, "/healthz"), ("http://localhost:28080", "/health"),
                       ("http://localhost:28000", "/health")):
        runner.http(opener, base, path)
    runner.http(opener, console, "/api/proxy/tasks", body=b"{}",
                headers={"Content-Type": "application/json"}, expected=401)
    admin = config["services"]["install"]["environment"]
    csrf = runner.http(opener, console, "/api/auth/csrf")
    credentials = urllib.parse.urlencode({"csrfToken": csrf["csrfToken"],
        "identifier": admin["CONSOLE_ADMIN_EMAIL"], "password": admin["CONSOLE_ADMIN_PASSWORD"],
        "callbackUrl": console + "/console", "json": "true"}).encode()
    runner.http(opener, console, "/api/auth/callback/credentials", body=credentials,
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    session = runner.http(opener, console, "/api/auth/session")
    require(session.get("user", {}).get("role") == "ADMIN", "Console admin session missing")
    token = uuid.uuid4().hex
    correlation = "m413-" + token
    trace = f"00-{token}-{uuid.uuid4().hex[:16]}-01"
    control_env = config["services"]["control"]["environment"]
    allowed_tenants = control_env.get("OMERTA_RUNTIME_TENANT_IDS") or control_env.get("AION_RUNTIME_TENANT_IDS") or ""
    tenant = next((item.strip() for item in allowed_tenants.split(",") if item.strip()), "tenant-m413")
    payload = json.dumps({"intent": "runtime.echo.v1", "params": {"message": "m413-parity-ok"}}).encode()
    headers = {"Content-Type": "application/json", "tenant-id": tenant,
               "x-correlation-id": correlation, "traceparent": trace,
               "idempotency-key": "m413-" + token}
    result = runner.http(opener, console, "/api/proxy/tasks", body=payload, headers=headers)
    normalized = normalized_result(result)
    replay = runner.http(opener, console, "/api/proxy/tasks", body=payload, headers=headers)
    require(replay.get("taskId") == result.get("taskId"), "idempotent replay changed task identity")
    require(normalized_result(replay) == normalized, "idempotent replay changed task outcome")
    env = config["services"]["control"]["environment"]
    service_token = next(env[key] for key in ("OMERTA_GATEWAY_ADMIN_TOKEN",
                         "AION_GATEWAY_ADMIN_TOKEN", "AION_ADMIN_TOKEN") if env.get(key))
    audit = runner.http(opener, "http://localhost:28000", "/v1/runtime/audit/" + result["taskId"],
                        headers={"Authorization": "Bearer " + service_token, "tenant-id": tenant})
    events = audit.get("items", [])
    require(bool(events), "Control audit evidence missing")
    require(all(event["tenant_id"] == tenant and event["request_id"] == correlation
                and event["trace_id"] == trace for event in events),
            "tenant/correlation/trace propagation mismatch")
    require(any(event["action"] == "runtime.dispatch.success" for event in events),
            "Control audit lacks successful dispatch")
    return normalized, len(events)


def scan_logs(runner, compose, stdin, config, coverage, since, secret_values):
    _, out, err = runner.run("application logs", compose + ["logs", "--no-color", "--since", since,
                                      *APPLICATIONS, "install"], data=stdin, guard=False)
    logs = out + err
    for name, value in secret_values.items():
        require(value.encode() not in logs and json.dumps(value)[1:-1].encode() not in logs,
                f"configured credential found in logs: {name}")
    consumed = sorted({alias for pairs in coverage.values() for alias in pairs.values()
                       if any(alias.encode() in line and b"deprecated" in line.lower()
                              for line in logs.splitlines())})
    return consumed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--console-image", required=True)
    parser.add_argument("--control-image", default="omertaos-control:m412-62fdfed")
    parser.add_argument("--runtime-image", default="omertaos-runtime:m412-62fdfed")
    parser.add_argument("--gateway-image", default="omertaos-gateway:m412-62fdfed")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Explicitly authorize starting the isolated stack")
    parser.add_argument("--build-console", action="store_true")
    args = parser.parse_args(argv)
    require(not args.build_console or args.run, "--build-console requires --run")
    require(args.output.resolve().is_relative_to(ROOT / "artifacts"),
            "sanitized reports must be written under the ignored artifacts directory")
    runner = Runner()
    active = None
    try:
        groups, unsupported = load_alias_contract()
        values = parse_environment_file(args.env_file)
        validation = validate_environment_aliases(values, groups, unsupported)
        require(not validation.errors, "environment alias preflight rejected the input file")
        runner.report["deprecated_host_key_count"] = len(validation.warnings)
        _, revision, _ = runner.run("source revision", ["git", "rev-parse", "HEAD"])
        runner.report["commit"] = revision.decode().strip()
        base = ["docker", "compose", "--project-directory", str(ROOT), "--project-name", PROJECT,
                "--env-file", str(args.env_file.resolve()), "-f", str(ROOT / "deploy/docker/compose/quickstart.yml")]
        _, raw, _ = runner.run("canonical Compose render", base + ["config", "--format", "json"])
        rendered = compose_dollars(json.loads(raw), encode=False)
        configs = {name: variant_config(rendered, groups, legacy=name == "legacy", console_image=args.console_image,
                                       control_image=args.control_image, runtime_image=args.runtime_image,
                                       gateway_image=args.gateway_image)
                   for name in ("canonical", "legacy")}
        runner.report["configured_aliases"] = configs["canonical"][1]
        runner.report["conflict_preflight_pairs"] = conflicting_pairs(groups, configs["canonical"][1])
        compose = ["docker", "compose", "--parallel", "1", "--project-directory", str(ROOT),
                   "--project-name", PROJECT, "-f", "-"]
        for name, (config, _) in configs.items():
            data = json.dumps(compose_dollars(config, encode=True)).encode()
            runner.run(f"{name}: Compose config", compose + ["config", "--quiet"], data=data)
        if not args.run:
            runner.report["status"] = "preflight-only"
            return 0
        runner.run("volume preservation preflight", ["docker", "volume", "inspect",
                   *(f"{PROJECT}_{name}" for name in VOLUMES)])
        _, running, _ = runner.run("project stopped preflight", ["docker", "ps", "-q", "--filter",
                                       f"label=com.docker.compose.project={PROJECT}"])
        require(not running.strip(), "isolated project is already running; refusing to take it over")
        if args.build_console:
            runner.run("Console image build", ["docker", "build", "--progress=plain", "-f",
                       "console/Dockerfile", "-t", args.console_image, "."], timeout=2400)
        runner.report["images"] = {}
        for service in APPLICATIONS:
            image = configs["canonical"][0]["services"][service]["image"]
            _, raw, _ = runner.run(f"{service}: image provenance", ["docker", "image", "inspect",
                                      "--format", "{{.Id}}", image])
            runner.report["images"][service] = {"tag": image, "id": raw.decode().strip()}
        runtime_image = configs["canonical"][0]["services"]["runtime"]["image"]
        code, out, err = runner.run("Runtime conflicting bind aliases", ["docker", "run", "--rm",
            "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-e", "OMERTA_RUNTIME_BIND_ADDR=canonical-probe", "-e", "AION_RUNTIME_BIND_ADDR=legacy-probe",
            runtime_image], timeout=20, check=False)
        diagnostic = out + err
        require(code != 0 and b"conflict" in diagnostic.lower()
                and b"OMERTA_RUNTIME_BIND_ADDR" in diagnostic and b"AION_RUNTIME_BIND_ADDR" in diagnostic
                and b"canonical-probe" not in diagnostic and b"legacy-probe" not in diagnostic,
                "Runtime conflict did not fail closed with a sanitized diagnostic")
        secret_names = {group.canonical_name for group in groups if group.secret}
        secret_names.update({"CONSOLE_ADMIN_PASSWORD", "NEXTAUTH_SECRET", "DATABASE_URL"})
        secret_values = {f"{service}.{key}": str(value)
                         for service in (*APPLICATIONS, "install")
                         for key, value in rendered["services"][service]["environment"].items()
                         if key in secret_names and value}
        key_path = Path(rendered["secrets"]["runtime-lease-hmac-key"]["file"])
        secret_values["OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE"] = key_path.read_text().strip()
        outcomes = []
        for name, (config, coverage) in configs.items():
            data = json.dumps(compose_dollars(config, encode=True)).encode()
            active = data
            since = datetime.now(timezone.utc).isoformat()
            try:
                runner.run(f"{name}: stack ready", compose + ["up", "-d", "--no-build", "--pull", "never",
                           "--force-recreate", "--wait", "--wait-timeout", "180", "mongo", *APPLICATIONS],
                           data=data, timeout=300)
                verify_container_environment(runner, compose, data, config, coverage, name == "legacy")
                outcome, event_count = authenticated_echo(runner, config)
                consumed = scan_logs(runner, compose, data, config, coverage, since, secret_values)
                require(bool(consumed) if name == "legacy" else not consumed,
                        f"{name}: unexpected deprecation warning behavior")
                outcomes.append(outcome)
                runner.report["variants"][name] = {"status": "passed", "audit_events": event_count,
                    "consumed_deprecated_aliases": consumed, "authenticated_echo": "passed",
                    "idempotent_replay": "passed", "context_propagation": "passed",
                    "credential_log_scan": sorted(secret_values)}
            finally:
                runner.run(f"{name}: normal stop", compose + ["stop", "--timeout", "30"], data=data,
                           timeout=90, guard=False)
                active = None
        require(outcomes[0] == outcomes[1], "canonical/legacy Runtime outcomes differ")
        _, running, _ = runner.run("final stopped check", ["docker", "ps", "-q", "--filter",
                                  f"label=com.docker.compose.project={PROJECT}"])
        require(not running.strip(), "isolated containers are still running")
        runner.run("retained volumes", ["docker", "volume", "inspect", *(f"{PROJECT}_{name}" for name in VOLUMES)])
        runner.report["status"] = "passed"
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        runner.report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        runner.report["error"] = str(exc) if isinstance(exc, AcceptanceFailure) else type(exc).__name__
        print("Acceptance failed: " + runner.report["error"], flush=True)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    finally:
        if active is not None:
            try:
                runner.run("emergency stop", compose + ["stop", "--timeout", "30"], data=active,
                           timeout=90, guard=False)
            except Exception:
                runner.report["cleanup"] = "failed; inspect isolated project manually"
        runner.report["minimum_available_ram_mib"] = (runner.minimum_ram or 0) // 1024
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(runner.report, indent=2) + "\n", encoding="utf-8")
        print("Report: " + str(args.output), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
