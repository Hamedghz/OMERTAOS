from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from shared.config.environment import EnvironmentConflictError


def _load_vector_size(monkeypatch: pytest.MonkeyPatch):
    qdrant_module = ModuleType("qdrant_client")
    qdrant_module.QdrantClient = object
    http_module = ModuleType("qdrant_client.http")
    http_module.models = SimpleNamespace(
        Distance=SimpleNamespace(COSINE="cosine")
    )
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_module)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http_module)
    sys.modules.pop("data.vector.qdrant_client", None)
    module = importlib.import_module("data.vector.qdrant_client")
    return module._vector_size


def test_qdrant_vector_size_uses_canonical_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vector_size = _load_vector_size(monkeypatch)
    assert vector_size({"OMERTA_RAG_VECTOR_SIZE": "128"}) == 128


def test_qdrant_vector_size_rejects_conflicting_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vector_size = _load_vector_size(monkeypatch)
    with pytest.raises(EnvironmentConflictError) as raised:
        vector_size(
            {
                "OMERTA_RAG_VECTOR_SIZE": "128",
                "AION_RAG_VECTOR_SIZE": "64",
            }
        )

    rendered = str(raised.value)
    assert "OMERTA_RAG_VECTOR_SIZE" in rendered
    assert "AION_RAG_VECTOR_SIZE" in rendered
    assert "128" not in rendered
    assert "64" not in rendered
