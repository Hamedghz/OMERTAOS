from __future__ import annotations

import json
from pathlib import Path

from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_ROOT = REPO_ROOT / "integrations" / "windows-agentic-bridge"
LEGACY_ROOT = REPO_ROOT / "execution" / "windows-agentic-bridge"


def test_bridge_dependencies_include_security_patches() -> None:
    lock = json.loads((CANONICAL_ROOT / "bridge-server/package-lock.json").read_text(encoding="utf-8"))
    security_floors = {
        "@hono/node-server": "2.1.3",
        "@modelcontextprotocol/sdk": "1.32.0",
        "axios": "1.20.0",
        "body-parser": "2.4.0",
        "fast-uri": "3.1.9",
        "follow-redirects": "1.16.2",
        "hono": "4.13.11",
        "ip-address": "10.7.4",
        "proxy-addr": "2.0.8",
        "qs": "6.16.1",
        "brace-expansion": "1.1.21",
        "js-yaml": "4.3.2",
        "source-map-js": "1.2.2",
        "vitest": "4.1.12",
    }
    for name, minimum in security_floors.items():
        packages = [package for path, package in lock["packages"].items()
                    if path.endswith(f"node_modules/{name}")]
        assert packages, f"expected transport dependency {name} in the lock"
        assert all(Version(package["version"]) >= Version(minimum) for package in packages), name

    manifest = json.loads((CANONICAL_ROOT / "bridge-server/package.json").read_text(encoding="utf-8"))
    assert manifest["devDependencies"]["vite"] == manifest["overrides"]["vite"] == "7.3.7"
    assert lock["packages"]["node_modules/vite"]["version"] == "7.3.7"
    assert "^7.0.0" in lock["packages"]["node_modules/vitest"]["dependencies"]["vite"]


def _files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not {"node_modules", "dist"}.intersection(path.relative_to(root).parts)
    }


def test_bridge_legacy_tree_is_retired_after_canonical_inventory_check() -> None:
    canonical = _files(CANONICAL_ROOT)
    assert len(canonical) == 43
    for component, package_name in (
        ("bridge-server", "omertaos-bridge-server"),
        ("bridge-ui", "omertaos-bridge-ui"),
    ):
        lock = json.loads((CANONICAL_ROOT / component / "package-lock.json").read_text(encoding="utf-8"))
        assert lock["lockfileVersion"] == 3
        assert lock["packages"][""]["name"] == package_name
    assert not LEGACY_ROOT.exists()


def test_bridge_ownership_and_active_references_are_canonical() -> None:
    canonical_readme = (CANONICAL_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Canonical owner: `integrations/windows-agentic-bridge/`" in canonical_readme
    assert not LEGACY_ROOT.exists()

    active_roots = (REPO_ROOT / "console" / "app" / "integrations" / "windows-bridge", CANONICAL_ROOT)
    for root in active_roots:
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            generated = {"node_modules", "dist"}.intersection(relative.parts)
            if (
                path.is_file()
                and not generated
                and path.suffix.lower() in {".ts", ".tsx", ".js", ".json", ".md", ".ps1", ".sh"}
            ):
                source = path.read_text(encoding="utf-8")
                assert "execution/windows-agentic-bridge" not in source, path


def test_bridge_calls_gateway_only_and_uses_versioned_task_routes() -> None:
    config = (CANONICAL_ROOT / "bridge-server" / "src" / "config.ts").read_text(encoding="utf-8")
    client = (CANONICAL_ROOT / "bridge-server" / "src" / "omertaClient.ts").read_text(encoding="utf-8")
    env_example = (CANONICAL_ROOT / "bridge-server" / ".env.example").read_text(encoding="utf-8")
    ui_config = (
        CANONICAL_ROOT / "bridge-ui" / "src" / "components" / "OmertaConfigForm.tsx"
    ).read_text(encoding="utf-8")

    assert "controlUrl" not in config
    assert "OMERTA_CONTROL_URL" not in env_example
    assert "OMERTA_GATEWAY_URL=http://localhost:8080" in env_example
    assert client.count("axios.create(") == 1
    assert "this.control" not in client
    assert "config.controlUrl" not in client
    assert "this.gateway.get('/health')" in client
    assert "this.gateway.post('/v1/tasks'" in client
    assert "this.gateway.get(`/v1/tasks/${taskId}`)" in client
    assert "controlUrl" not in ui_config


def test_bridge_manifests_and_packages_are_safe_local_inputs() -> None:
    manifest = json.loads((CANONICAL_ROOT / "manifests" / "omertaos-wsl.mcp.json").read_text(encoding="utf-8"))
    server_package = json.loads((CANONICAL_ROOT / "bridge-server" / "package.json").read_text(encoding="utf-8"))
    ui_package = json.loads((CANONICAL_ROOT / "bridge-ui" / "package.json").read_text(encoding="utf-8"))
    logger = (CANONICAL_ROOT / "bridge-server" / "src" / "logger.ts").read_text(encoding="utf-8")

    command = manifest["server"]["mcp_config"]["command"]
    args = " ".join(manifest["server"]["mcp_config"]["args"])
    assert command.endswith("wsl.exe")
    assert "integrations/windows-agentic-bridge/bridge-server" in args
    assert "token" not in args.lower()
    assert server_package["private"] is True
    assert ui_package["private"] is True
    assert "@modelcontextprotocol/sdk" in server_package["dependencies"]
    assert "@microsoft/ai-mcp-sdk" not in server_package["dependencies"]
    assert "ajv" in server_package["dependencies"]
    assert "@vitejs/plugin-react" in ui_package["devDependencies"]
    assert "console.log" not in logger
