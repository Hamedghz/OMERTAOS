"""Qdrant client helpers for centralized data plane."""
from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from shared.config.environment import integer_parser, resolve_environment

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")


def _vector_size(environ: Mapping[str, str] | None = None) -> int:
    value = resolve_environment(
        "OMERTA_RAG_VECTOR_SIZE",
        aliases=("AION_RAG_VECTOR_SIZE",),
        default="64",
        parser=integer_parser(minimum=1),
        environ=environ,
    )
    assert isinstance(value, int)
    return value


VECTOR_SIZE = _vector_size()


def _client_kwargs() -> dict[str, str]:
    kwargs: dict[str, str] = {"url": QDRANT_URL}
    if QDRANT_API_KEY:
        kwargs["api_key"] = QDRANT_API_KEY
    return kwargs


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(**_client_kwargs())


def collection_exists(client: QdrantClient, collection_name: str) -> bool:
    try:
        collections = client.get_collections().collections or []
    except Exception:
        return False
    return any(col.name == collection_name for col in collections)


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int | None = None,
    distance: rest.Distance = rest.Distance.COSINE,
) -> None:
    if collection_exists(client, collection_name):
        return
    client.create_collection(
        collection_name=collection_name,
        vectors_config=rest.VectorParams(size=vector_size or VECTOR_SIZE, distance=distance),
    )


def list_collections(client: QdrantClient) -> Iterable[str]:
    collections = client.get_collections().collections or []
    for collection in collections:
        yield collection.name

__all__ = ["QDRANT_URL", "QDRANT_API_KEY", "VECTOR_SIZE", "get_qdrant_client", "collection_exists", "ensure_collection", "list_collections"]
