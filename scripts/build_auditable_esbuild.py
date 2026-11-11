#!/usr/bin/env python3
"""Build and scan a private esbuild artifact without modifying an installation."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import stat
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
INPUTS = Path(__file__).with_name("esbuild-provenance-inputs.json")
GIB = 1024 ** 3


class BuildFailure(RuntimeError):
    """An operator-safe failed gate."""


class BuildBlocked(BuildFailure):
    """A network or resource prerequisite is unavailable."""


def require(condition, message):
    if not condition:
        raise BuildFailure(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_digest(path, expected):
    actual = sha256(path)
    require(actual == expected, "SHA256 mismatch")
    return actual


class ResourceGuard:
    def __init__(self, directory):
        self.directory = directory
        self.minimum_ram_bytes = None
        self.minimum_disk_bytes = None

    def check(self):
        available = next(int(line.split()[1]) * 1024
                         for line in Path("/proc/meminfo").read_text().splitlines()
                         if line.startswith("MemAvailable:"))
        space = shutil.disk_usage(self.directory).free
        self.minimum_ram_bytes = min(self.minimum_ram_bytes or available, available)
        self.minimum_disk_bytes = min(self.minimum_disk_bytes or space, space)
        if available < GIB:
            raise BuildBlocked("available RAM below 1 GiB")
        if space < 3 * GIB:
            raise BuildBlocked("available disk below 3 GiB")


def signal_group(child, sig):
    try:
        os.killpg(child.pid, sig)
    except ProcessLookupError:
        pass


class Runner:
    def __init__(self, work, environment, guard):
        self.work, self.environment, self.guard = work, environment, guard
        self.report = {"status": "running", "stage": "P4-esbuild-A",
                       "started_at": datetime.now(timezone.utc).isoformat(), "gates": [],
                       "installation_changed": False, "live_acceptance": False}

    def save(self):
        self.report["minimum_available_ram_bytes"] = self.guard.minimum_ram_bytes
        self.report["minimum_free_disk_bytes"] = self.guard.minimum_disk_bytes
        (self.work / "receipt.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def step(self, label, operation):
        entry = {"gate": label, "status": "running"}
        self.report["gates"].append(entry)
        started = time.monotonic()
        try:
            self.guard.check()
            result = operation()
            self.guard.check()
            entry["status"] = "passed"
            return result
        except BaseException as exc:
            entry["status"] = "blocked" if isinstance(exc, BuildBlocked) else "failed"
            raise
        finally:
            entry["duration_s"] = round(time.monotonic() - started, 3)
            self.save()

    def command(self, label, argv, *, cwd=None, timeout=180, check=True, guard=True):
        entry = {"gate": label, "command": [str(arg) for arg in argv], "status": "running"}
        self.report["gates"].append(entry)
        index, started = len(self.report["gates"]), time.monotonic()
        child = None
        failure = None
        with (self.work / f"{index:02d}.stdout").open("wb") as out, \
                (self.work / f"{index:02d}.stderr").open("wb") as err:
            try:
                if guard:
                    self.guard.check()
                child = subprocess.Popen(argv, cwd=cwd or ROOT, env=self.environment,
                                         stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                         start_new_session=True)
                while True:
                    try:
                        child.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        if guard:
                            self.guard.check()
                        require(time.monotonic() - started < timeout, "command timeout")
                if guard:
                    self.guard.check()
                if check:
                    require(child.returncode == 0, f"{label}: command failed; see private logs")
                entry["status"] = "passed" if child.returncode == 0 else "failed"
            except BaseException as exc:
                failure = exc
                entry["status"] = "blocked" if isinstance(exc, BuildBlocked) else "failed"
            finally:
                if child is not None:
                    if failure is not None:
                        signal_group(child, signal.SIGTERM)
                        try:
                            child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            signal_group(child, signal.SIGKILL)
                            child.wait(timeout=10)
                    entry["exit_code"] = child.returncode
                entry["duration_s"] = round(time.monotonic() - started, 3)
                entry["stdout_file"], entry["stderr_file"] = f"{index:02d}.stdout", f"{index:02d}.stderr"
                self.save()
        print(f"{label}: {entry['status']} exit={entry.get('exit_code')}", flush=True)
        if failure is not None:
            raise failure
        return child.returncode, (self.work / entry["stdout_file"]).read_text()


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(urllib.parse.urlsplit(newurl).scheme == "https", "non-HTTPS redirect rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(spec, output, guard):
    require(urllib.parse.urlsplit(spec["url"]).scheme == "https", "HTTPS required")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), HTTPSRedirects())
    started, size = time.monotonic(), 0
    try:
        with opener.open(spec["url"], timeout=15) as response, output.open("xb") as target:
            while True:
                guard.check()
                require(time.monotonic() - started < 180, "download timeout")
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                require(size <= spec["maximum_download_bytes"], "download size bound exceeded")
                target.write(chunk)
    except urllib.error.HTTPError as exc:
        raise BuildBlocked(f"HTTPS input unavailable: HTTP {exc.code}; work directory retained") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise BuildBlocked("HTTPS transport unavailable; work directory retained") from exc
    verify_digest(output, spec["sha256"])
    return size


def copy_verified_input(path, spec, output, guard):
    require(path.is_absolute() and path == path.resolve() and path.is_file(),
            "absolute non-symlink input archive required")
    require(path.stat().st_size <= spec["maximum_download_bytes"], "input archive size bound exceeded")
    verify_digest(path, spec["sha256"])
    with path.open("rb") as source, output.open("xb") as target:
        while chunk := source.read(65536):
            guard.check()
            target.write(chunk)
    verify_digest(output, spec["sha256"])
    return output.stat().st_size


def extract_verified(archive, spec, destination, guard):
    verify_digest(archive, spec["sha256"])
    destination.mkdir(mode=0o700)
    seen, expanded, links = set(), 0, []
    root = destination / spec["root"]
    # Defer internal symlinks so no archive file is ever written through a link.
    with tarfile.open(archive, "r:gz") as source:
        for index, member in enumerate(source):
            guard.check()
            name = PurePosixPath(member.name)
            require(index < 50000 and name.parts and name.parts[0] == spec["root"]
                    and not name.is_absolute() and ".." not in name.parts
                    and "\\" not in member.name, "unsafe archive member")
            require(name not in seen and (member.isdir() or member.isfile() or member.issym())
                    and not member.issparse(), "archive duplicate/link/special member rejected")
            seen.add(name)
            expanded += member.size
            require(0 <= member.size and expanded <= spec["maximum_expanded_bytes"],
                    "expanded archive size bound exceeded")
            path = destination.joinpath(*name.parts)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if member.issym():
                target = PurePosixPath(member.linkname)
                require(not target.is_absolute() and "\\" not in member.linkname
                        and (path.parent / member.linkname).resolve().is_relative_to(root),
                        "archive symlink escapes root")
                links.append((path, member.linkname))
            elif member.isdir():
                path.mkdir(exist_ok=True, mode=0o700)
            else:
                with source.extractfile(member) as data, path.open("xb") as target:
                    while chunk := data.read(65536):
                        guard.check()
                        target.write(chunk)
                path.chmod(0o700 if member.mode & 0o111 else 0o600)
    for path, target in links:
        guard.check()
        require((path.parent / target).resolve().is_relative_to(root), "archive symlink escapes root")
        path.symlink_to(target)
    return root


def build_environment(work, compiler):
    forbidden = ("GOFLAGS", "GOROOT", "GOWORK", "GOPRIVATE", "GONOSUMDB", "GONOPROXY",
                 "GOPROXY", "GOSUMDB", "GOTOOLCHAIN", "GOENV", "GODEBUG", "GOEXPERIMENT")
    require(not any(os.environ.get(key) for key in forbidden), "inherited Go override rejected")
    environment = {"PATH": f"{compiler / 'bin'}:/usr/bin:/bin", "HOME": str(work / "home"),
                   "LANG": "C.UTF-8", "TZ": "UTC", "GOROOT": str(compiler),
                   "GOENV": "off", "GOTOOLCHAIN": "local", "GOWORK": "off",
                   "GOPROXY": "https://proxy.golang.org", "GOSUMDB": "sum.golang.org",
                   "GOMAXPROCS": "2", "GOMEMLIMIT": "768MiB", "CGO_ENABLED": "0",
                   "GOOS": "linux", "GOARCH": "amd64", "GOAMD64": "v1"}
    for key, subdirectory in (("GOCACHE", "go-cache"), ("GOMODCACHE", "modules"),
                              ("GOTMPDIR", "tmp"), ("GOPATH", "gopath"), ("HOME", "home")):
        directory = work / subdirectory
        directory.mkdir(mode=0o700)
        environment[key] = str(directory)
    environment["TMPDIR"] = environment["GOTMPDIR"]
    return environment


def require_binary_path(binary, expected):
    require(binary.is_absolute() and binary == binary.resolve(), "absolute non-symlink binary required")
    mode = binary.stat()
    require(stat.S_ISREG(mode.st_mode) and mode.st_mode & 0o111
            and not mode.st_mode & 0o222, "binary must be executable and non-writable")
    for parent in binary.parents:
        info = parent.stat()
        sticky_root = info.st_uid == 0 and info.st_mode & stat.S_ISVTX
        require(info.st_uid in (0, os.getuid()) and (not info.st_mode & 0o022 or sticky_root),
                "untrusted binary parent directory")
    verify_digest(binary, expected)


def verify_go_metadata(text, inputs):
    lines = text.splitlines()
    require(lines and lines[0].endswith(": " + inputs["compiler_version"]),
            "compiler build metadata missing or mismatched")
    require("\tpath\tgithub.com/evanw/esbuild/cmd/esbuild" in lines,
            "esbuild module metadata missing")
    for key, value in inputs["target"].items():
        require(f"\tbuild\t{key}={value}" in lines, "binary target metadata mismatch")
    require(any(line.startswith("\tdep\tgolang.org/x/sys\t") for line in lines),
            "dependency build metadata missing")


def verify_scan_coverage(payload, inputs):
    results = [result for result in payload.get("Results", []) if result.get("Type") == "gobinary"]
    require(any(any(pkg.get("Name") == "stdlib"
                    and pkg.get("Version", "").removeprefix("go")
                    == inputs["compiler_version"].removeprefix("go")
                    for pkg in result.get("Packages", [])) for result in results),
            "scanner did not identify the expected Go stdlib")


def tree_hashes(root):
    return {str(path.relative_to(root)): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def container_go_argv(work, environment, image, cidfile, argv, cwd, network):
    def mapped(value):
        if str(value) == str(work):
            return "/work"
        return str(value).replace(str(work), "/work", 1) if str(value).startswith(str(work) + "/") else str(value)

    command = ["/usr/bin/docker", "run", "--rm", "--cidfile", str(cidfile),
               "--network", "bridge" if network else "none", "--read-only",
               "--memory", "1024m", "--cpus", "2", "--pids-limit", "256",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "--user", f"{os.getuid()}:{os.getgid()}",
               "--mount", f"type=bind,src={work},dst=/work",
               "--workdir", mapped(cwd), "--entrypoint", "/usr/local/go/bin/go"]
    for key, value in environment.items():
        if key not in ("PATH", "GOROOT"):
            command.extend(["--env", f"{key}={mapped(value)}"])
    command.extend(["--env", "GOROOT=/usr/local/go", image, *map(mapped, argv)])
    return command


class GoCompiler:
    def __init__(self, runner, inputs, *, image):
        self.runner, self.inputs, self.image = runner, inputs, image

    def run(self, label, argv, *, cwd=None, timeout=180, network=False):
        if not self.image:
            return self.runner.command(label, [str(self.runner.work / "compiler/go/bin/go"), *argv],
                                       cwd=cwd, timeout=timeout)
        cidfile = self.runner.work / f"go-{uuid.uuid4().hex}.cid"
        command = container_go_argv(self.runner.work, self.runner.environment, self.image,
                                    cidfile, argv, cwd or self.runner.work, network)
        try:
            return self.runner.command(label, command, timeout=timeout)
        finally:
            # Only this invocation's privately recorded container may be removed.
            if cidfile.exists():
                cid = cidfile.read_text().strip()
                require(len(cid) == 64 and all(char in "0123456789abcdef" for char in cid),
                        "invalid owned compiler container id")
                _, existing = self.runner.command("check owned compiler container", ["/usr/bin/docker", "ps",
                    "--all", "--quiet", "--no-trunc", "--filter", f"id={cid}"], guard=False)
                if existing.strip():
                    require(existing.strip() == cid, "compiler container identity mismatch")
                    self.runner.command("remove owned ephemeral compiler container",
                                        ["/usr/bin/docker", "rm", "--force", cid], guard=False)


def build(runner, inputs, node, readelf, scanner, cache, local_inputs, compiler_image=False):
    work = runner.work
    runner.report["inputs"] = inputs
    runner.report["builder_sha256"] = sha256(Path(__file__))
    runner.report["inputs_sha256"] = sha256(INPUTS)
    _, revision = runner.command("OMERTA source commit", ["/usr/bin/git", "rev-parse", "HEAD"])
    runner.report["omerta_commit"] = revision.strip()
    _, status = runner.command("working tree state", ["/usr/bin/git", "status", "--porcelain=v1"])
    runner.report["worktree_clean"] = not bool(status.strip())
    roots = {}
    image = inputs["official_compiler_image"]["reference"] if compiler_image else None
    if image:
        runner.report["compiler_transport"] = "digest-pinned official OCI image; not archive verification"
        runner.command("pull pinned official compiler", ["/usr/bin/docker", "pull", "--platform", "linux/amd64", image], timeout=300)
        _, volumes = runner.command("compiler image has no implicit volumes", ["/usr/bin/docker", "image", "inspect",
                                   "--format", "{{json .Config.Volumes}}", image])
        require(json.loads(volumes) in (None, {}), "compiler image declares implicit volumes")
        runner.command("compiler image identity", ["/usr/bin/docker", "image", "inspect", "--format", "{{.Id}}", image])
    for name in (("source",) if image else ("compiler", "source")):
        spec, archive = inputs[name], work / f"{name}.tar.gz"
        local = local_inputs.get(name)
        runner.report[f"{name}_transport"] = "operator-provided pinned archive" if local else "HTTPS"
        size = runner.step(f"acquire and verify {name}", lambda: (
            copy_verified_input(local, spec, archive, runner.guard) if local
            else download(spec, archive, runner.guard)))
        runner.report[f"{name}_download_bytes"] = size
        roots[name] = runner.step(f"extract verified {name}", lambda: extract_verified(
            archive, spec, work / name, runner.guard))
    source = roots["source"]
    go = GoCompiler(runner, inputs, image=image)
    _, version = go.run("compiler version", ["version"])
    require(version.strip() == f"go version {inputs['compiler_version']} linux/amd64", "unexpected compiler")
    require((source / "version.txt").read_text().strip() == inputs["esbuild_version"], "source version mismatch")
    before = tree_hashes(source)
    version_file = source / "cmd/esbuild/version.go"
    previous = version_file.read_text() if version_file.exists() else ""
    runner.command("generate source version", [node, "scripts/esbuild.js", "--update-version-go"], cwd=source)
    runner.report["generated_version_diff"] = "".join(difflib.unified_diff(
        previous.splitlines(keepends=True), version_file.read_text().splitlines(keepends=True),
        fromfile="original/cmd/esbuild/version.go", tofile="generated/cmd/esbuild/version.go"))
    baseline = tree_hashes(source)
    require({key: value for key, value in before.items() if key != "cmd/esbuild/version.go"}
            == {key: value for key, value in baseline.items() if key != "cmd/esbuild/version.go"},
            "version generator changed other source files")
    go.run("download checksum-verified modules", ["mod", "download"], cwd=source, network=True)
    go.run("module checksum verification", ["mod", "verify"], cwd=source)
    go.run("module inventory", ["list", "-m", "-json", "all"], cwd=source)
    binaries = []
    for index in (1, 2):
        output = work / f"build-{index}"
        output.mkdir(mode=0o700)
        binary = output / "esbuild"
        go.run(f"build {index}", ["build", "-p=1", "-mod=readonly", "-trimpath",
                                        "-buildvcs=false", "-o", str(binary), "./cmd/esbuild"],
                       cwd=source, timeout=900)
        binary.chmod(0o555)
        binaries.append(binary)
    digest = sha256(binaries[0])
    require(sha256(binaries[1]) == digest, "repeat-build digest mismatch")
    require_binary_path(binaries[0], digest)
    _, sections = runner.command("ELF section inventory", [readelf, "-SW", str(binaries[0])])
    require(".go.buildinfo" in sections, "Go build-info section missing")
    _, metadata = go.run("Go binary metadata", ["version", "-m", str(binaries[0])])
    verify_go_metadata(metadata, inputs)
    _, application_version = runner.command("esbuild version", [str(binaries[0]), "--version"])
    require(application_version.strip() == inputs["esbuild_version"], "binary version mismatch")
    go.run("upstream Go tests", ["test", "-p=1", "-parallel=1", "-mod=readonly",
                                       "./cmd/...", "./internal/...", "./pkg/..."], cwd=source, timeout=900)
    require(tree_hashes(source) == baseline, "build/test changed pinned source or module locks")
    runner.report["binary"] = {"path": str(binaries[0]), "sha256": digest, "metadata": metadata,
                               "repeat_build_equal": True}
    runner.report["scanner_sha256"] = sha256(scanner)
    _, scanner_version = runner.command("scanner version", [scanner, "--version"])
    require(f"Version: {inputs['trivy_version']}" in scanner_version, "scanner version mismatch")
    db = cache / "db/trivy.db"
    db_metadata = json.loads((cache / "db/metadata.json").read_text())
    updated = datetime.fromisoformat(db_metadata["UpdatedAt"].replace("Z", "+00:00"))
    require(0 <= (datetime.now(timezone.utc) - updated).total_seconds() <= 86400,
            "scanner database is not fresh within 24 hours")
    runner.report["scanner_database"] = {"metadata": db_metadata, "sha256": sha256(db)}
    common = [scanner, "rootfs", "--scanners", "vuln", "--cache-dir", str(cache),
              "--cache-backend", "memory", "--skip-db-update", "--skip-java-db-update",
              "--offline-scan", "--parallel", "1", "--timeout", "2m"]
    code, raw = runner.command("binary vulnerability scan", [*common, "--list-all-pkgs", "--exit-code", "1",
                                                          "--format", "json", str(binaries[0])], check=False)
    payload = json.loads(raw)
    runner.step("positive Go scan coverage", lambda: verify_scan_coverage(payload, inputs))
    _, sbom = runner.command("binary CycloneDX SBOM", [*common, "--format", "cyclonedx", str(binaries[0])])
    require(json.loads(sbom).get("bomFormat") == "CycloneDX", "invalid SBOM")
    require(code == 0 and not any(result.get("Vulnerabilities") for result in payload.get("Results", [])),
            "binary vulnerability findings or scanner failure")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="explicitly download/build/test/scan")
    parser.add_argument("--work-dir", type=Path, required=True, help="new absolute private directory outside repo")
    parser.add_argument("--trivy", type=Path, required=True)
    parser.add_argument("--trivy-cache", type=Path, required=True, help="existing fresh DB; never updated here")
    parser.add_argument("--compiler-archive", type=Path, help="optional local archive; same pinned SHA256 required")
    parser.add_argument("--source-archive", type=Path, help="optional local archive; same pinned SHA256 required")
    parser.add_argument("--compiler-image", action="store_true", help="explicitly use the pinned official Go image instead of the compiler archive")
    args = parser.parse_args(argv)
    require(args.run, "--run is required; no operations performed")
    require(not (args.compiler_image and args.compiler_archive), "choose only one compiler transport")
    require(platform.system() == "Linux" and platform.machine() == "x86_64", "Linux x64 host required")
    require(args.work_dir.is_absolute() and args.work_dir == args.work_dir.resolve()
            and not args.work_dir.is_relative_to(ROOT) and not args.work_dir.exists(), "new external absolute work directory required")
    require(args.trivy.is_absolute() and args.trivy.is_file() and args.trivy_cache.is_absolute(),
            "absolute scanner/cache paths required")
    node, readelf = shutil.which("node"), shutil.which("readelf")
    require(node and readelf, "Node and readelf are required")
    inputs = json.loads(INPUTS.read_text())
    guard = ResourceGuard(args.work_dir.parent)
    guard.check()
    args.work_dir.mkdir(mode=0o700)
    os.umask(0o077)
    runner = Runner(args.work_dir, {}, guard)
    try:
        runner.environment = build_environment(args.work_dir, args.work_dir / "compiler/go")
        runner.report["build_environment"] = runner.environment
        build(runner, inputs, node, readelf, str(args.trivy), args.trivy_cache,
              {"compiler": args.compiler_archive, "source": args.source_archive}, args.compiler_image)
        runner.report["status"] = "passed"
    except BuildBlocked as exc:
        runner.report["status"] = "blocked"
        runner.report["error"] = str(exc)
    except (Exception, KeyboardInterrupt) as exc:
        runner.report["status"] = "failed"
        runner.report["error_type"] = type(exc).__name__
        if isinstance(exc, BuildFailure):
            runner.report["error"] = str(exc)
    finally:
        runner.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        runner.save()
    print(f"Stage A {runner.report['status']}; receipt: {args.work_dir / 'receipt.json'}")
    return 0 if runner.report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
