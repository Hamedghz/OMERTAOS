from __future__ import annotations

import ast
import io
import json
import sys
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import validate_historical_quickstart_upgrade as upgrade
from scripts.validate_environment_aliases import AliasGroup
from scripts.validate_quickstart_environment_parity import AcceptanceFailure


class HistoricalUpgradeTests(unittest.TestCase):
    def test_legacy_aliases_preserve_tenant_and_secret_without_mutating_input(self):
        groups = (AliasGroup("OMERTA_RUNTIME_TENANT_IDS", ("AION_RUNTIME_TENANT_IDS",), False),
                  AliasGroup("OMERTA_GATEWAY_ADMIN_TOKEN", ("AION_GATEWAY_ADMIN_TOKEN",), True))
        current = {"OMERTA_RUNTIME_TENANT_IDS": "", "OMERTA_GATEWAY_ADMIN_TOKEN": "fixture-current"}
        result = upgrade.merge_legacy_environment(current, {"AION_RUNTIME_TENANT_IDS": "tenant-old",
            "AION_GATEWAY_ADMIN_TOKEN": "fixture-old"}, groups)
        self.assertEqual(result, {"OMERTA_RUNTIME_TENANT_IDS": "tenant-old", "OMERTA_GATEWAY_ADMIN_TOKEN": "fixture-old"})
        self.assertEqual(current["OMERTA_GATEWAY_ADMIN_TOKEN"], "fixture-current")

    def test_conflicting_retained_aliases_fail_without_values(self):
        group = AliasGroup("OMERTA_GATEWAY_ADMIN_TOKEN", ("AION_GATEWAY_ADMIN_TOKEN",), True)
        with self.assertRaises(AcceptanceFailure) as error:
            upgrade.merge_legacy_environment({group.canonical_name: "fixture"}, {
                group.canonical_name: "fixture-new", "AION_GATEWAY_ADMIN_TOKEN": "fixture-old"}, (group,))
        self.assertNotIn("fixture-old", str(error.exception))
        self.assertNotIn("fixture-new", str(error.exception))

    def test_clone_transport_addresses_are_not_replaced_by_historical_host_bindings(self):
        group = AliasGroup("OMERTA_CORS_ORIGINS", ("AION_CORS_ORIGINS",), False)
        result = upgrade.merge_legacy_environment({group.canonical_name: "http://localhost:23000"},
            {"AION_CORS_ORIGINS": "http://localhost:13000"}, (group,))
        self.assertEqual(result[group.canonical_name], "http://localhost:23000")

    def test_preservation_accepts_additions_but_rejects_row_loss_changes_and_duplicate_loss(self):
        before = {"User": {"columns": ["id", "password"], "hashes": {"hash1": 2}, "rows": 2}}
        after = {"User": {"columns": ["id", "password"], "hashes": {"hash1": 2, "hash2": 1}, "rows": 3}}
        upgrade.assert_old_rows_preserved(before, after)
        for changed in ({}, {"User": {"columns": ["id"], "hashes": {"hash1": 2}}},
                        {"User": {"columns": ["id", "password"], "hashes": {"hash1": 1}}},
                        {"User": {"columns": ["id", "password"], "hashes": {"changed": 2}}}):
            with self.assertRaises(AcceptanceFailure):
                upgrade.assert_old_rows_preserved(before, changed)

    def test_tar_inventory_normalizes_root_without_discarding_data(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as archive:
            root = tarfile.TarInfo("./")
            root.type, root.mode = tarfile.DIRTYPE, 0o755
            archive.addfile(root)
            file = tarfile.TarInfo("./fixture")
            file.size = 4
            archive.addfile(file, io.BytesIO(b"test"))
        output = io.StringIO()
        with patch.object(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(data.getvalue()))), patch.object(sys, "stdout", output):
            exec(upgrade.TAR_INVENTORY, {})
        result = json.loads(output.getvalue())
        self.assertEqual(result["entries"], 2)
        self.assertEqual(len(result["sha256"]), 64)

    def test_snapshot_uses_structured_identifiers_and_starts_no_service_without_run(self):
        ast.parse(upgrade.SQL_SNAPSHOT)
        self.assertIn("sql.Identifier", upgrade.SQL_SNAPSHOT)
        with self.assertRaises(AcceptanceFailure):
            upgrade.main(["--env-file", "fixture.env", "--key-dir", "/tmp/key", "--backup-dir", "/tmp/backup",
                          "--project", "omerta-p3-restore-fixture", "--output", "artifacts/test.json"])


if __name__ == "__main__":
    unittest.main()
