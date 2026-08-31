from __future__ import annotations
import base64
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GRPC_DIR = ROOT / "control" / "app" / "grpc"
if str(GRPC_DIR) not in sys.path:
    sys.path.insert(0, str(GRPC_DIR))

CLI_DIR = ROOT / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))


@pytest.fixture(autouse=True)
def runtime_lease_hmac_key(monkeypatch: pytest.MonkeyPatch) -> None:
    encoded = base64.b64encode(b"test-runtime-lease-key-material-32").decode()
    monkeypatch.setenv("OMERTA_RUNTIME_LEASE_HMAC_KEY", encoded)
