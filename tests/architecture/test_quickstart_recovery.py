from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from scripts import validate_quickstart_recovery as recovery
from scripts.validate_quickstart_environment_parity import AcceptanceFailure, VOLUMES
from tests.architecture.test_quickstart_environment_parity import GROUPS, fixture


class RecoveryTests(unittest.TestCase):
    def test_fresh_only_cli_selects_exact_images_and_preserves_default_source_guard(self):
        for fresh_only, source_present, expected_exit in ((True, False, 0), (False, False, 1), (False, True, 2)):
            with self.subTest(fresh_only=fresh_only, source_present=source_present), TemporaryDirectory() as temporary:
                root = Path(temporary)
                runner = Mock()
                runner.report = {}
                runner.minimum_ram = 2 * 1024 * 1024

                def run(label, *args, **kwargs):
                    if label == "canonical render":
                        return 0, json.dumps(fixture()).encode(), b""
                    if label == "volume inventory":
                        volumes = [f"{recovery.parity.PROJECT}_{name}" for name in VOLUMES] if source_present else []
                        return 0, "\n".join(volumes).encode(), b""
                    return 0, b"", b""

                runner.run.side_effect = run
                argv = ["--env-file", "unused.env", "--console-image", "console:new", "--control-image", "control:new",
                        "--runtime-image", "runtime:new", "--gateway-image", "gateway:new", "--run",
                        "--output", str(root / "artifacts/result.json")]
                if fresh_only:
                    argv.append("--fresh-only")
                with patch.object(recovery, "ROOT", root), patch.object(recovery.parity, "Runner", return_value=runner), \
                     patch.object(recovery, "load_alias_contract", return_value=(GROUPS, ())), \
                     patch.object(recovery, "parse_environment_file", return_value={}), \
                     patch.object(recovery.shutil, "disk_usage", return_value=Mock(free=8 * 1024**3)), \
                     patch.object(recovery, "run_project", return_value={"status": "passed"}) as live:
                    self.assertEqual(recovery.main(argv), expected_exit)
                self.assertEqual(live.call_count, 0 if expected_exit == 1 else (1 if fresh_only else 2))
                for call in live.call_args_list:
                    config = call.args[1]
                    self.assertEqual(config["services"]["runtime"]["image"], "runtime:new")
                    self.assertEqual(config["services"]["gateway"]["image"], "gateway:new")
                if fresh_only:
                    self.assertEqual(runner.report["scope"], "fresh-install/restart only")
                    self.assertEqual(runner.report["skipped"][0],
                        "existing-data reapply, encrypted backup/restore and historical upgrade are outside this invocation")

    def test_fresh_storage_and_network_cannot_alias_existing_project(self):
        source = fixture()
        original = copy.deepcopy(source)
        config = recovery.recovery_config(source, GROUPS, recovery.FRESH_PROJECT, "console:test", "control:test")
        self.assertEqual(source, original)
        self.assertEqual(set(config["volumes"]), set(VOLUMES))
        for name in VOLUMES:
            self.assertEqual(config["volumes"][name], {"name": f"omerta-p3-fresh_{name}"})
        self.assertEqual(config["networks"]["default"]["name"], "omerta-p3-fresh-net")
        self.assertEqual(config["secrets"], original["secrets"])

    def test_arbitrary_or_other_worker_project_is_rejected(self):
        for project in ("compose", "production", "omerta-p3-fresh_bad", "--privileged"):
            with self.subTest(project=project), self.assertRaises(AcceptanceFailure):
                recovery.recovery_config(fixture(), GROUPS, project, "console:test", "control:test")

    def test_existing_data_keeps_its_volume_identity(self):
        config = recovery.recovery_config(fixture(), GROUPS, recovery.parity.PROJECT,
                                          "console:test", "control:test")
        self.assertEqual(config["volumes"]["runtime-state"]["name"], "omerta-m4-validation_runtime-state")

    def test_existing_fresh_volume_is_never_reused_as_fresh_acceptance(self):
        recovery.assert_fresh_absent(["compose_postgres-data", "omerta-m4-validation_postgres-data"])
        with self.assertRaises(AcceptanceFailure):
            recovery.assert_fresh_absent(["omerta-p3-fresh_runtime-state"])

    def test_failed_fresh_attempt_can_use_distinct_new_project_without_deletion(self):
        config = recovery.recovery_config(fixture(), GROUPS, "omerta-p3-fresh-retry1", "console:test", "control:test")
        recovery.assert_fresh_absent(["omerta-p3-fresh_runtime-state"], "omerta-p3-fresh-retry1")
        self.assertEqual(config["volumes"]["postgres-data"]["name"], "omerta-p3-fresh-retry1_postgres-data")

    def test_lease_rejection_matches_public_status_not_internal_error_detail(self):
        public = "runtime execution lease is missing, expired, or fenced"
        recovery.assert_fenced({"code": "FAILED_PRECONDITION", "detail": public})
        for detail in ("lease has expired", "invalid signature", "", "stale"):
            with self.subTest(detail=detail), self.assertRaises(AcceptanceFailure):
                recovery.assert_fenced({"code": "FAILED_PRECONDITION", "detail": detail})
        with self.assertRaises(AcceptanceFailure):
            recovery.assert_fenced({"code": "OK", "detail": public})

    def test_stale_evidence_also_requires_matching_persisted_unexpired_claim(self):
        lease = {"tenant_id": "tenant", "task_id": "task", "lease_generation": 7, "lease_expires_at_ms": 20000}
        payload = struct.pack(">I", 6) + b"tenant" + struct.pack(">I", 4) + b"task"
        key = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        state = {"version": 1, "records": {key: {"generation": 7, "expires_at_ms": 20000}}}
        recovery.assert_persisted_claim(state, lease, 10000)
        with self.assertRaises(AcceptanceFailure):
            recovery.assert_persisted_claim(state, lease, 20000)
        with self.assertRaises(AcceptanceFailure):
            recovery.assert_persisted_claim({"version": 1, "records": {}}, lease, 10000)
        with self.assertRaises(AcceptanceFailure):
            recovery.assert_persisted_claim(state, {**lease, "lease_generation": 8}, 10000)

    def test_restart_replay_is_explicitly_fail_closed_not_result_recovery(self):
        result = {"taskId": "task", "status": "ERROR", "error": {"code": "RUNTIME_RESULT_REPLAY_UNAVAILABLE"}}
        recovery.assert_restart_replay(result, "task")
        for changed in ({"taskId": "other"}, {"status": "OK"}, {"error": {"code": "UNAVAILABLE"}}):
            with self.assertRaises(AcceptanceFailure):
                recovery.assert_restart_replay({**result, **changed}, "task")

    def test_container_fragments_are_valid_python_before_live_acceptance(self):
        for code in (recovery.LEASE_PROBE, recovery.STORE_PROBE, recovery.DISPATCH_COUNT, recovery.CONTROL_REPLAY):
            ast.parse(code)

    def test_foreign_or_active_volume_consumer_prevents_start(self):
        import json
        for project, active in (("compose", False), (recovery.parity.PROJECT, True)):
            runner = Mock()
            runner.run.side_effect = [(0, b"container-id", b""), (0, json.dumps([{
                "Config": {"Labels": {"com.docker.compose.project": project}},
                "State": {"Running": active}}]).encode(), b"")]
            with self.subTest(project=project, active=active), self.assertRaises(AcceptanceFailure):
                recovery.volume_consumer_guard(runner, recovery.parity.PROJECT)


if __name__ == "__main__":
    unittest.main()
