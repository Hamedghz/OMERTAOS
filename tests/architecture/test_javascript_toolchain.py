from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_VERSION = "22.23.2"
NPM_VERSION = "10.9.8"
PNPM_VERSION = "11.13.1"

NPM_APPS = (
    "gateway",
    "console/desktop-shell",
    "integrations/windows-agentic-bridge/bridge-server",
    "integrations/windows-agentic-bridge/bridge-ui",
)
SHARED_PACKAGES = ("packages/ui-core", "shared/secret-provider-node")


def _json(path: str) -> dict:
    return json.loads((REPO_ROOT / path).read_text())


def test_javascript_version_files_and_manifests_are_aligned() -> None:
    assert (REPO_ROOT / ".node-version").read_text().strip() == NODE_VERSION
    assert (REPO_ROOT / ".nvmrc").read_text().strip() == NODE_VERSION
    assert (REPO_ROOT / ".npmrc").read_text().strip() == "engine-strict=true"

    for app in NPM_APPS:
        package = _json(f"{app}/package.json")
        lock_root = _json(f"{app}/package-lock.json")["packages"][""]
        expected = {"node": NODE_VERSION, "npm": NPM_VERSION}
        assert package["engines"] == expected
        assert package["packageManager"] == f"npm@{NPM_VERSION}"
        assert lock_root["engines"] == expected

    for package_dir in SHARED_PACKAGES:
        assert _json(f"{package_dir}/package.json")["engines"] == {
            "node": NODE_VERSION
        }

    console = _json("console/package.json")
    console_lock = _json("console/package-lock.json")["packages"][""]
    expected_console = {
        "node": NODE_VERSION,
        "npm": NPM_VERSION,
        "pnpm": PNPM_VERSION,
    }
    assert console["engines"] == expected_console
    assert console["packageManager"] == f"pnpm@{PNPM_VERSION}"
    assert console_lock["engines"] == expected_console


def test_ci_and_container_images_use_the_canonical_node_version() -> None:
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    gateway = (REPO_ROOT / "gateway/Dockerfile").read_text()
    console = (REPO_ROOT / "console/Dockerfile").read_text()
    image = f"node:{NODE_VERSION}-alpine3.24"

    assert "node-version: '20'" not in ci
    assert "node-version: '22'" not in ci
    assert ci.count(f"node-version: '{NODE_VERSION}'") == 2
    assert gateway.count(f"FROM --platform=$BUILDPLATFORM {image}") == 2
    assert f"FROM {image} AS runner" in gateway
    assert console.count(f"FROM {image}") == 3
    assert f"corepack prepare pnpm@{PNPM_VERSION} --activate" in console


def test_console_bootstrap_tsconfig_can_emit_installer_artifact() -> None:
    config = _json("console/scripts/tsconfig.json")
    compiler_options = config["compilerOptions"]

    assert compiler_options["noEmit"] is False
    assert compiler_options["allowImportingTsExtensions"] is False
