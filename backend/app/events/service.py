"""Best-effort event storage, isolated from the operation that generated it."""

import logging
from datetime import datetime, timezone
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.events.model import EventLog
from app.events.schemas import EventCreate

logger = logging.getLogger(__name__)


def store_client_event(db: Session, user_id: UUID, event: EventCreate) -> bool:
    """Return False for a duplicate or storage error; never fail the user's action."""
    properties = event.model_dump(include={
        "screen", "category_id", "has_query", "has_title_terms", "has_content_terms",
        "has_location_terms", "has_event_time",
    }, exclude_none=True)
    row = EventLog(
        id=event.event_id, user_id=user_id, event_type=event.event_type,
        occurred_at=event.occurred_at.astimezone(timezone.utc), visit_id=event.visit_id,
        post_id=event.post_id, source_post_id=event.source_post_id,
        candidate_post_id=event.candidate_post_id, run_id=event.run_id,
        rank=event.rank, properties=properties,
    )
    try:
        db.add(row)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception:
        db.rollback()
        logger.exception("Event storage failed")
        return False


def record_business_event(db: Session, user_id: UUID, event_type: str, resource_id: UUID,
                          *, post_id: UUID | None = None, source_post_id: UUID | None = None,
                          candidate_post_id: UUID | None = None, properties: dict | None = None) -> None:
    """Call only after the business transaction committed."""
    try:
        db.add(EventLog(
            id=uuid5(NAMESPACE_URL, f"skku-finder:{event_type}:{resource_id}"),
            user_id=user_id, event_type=event_type,
            occurred_at=datetime.now(timezone.utc), post_id=post_id,
            source_post_id=source_post_id, candidate_post_id=candidate_post_id,
            properties=properties or {},
        ))
        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception:
        db.rollback()
        logger.exception("Business event storage failed")
