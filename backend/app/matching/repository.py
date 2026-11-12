"""Database queries for recommendation candidates."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.matching.model import PostEmbedding
from app.posts.model import Post


class MatchingRepository:
    @staticmethod
    def cosine_similarities(db: Session, source: Post, candidate_ids: list[UUID]) -> dict[UUID, float]:
        """Compute all available similarities in PostgreSQL with pgvector."""
        if not candidate_ids or db.get_bind().dialect.name != "postgresql":
            return {}
        source_embedding = db.get(PostEmbedding, source.id)
        if source_embedding is None:
            return {}
        # Supabase and our migration install pgvector in the extensions schema.
        # Its distance operator must be visible in the current transaction.
        db.execute(text("SET LOCAL search_path TO public, extensions"))
        similarity = (1 - PostEmbedding.embedding.cosine_distance(source_embedding.embedding)).label("similarity")
        statement = select(PostEmbedding.post_id, similarity).where(
            PostEmbedding.post_id.in_(candidate_ids),
            PostEmbedding.model == source_embedding.model,
        )
        return {
            post_id: max(0.0, min(1.0, float(score)))
            for post_id, score in db.execute(statement).all()
            if score is not None
        }

    @staticmethod
    def list_candidates(db: Session, source: Post) -> list[Post]:
        opposite_type = "FOUND" if source.post_type == "LOST" else "LOST"
        statement = select(Post).where(
            Post.post_type == opposite_type,
            Post.status == "OPEN",
            Post.deleted_at.is_(None),
        )
        return list(db.scalars(statement).all())
