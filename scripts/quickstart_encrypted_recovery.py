#!/usr/bin/env python3
"""Opt-in signed/encrypted cold-volume backup and isolated Quickstart restore."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from scripts import validate_quickstart_environment_parity as parity  # noqa: E402
from scripts import validate_quickstart_recovery as recovery  # noqa: E402
from scripts.validate_environment_aliases import (  # noqa: E402
    load_alias_contract, parse_environment_file, validate_environment_aliases,
)

VALIDATOR_IMAGE = "omertaos-python-validation:local"


def outside_git(path):
    path = path.expanduser().absolute()
    parity.require(not path.is_relative_to(ROOT), "sensitive recovery files must be outside the workspace")
    try:
        parity.require(path.resolve() == path, "recovery path must not contain symlinks")
        parity.require(not any((parent / ".git").exists() for parent in (path, *path.parents)),
                       "sensitive recovery files must be outside Git worktrees")
    except OSError as exc:
        raise parity.AcceptanceFailure("recovery path cannot be safely inspected") from exc
    return path


def private_directory(path):
    path = outside_git(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    return path


def secure_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def require_private(path, *, directory=False):
    info = path.lstat()
    parity.require(not path.is_symlink() and info.st_uid == os.getuid()
                   and stat.S_IMODE(info.st_mode) & 0o077 == 0
                   and (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)),
                   "recovery key/config ownership or permissions are unsafe")


def digest_file(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def valid_restore_project(project):
    parity.require(re.fullmatch(r"omerta-p3-restore-[a-z0-9][a-z0-9-]{0,19}", project),
                   "restore project must be a bounded, dedicated omerta-p3-restore-* name")


def local_restore_endpoints(config):
    expected = {
        "OMERTA_CONTROL_POSTGRES_DSN": "postgres", "OMERTA_CONTROL_DATABASE_URL": "postgres",
        "DATABASE_URL": "postgres", "OMERTA_CONTROL_MONGO_DSN": "mongo", "OMERTA_CONTROL_REDIS_URL": "redis",
        "OMERTA_REDIS_URL": "redis", "OMERTA_CONTROL_QDRANT_URL": "qdrant",
        "OMERTA_CONTROL_MINIO_ENDPOINT": "minio", "OMERTA_RUNTIME_ENDPOINT": "runtime",
        "CONTROL_URL": "control", "OMERTA_CONTROL_BASE_URL": "control", "OMERTA_CONTROL_GRPC": "control",
        "OMERTA_GATEWAY_URL": "gateway", "GATEWAY_URL": "gateway",
    }
    for service in (*parity.APPLICATIONS, "install"):
        env = config["services"][service]["environment"]
        parity.require(not env.get("OMERTA_RUNTIME_NODES_JSON"), "external/static worker inventory is unsupported in restore")
        for name, host in expected.items():
            if env.get(name):
                value = str(env[name])
                parity.require(urlsplit(value if "://" in value else "//" + value).hostname == host,
                               "restore endpoint is not a selected Compose service: " + name)


def verify_manifest_shape(manifest):
    parity.require(manifest.get("format_version") == 1
                   and manifest.get("source_project") == parity.PROJECT, "unsupported backup format/source")
    expected = {f"{name}.tar.gz.gpg" for name in parity.VOLUMES}
    expected.update({"compose.json.gpg", "environment.gpg", "runtime-lease-key.gpg"})
    parity.require(set(manifest.get("files", {})) == expected, "backup file inventory mismatch")
    parity.require(set(manifest.get("volume_inventories", {})) == set(parity.VOLUMES), "volume inventory missing")
    for name, item in manifest["files"].items():
        parity.require(PurePosixPath(name).name == name
                       and isinstance(item.get("bytes"), int) and item["bytes"] > 0
                       and re.fullmatch(r"[a-f0-9]{64}", item.get("sha256", "")), "invalid backup file entry")


def status_signature(raw, fingerprint, *, decrypted=False):
    lines = raw.decode("utf-8", errors="replace").splitlines()
    signatures = [line.split()[2] for line in lines if line.startswith("[GNUPG:] VALIDSIG ")]
    parity.require(signatures == [fingerprint], "backup signature does not match the pinned recovery key")
    if decrypted:
        parity.require("[GNUPG:] DECRYPTION_OKAY" in lines and "[GNUPG:] GOODMDC" in lines,
                       "backup encryption integrity verification is missing")


class Crypto:
    def __init__(self, runner, directory, *, create=False):
        self.runner = runner
        self.directory = outside_git(directory)
        if create:
            private_directory(self.directory)
            private_directory(self.directory / "keyring")
            secure_write(self.directory / "passphrase", secrets.token_urlsafe(48).encode() + b"\n")
        require_private(self.directory, directory=True)
        require_private(self.directory / "keyring", directory=True)
        require_private(self.directory / "passphrase")
        self.home = self.directory / "keyring"
        self.passphrase = self.directory / "passphrase"
        if create:
            runner.run("generate protected signing key", self.command(private=True) + [
                "--quick-generate-key", "OMERTAOS P3 local recovery", "ed25519", "sign", "1y"], timeout=180)
        _, raw, _ = runner.run("recovery key identity", self.command() + ["--with-colons", "--list-keys"])
        fingerprints = [line.split(":")[9] for line in raw.decode().splitlines() if line.startswith("fpr:")]
        parity.require(bool(fingerprints), "recovery keyring has no public key")
        self.fingerprint = fingerprints[0]
        if create:
            runner.run("generate protected encryption subkey", self.command(private=True) + [
                "--quick-add-key", self.fingerprint, "cv25519", "encrypt", "1y"], timeout=180)
            for label, option in (("public", "--export"), ("private", "--export-secret-keys")):
                _, raw, _ = runner.run(f"export {label} recovery key", self.command(private=label == "private") + [
                    "--armor", option, self.fingerprint])
                secure_write(self.directory / f"recovery-{label}.asc", raw)

    def command(self, *, private=False, home=None):
        command = ["gpg", "--batch", "--homedir", str(home or self.home)]
        if private:
            command += ["--pinentry-mode", "loopback", "--passphrase-file", str(self.passphrase)]
        return command

    def encrypt(self):
        return self.command(private=True) + ["--local-user", self.fingerprint, "--recipient", self.fingerprint,
            "--cipher-algo", "AES256", "--compress-algo", "none", "--sign", "--encrypt", "--output", "-"]

    def decrypt(self, path, home):
        return self.command(private=True, home=home) + ["--output", "-", "--decrypt", str(path)]

    def verify(self, path, home):
        _, raw, _ = self.runner.run("authenticate " + path.name, self.command(private=True, home=home) + [
            "--status-fd", "1", "--output", "/dev/null", "--decrypt", str(path)], timeout=300)
        status_signature(raw, self.fingerprint, decrypted=True)


def pipeline(runner, label, producer, consumer, *, output=None, timeout=600):
    """Stream plaintext only through a pipe; retain partial ciphertext on failure."""
    runner.memory()
    started = time.monotonic()
    children = []
    handle = None
    try:
        if output is not None:
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            handle = os.fdopen(fd, "wb")
        first = subprocess.Popen(producer, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        children.append(first)
        second = subprocess.Popen(consumer, cwd=ROOT, stdin=first.stdout,
                                  stdout=handle if handle is not None else subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, start_new_session=True)
        children.append(second)
        first.stdout.close()
        while any(child.poll() is None for child in children):
            runner.memory()
            parity.require(time.monotonic() - started < timeout, label + ": timeout")
            parity.require(not any(child.poll() not in (None, 0) for child in children), label + ": pipeline failed")
            time.sleep(0.25)
        parity.require(all(child.returncode == 0 for child in children), label + ": pipeline failed")
        if handle is not None:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if handle is not None:
            handle.close()
        runner.report["gates"].append({"gate": label, "producer": producer, "consumer": consumer,
            "exit_codes": [child.returncode for child in children],
            "duration_s": round(time.monotonic() - started, 2)})
        print(label + ": exits=" + str([child.returncode for child in children]), flush=True)


INVENTORY = r'''
import hashlib,json,os,stat
records=[]
for parent, dirs, files in os.walk('/source', followlinks=False):
    for name in sorted(dirs + files):
        path=os.path.join(parent,name)
        info=os.lstat(path)
        assert stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        digest=None
        if stat.S_ISREG(info.st_mode):
            h=hashlib.sha256()
            with open(path,'rb') as handle:
                for chunk in iter(lambda:handle.read(1048576),b''): h.update(chunk)
            digest=h.hexdigest()
        records.append((os.path.relpath(path,'/source'),stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid,digest))
root=os.stat('/source')
records.append(('.',stat.S_IMODE(root.st_mode),root.st_uid,root.st_gid,None))
print(json.dumps({'entries':len(records),'sha256':hashlib.sha256(json.dumps(sorted(records)).encode()).hexdigest()}))
'''

ARCHIVE_CHECK = r'''
import pathlib,sys,tarfile
with tarfile.open(fileobj=sys.stdin.buffer, mode='r|gz') as archive:
    for member in archive:
        path=pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isdir() or member.isfile()
        assert not member.issym() and not member.islnk() and member.mode & 0o6000 == 0
        if member.isfile():
            with archive.extractfile(member) as handle:
                while handle.read(1048576):
                    pass
'''


def container_tool(image, volume, *, writable=False):
    command = ["docker", "run", "--rm", "--network", "none", "--read-only", "--memory", "256m", "--cpus", "1",
               "--security-opt", "no-new-privileges", "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE", "--user", "0:0"]
    if writable:
        command += ["-i", "--cap-add", "CHOWN", "--cap-add", "FOWNER"]
    command += ["--mount", f"type=volume,src={volume},dst={'/target' if writable else '/source'}"
                + ("" if writable else ",readonly"), image]
    return command


def inventory(runner, project, name):
    _, raw, _ = runner.run("cold inventory " + name, container_tool(VALIDATOR_IMAGE, f"{project}_{name}") + [
        "python", "-c", INVENTORY], timeout=300)
    return json.loads(raw)


def source_config(runner, args):
    recovery.volume_consumer_guard(runner, parity.PROJECT)
    _, raw, _ = runner.run("source stopped containers", ["docker", "ps", "-aq", "--filter",
        f"label=com.docker.compose.project={parity.PROJECT}"])
    ids = raw.decode().split()
    parity.require(len(ids) == 11, "expected eleven retained source containers")
    _, raw, _ = runner.run("source container provenance", ["docker", "inspect", *ids])
    records = json.loads(raw)
    parity.require(not any(record["State"]["Running"] for record in records), "source must be fully stopped")
    groups, unsupported = load_alias_contract()
    parity.require(not validate_environment_aliases(parse_environment_file(args.env_file), groups, unsupported).errors,
                   "source environment preflight failed")
    command = ["docker", "compose", "--project-directory", str(ROOT), "-p", parity.PROJECT,
        "--env-file", str(args.env_file.resolve()), "-f", str(ROOT / "deploy/docker/compose/quickstart.yml")]
    _, raw, _ = runner.run("source canonical render", command + ["config", "--format", "json"])
    config = recovery.recovery_config(parity.compose_dollars(json.loads(raw), encode=False), groups,
                                     parity.PROJECT, args.console_image, args.control_image)
    images = {}
    for record in records:
        service = record["Config"]["Labels"]["com.docker.compose.service"]
        config["services"][service]["image"] = record["Image"]
        images[service] = record["Image"]
        if service in (*parity.APPLICATIONS, "install"):
            actual = dict(item.split("=", 1) for item in record["Config"]["Env"])
            parity.require(all(actual.get(key) == str(value) for key, value in
                               config["services"][service]["environment"].items()),
                           "source env changed since last acceptance; refusing mismatched config backup")
    data = json.dumps(parity.compose_dollars(config, encode=True)).encode()
    runner.run("pinned source Compose config", recovery.compose_command(parity.PROJECT) + ["config", "--quiet"], data=data)
    return config, images


def backup(runner, crypto, args, config, images):
    destination = private_directory(args.backup_dir)
    alpine = config["services"]["runtime-lease-secret-init"]["image"]
    key_path = Path(config["secrets"]["runtime-lease-hmac-key"]["file"])
    _, key, _ = runner.run("paired lease key verification", ["docker", "run", "--rm", "--network", "none",
        "--read-only", "--cap-drop", "ALL", "--user", "10001:10001", "--mount",
        f"type=volume,src={parity.PROJECT}_runtime-lease-secret,dst=/source,readonly", alpine,
        "cat", "/source/runtime-lease-hmac-key"])
    parity.require(key.rstrip() == key_path.read_bytes().rstrip(), "lease key/state backup pair differs from source config")
    manifest = {"format_version": 1, "source_project": parity.PROJECT, "created_at": datetime.now(timezone.utc).isoformat(),
                "recipient": crypto.fingerprint, "images": images, "files": {}, "volume_inventories": {}}
    _, raw, _ = runner.run("source revision", ["git", "rev-parse", "HEAD"])
    manifest["commit"] = raw.decode().strip()
    for name in parity.VOLUMES:
        manifest["volume_inventories"][name] = inventory(runner, parity.PROJECT, name)
        filename = name + ".tar.gz.gpg"
        pipeline(runner, "encrypted cold backup " + name,
                 container_tool(alpine, f"{parity.PROJECT}_{name}") + ["tar", "-czpf", "-", "-C", "/source", "."],
                 crypto.encrypt(), output=destination / filename)
        parity.require(manifest["volume_inventories"][name] == inventory(runner, parity.PROJECT, name),
                       "source volume changed during backup")
    for filename, payload in (("compose.json.gpg", json.dumps(config).encode()),
                              ("environment.gpg", args.env_file.read_bytes()),
                              ("runtime-lease-key.gpg", key_path.read_bytes())):
        _, raw, _ = runner.run("encrypt " + filename, crypto.encrypt(), data=payload)
        secure_write(destination / filename, raw)
    for filename in sorted(destination.iterdir()):
        manifest["files"][filename.name] = {"bytes": filename.stat().st_size, "sha256": digest_file(filename)}
    verify_manifest_shape(manifest)
    secure_write(destination / "manifest.json", json.dumps(manifest, indent=2).encode() + b"\n")
    _, raw, _ = runner.run("sign backup manifest", crypto.command(private=True) + ["--local-user", crypto.fingerprint,
        "--output", "-", "--detach-sign", str(destination / "manifest.json")])
    secure_write(destination / "manifest.sig", raw)
    runner.report["backup"] = {"directory": str(destination), "encrypted_files": len(manifest["files"]),
                               "signed_manifest": True, "cold_consistent_volumes": len(parity.VOLUMES)}
    return manifest


def verify_backup(runner, crypto, args):
    home = private_directory(crypto.directory / ("keyring-" + args.restore_project))
    runner.run("import exported recovery key", crypto.command(private=True, home=home) + [
        "--import", str(crypto.directory / "recovery-private.asc")])
    runner.run("clear isolated key agent cache", ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"])
    code, _, _ = runner.run("wrong passphrase rejected", crypto.command(home=home) + [
        "--pinentry-mode", "loopback", "--passphrase", "invalid-test-only-probe", "--output", "/dev/null",
        "--decrypt", str(args.backup_dir / "compose.json.gpg")], check=False)
    parity.require(code != 0, "exported private recovery key was not passphrase protected")
    _, raw, _ = runner.run("verify pinned manifest signature", crypto.command(home=home) + ["--status-fd", "1",
        "--verify", str(args.backup_dir / "manifest.sig"), str(args.backup_dir / "manifest.json")])
    status_signature(raw, crypto.fingerprint)
    manifest = json.loads((args.backup_dir / "manifest.json").read_bytes())
    verify_manifest_shape(manifest)
    parity.require(manifest["recipient"] == crypto.fingerprint, "manifest recipient mismatch")
    for filename, expected in manifest["files"].items():
        path = args.backup_dir / filename
        parity.require(path.is_file() and not path.is_symlink() and path.stat().st_size == expected["bytes"]
                       and digest_file(path) == expected["sha256"], "backup ciphertext checksum mismatch")
        crypto.verify(path, home)
    sample = bytearray((args.backup_dir / "compose.json.gpg").read_bytes())
    parity.require(len(sample) > 512, "encrypted config is unexpectedly short")
    sample[len(sample) // 2] ^= 1
    tampered = crypto.directory / ("tampered-probe-" + args.restore_project + ".gpg")
    secure_write(tampered, sample)
    code, _, _ = runner.run("tampered ciphertext rejected", crypto.command(private=True, home=home) + [
        "--output", "/dev/null", "--decrypt", str(tampered)], check=False)
    parity.require(code != 0, "tampered ciphertext was accepted")
    runner.report["independent_key_import_and_backup_authentication"] = "passed"
    return home, manifest


def restore(runner, crypto, args, home, manifest):
    valid_restore_project(args.restore_project)
    _, raw, _ = runner.run("restore volume absence", ["docker", "volume", "ls", "--format", "{{.Name}}"])
    parity.require(not any(name.startswith(args.restore_project + "_") for name in raw.decode().splitlines()),
                   "restore volumes already exist; refusing replacement")
    _, raw, _ = runner.run("restore project absence", ["docker", "ps", "-aq", "--filter",
        f"label=com.docker.compose.project={args.restore_project}"])
    parity.require(not raw.strip(), "restore project already has containers")
    for name in parity.VOLUMES:
        pipeline(runner, "validate archive paths " + name,
            crypto.decrypt(args.backup_dir / (name + ".tar.gz.gpg"), home),
            ["docker", "run", "--rm", "-i", "--read-only", "--network", "none", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--memory", "256m", "--cpus", "1",
             VALIDATOR_IMAGE, "python", "-c", ARCHIVE_CHECK])
    _, raw, _ = runner.run("recover encrypted Compose configuration",
                          crypto.decrypt(args.backup_dir / "compose.json.gpg", home))
    config = json.loads(raw)
    local_restore_endpoints(config)
    config["name"] = args.restore_project
    config["networks"]["default"]["name"] = args.restore_project + "-net"
    config["volumes"] = {name: {"name": f"{args.restore_project}_{name}", "external": True} for name in parity.VOLUMES}
    restored = private_directory(crypto.directory / ("configuration-" + args.restore_project))
    for encrypted, filename in (("environment.gpg", "environment"), ("runtime-lease-key.gpg", "runtime-lease-hmac-key")):
        _, raw, _ = runner.run("recover " + filename, crypto.decrypt(args.backup_dir / encrypted, home))
        secure_write(restored / filename, raw)
    config["secrets"]["runtime-lease-hmac-key"]["file"] = str(restored / "runtime-lease-hmac-key")
    data = json.dumps(parity.compose_dollars(config, encode=True)).encode()
    runner.run("isolated restored Compose config", recovery.compose_command(args.restore_project) + ["config", "--quiet"], data=data)
    alpine = config["services"]["runtime-lease-secret-init"]["image"]
    for name in parity.VOLUMES:
        runner.run("create new restore volume " + name, ["docker", "volume", "create", f"{args.restore_project}_{name}"])
        pipeline(runner, "restore cold volume " + name,
            crypto.decrypt(args.backup_dir / (name + ".tar.gz.gpg"), home),
            container_tool(alpine, f"{args.restore_project}_{name}", writable=True) + ["tar", "-xzpf", "-", "-C", "/target"])
        parity.require(inventory(runner, args.restore_project, name) == manifest["volume_inventories"][name],
                       "restored volume bytes/ownership/modes differ from the signed cold inventory")
    runner.report["isolated_cold_restore"] = "six volume inventories match before service startup"
    return config, data


def live_restore(runner, crypto, args, home, config, data):
    compose = recovery.compose_command(args.restore_project)
    try:
        runner.run("restored stores ready", compose + ["up", "-d", "--pull", "never", "--no-build", "--wait",
            "--wait-timeout", "180", "postgres", "mongo", "qdrant", "minio", "redis"], data=data, timeout=300)
        exports = {}
        for name, service, command in (
            ("postgres-logical.pgdump.gpg", "postgres", ["sh", "-ec", 'exec pg_dump --format=custom --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"']),
            ("mongo-logical.archive.gpg", "mongo", ["mongodump", "--archive", "--gzip"]),
        ):
            pipeline(runner, "encrypted restored-store logical export " + service,
                ["docker", "exec", f"{args.restore_project}-{service}-1", *command], crypto.encrypt(),
                output=args.backup_dir / name)
            crypto.verify(args.backup_dir / name, home)
            exports[name] = {"bytes": (args.backup_dir / name).stat().st_size,
                             "sha256": digest_file(args.backup_dir / name)}
        export_manifest = args.backup_dir / "logical-exports.json"
        secure_write(export_manifest, json.dumps({"origin": "restored stores before application startup",
            "restore_project": args.restore_project, "files": exports}, indent=2).encode() + b"\n")
        _, raw, _ = runner.run("sign logical export manifest", crypto.command(private=True) + [
            "--local-user", crypto.fingerprint, "--output", "-", "--detach-sign", str(export_manifest)])
        secure_write(args.backup_dir / "logical-exports.sig", raw)
        _, raw, _ = runner.run("verify logical export manifest", crypto.command(home=home) + ["--status-fd", "1",
            "--verify", str(args.backup_dir / "logical-exports.sig"), str(export_manifest)])
        status_signature(raw, crypto.fingerprint)
        runner.report["logical_exports"] = {"status": "encrypted and signed; decryption authenticated",
            "origin": "restored stores before application startup", "independent_logical_restore": "not tested"}
        runner.run("restored full stack ready", compose + ["up", "-d", "--pull", "never", "--no-build", "--wait",
            "--wait-timeout", "180", "mongo", *parity.APPLICATIONS], data=data, timeout=300)
        _, raw, _ = runner.run("restored Mongo fixture identities", ["docker", "exec", f"{args.restore_project}-mongo-1",
            "mongosh", "--quiet", "--eval", 'print(JSON.stringify(db.getSiblingDB("omerta_p3_acceptance").probes.find({purpose:"p3-recovery"},{_id:1}).toArray()))'])
        fixtures = json.loads(raw)
        parity.require(bool(fixtures), "restored historical Mongo fixtures missing")
        code = '''
import json
from sqlalchemy import text
from control.app.network.models import engine
with engine.connect() as db:
    row=db.execute(text("SELECT task_id,tenant_id FROM runtime_audit_events WHERE action='runtime.dispatch.success' ORDER BY id DESC LIMIT 1")).one()
    print(json.dumps({'task':row[0],'tenant':row[1]}))
'''
        identity = recovery.exec_probe(runner, args.restore_project, "control", code, {}, "restored historical audit identity")
        admin = config["services"]["install"]["environment"]["CONSOLE_ADMIN_EMAIL"]
        for fixture in fixtures:
            probe = {**identity, "fixture": fixture["_id"], "email": admin, "seed": False}
            result = recovery.exec_probe(runner, args.restore_project, "control", recovery.STORE_PROBE, probe,
                                         "restored historical stores read")
            parity.require(result["admin_count"] == 1 and result["audit_ids"], "restored admin/audit verification failed")
        parity.authenticated_echo(runner, config)
        runner.report["live_restore"] = {"historical_fixture_count": len(fixtures),
            "postgres_mongo_minio_qdrant": "passed", "administrator_login": "passed", "canonical_authenticated_echo": "passed"}
    finally:
        runner.run("restored normal stop", compose + ["stop", "--timeout", "30"], data=data, timeout=120, guard=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--key-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--restore-project", required=True)
    parser.add_argument("--console-image", default="omertaos-console:m413-1ac6890")
    parser.add_argument("--control-image", default="omertaos-control:m413-9689b8a")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--create-key", action="store_true")
    parser.add_argument("--existing-backup", action="store_true", help="Authenticate an existing signed backup instead of creating one")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    parity.require(args.run, "--run is required for key generation, backup and starting an isolated restore")
    parity.require(not (args.create_key and args.existing_backup), "existing backup requires its existing recovery key")
    parity.require(args.output.resolve().is_relative_to(ROOT / "artifacts"), "sanitized output must be under artifacts")
    args.key_dir = outside_git(args.key_dir)
    args.backup_dir = outside_git(args.backup_dir)
    parity.require(not args.key_dir.is_relative_to(args.backup_dir)
                   and not args.backup_dir.is_relative_to(args.key_dir), "key and backup directories must be separate")
    valid_restore_project(args.restore_project)
    runner = parity.Runner()
    runner.report.update(phase="P3-encrypted-restore", project=args.restore_project,
        skipped=["native/systemd, benchmarks and P4 review", "logical export restore: cold-volume restore is tested instead"],
        blocked=["historical older-release upgrade is a separate gate"],
        limitations=["same-host recovery only; off-host loss recovery is not tested",
                     "MinIO/Qdrant use consistent cold volumes, not portable S3/API-snapshot exports"])
    try:
        runner.memory()
        parity.require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, "less than 5 GiB free disk")
        config, images = source_config(runner, args)
        crypto = Crypto(runner, args.key_dir, create=args.create_key)
        manifest = None if args.existing_backup else backup(runner, crypto, args, config, images)
        home, verified = verify_backup(runner, crypto, args)
        parity.require(manifest is None or manifest == verified, "verified manifest changed")
        manifest = verified
        config, data = restore(runner, crypto, args, home, verified)
        live_restore(runner, crypto, args, home, config, data)
        recovery.volume_consumer_guard(runner, parity.PROJECT)
        for name in parity.VOLUMES:
            parity.require(inventory(runner, parity.PROJECT, name) == manifest["volume_inventories"][name],
                           "source cold state changed during isolated restore")
        runner.report["source_unchanged"] = True
        runner.report["status"] = "partial-blocked"
        return 2
    except (Exception, KeyboardInterrupt) as exc:
        runner.report["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        runner.report["error"] = str(exc) if isinstance(exc, parity.AcceptanceFailure) else type(exc).__name__
        print("Encrypted recovery: " + runner.report["error"], flush=True)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    finally:
        for home in (args.key_dir / "keyring", args.key_dir / ("keyring-" + args.restore_project)):
            if home.is_dir():
                runner.run("clear recovery key-agent cache", ["gpgconf", "--homedir", str(home), "--kill", "gpg-agent"],
                           guard=False, check=False)
        runner.report["minimum_available_ram_mib"] = (runner.minimum_ram or 0) // 1024
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(runner.report, indent=2) + "\n", encoding="utf-8")
        print("Sanitized report: " + str(args.output), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
