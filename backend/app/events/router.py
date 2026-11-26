from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.events.schemas import EventAccepted, EventCreate
from app.events.service import store_client_event
from app.matching.model import RecommendationItem, RecommendationRun
from app.core.errors import ApiError
from app.posts.model import Post
from app.users.model import User

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventAccepted, status_code=202)
def collect_event(event: EventCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EventAccepted:
    if event.event_type in ("recommendation_impression", "recommendation_click"):
        run = db.get(RecommendationRun, event.run_id)
        item = db.get(RecommendationItem, (event.run_id, event.candidate_post_id))
        source = db.get(Post, event.source_post_id)
        if (run is None or item is None or run.source_post_id != event.source_post_id
                or item.rank != event.rank or source is None or source.author_id != user.id):
            raise ApiError(422, "invalid_recommendation_event", "추천 실행 정보가 일치하지 않습니다.")
    return EventAccepted(event_id=event.event_id, accepted=store_client_event(db, user.id, event))
