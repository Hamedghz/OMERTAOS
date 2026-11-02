#!/usr/bin/env python3
"""Upgrade a verified cold clone of the retained R6 single-worker dataset."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts import quickstart_encrypted_recovery as encrypted  # noqa: E402
from scripts import validate_quickstart_environment_parity as parity  # noqa: E402
from scripts import validate_quickstart_recovery as recovery  # noqa: E402
from scripts.validate_environment_aliases import load_alias_contract  # noqa: E402

LEGACY = "omertaos-r6-fixed"
VOLUME_PATHS = {"postgres-data": ("postgres", "/var/lib/postgresql/data"),
                "mongo-data": ("mongo", "/data/db"), "mongo-configdb": ("mongo", "/data/configdb"),
                "minio-data": ("minio", "/data"), "redis-data": ("redis", "/data")}
TAR_INVENTORY = r'''
import hashlib,json,pathlib,sys,tarfile
records=[]
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz') as archive:
    for member in archive:
        path=pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isdir() or member.isfile()
        assert not member.issym() and not member.islnk() and member.mode & 0o6000 == 0
        digest=None
        if member.isfile():
            h=hashlib.sha256()
            with archive.extractfile(member) as handle:
                for chunk in iter(lambda:handle.read(1048576),b''):h.update(chunk)
            digest=h.hexdigest()
        records.append((str(path),member.mode,member.uid,member.gid,digest))
print(json.dumps({'entries':len(records),'sha256':hashlib.sha256(json.dumps(sorted(records)).encode()).hexdigest()}))
'''

SQL_SNAPSHOT = r'''
import collections,hashlib,json,sys
import psycopg2
from psycopg2 import sql
p=json.load(sys.stdin)
result={}
with psycopg2.connect(p['dsn']) as db:
    with db.cursor() as cursor:
        if p.get('selection') is None:
            cursor.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename")
            tables=[row[0] for row in cursor.fetchall()]
            selection={}
            for table in tables:
                cursor.execute(sql.SQL('SELECT * FROM {} LIMIT 0').format(sql.Identifier('public',table)))
                selection[table]=[col.name for col in cursor.description]
        else:selection=p['selection']
        for table,columns in selection.items():
            query=sql.SQL('SELECT row_to_json(record)::text FROM (SELECT {} FROM {}) record').format(
                sql.SQL(',').join(map(sql.Identifier,columns)),sql.Identifier('public',table))
            cursor.execute(query)
            hashes=collections.Counter()
            count=0
            for row in cursor:
                count+=1
                assert count<=100000,'acceptance row budget exceeded'
                hashes[hashlib.sha256(row[0].encode()).hexdigest()]+=1
            result[table]={'columns':columns,'hashes':dict(hashes),'rows':count}
print(json.dumps(result))
'''


def merge_legacy_environment(current, legacy, groups):
    """Preserve supported semantic settings while keeping clone transport bindings."""
    excluded = {"OMERTA_CORS_ORIGINS", "OMERTA_GATEWAY_PORT", "OMERTA_GATEWAY_HOST",
                "OMERTA_RUNTIME_BIND_ADDR", "OMERTA_GATEWAY_URL"}
    merged = dict(current)
    for group in groups:
        if group.canonical_name not in merged or group.canonical_name in excluded:
            continue
        values = {legacy[key] for key in (group.canonical_name, *group.aliases) if legacy.get(key)}
        parity.require(len(values) <= 1, "conflicting retained legacy aliases: " + group.canonical_name)
        if values:
            merged[group.canonical_name] = values.pop()
    return merged


def assert_old_rows_preserved(before, after):
    for table, original in before.items():
        parity.require(table in after and after[table]["columns"] == original["columns"],
                       "historical columns disappeared: " + table)
        parity.require(not (Counter(original["hashes"]) - Counter(after[table]["hashes"])),
                       "historical row contents changed or disappeared: " + table)


def retained_source(runner):
    _, raw, _ = runner.run("retained R6 containers", ["docker", "ps", "-aq", "--filter",
                          f"label=com.docker.compose.project={LEGACY}"])
    ids = raw.decode().split()
    parity.require(len(ids) == 10, "expected ten retained single-worker R6 containers")
    _, raw, _ = runner.run("retained R6 provenance", ["docker", "inspect", *ids])
    rows = json.loads(raw)
    parity.require(not any(row["State"]["Running"] for row in rows), "historical source is running")
    by_service = {row["Config"]["Labels"]["com.docker.compose.service"]: row for row in rows}
    for row in rows:
        parity.require(row["State"]["FinishedAt"].startswith("2026-08-30"), "historical source provenance changed")
    volumes = {}
    for name, (service, path) in VOLUME_PATHS.items():
        mounts = [mount for mount in by_service[service]["Mounts"] if mount["Destination"] == path]
        parity.require(len(mounts) == 1 and mounts[0]["Type"] == "volume", "missing historical data mount")
        volumes[name] = mounts[0]["Name"]
        _, raw, _ = runner.run("historical volume consumers " + name, ["docker", "ps", "-aq", "--filter",
                               "volume=" + volumes[name]])
        consumers = raw.decode().split()
        _, raw, _ = runner.run("historical volume ownership " + name, ["docker", "inspect", *consumers])
        parity.require(all(not row["State"]["Running"] and
            row["Config"].get("Labels", {}).get("com.docker.compose.project") == LEGACY for row in json.loads(raw)),
            "historical volume has an active or foreign consumer")
    parity.require(not by_service["qdrant"]["Mounts"], "unexpected historical Qdrant storage contract")
    runner.report["historical_source"] = {"project": LEGACY, "source_is_synthetic": False,
        "services": {name: {"image": row["Image"], "created": row["Created"],
                            "finished": row["State"]["FinishedAt"]} for name, row in by_service.items()},
        "volume_sources": volumes, "qdrant_source": "retained stopped container writable layer"}
    return by_service, volumes


def clone_config(runner, args, source):
    groups, _ = load_alias_contract()
    base = ["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(args.env_file),
            "-p", args.project, "-f", str(ROOT / "deploy/docker/compose/quickstart.yml")]
    _, raw, _ = runner.run("canonical current Compose render", base + ["config", "--format", "json"])
    config, _ = parity.variant_config(parity.compose_dollars(json.loads(raw), encode=False), groups,
        legacy=False, console_image="omertaos-console:m413-1ac6890", control_image="omertaos-control:m413-9689b8a")
    config["name"] = args.project
    config["networks"]["default"]["name"] = args.project + "-net"
    for name in (*parity.APPLICATIONS, "install"):
        old_env = dict(item.split("=", 1) for item in source[name]["Config"]["Env"])
        env = merge_legacy_environment(config["services"][name]["environment"], old_env, groups)
        for key in ("DATABASE_URL", "NEXTAUTH_SECRET"):
            if old_env.get(key):
                env[key] = old_env[key]
        if name == "install":
            for key in ("CONSOLE_ADMIN_EMAIL", "CONSOLE_ADMIN_PASSWORD", "CONSOLE_ADMIN_NAME",
                        "CONSOLE_ADMIN_PASSWORD_MIN_LENGTH", "CONSOLE_ADMIN_PASSWORD_MAX_LENGTH"):
                if key in old_env:
                    env[key] = old_env[key]
        config["services"][name]["environment"] = env
    config["services"]["postgres"]["environment"] = dict(
        item.split("=", 1) for item in source["postgres"]["Config"]["Env"] if item.startswith("POSTGRES_"))
    for name in ("minio", "mongo", "qdrant", "redis", "postgres"):
        config["services"][name]["image"] = source[name]["Image"]
    old_minio = dict(item.split("=", 1) for item in source["minio"]["Config"]["Env"])
    config["services"]["minio"]["environment"] = {key: old_minio[key] for key in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD")}
    for name in parity.APPLICATIONS:
        _, raw, _ = runner.run("target image identity " + name, ["docker", "image", "inspect", "--format", "{{.Id}}",
            config["services"][name]["image"]])
        config["services"][name]["image"] = raw.decode().strip()
    config["services"]["install"]["image"] = config["services"]["console"]["image"]
    all_names = set(parity.VOLUMES) | set(VOLUME_PATHS)
    config["volumes"] = {name: {"name": f"{args.project}_{name}", "external": True} for name in all_names}
    for service, name, path in (("redis", "redis-data", "/data"), ("mongo", "mongo-configdb", "/data/configdb")):
        config["services"][service].setdefault("volumes", []).append({"type": "volume", "source": name, "target": path})
    encrypted.local_restore_endpoints(config)
    return config


def volume_inventory(runner, volume, label):
    _, raw, _ = runner.run("inventory " + label, encrypted.container_tool(encrypted.VALIDATOR_IMAGE, volume) + [
        "python", "-c", encrypted.INVENTORY], timeout=300)
    return json.loads(raw)


def archive_summary(runner, producer, output, label):
    encrypted.pipeline(runner, label, producer, ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--memory", "256m", "--cpus", "1", encrypted.VALIDATOR_IMAGE,
        "python", "-c", TAR_INVENTORY], output=output)
    return json.loads(output.read_bytes())


def sql_snapshot(runner, config, project, selection=None, *, migrate=False):
    dsn = config["services"]["control"]["environment"]["OMERTA_CONTROL_POSTGRES_DSN"]
    code = SQL_SNAPSHOT if not migrate else '''
import json,os,sys
os.environ['OMERTA_CONTROL_POSTGRES_DSN']=json.load(sys.stdin)['dsn']
from control.app.network.migrate import apply_schema
apply_schema()
'''
    _, raw, _ = runner.run("historical schema migration" if migrate else "historical row snapshot", [
        "docker", "run", "--rm", "-i", "--network", project + "-net", "--read-only", "--cap-drop", "ALL",
        "--memory", "512m", "--cpus", "1", config["services"]["control"]["image"], "python", "-c", code],
        data=json.dumps({"dsn": dsn, "selection": selection}).encode(), timeout=90)
    return None if migrate else json.loads(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--key-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    parity.require(args.run, "--run required for historical backup/clone/migration acceptance")
    encrypted.valid_restore_project(args.project)
    args.key_dir, args.backup_dir = encrypted.outside_git(args.key_dir), encrypted.outside_git(args.backup_dir)
    parity.require(not args.key_dir.is_relative_to(args.backup_dir) and not args.backup_dir.is_relative_to(args.key_dir),
                   "backup and key directories must be separate")
    parity.require(args.output.resolve().is_relative_to(ROOT / "artifacts"), "reports must be under artifacts")
    runner = parity.Runner()
    runner.report.update(phase="P3-historical-upgrade", project=args.project,
        skipped=["old Console UI startup", "historical unexpired Runtime fence: source predates durable fencing",
                 "production, off-host, native/systemd and benchmarks"])
    crypto = None
    home = None
    config = data = None
    active = False
    try:
        runner.memory()
        parity.require(shutil.disk_usage(ROOT).free > 5 * 1024**3, "less than 5 GiB available disk")
        source, volumes = retained_source(runner)
        _, raw, _ = runner.run("clone volume absence", ["docker", "volume", "ls", "--format", "{{.Name}}"])
        parity.require(not any(name.startswith(args.project + "_") for name in raw.decode().splitlines()), "clone volumes exist")
        _, raw, _ = runner.run("clone container absence", ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={args.project}"])
        parity.require(not raw.strip(), "clone containers exist")
        config = clone_config(runner, args, source)
        data = json.dumps(parity.compose_dollars(config, encode=True)).encode()
        compose = recovery.compose_command(args.project)
        runner.run("upgrade Compose validation", compose + ["config", "--quiet"], data=data)
        encrypted.private_directory(args.backup_dir)
        crypto = encrypted.Crypto(runner, args.key_dir)
        home = encrypted.private_directory(args.key_dir / ("keyring-" + args.project))
        runner.run("import exported upgrade recovery key", crypto.command(private=True, home=home) + [
            "--import", str(args.key_dir / "recovery-private.asc")])
        alpine = config["services"]["runtime-lease-secret-init"]["image"]
        inventories = {}
        for name, volume in volumes.items():
            inventories[name] = volume_inventory(runner, volume, "source " + name)
            encrypted.pipeline(runner, "encrypt old " + name,
                encrypted.container_tool(alpine, volume) + ["tar", "-czpf", "-", "-C", "/source", "."],
                crypto.encrypt(), output=args.backup_dir / (name + ".tar.gz.gpg"))
        qdrant = source["qdrant"]["Id"]
        qdrant_source = ["bash", "-o", "pipefail", "-c", shlex.join(["docker", "cp", "-a", qdrant + ":/qdrant/storage/.", "-"]) + " | gzip -c"]
        inventories["qdrant-data"] = archive_summary(runner, qdrant_source, args.backup_dir / "qdrant-inventory.json", "inventory old Qdrant layer")
        encrypted.pipeline(runner, "encrypt old Qdrant layer", qdrant_source, crypto.encrypt(), output=args.backup_dir / "qdrant-data.tar.gz.gpg")
        payload = {"retained_environment": {name: row["Config"]["Env"] for name, row in source.items()}, "target_config": config}
        _, raw, _ = runner.run("encrypt historical config", crypto.encrypt(), data=json.dumps(payload).encode())
        encrypted.secure_write(args.backup_dir / "configuration.gpg", raw)
        manifest = {"format": "omerta-r6-upgrade-v1", "source": runner.report["historical_source"], "inventories": inventories,
            "files": {path.name: {"sha256": encrypted.digest_file(path), "bytes": path.stat().st_size}
                      for path in args.backup_dir.glob("*.gpg")}}
        encrypted.secure_write(args.backup_dir / "manifest.json", json.dumps(manifest, indent=2).encode())
        _, raw, _ = runner.run("sign historical manifest", crypto.command(private=True) + ["--local-user", crypto.fingerprint,
            "--output", "-", "--detach-sign", str(args.backup_dir / "manifest.json")])
        encrypted.secure_write(args.backup_dir / "manifest.sig", raw)
        _, raw, _ = runner.run("verify historical manifest", crypto.command(home=home) + ["--status-fd", "1", "--verify",
            str(args.backup_dir / "manifest.sig"), str(args.backup_dir / "manifest.json")])
        encrypted.status_signature(raw, crypto.fingerprint)
        for name, expected in manifest["files"].items():
            path = args.backup_dir / name
            parity.require(encrypted.digest_file(path) == expected["sha256"], "historical ciphertext changed")
            crypto.verify(path, home)
        for name, expected in inventories.items():
            summary = archive_summary(runner, crypto.decrypt(args.backup_dir / (name + ".tar.gz.gpg"), home),
                args.backup_dir / (name + "-verified-inventory.json"), "verify historical archive " + name)
            parity.require(summary == expected, "historical archive inventory mismatch")
            runner.run("create historical clone " + name, ["docker", "volume", "create", f"{args.project}_{name}"])
            encrypted.pipeline(runner, "extract historical clone " + name, crypto.decrypt(args.backup_dir / (name + ".tar.gz.gpg"), home),
                encrypted.container_tool(alpine, f"{args.project}_{name}", writable=True) + ["tar", "-xzpf", "-", "-C", "/target"])
            parity.require(volume_inventory(runner, f"{args.project}_{name}", "clone " + name) == expected, "clone content/mode/owner mismatch")
        for name in ("runtime-state", "runtime-lease-secret"):
            runner.run("new post-R6 fencing volume " + name, ["docker", "volume", "create", f"{args.project}_{name}"])
        active = True
        runner.run("historical clone PostgreSQL ready", compose + ["up", "-d", "--pull", "never", "--no-build", "--wait",
            "--wait-timeout", "120", "postgres"], data=data, timeout=180)
        before = sql_snapshot(runner, config, args.project)
        parity.require(all(before.get(name, {}).get("rows", 0) > 0 for name in ("User", "task_attempts", "runtime_nodes")),
                       "retained dataset lacks historical administrator or Runtime work")
        selection = {name: item["columns"] for name, item in before.items()}
        runner.report["pre_upgrade"] = {name: {"rows": item["rows"], "columns": item["columns"]} for name, item in before.items()}
        runner.run("forward Console migrations and preserved bootstrap", compose + ["run", "--rm", "--no-deps", "-T",
            "--pull", "never", "install"], data=data, timeout=180)
        sql_snapshot(runner, config, args.project, migrate=True)
        assert_old_rows_preserved(before, sql_snapshot(runner, config, args.project, selection))
        after_schema = sql_snapshot(runner, config, args.project)
        added = sorted(set(after_schema) - set(before))
        parity.require("runtime_audit_events" in after_schema and "runtime_execution_leases" in after_schema and added,
                       "dataset did not exercise an older schema upgrade")
        runner.report["migration"] = {"original_rows_preserved": True, "added_tables": added}
        runner.run("upgraded canonical stack ready", compose + ["up", "-d", "--no-build", "--pull", "never", "--wait",
            "--wait-timeout", "180", "mongo", *parity.APPLICATIONS], data=data, timeout=300)
        parity.authenticated_echo(runner, config)
        immutable = {name: cols for name, cols in selection.items() if name != "runtime_nodes"}
        assert_old_rows_preserved({name: before[name] for name in immutable}, sql_snapshot(runner, config, args.project, immutable))
        runner.report["upgraded_authenticated_path"] = "passed with retained administrator credentials and fresh lease"
        runner.run("upgraded normal stop", compose + ["stop", "--timeout", "30"], data=data, timeout=120, guard=False)
        active = False
        retained_source(runner)
        for name, volume in volumes.items():
            parity.require(volume_inventory(runner, volume, "unchanged source " + name) == inventories[name], "original historical data changed")
        final_qdrant = archive_summary(runner, qdrant_source, args.backup_dir / "qdrant-final-inventory.json", "unchanged old Qdrant layer")
        parity.require(final_qdrant == inventories["qdrant-data"], "original Qdrant layer changed")
        runner.report.update(status="passed", source_unchanged=True, backup_directory=str(args.backup_dir))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        runner.report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        runner.report["error"] = str(exc) if isinstance(exc, parity.AcceptanceFailure) else type(exc).__name__
        print("Historical upgrade: " + runner.report["error"], flush=True)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    finally:
        if active and data is not None:
            runner.run("historical clone emergency normal stop", recovery.compose_command(args.project) + ["stop", "--timeout", "30"],
                       data=data, timeout=120, guard=False)
        for path in (args.key_dir / "keyring", home):
            if path is not None and path.is_dir():
                runner.run("clear historical recovery key cache", ["gpgconf", "--homedir", str(path), "--kill", "gpg-agent"], guard=False)
        runner.report["minimum_available_ram_mib"] = (runner.minimum_ram or 0) // 1024
        runner.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(runner.report, indent=2) + "\n")
        print("Report: " + str(args.output), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
