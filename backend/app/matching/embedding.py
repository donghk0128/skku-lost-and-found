"""Generate and maintain post text embeddings with the Gemini API."""

import hashlib
import logging
from math import isfinite, sqrt

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.matching.model import PostEmbedding
from app.posts.model import Post

MODEL = "gemini-embedding-001"
DIMENSIONS = 768
logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """The embedding API did not return a usable vector."""


def post_text(post: Post) -> str:
    parts = [
        f"물건: {post.item_name}" if post.item_name else "",
        f"제목: {post.title}",
        f"설명: {post.description}",
    ]
    # Keep requests within the model input limit for ordinary post descriptions.
    return "\n".join(part for part in parts if part)[:1800]


def embed_text(text: str, api_key: str, timeout_seconds: float) -> list[float]:
    try:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent",
            headers={"x-goog-api-key": api_key},
            json={
                "model": f"models/{MODEL}",
                "content": {"parts": [{"text": text}]},
                "taskType": "SEMANTIC_SIMILARITY",
                "outputDimensionality": DIMENSIONS,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        values = response.json()["embedding"]["values"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        raise EmbeddingError("Gemini embedding request failed") from error

    if not isinstance(values, list) or len(values) != DIMENSIONS:
        raise EmbeddingError("Gemini returned an unexpected embedding size")
    try:
        vector = [float(value) for value in values]
    except (TypeError, ValueError) as error:
        raise EmbeddingError("Gemini returned invalid embedding values") from error
    if not all(isfinite(value) for value in vector):
        raise EmbeddingError("Gemini returned non-finite embedding values")
    length = sqrt(sum(value * value for value in vector))
    if length == 0:
        raise EmbeddingError("Gemini returned a zero embedding")
    # Gemini embedding 001 needs normalization when output is truncated to 768.
    return [value / length for value in vector]


def sync_post_embedding(db: Session, post: Post) -> bool:
    """Update a changed vector; keep post writes available if Gemini fails."""
    text = post_text(post)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = db.get(PostEmbedding, post.id)
    if existing is not None and existing.model == MODEL and existing.content_hash == content_hash:
        return True

    settings = get_settings()
    if not settings.gemini_api_key:
        if existing is not None:
            db.delete(existing)
        return False

    try:
        vector = embed_text(text, settings.gemini_api_key, settings.gemini_embedding_timeout_seconds)
    except EmbeddingError:
        logger.warning("Post embedding unavailable for post %s; using rule-based recommendations", post.id)
        if existing is not None:
            db.delete(existing)
        return False

    if existing is None:
        db.add(PostEmbedding(post_id=post.id, model=MODEL, content_hash=content_hash, embedding=vector))
    else:
        existing.model = MODEL
        existing.content_hash = content_hash
        existing.embedding = vector
    return True

