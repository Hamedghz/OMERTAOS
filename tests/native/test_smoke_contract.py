import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "deploy" / "native" / "scripts" / "smoke-test.sh"


def test_n7_smoke_is_read_only_and_covers_every_native_boundary() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    for marker in (
        "omertaos-install.service",
        "omertaos-runtime.service",
        "omertaos-control.service",
        "omertaos-gateway.service",
        "omertaos-console.service",
        "omertaos.target",
        "postgresql.service",
        "redis-server.service",
        "pg_isready",
        "redis-cli",
        "runtime-daemon --healthcheck",
        "127.0.0.1:8000/healthz",
        "127.0.0.1:8080/health",
        "127.0.0.1:3000/healthz",
        "127.0.0.1:3000/api/system/health",
        "journalctl",
        "NRestarts",
        "journald has no entry",
    ):
        assert marker in text

    for forbidden in (
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl enable",
        "systemctl daemon-reload",
        "prisma migrate deploy",
        "bootstrap-admin.sh",
        "rm -rf",
    ):
        assert forbidden not in text


def test_n7_validates_payloads_not_only_http_status() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    assert "jq -e" in text
    assert '.dependencies.redis == "ok"' in text
    assert '.dependencies.control == "ok"' in text
    assert '.services.console.status == "ok"' in text
    assert '.services.gateway.status == "ok"' in text
    assert '.services.control.status == "ok"' in text


def test_n7_requires_internal_loopback_listeners() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    assert "check_listener 50051 Runtime true" in text
    assert "check_listener 8000 Control true" in text
    assert "check_listener 8080 Gateway false" in text
    assert "check_listener 3000 Console false" in text


def test_capo_smoke_is_a_thin_native_wrapper() -> None:
    wrapper = (REPO_ROOT / "deploy" / "CAPO" / "scripts" / "smoke-test.sh").read_text(encoding="utf-8")
    assert "deploy/native/scripts/smoke-test.sh" in wrapper
    assert len(wrapper.splitlines()) <= 7


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_quickstart_smoke_targets_selected_project_and_isolated_ports(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"

    _write_executable(
        bin_dir / "docker",
        """#!/bin/sh
printf '%s\n' "$*" >> "$SMOKE_DOCKER_LOG"
if [ "$1" = compose ]; then
  previous=
  last=
  for argument in "$@"; do previous="$last"; last="$argument"; done
  if [ "$previous" = "-q" ]; then printf '%s-id\n' "$last"; fi
  exit 0
fi
case "$*" in
  *State.Status*State.ExitCode*) printf 'exited:0\n' ;;
  *) printf 'healthy\n' ;;
esac
""",
    )
    _write_executable(
        bin_dir / "curl",
        """#!/bin/sh
for argument in "$@"; do url="$argument"; done
printf '%s\n' "$url" >> "$SMOKE_CURL_LOG"
case "$url" in
  *:18000/*) printf '{"status":"ok","service":"control"}\n' ;;
  *:18080/*) printf '{"status":"ok","service":"gateway","dependencies":{"redis":"ok","control":"ok"}}\n' ;;
  */api/system/health) printf '{"status":"ok","services":{"console":{"status":"ok"},"gateway":{"status":"ok"},"control":{"status":"ok"}}}\n' ;;
  *:13000/*) printf '{"status":"ok","service":"console"}\n' ;;
  *) exit 22 ;;
esac
""",
    )

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "SMOKE_DOCKER_LOG": str(docker_log),
        "SMOKE_CURL_LOG": str(curl_log),
        "OMERTA_CONSOLE_HOST_PORT": "13000",
        "OMERTA_GATEWAY_HOST_PORT": "18080",
        "OMERTA_CONTROL_HOST_PORT": "18000",
    }
    result = subprocess.run(
        ["bash", str(SMOKE), "--mode", "quickstart", "--project-name", "omertaos-test"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OMERTAOS quickstart smoke test passed." in result.stdout
    docker_calls = docker_log.read_text(encoding="utf-8")
    assert "--project-name omertaos-test" in docker_calls
    assert f"--project-directory {REPO_ROOT}" in docker_calls
    assert "ps --all -q install" in docker_calls
    assert "exec -T runtime /usr/local/bin/runtime-daemon --healthcheck" in docker_calls
    assert "exec -T control python -c" in docker_calls
    assert "Runtime Quickstart automatic registration" in result.stdout
    curl_calls = curl_log.read_text(encoding="utf-8")
    assert "http://127.0.0.1:18000/healthz" in curl_calls
    assert "http://127.0.0.1:18080/health" in curl_calls
    assert "http://127.0.0.1:13000/api/system/health" in curl_calls


def test_quickstart_smoke_rejects_invalid_isolated_port(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SMOKE), "--mode", "quickstart", "--project-name", "omertaos-test"],
        cwd=tmp_path,
        env={**os.environ, "OMERTA_CONSOLE_HOST_PORT": "0"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "OMERTA_CONSOLE_HOST_PORT must be an integer between 1 and 65535" in result.stderr


def test_quickstart_smoke_accepts_legacy_host_port_with_names_only_warning(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        ["bash", str(SMOKE), "--help"],
        cwd=tmp_path,
        env={**os.environ, "AION_CONSOLE_HOST_PORT": "13000"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert (
        "deprecated environment alias AION_CONSOLE_HOST_PORT; "
        "use OMERTA_CONSOLE_HOST_PORT" in result.stderr
    )


def test_quickstart_smoke_rejects_conflicting_host_ports(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SMOKE), "--help"],
        cwd=tmp_path,
        env={
            **os.environ,
            "OMERTA_CONSOLE_HOST_PORT": "13000",
            "AION_CONSOLE_HOST_PORT": "13001",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert (
        "conflicting environment aliases: "
        "OMERTA_CONSOLE_HOST_PORT, AION_CONSOLE_HOST_PORT" in result.stderr
    )
