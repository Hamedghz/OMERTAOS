from __future__ import annotations

import copy
import json
import sys
import unittest
from unittest.mock import patch

from scripts.validate_environment_aliases import AliasGroup
from scripts import validate_quickstart_environment_parity as parity


def fixture():
    services = {
        name: {"environment": {"OMERTA_DOCKER": "1", "OMERTA_GATEWAY_URL": "http://gateway:8080"},
               "image": "fixture-image", "build": {"context": "."}}
        for name in (*parity.APPLICATIONS, "install")
    }
    services["console"]["environment"]["GATEWAY_URL"] = "http://masked.invalid"
    services["console"]["environment"]["DOCKER"] = "true"
    services["runtime"]["environment"]["OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE"] = "/run/secrets/lease"
    return {"services": services, "networks": {"default": {"name": "fixture-net"}},
            "volumes": {"postgres-data": {"name": "fixture-postgres"}},
            "secrets": {"lease": {"file": "/fixture/key-file"}}}


GROUPS = (
    AliasGroup("OMERTA_DOCKER", ("AION_DOCKER",), False),
    AliasGroup("OMERTA_GATEWAY_URL", ("AION_GATEWAY_URL",), False),
)


class QuickstartParityTests(unittest.TestCase):
    def test_variants_do_not_mutate_input_or_storage_identity(self):
        source = fixture()
        original = copy.deepcopy(source)
        config, _ = parity.variant_config(source, GROUPS, legacy=True, console_image="console:new")

        self.assertEqual(source, original)
        self.assertEqual(config["volumes"], original["volumes"])
        self.assertEqual(config["secrets"], original["secrets"])
        self.assertEqual(config["services"]["runtime"]["environment"]["OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE"],
                         "/run/secrets/lease")

    def test_legacy_variant_changes_actual_environment_and_removes_masking_overrides(self):
        config, coverage = parity.variant_config(fixture(), GROUPS, legacy=True, console_image="console:new")
        env = config["services"]["console"]["environment"]

        self.assertNotIn("OMERTA_DOCKER", env)
        self.assertNotIn("OMERTA_GATEWAY_URL", env)
        self.assertNotIn("GATEWAY_URL", env)
        self.assertNotIn("DOCKER", env)
        self.assertEqual(env["AION_GATEWAY_URL"], "http://gateway:8080")
        self.assertEqual(coverage["console"]["OMERTA_DOCKER"], "AION_DOCKER")

    def test_canonical_variant_keeps_canonical_reader_and_locks_image_and_ports(self):
        config, _ = parity.variant_config(fixture(), GROUPS, legacy=False, console_image="console:new")

        for name in (*parity.APPLICATIONS, "install"):
            self.assertNotIn("build", config["services"][name])
        self.assertEqual(config["services"]["console"]["image"], "console:new")
        self.assertEqual(config["services"]["install"]["image"], "console:new")
        self.assertEqual(config["services"]["console"]["environment"]["OMERTA_GATEWAY_URL"], "http://gateway:8080")
        for name in parity.APPLICATIONS:
            self.assertEqual(config["services"][name]["ports"][0]["host_ip"], "127.0.0.1")

    def test_alias_conflict_is_rejected_without_values(self):
        _, coverage = parity.variant_config(fixture(), GROUPS, legacy=True, console_image="console:new")
        self.assertEqual(parity.conflicting_pairs(GROUPS, coverage), 2)

    def test_rendered_dollars_are_escaped_recursively(self):
        source = {"environment": {"PASSWORD": "probe$with${interpolation}"}, "command": ["$HOME"]}
        self.assertEqual(parity.compose_dollars(source, encode=True),
                         {"environment": {"PASSWORD": "probe$$with$${interpolation}"}, "command": ["$$HOME"]})
        self.assertEqual(source["command"], ["$HOME"])

    def test_compose_config_health_and_secret_dollars_are_decoded_before_reencoding(self):
        rendered = {"healthcheck": {"test": ["CMD", "bash", "-ec", 'test "$$status" = 200']},
                    "environment": {"PASSWORD": "synthetic$$credential$$$$suffix"}}
        logical = parity.compose_dollars(rendered, encode=False)

        self.assertEqual(logical["healthcheck"]["test"][-1], 'test "$status" = 200')
        self.assertEqual(logical["environment"]["PASSWORD"], "synthetic$credential$$suffix")
        self.assertEqual(parity.compose_dollars(logical, encode=True), rendered)

    def test_memory_guard_rejects_starting_a_child_below_one_gib(self):
        from unittest.mock import mock_open

        runner = parity.Runner()
        with patch("builtins.open", mock_open(read_data="MemAvailable: 1048575 kB\n")), \
             patch.object(parity.subprocess, "Popen") as child:
            with self.assertRaises(parity.AcceptanceFailure):
                runner.run("insufficient RAM", ["unused"])
        child.assert_not_called()

    def test_timeout_terminates_the_child_and_records_its_exit(self):
        runner = parity.Runner()
        with self.assertRaises(parity.AcceptanceFailure) as error:
            runner.run("bounded timeout", [sys.executable, "-c", "import time; time.sleep(60)"],
                       timeout=0.01, guard=False)
        self.assertIn("timeout", str(error.exception))
        self.assertLess(runner.report["gates"][-1]["exit_code"], 0)

    def test_normalization_ignores_only_dynamic_fields(self):
        first = {"status": "OK", "taskId": "one", "engine": {"route": "runtime"},
                 "result": {"exit_code": "0", "stdout": "m413-parity-ok\n"}}
        second = {**first, "taskId": "two", "usage": {"latencyMs": 99}}
        self.assertEqual(parity.normalized_result(first), parity.normalized_result(second))
        second["result"] = {"exit_code": "1", "stdout": "m413-parity-ok\n"}
        with self.assertRaises(parity.AcceptanceFailure):
            parity.normalized_result(second)

    def test_failed_command_output_is_not_persisted_in_report_or_error(self):
        runner = parity.Runner()
        sentinel = "private-value-for-test-only"
        command = [sys.executable, "-c", "import sys; print(sys.stdin.read(), file=sys.stderr); sys.exit(7)"]
        with self.assertRaises(parity.AcceptanceFailure) as error:
            runner.run("synthetic failing child", command, data=sentinel.encode(), guard=False)

        self.assertNotIn(sentinel, str(error.exception))
        self.assertNotIn(sentinel, json.dumps(runner.report))
        self.assertEqual(runner.report["gates"][-1]["exit_code"], 7)

    def test_missing_run_flag_never_builds_or_starts_a_service(self):
        with self.assertRaises(parity.AcceptanceFailure), patch.object(parity.Runner, "run") as run:
            parity.main(["--env-file", "ignored.env", "--console-image", "console:new",
                         "--output", str(parity.ROOT / "artifacts/test.json"), "--build-console"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
