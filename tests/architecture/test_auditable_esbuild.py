from __future__ import annotations

import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import build_auditable_esbuild as builder


class AuditableEsbuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.guard = Mock()
        self.inputs = json.loads(builder.INPUTS.read_text())

    def archive(self, members):
        archive = self.root / "input.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            for name, kind, content in members:
                item = tarfile.TarInfo(name)
                item.type = kind
                if kind == tarfile.REGTYPE:
                    item.size = len(content)
                    handle.addfile(item, io.BytesIO(content))
                else:
                    item.linkname = content.decode()
                    handle.addfile(item)
        return archive, {"sha256": builder.sha256(archive), "root": "fixture",
                         "maximum_download_bytes": 1024 * 1024,
                         "maximum_expanded_bytes": 100}

    def metadata(self):
        return (f"/private/esbuild: {self.inputs['compiler_version']}\n"
                "\tpath\tgithub.com/evanw/esbuild/cmd/esbuild\n"
                "\tmod\tgithub.com/evanw/esbuild\t(devel)\n"
                "\tdep\tgolang.org/x/sys\tv0.0.0-fixture\th1:fixture\n"
                + "".join(f"\tbuild\t{key}={value}\n" for key, value in self.inputs["target"].items()))

    def runner(self):
        guard = Mock(minimum_ram_bytes=4 * builder.GIB, minimum_disk_bytes=4 * builder.GIB,
                     minimum_scratch_bytes=None)
        return builder.Runner(self.root, {"PATH": "/usr/bin:/bin"}, guard)

    def test_input_manifest_matches_reviewed_plan(self):
        self.assertEqual(self.inputs["schema_version"], 1)
        self.assertEqual(self.inputs["esbuild_version"], "0.28.2")
        for name in ("source", "compiler"):
            self.assertTrue(self.inputs[name]["url"].startswith("https://"))
            self.assertRegex(self.inputs[name]["sha256"], r"^[0-9a-f]{64}$")
        plan = (builder.ROOT / "docs/capo/p4-esbuild-provenance-plan.md").read_text()
        for value in (self.inputs["source_commit"], self.inputs["source"]["sha256"],
                      self.inputs["compiler"]["sha256"]):
            self.assertIn(value, plan)

    def test_hash_mismatch_rejected_before_extraction(self):
        archive, spec = self.archive([("fixture/input", tarfile.REGTYPE, b"ok")])
        spec["sha256"] = "0" * 64
        with self.assertRaisesRegex(builder.BuildFailure, "SHA256"):
            builder.extract_verified(archive, spec, self.root / "output", self.guard)
        self.assertFalse((self.root / "output").exists())

    def test_local_archive_requires_same_pin_before_copy(self):
        archive, spec = self.archive([("fixture/input", tarfile.REGTYPE, b"ok")])
        output = self.root / "copy.tar.gz"
        self.assertEqual(builder.copy_verified_input(archive, spec, output, self.guard), archive.stat().st_size)
        self.assertEqual(builder.sha256(output), spec["sha256"])
        spec["sha256"] = "0" * 64
        with self.assertRaisesRegex(builder.BuildFailure, "SHA256"):
            builder.copy_verified_input(archive, spec, self.root / "invalid.tar.gz", self.guard)
        self.assertFalse((self.root / "invalid.tar.gz").exists())

    def test_network_404_is_blocked_without_extraction(self):
        import urllib.error

        spec = {"url": "https://go.dev/fixture", "sha256": "0" * 64}
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(spec["url"], 404, "Not Found", {}, None)
        with patch.object(builder.urllib.request, "build_opener", return_value=opener), \
                self.assertRaisesRegex(builder.BuildBlocked, "HTTP 404"):
            builder.download(spec, self.root / "missing.tar.gz", self.guard)
        self.assertFalse((self.root / "missing.tar.gz").exists())

    def test_regular_files_extract_with_private_permissions(self):
        archive, spec = self.archive([("fixture/input", tarfile.REGTYPE, b"ok")])
        output = builder.extract_verified(archive, spec, self.root / "output", self.guard)
        self.assertEqual((output / "input").read_bytes(), b"ok")
        self.assertEqual((output / "input").stat().st_mode & 0o777, 0o600)

    def test_archive_paths_links_and_special_files_are_rejected(self):
        for name, kind in (("fixture/../../escape", tarfile.REGTYPE),
                           ("/fixture/absolute", tarfile.REGTYPE),
                           ("other/file", tarfile.REGTYPE),
                           ("fixture/symlink", tarfile.SYMTYPE),
                           ("fixture/hardlink", tarfile.LNKTYPE),
                           ("fixture/fifo", tarfile.FIFOTYPE)):
            with self.subTest(name=name):
                archive, spec = self.archive([(name, kind, b"../../escape" if kind == tarfile.SYMTYPE else b"target")])
                with self.assertRaises(builder.BuildFailure):
                    builder.extract_verified(archive, spec, self.root / f"out-{len(name)}-{kind!r}", self.guard)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_internal_dangling_symlink_is_preserved_without_writing_through_it(self):
        archive, spec = self.archive([("fixture/browser/fixture-link", tarfile.SYMTYPE, b"../generated/fixture.wasm")])
        output = builder.extract_verified(archive, spec, self.root / "output", self.guard)
        self.assertTrue((output / "browser/fixture-link").is_symlink())
        self.assertEqual(os.readlink(output / "browser/fixture-link"), "../generated/fixture.wasm")
        self.assertFalse((output / "generated/fixture.wasm").exists())

    def test_archive_does_not_write_files_through_a_deferred_link(self):
        archive, spec = self.archive([("fixture/link", tarfile.SYMTYPE, b"inside"),
                                      ("fixture/link/child", tarfile.REGTYPE, b"data")])
        with self.assertRaises(FileExistsError):
            builder.extract_verified(archive, spec, self.root / "output", self.guard)
        self.assertFalse((self.root / "output/fixture/inside/child").exists())

    def test_duplicate_archive_members_are_rejected(self):
        archive, spec = self.archive([("fixture/input", tarfile.REGTYPE, b"one"),
                                      ("fixture/input", tarfile.REGTYPE, b"two")])
        with self.assertRaisesRegex(builder.BuildFailure, "duplicate"):
            builder.extract_verified(archive, spec, self.root / "output", self.guard)

    def test_expanded_archive_size_is_bounded(self):
        archive, spec = self.archive([("fixture/input", tarfile.REGTYPE, b"too large")])
        spec["maximum_expanded_bytes"] = 1
        with self.assertRaisesRegex(builder.BuildFailure, "size bound"):
            builder.extract_verified(archive, spec, self.root / "output", self.guard)

    def test_inherited_go_override_rejected(self):
        for key in ("GOFLAGS", "GOROOT", "GOWORK", "GONOSUMDB", "GOPROXY", "GOSUMDB", "GOENV"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "fixture-override"}), \
                    self.assertRaisesRegex(builder.BuildFailure, "inherited"):
                builder.build_environment(self.root, self.root / "go")

    def test_environment_is_allowlisted_and_private(self):
        with patch.dict(os.environ, {"UNRELATED_PRIVATE_VALUE": "fixture-only"}, clear=True):
            env = builder.build_environment(self.root, self.root / "go")
        self.assertNotIn("UNRELATED_PRIVATE_VALUE", env)
        self.assertEqual(env["GOSUMDB"], "sum.golang.org")
        self.assertEqual(env["GOTOOLCHAIN"], "local")
        self.assertEqual(env["CGO_ENABLED"], "0")
        for key in ("GOCACHE", "GOMODCACHE", "GOTMPDIR", "GOPATH", "HOME"):
            self.assertTrue(Path(env[key]).is_relative_to(self.root))

    def test_writable_or_relative_binary_rejected(self):
        binary = self.root / "esbuild"
        binary.write_bytes(b"not-executed")
        binary.chmod(0o755)
        with self.assertRaisesRegex(builder.BuildFailure, "non-writable"):
            builder.require_binary_path(binary, builder.sha256(binary))
        with self.assertRaisesRegex(builder.BuildFailure, "absolute"):
            builder.require_binary_path(Path("esbuild"), "0" * 64)

    def test_symlink_or_changed_binary_rejected(self):
        binary = self.root / "esbuild"
        binary.write_bytes(b"not-executed")
        binary.chmod(0o555)
        link = self.root / "alias"
        link.symlink_to(binary)
        with self.assertRaisesRegex(builder.BuildFailure, "non-symlink"):
            builder.require_binary_path(link, builder.sha256(binary))
        with self.assertRaisesRegex(builder.BuildFailure, "SHA256"):
            builder.require_binary_path(binary, "0" * 64)
        builder.require_binary_path(binary, builder.sha256(binary))

    def test_metadata_requires_compiler_dependencies_and_target(self):
        builder.verify_go_metadata(self.metadata(), self.inputs)
        for bad in ("", self.metadata().replace("go1.27.4", "go1.23.12"),
                    self.metadata().replace("GOARCH=amd64", "GOARCH=arm64"),
                    self.metadata().replace("golang.org/x/sys", "missing-module")):
            with self.subTest(metadata=bad), self.assertRaises(builder.BuildFailure):
                builder.verify_go_metadata(bad, self.inputs)

    def test_scan_zero_without_correct_go_coverage_is_rejected(self):
        for payload in ({}, {"Results": []}, {"Results": [{"Type": "npm"}]},
                        {"Results": [{"Type": "gobinary", "Packages": [{"Name": "stdlib", "Version": "1.23.12"}]}]}):
            with self.subTest(payload=payload), self.assertRaisesRegex(builder.BuildFailure, "stdlib"):
                builder.verify_scan_coverage(payload, self.inputs)
        builder.verify_scan_coverage({"Results": [{"Type": "gobinary", "Packages": [
            {"Name": "stdlib", "Version": "1.27.4"}]}]}, self.inputs)
        builder.verify_scan_coverage({"Results": [{"Type": "gobinary", "Packages": [
            {"Name": "stdlib", "Version": "v1.27.4"}]}]}, self.inputs)
        with self.assertRaises(builder.BuildFailure):
            builder.verify_scan_coverage({"Results": [{"Type": "gobinary", "Packages": [
                {"Name": "stdlib", "Version": "v1.23.12"}]}]}, self.inputs)

    def test_resource_guards_fail_before_child_start(self):
        runner = self.runner()
        runner.guard.check.side_effect = builder.BuildBlocked("available disk below 3 GiB")
        with patch.object(builder.subprocess, "Popen") as start, self.assertRaises(builder.BuildBlocked):
            runner.command("resource guard", ["unused"])
        start.assert_not_called()
        self.assertEqual(runner.report["gates"][-1]["status"], "blocked")

    def test_guard_enforces_disk_and_memory_thresholds(self):
        guard = builder.ResourceGuard(self.root)
        for memory, disk in ((1048575, 4 * builder.GIB), (4194304, 3 * builder.GIB - 1)):
            with self.subTest(memory=memory, disk=disk), \
                    patch.object(Path, "read_text", return_value=f"MemAvailable: {memory} kB\n"), \
                    patch.object(builder.shutil, "disk_usage", return_value=Mock(free=disk)), \
                    self.assertRaises(builder.BuildBlocked):
                guard.check()

    def test_command_exit_failure_remains_failure(self):
        runner = self.runner()
        with self.assertRaises(builder.BuildFailure):
            runner.command("failed child", [sys.executable, "-c", "raise SystemExit(7)"])
        self.assertEqual(runner.report["gates"][-1]["exit_code"], 7)
        self.assertEqual(runner.report["gates"][-1]["status"], "failed")

    def test_timeout_exit_race_does_not_hide_failure(self):
        runner = self.runner()
        child = Mock(pid=12345, returncode=0)
        child.wait.side_effect = [subprocess.TimeoutExpired(["fixture"], 1), None]
        with patch.object(builder.subprocess, "Popen", return_value=child), \
                patch.object(builder.os, "killpg", side_effect=ProcessLookupError), \
                self.assertRaisesRegex(builder.BuildFailure, "timeout"):
            runner.command("fixture race", ["not-executed"], timeout=0)
        self.assertEqual(runner.report["gates"][-1]["status"], "failed")

    def test_signal_permission_errors_are_not_suppressed(self):
        with patch.object(builder.os, "killpg", side_effect=PermissionError), self.assertRaises(PermissionError):
            builder.signal_group(Mock(pid=12345), signal.SIGTERM)

    def test_missing_run_flag_is_side_effect_free(self):
        with self.assertRaisesRegex(builder.BuildFailure, "--run"), patch.object(builder, "build") as build:
            builder.main(["--work-dir", str(self.root / "new"), "--trivy", "/fixture/trivy",
                          "--trivy-cache", "/fixture/cache"])
        build.assert_not_called()
        self.assertFalse((self.root / "new").exists())

    def test_https_downgrade_is_rejected(self):
        with self.assertRaisesRegex(builder.BuildFailure, "non-HTTPS"):
            builder.HTTPSRedirects().redirect_request(None, None, 302, "", {}, "http://fixture.invalid")

    def test_official_image_commands_are_constrained_and_paths_are_relocated(self):
        image = self.inputs["official_compiler_image"]["reference"]
        command = builder.container_go_argv(self.root, {"HOME": str(self.root / "home")},
            image, self.root / "fixture.cid", ["build", "-o", str(self.root / "esbuild")], self.root, False)
        self.assertRegex(image, r"^docker.io/library/golang@sha256:[0-9a-f]{64}$")
        self.assertEqual(command[command.index("--workdir") + 1], "/work")
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertEqual(command[command.index("--user") + 1], f"{os.getuid()}:{os.getgid()}")
        self.assertIn("--read-only", command)
        self.assertIn("ALL", command)
        self.assertIn("no-new-privileges:true", command)
        self.assertIn("1024m", command)
        self.assertIn("HOME=/work/home", command)
        self.assertEqual(command[-1], "/work/esbuild")
        self.assertNotIn("--privileged", command)
        self.assertNotIn("--volume", command)

    def test_failed_image_command_cleans_up_only_its_owned_container(self):
        runner = Mock(work=self.root, environment={})
        cid = "a" * 64
        calls = []

        def command(label, argv, **kwargs):
            calls.append((label, argv))
            if "--cidfile" in argv:
                Path(argv[argv.index("--cidfile") + 1]).write_text(cid)
                raise builder.BuildBlocked("synthetic resource stop")
            return 0, cid + "\n"

        runner.command.side_effect = command
        compiler = builder.GoCompiler(runner, self.inputs,
                                      image=self.inputs["official_compiler_image"]["reference"])
        with self.assertRaises(builder.BuildBlocked):
            compiler.run("synthetic failed compiler", ["version"])
        self.assertEqual(calls[-1][1], ["/usr/bin/docker", "rm", "--force", cid])
        self.assertFalse(any("--volumes" in argv for _, argv in calls))

    def test_conflicting_compiler_inputs_are_rejected_before_side_effects(self):
        with self.assertRaisesRegex(builder.BuildFailure, "one compiler"):
            builder.main(["--run", "--work-dir", str(self.root / "new"), "--trivy", "/fixture/trivy",
                          "--trivy-cache", "/fixture/cache", "--compiler-image", "--compiler-archive", "/fixture/go.tgz"])
        self.assertFalse((self.root / "new").exists())

    def test_external_scratch_is_mapped_without_changing_mount_security(self):
        scratch = self.root / "ram-scratch"
        scratch.mkdir(mode=0o700)
        work = self.root / "work"
        work.mkdir(mode=0o700)
        with patch.dict(os.environ, {}, clear=True):
            env = builder.build_environment(work, work / "go", scratch)
        self.assertEqual(env["GOCACHE"], str(scratch / "go-cache"))
        command = builder.container_go_argv(work, env, "fixture-image", work / "fixture.cid",
                                            ["test"], work, False, scratch)
        self.assertIn(f"type=bind,src={scratch},dst=/scratch", command)
        self.assertIn("GOCACHE=/scratch/go-cache", command)
        self.assertIn("TMPDIR=/scratch/tmp", command)
        self.assertFalse(any("exec=" in part or "privileged" in part for part in command))

    def test_scratch_guard_does_not_relax_the_primary_disk_guard(self):
        guard = builder.ResourceGuard(self.root, self.root / "scratch")
        with patch.object(Path, "read_text", return_value="MemAvailable: 4194304 kB\n"), \
                patch.object(builder.shutil, "disk_usage", side_effect=[Mock(free=3 * builder.GIB - 1)]), \
                self.assertRaisesRegex(builder.BuildBlocked, "3 GiB"):
            guard.check()
        with patch.object(Path, "read_text", return_value="MemAvailable: 4194304 kB\n"), \
                patch.object(builder.shutil, "disk_usage", side_effect=[Mock(free=4 * builder.GIB), Mock(free=1)]), \
                self.assertRaisesRegex(builder.BuildBlocked, "scratch"):
            guard.check()

    def test_database_nanosecond_timestamp_uses_standard_iso_parser(self):
        actual = builder.parse_metadata_time("2026-11-10T19:01:23.081219346Z")
        self.assertEqual(actual.microsecond, 81219)
        self.assertEqual(actual.isoformat(), "2026-11-10T19:01:23.081219+00:00")
        self.assertEqual(actual, builder.parse_metadata_time("2026-11-10T19:01:23.081219346+00:00"))
        for invalid in ("not-a-date", "2026-11-10T19:01:23", "2026-99-10T19:01:23Z"):
            with self.subTest(invalid=invalid), self.assertRaises(builder.BuildFailure):
                builder.parse_metadata_time(invalid)

    def test_audit_logs_preserve_original_build_receipt(self):
        original = self.root / "receipt.json"
        original.write_text("original-build-receipt\n")
        runner = self.runner()
        audit = builder.Runner(self.root, runner.environment, runner.guard, self.root / "audit")
        audit.command("audit child", [sys.executable, "-c", "print('audit-only')"])
        self.assertEqual(original.read_text(), "original-build-receipt\n")
        self.assertTrue((self.root / "audit/receipt.json").exists())
        self.assertFalse((self.root / "01.stdout").exists())
