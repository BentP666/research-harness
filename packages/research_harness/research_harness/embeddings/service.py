"""Embedding provider + cache integration."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import struct
from dataclasses import dataclass, field

from ..storage.db import Database
from .cache import content_hash, read_cached, write_cached

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIM = 1536  # matches text-embedding-3-small
FAKE_DIM = 64


@dataclass
class EmbeddingResult:
    provider: str
    model: str
    vectors: list[list[float]]
    dim: int
    cache_hits: int = 0
    cache_misses: int = 0
    errors: list[str] = field(default_factory=list)


def _select_provider() -> tuple[str, str]:
    provider = (
        (os.environ.get("RESEARCH_HARNESS_EMBEDDING_PROVIDER") or "").strip().lower()
    )
    model = (os.environ.get("RESEARCH_HARNESS_EMBEDDING_MODEL") or "").strip()
    if not provider:
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        provider = "openai" if has_openai else "fake"
    if not model:
        model = DEFAULT_MODEL if provider == "openai" else "fake-v1"
    return provider, model


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic hash-based vectors. No external calls. Unit-norm."""
    vectors: list[list[float]] = []
    for t in texts:
        h = hashlib.sha512(t.encode("utf-8")).digest()
        # Expand to FAKE_DIM floats by hashing iteratively.
        buf = bytearray()
        seed = h
        while len(buf) < FAKE_DIM * 4:
            seed = hashlib.sha512(seed).digest()
            buf.extend(seed)
        floats = []
        for i in range(FAKE_DIM):
            (v,) = struct.unpack_from("f", buf, i * 4)
            # Clamp weird NaN/Inf from random bytes.
            if not math.isfinite(v):
                v = 0.0
            floats.append(v)
        norm = math.sqrt(sum(x * x for x in floats)) or 1.0
        vectors.append([x / norm for x in floats])
    return vectors


def _openai_embed(texts: list[str], model: str) -> tuple[list[list[float]], list[str]]:
    """Call OpenAI embeddings. Returns (vectors, errors)."""
    errors: list[str] = []
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        errors.append("openai package not installed")
        return [], errors
    try:
        client = OpenAI()
        response = client.embeddings.create(model=model, input=texts)
        vectors = [list(item.embedding) for item in response.data]
        return vectors, errors
    except Exception as exc:  # pragma: no cover - network paths
        errors.append(f"openai error: {exc}")
        return [], errors


def embed_texts(
    db: Database,
    texts: list[str],
    *,
    provider: str | None = None,
    model: str | None = None,
    use_cache: bool = True,
) -> EmbeddingResult:
    """Return an embedding for each input text.

    - Normalizes each input (whitespace collapse) before hashing for the cache.
    - Uses content-hash cache (migration 051): same (provider, model, hash) →
      reuse vector, no provider call.
    - Falls back to the `fake` provider whenever no API key is set or the
      selected provider fails, so callers never see None.
    """
    p_env, m_env = _select_provider()
    provider = (provider or p_env).lower()
    model = model or m_env

    if not texts:
        return EmbeddingResult(provider=provider, model=model, vectors=[], dim=0)

    # Cache lookup.
    cached = (
        read_cached(db, provider=provider, model=model, texts=texts)
        if use_cache
        else {}
    )
    hits = 0
    misses_indices: list[int] = []
    vectors: list[list[float] | None] = [None] * len(texts)
    for i, t in enumerate(texts):
        h = content_hash(t)
        vec = cached.get(h)
        if vec is not None:
            vectors[i] = vec
            hits += 1
        else:
            misses_indices.append(i)

    errors: list[str] = []
    if misses_indices:
        miss_texts = [texts[i] for i in misses_indices]
        if provider == "openai":
            raw, err = _openai_embed(miss_texts, model)
            errors.extend(err)
            if not raw:
                # Fall back to fake so the caller still gets usable vectors.
                logger.warning(
                    "openai embed failed (%s); falling back to fake provider",
                    errors,
                )
                provider = "fake"
                model = "fake-v1"
                raw = _fake_embed(miss_texts)
        elif provider == "fake":
            raw = _fake_embed(miss_texts)
        else:
            errors.append(f"unknown provider: {provider}")
            raw = _fake_embed(miss_texts)
            provider = "fake"
            model = "fake-v1"

        for idx, vec in zip(misses_indices, raw):
            vectors[idx] = vec

        if use_cache:
            write_cached(
                db,
                provider=provider,
                model=model,
                pairs=list(zip(miss_texts, raw)),
            )

    final_vectors: list[list[float]] = [v if v is not None else [] for v in vectors]
    dim = len(next((v for v in final_vectors if v), []))
    return EmbeddingResult(
        provider=provider,
        model=model,
        vectors=final_vectors,
        dim=dim,
        cache_hits=hits,
        cache_misses=len(misses_indices),
        errors=errors,
    )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain Python cosine. Returns 0 for degenerate inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
