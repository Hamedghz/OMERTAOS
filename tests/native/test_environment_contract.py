import importlib.util
import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_DIR = REPO_ROOT / "deploy" / "native" / "env"
SPEC = importlib.util.spec_from_file_location("native_env_validator", ENV_DIR / "validate.py")
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def test_native_environment_examples_satisfy_contract() -> None:
    assert VALIDATOR.validate_directory(ENV_DIR) == []


def test_console_environment_respects_gateway_boundary() -> None:
    values = VALIDATOR.parse_env(ENV_DIR / "console.env.example")
    forbidden = (
        "AION_CONTROL_",
        "AION_RUNTIME_",
        "OMERTA_CONTROL_",
        "OMERTA_RUNTIME_",
        "CONTROL_",
    )
    assert not [key for key in values if key.startswith(forbidden)]
    assert values["NEXT_PUBLIC_GATEWAY_URL"].startswith("http://127.0.0.1:")


def test_native_internal_endpoints_are_loopback_only() -> None:
    control = VALIDATOR.parse_env(ENV_DIR / "control.env.example")
    runtime = VALIDATOR.parse_env(ENV_DIR / "runtime.env.example")
    gateway = VALIDATOR.parse_env(ENV_DIR / "gateway.env.example")
    assert control["CONTROL_HOST"] == "127.0.0.1"
    assert runtime["OMERTA_RUNTIME_BIND_ADDR"].startswith("127.0.0.1:")
    assert gateway["OMERTA_CONTROL_BASE_URL"].startswith("http://127.0.0.1:")
    assert "://" not in gateway["OMERTA_CONTROL_GRPC"]


def test_native_code_paths_follow_the_active_release_symlink() -> None:
    common = VALIDATOR.parse_env(ENV_DIR / "omertaos.env.example")
    control = VALIDATOR.parse_env(ENV_DIR / "control.env.example")
    assert common["OMERTAOS_ROOT"] == "/opt/omertaos/current"
    assert control["OMERTA_CONTROL_MODELS_DIRECTORY"].startswith("/opt/omertaos/current/")
    assert control["OMERTA_CONTROL_POLICIES_DIRECTORY"].startswith("/opt/omertaos/current/")


def test_native_contract_v2_publishes_only_canonical_product_keys() -> None:
    contract = json.loads((ENV_DIR / "contract.json").read_text(encoding="utf-8"))

    assert contract["version"] == 2
    for filename in contract["templates"]:
        values = VALIDATOR.parse_env(ENV_DIR / filename)
        assert not [key for key in values if key.startswith("AION_")]


def test_strict_validation_accepts_a_legacy_alias_during_rollout(
    tmp_path: Path,
) -> None:
    contract = json.loads((ENV_DIR / "contract.json").read_text(encoding="utf-8"))
    shutil.copy2(ENV_DIR / "contract.json", tmp_path / "contract.json")
    shutil.copytree(ENV_DIR / "profiles", tmp_path / "profiles")
    for filename in contract["templates"]:
        rendered = (ENV_DIR / filename).read_text(encoding="utf-8").replace(
            "CHANGE_ME", "N1-test-secret"
        )
        if filename == "runtime.env.example":
            rendered = rendered.replace(
                "OMERTA_RUNTIME_BIND_ADDR=", "AION_RUNTIME_BIND_ADDR="
            )
        (tmp_path / filename.removesuffix(".example")).write_text(
            rendered,
            encoding="utf-8",
        )

    assert VALIDATOR.validate_directory(tmp_path, strict=True) == []


def test_strict_validation_rejects_conflicting_aliases_without_values(
    tmp_path: Path,
) -> None:
    contract = json.loads((ENV_DIR / "contract.json").read_text(encoding="utf-8"))
    shutil.copy2(ENV_DIR / "contract.json", tmp_path / "contract.json")
    shutil.copytree(ENV_DIR / "profiles", tmp_path / "profiles")
    for filename in contract["templates"]:
        rendered = (ENV_DIR / filename).read_text(encoding="utf-8").replace(
            "CHANGE_ME", "N1-test-secret"
        )
        if filename == "runtime.env.example":
            rendered += "AION_RUNTIME_BIND_ADDR=127.0.0.1:59999\n"
        (tmp_path / filename.removesuffix(".example")).write_text(
            rendered,
            encoding="utf-8",
        )

    errors = VALIDATOR.validate_directory(tmp_path, strict=True)
    rendered_errors = " ".join(errors)
    assert "OMERTA_RUNTIME_BIND_ADDR" in rendered_errors
    assert "AION_RUNTIME_BIND_ADDR" in rendered_errors
    assert "127.0.0.1:50051" not in rendered_errors
    assert "127.0.0.1:59999" not in rendered_errors


def test_committed_examples_do_not_contain_real_secrets() -> None:
    contract = json.loads((ENV_DIR / "contract.json").read_text(encoding="utf-8"))
    for filename in contract["templates"]:
        values = VALIDATOR.parse_env(ENV_DIR / filename)
        for key in contract["secret_keys"]:
            if key in values:
                assert values[key] == "CHANGE_ME"
        for key in contract["credential_url_keys"]:
            if key in values:
                assert "CHANGE_ME@" in values[key]


def test_strict_mode_rejects_placeholders_and_accepts_rendered_files(tmp_path: Path) -> None:
    contract = json.loads((ENV_DIR / "contract.json").read_text(encoding="utf-8"))
    shutil.copy2(ENV_DIR / "contract.json", tmp_path / "contract.json")
    shutil.copytree(ENV_DIR / "profiles", tmp_path / "profiles")
    for filename in contract["templates"]:
        rendered = (ENV_DIR / filename).read_text(encoding="utf-8")
        (tmp_path / filename.removesuffix(".example")).write_text(rendered, encoding="utf-8")

    assert any("placeholder" in error for error in VALIDATOR.validate_directory(tmp_path, strict=True))

    for filename in contract["templates"]:
        path = tmp_path / filename.removesuffix(".example")
        path.write_text(path.read_text(encoding="utf-8").replace("CHANGE_ME", "N1-test-secret"), encoding="utf-8")
    assert VALIDATOR.validate_directory(tmp_path, strict=True) == []
