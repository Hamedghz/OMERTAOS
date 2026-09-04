from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD = REPO_ROOT / "deploy" / "native" / "systemd"
CAPO_SYSTEMD = REPO_ROOT / "deploy" / "CAPO" / "systemd"
SCRIPTS = REPO_ROOT / "deploy" / "native" / "scripts"
SERVICES = ("runtime", "control", "gateway", "console")


def _unit(name: str) -> str:
    return (SYSTEMD / name).read_text(encoding="utf-8")


def test_n6_has_install_unit_four_services_and_target() -> None:
    expected = {
        "omertaos-install.service",
        *(f"omertaos-{name}.service" for name in SERVICES),
        "omertaos.target",
    }
    assert expected <= {path.name for path in SYSTEMD.iterdir() if path.is_file()}


def test_each_service_loads_common_and_only_its_own_environment() -> None:
    for name in SERVICES:
        text = _unit(f"omertaos-{name}.service")
        environment_files = [
            line.split("=", 1)[1]
            for line in text.splitlines()
            if line.startswith("EnvironmentFile=")
        ]
        assert environment_files == [
            "/etc/omertaos/omertaos.env",
            f"/etc/omertaos/{name}.env",
        ]
        assert "User=omertaos" in text
        assert "Group=omertaos" in text


def test_install_precedes_runtime_control_gateway_console() -> None:
    install = _unit("omertaos-install.service")
    runtime = _unit("omertaos-runtime.service")
    control = _unit("omertaos-control.service")
    gateway = _unit("omertaos-gateway.service")
    console = _unit("omertaos-console.service")
    target = _unit("omertaos.target")

    assert "Type=oneshot" in install
    assert "RemainAfterExit=yes" in install
    assert "migrate-database.sh" in install
    assert "bootstrap-admin.sh" in install
    assert "Before=omertaos-runtime.service" in install
    assert "ConditionPathExists" not in install
    assert "Requires=omertaos-install.service" in runtime
    assert "Requires=omertaos-runtime.service" in control
    assert "Requires=omertaos-control.service" in gateway
    assert "Requires=omertaos-gateway.service" in console
    for name in ("install", *SERVICES):
        assert f"omertaos-{name}.service" in target


def test_units_use_built_artifacts_not_package_managers() -> None:
    assert "ExecStart=/opt/omertaos/current/bin/runtime-daemon" in _unit("omertaos-runtime.service")
    assert "/opt/omertaos/current/.venv/control/bin/python -m control.app.serve" in _unit("omertaos-control.service")
    assert "ExecStart=/usr/bin/node dist/server.js" in _unit("omertaos-gateway.service")
    assert "node_modules/next/dist/bin/next start" in _unit("omertaos-console.service")
    combined = "\n".join(_unit(f"omertaos-{name}.service") for name in SERVICES)
    assert "npm start" not in combined
    assert "pnpm start" not in combined


def test_services_have_common_hardening_and_bounded_restart() -> None:
    for name in SERVICES:
        text = _unit(f"omertaos-{name}.service")
        for marker in (
            "Restart=on-failure",
            "StartLimitBurst=3",
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectHome=true",
            "ProtectSystem=strict",
            "RestrictSUIDSGID=true",
            "LockPersonality=true",
            "UMask=0027",
        ):
            assert marker in text


def test_install_script_verifies_before_copy_and_never_starts_services() -> None:
    text = (SCRIPTS / "install-systemd.sh").read_text(encoding="utf-8")
    assert "--check" in text
    assert "systemd-analyze verify" in text
    assert text.index("systemd-analyze verify") < text.index('install -o root -g root -m 0644')
    assert "systemctl enable omertaos.target" in text
    assert "systemctl start" not in text
    assert "validate_data_env.py" in text
    assert "contains a placeholder" in text
    assert "forbidden shell expansion" in text
    for name in ("omertaos.env", "runtime.env", "control.env", "gateway.env", "console.env", "installer.env"):
        assert name in text


def test_lifecycle_scripts_touch_only_aggregate_target() -> None:
    run = (SCRIPTS / "run.sh").read_text(encoding="utf-8")
    stop = (SCRIPTS / "stop.sh").read_text(encoding="utf-8")
    assert "systemctl start omertaos.target" in run
    assert "systemctl stop omertaos.target" in stop
    assert "postgresql" not in stop
    assert "redis-server" not in stop


def test_capo_systemd_payload_matches_canonical_native_owner() -> None:
    for name in (
        "omertaos-install.service",
        *(f"omertaos-{service}.service" for service in SERVICES),
        "omertaos.target",
    ):
        assert (CAPO_SYSTEMD / name).read_bytes() == (SYSTEMD / name).read_bytes()
    for wrapper, target in (
        ("setup-systemd.sh", "install-systemd.sh"),
        ("run-all.sh", "run.sh"),
        ("stop-all.sh", "stop.sh"),
        ("update.sh", "update.sh"),
        ("rollback.sh", "rollback.sh"),
    ):
        text = (REPO_ROOT / "deploy" / "CAPO" / "scripts" / wrapper).read_text(encoding="utf-8")
        assert f"deploy/native/scripts/{target}" in text
        assert len(text.splitlines()) <= 7
