from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import quickstart_encrypted_recovery as encrypted
from scripts.validate_quickstart_environment_parity import AcceptanceFailure, Runner, VOLUMES


def manifest():
    names = [name + ".tar.gz.gpg" for name in VOLUMES]
    names += ["compose.json.gpg", "environment.gpg", "runtime-lease-key.gpg"]
    return {"format_version": 1, "source_project": encrypted.parity.PROJECT,
            "files": {name: {"bytes": 100, "sha256": "f" * 64} for name in names},
            "volume_inventories": dict.fromkeys(VOLUMES, {})}


class EncryptedRecoveryTests(unittest.TestCase):
    def test_never_write_sensitive_files_inside_any_git_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").write_text("gitdir: fixture", encoding="ascii")
            with self.assertRaises(AcceptanceFailure):
                encrypted.outside_git(root / "private")
        with self.assertRaises(AcceptanceFailure):
            encrypted.outside_git(encrypted.ROOT / ".secrets-out")

    def test_secure_files_are_exclusive_owned_and_not_world_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = encrypted.private_directory(Path(directory) / "private")
            path = root / "fixture"
            encrypted.secure_write(path, b"synthetic-fixture")
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            encrypted.require_private(path)
            with self.assertRaises(FileExistsError):
                encrypted.secure_write(path, b"replacement")
            path.chmod(0o644)
            with self.assertRaises(AcceptanceFailure):
                encrypted.require_private(path)

    def test_symlink_key_files_and_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "file"
            encrypted.secure_write(path, b"synthetic-fixture")
            link = root / "link"
            link.symlink_to(path)
            with self.assertRaises(AcceptanceFailure):
                encrypted.require_private(link)
            with self.assertRaises(AcceptanceFailure):
                encrypted.outside_git(link)

    def test_unreadable_path_fails_closed_with_a_sanitized_error(self):
        with patch.object(Path, "exists", side_effect=PermissionError("synthetic-private-detail")):
            with self.assertRaises(AcceptanceFailure) as result:
                encrypted.outside_git(Path("/tmp/isolated-recovery-test"))
        self.assertNotIn("synthetic-private-detail", str(result.exception))

    def test_project_cannot_select_source_or_other_worker(self):
        encrypted.valid_restore_project("omerta-p3-restore-20261102")
        for name in ("compose", encrypted.parity.PROJECT, "omerta-p3-restore-", "omerta-p3-restore-a_1"):
            with self.subTest(name=name), self.assertRaises(AcceptanceFailure):
                encrypted.valid_restore_project(name)

    def test_manifest_rejects_missing_extra_and_traversal_entries(self):
        encrypted.verify_manifest_shape(manifest())
        for name in ("../outside", "/absolute", "unlisted.gpg"):
            source = manifest()
            source["files"][name] = {"bytes": 100, "sha256": "f" * 64}
            with self.assertRaises(AcceptanceFailure):
                encrypted.verify_manifest_shape(source)
        source = manifest()
        source["files"].pop("runtime-lease-key.gpg")
        with self.assertRaises(AcceptanceFailure):
            encrypted.verify_manifest_shape(source)

    def test_restored_endpoints_must_resolve_inside_the_selected_compose_network(self):
        config = {"services": {name: {"environment": {"DATABASE_URL": "postgresql://user:fixture@postgres/db"}}
                               for name in (*encrypted.parity.APPLICATIONS, "install")}}
        encrypted.local_restore_endpoints(config)
        config["services"]["control"]["environment"]["DATABASE_URL"] = "postgresql://user:fixture@external.invalid/db"
        with self.assertRaises(AcceptanceFailure):
            encrypted.local_restore_endpoints(config)
        config["services"]["control"]["environment"].pop("DATABASE_URL")
        config["services"]["control"]["environment"]["OMERTA_RUNTIME_NODES_JSON"] = "[]"
        with self.assertRaises(AcceptanceFailure):
            encrypted.local_restore_endpoints(config)

    def test_success_requires_pinned_signature_and_encryption_integrity_status(self):
        fingerprint = "F" * 40
        raw = (f"[GNUPG:] VALIDSIG {fingerprint} remaining-fields\n"
               "[GNUPG:] DECRYPTION_OKAY\n[GNUPG:] GOODMDC\n").encode()
        encrypted.status_signature(raw, fingerprint, decrypted=True)
        for changed in (raw.replace(b"GOODMDC", b"BADMDC"), raw.replace(b"F" * 40, b"A" * 40),
                        raw.replace(b"DECRYPTION_OKAY", b"DECRYPTION_FAILED")):
            with self.assertRaises(AcceptanceFailure):
                encrypted.status_signature(changed, fingerprint, decrypted=True)

    def test_archive_rejects_traversal_symlinks_special_and_setuid_files(self):
        for name, kind, mode in (("./fixture", tarfile.REGTYPE, 0o600),
                                  ("../escape", tarfile.REGTYPE, 0o600),
                                  ("/absolute", tarfile.REGTYPE, 0o600),
                                  ("link", tarfile.SYMTYPE, 0o600),
                                  ("hardlink", tarfile.LNKTYPE, 0o600),
                                  ("fifo", tarfile.FIFOTYPE, 0o600),
                                  ("setuid", tarfile.REGTYPE, 0o4600)):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w:gz") as archive:
                member = tarfile.TarInfo(name)
                member.type, member.mode = kind, mode
                archive.addfile(member, io.BytesIO())
            with self.subTest(name=name), patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(data.getvalue()))):
                if name == "./fixture":
                    exec(encrypted.ARCHIVE_CHECK, {})
                else:
                    with self.assertRaises(AssertionError):
                        exec(encrypted.ARCHIVE_CHECK, {})

    def test_pipeline_streams_without_recording_payload_and_rejects_child_failure(self):
        sentinel = "synthetic-private-payload"
        with tempfile.TemporaryDirectory() as directory:
            runner = Runner()
            output = Path(directory) / "synthetic-output"
            producer = [sys.executable, "-c", "import sys; sys.stdout.write('x'*2097152)"]
            consumer = [sys.executable, "-c", "import shutil,sys; shutil.copyfileobj(sys.stdin.buffer,sys.stdout.buffer)"]
            encrypted.pipeline(runner, "synthetic stream", producer, consumer, output=output)
            self.assertEqual(output.stat().st_size, 2097152)
            bad = [sys.executable, "-c", "import sys; sys.stderr.write(sys.stdin.read()); sys.exit(7)"]
            with patch.dict(os.environ, {"OMERTA_TEST_PRIVATE_STREAM": sentinel}), self.assertRaises(AcceptanceFailure):
                encrypted.pipeline(runner, "synthetic failure", [sys.executable, "-c",
                    'import os,sys; sys.stdout.write(os.environ["OMERTA_TEST_PRIVATE_STREAM"])'], bad)
            self.assertNotIn(sentinel, json.dumps(runner.report))
            self.assertIn(7, runner.report["gates"][-1]["exit_codes"])

    def test_large_archive_files_are_explicitly_consumed_in_bounded_chunks(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as archive:
            member = tarfile.TarInfo("large-fixture")
            member.size = 3 * 1024 * 1024
            archive.addfile(member, io.BytesIO(b"x" * member.size))
        original = tarfile.TarFile.extractfile
        sizes = []

        def checked_extract(archive, member):
            handle = original(archive, member)

            class Reader:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    handle.close()

                def read(self, size):
                    self_test.assertLessEqual(size, 1024 * 1024)
                    sizes.append(size)
                    return handle.read(size)

            return Reader()

        self_test = self
        with patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(data.getvalue()))), \
                patch.object(tarfile.TarFile, "extractfile", checked_extract):
            exec(encrypted.ARCHIVE_CHECK, {})
        self.assertGreaterEqual(len(sizes), 4)

    def test_pipeline_timeout_terminates_and_reaps_both_children(self):
        runner = Runner()
        sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
        with self.assertRaises(AcceptanceFailure):
            encrypted.pipeline(runner, "synthetic timeout", sleeper, sleeper, timeout=0.01)
        self.assertTrue(all(code is not None and code != 0 for code in runner.report["gates"][-1]["exit_codes"]))

    def test_opt_in_required_before_key_generation_or_docker_commands(self):
        with patch.object(encrypted, "Crypto") as crypto, self.assertRaises(AcceptanceFailure):
            encrypted.main(["--env-file", "fixture.env", "--key-dir", "/tmp/keys", "--backup-dir", "/tmp/backup",
                            "--restore-project", "omerta-p3-restore-test", "--output", "artifacts/test.json", "--create-key"])
        crypto.assert_not_called()

    def test_second_restore_exports_do_not_replace_first_restore_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = []
            for project in ("omerta-p3-restore-first", "omerta-p3-restore-second"):
                args = SimpleNamespace(backup_dir=root, restore_project=project)
                with patch.object(encrypted, "pipeline", side_effect=RuntimeError("stop-before-I/O")) as pipe:
                    with self.assertRaisesRegex(RuntimeError, "stop-before-I/O"):
                        encrypted.live_restore(Mock(), Mock(), args, None, {}, b"{}")
                output = pipe.call_args.kwargs["output"]
                self.assertEqual(output.parent.name, "exports-" + project)
                encrypted.secure_write(output, b"synthetic-ciphertext")
                outputs.append(output)
            self.assertNotEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[0].read_bytes(), b"synthetic-ciphertext")
            with self.assertRaises(FileExistsError):
                encrypted.private_directory(outputs[0].parent)

    def test_container_probes_are_valid_python_and_originals_are_read_only(self):
        ast.parse(encrypted.INVENTORY)
        ast.parse(encrypted.ARCHIVE_CHECK)
        command = encrypted.container_tool("fixture:image", "source")
        self.assertIn("type=volume,src=source,dst=/source,readonly", command)
        self.assertNotIn("--privileged", command)
        self.assertNotIn("CHOWN", command)


if __name__ == "__main__":
    unittest.main()
