from __future__ import annotations

import json
import re
from pathlib import Path

from packaging.version import Version
import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_VERSION = "22.23.2"
NPM_VERSION = "10.9.10"
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
    assert re.search(rf"FROM {re.escape(image)}@sha256:[a-f0-9]{{64}} AS runner", gateway)
    assert console.count(f"FROM {image}") == 3
    assert f"corepack prepare pnpm@{PNPM_VERSION} --activate" in console
    npm_install = f"npm install --global npm@{NPM_VERSION} --ignore-scripts --no-fund"
    assert ci.count(npm_install) == 2
    assert gateway.count(npm_install) == 3
    assert console.count(npm_install) == 3
    version_guard = f'test "$(npm --version)" = "{NPM_VERSION}"'
    assert ci.count(version_guard) == 2
    assert gateway.count(version_guard) == 3
    assert console.count(version_guard) == 3


def test_quickstart_upstream_images_and_build_bases_are_digest_pinned() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()
    images = re.findall(r"^\s+image: (\S+)$", compose, re.MULTILINE)
    upstream_images = [image for image in images if not image.startswith("${")]
    assert upstream_images
    for image in upstream_images:
        assert re.fullmatch(r"\S+@sha256:[a-f0-9]{64}", image), image

    node_base = (
        f"node:{NODE_VERSION}-alpine3.24@sha256:"
        "b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85"
    )
    reviewed_bases = {
        "control": "python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b",
        "runtime-daemon": "debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc",
        "gateway": node_base,
        "console": node_base,
    }
    for service, reviewed_base in reviewed_bases.items():
        dockerfile = (REPO_ROOT / service / "Dockerfile").read_text()
        bases = re.findall(r"^FROM (?:--platform=\S+ )?(\S+)", dockerfile, re.MULTILINE)
        assert bases
        for base in bases:
            assert re.fullmatch(r"\S+@sha256:[a-f0-9]{64}", base), base
        assert bases[-1] == reviewed_base, service
        if service in {"gateway", "console"}:
            assert set(bases) == {reviewed_base}, service

    assert ".secrets-out/" in (REPO_ROOT / ".dockerignore").read_text().splitlines()


def test_console_bootstrap_tsconfig_can_emit_installer_artifact() -> None:
    config = _json("console/scripts/tsconfig.json")
    compiler_options = config["compilerOptions"]

    assert compiler_options["noEmit"] is False
    assert compiler_options["allowImportingTsExtensions"] is False


def test_node_image_alpine_mirror_selection_preserves_secure_defaults() -> None:
    for app in ("gateway", "console"):
        dockerfile = (REPO_ROOT / app / "Dockerfile").read_text()
        assert "ARG ALPINE_MIRROR=cdn" in dockerfile
        assert 'case "$ALPINE_MIRROR" in' in dockerfile
        assert "cdn) ;;" in dockerfile
        assert "https://mirrors.edge.kernel.org/alpine/" in dockerfile
        assert '*) echo "Unsupported ALPINE_MIRROR; expected cdn or kernel" >&2; exit 1 ;;' in dockerfile
        assert "&& apk add --no-cache curl" in dockerfile
        assert "--allow-untrusted" not in dockerfile
        assert "--no-check-certificate" not in dockerfile
        assert "http://" not in dockerfile

    console = (REPO_ROOT / "console/Dockerfile").read_text()
    assert "pnpm install --frozen-lockfile --prefer-offline --network-concurrency=2 --child-concurrency=2" in console
    assert "--fetch-retries=1 --fetch-timeout=120000" in console


def test_major_security_migration_keeps_owner_scoped_dependency_contracts() -> None:
    for app in ("console", "gateway", "integrations/windows-agentic-bridge/bridge-server"):
        packages = _json(f"{app}/package-lock.json")["packages"]
        zod = [package for name, package in packages.items() if name.endswith("/zod")]
        assert zod
        assert all(Version(package["version"]) >= Version("4.6.7") for package in zod)
        for name, package in packages.items():
            if not name.endswith(("/minimatch", "/glob")):
                continue
            version = Version(package.get("version", "0"))
            if name.endswith("/minimatch") and version.major >= 9:
                assert version == Version("11.0.5"), (app, name)
            if name.endswith("/glob") and version.major >= 10:
                assert version >= Version("14.0.2"), (app, name)

    packages = _json("console/package-lock.json")["packages"]
    assert Version(packages["node_modules/deepmerge-ts"]["version"]) >= Version("8.0.0")
    assert Version(_json("console/package.json")["devDependencies"]["typescript"]) >= Version("5.5")
    workspace = yaml.safe_load((REPO_ROOT / "console/pnpm-workspace.yaml").read_text())
    assert workspace["overrides"] == _json("console/package.json")["overrides"]
    assert workspace["minimumReleaseAgeStrict"] is True
    assert not workspace.get("minimumReleaseAgeExclude")


@pytest.mark.parametrize("app", [
    "console/desktop-shell",
    "integrations/windows-agentic-bridge/bridge-ui",
])
def test_auxiliary_ui_locks_keep_security_floors_without_a_vite_major_change(app: str) -> None:
    manifest = _json(f"{app}/package.json")
    packages = _json(f"{app}/package-lock.json")["packages"]
    assert manifest["devDependencies"]["vite"] == "^6.4.6"
    assert packages[""]["devDependencies"]["vite"] == "^6.4.6"
    floors = {
        "vite": "6.4.6",
        "baseline-browser-mapping": "2.11.0",
        "browserslist": "4.28.7",
        "source-map-js": "1.2.2",
    }
    for name, minimum in floors.items():
        if name != "vite":
            assert manifest["overrides"][name] == f"^{minimum}"
        versions = [Version(package["version"]) for path, package in packages.items()
                    if path.endswith(f"node_modules/{name}")]
        assert versions, (app, name)
        assert all(version >= Version(minimum) for version in versions), (app, name)
        if name == "vite":
            assert all(version.major == 6 for version in versions), app
