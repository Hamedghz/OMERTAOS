import pytest

from data.vector.qdrant_client import _vector_size
from shared.config.environment import EnvironmentConflictError


def test_qdrant_vector_size_uses_canonical_name() -> None:
    assert _vector_size({"OMERTA_RAG_VECTOR_SIZE": "128"}) == 128


def test_qdrant_vector_size_rejects_conflicting_aliases(
) -> None:
    with pytest.raises(EnvironmentConflictError) as raised:
        _vector_size(
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
