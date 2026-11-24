"""Freeze recipients at post creation; deliver only after the transaction commits."""

from collections import defaultdict
from datetime import timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.notifications.model import PushDelivery, PushDevice, PushNotification
from app.posts.filters import PostFilterConditions, post_filter_expressions
from app.posts.model import Post
from app.users.model import KeywordCondition, UserSession, now_utc


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def enqueue_post_notifications(db: Session, post: Post) -> None:
    """Called exactly once on create, inside the post transaction, never on edit."""
    if not get_settings().push_enabled:
        return
    conditions = db.scalars(select(KeywordCondition).where(
        KeywordCondition.notification_enabled.is_(True),
        KeywordCondition.post_type == post.post_type,
        KeywordCondition.user_id != post.author_id,
        KeywordCondition.created_at <= post.created_at,
        KeywordCondition.notification_enabled_at <= post.created_at,
    )).all()
    recipients = defaultdict(list)
    for condition in conditions:
        filters = PostFilterConditions.model_validate(condition.conditions)
        if db.scalar(select(Post.id).where(Post.id == post.id, *post_filter_expressions(filters))) is not None:
            recipients[condition.user_id].append(str(condition.id))
    if not recipients:
        return
    devices = db.scalars(select(PushDevice).join(UserSession, PushDevice.session_id == UserSession.id).where(
        PushDevice.user_id.in_(recipients), PushDevice.enabled.is_(True),
        UserSession.revoked_at.is_(None), UserSession.expires_at > now_utc(),
    )).all()
    by_user = defaultdict(list)
    for device in devices:
        by_user[device.user_id].append(device)
    for user_id, rows in by_user.items():
        notification = PushNotification(
            user_id=user_id, post_id=post.id, condition_ids=recipients[user_id],
            title="저장한 조건에 맞는 새 게시물", body=post.title[:200],
        )
        db.add(notification)
        db.flush()
        for device in rows:
            db.add(PushDelivery(notification_id=notification.id, device_id=device.id, device_generation=device.generation))


def deliver_next(db: Session, sender) -> bool:
    """Row locks allow multiple workers. A rollback leaves the work retryable."""
    settings = get_settings()
    if not settings.push_enabled:
        return False
    now = now_utc()
    delivery = db.scalar(select(PushDelivery).where(
        PushDelivery.status == "PENDING", PushDelivery.next_attempt_at <= now,
    ).order_by(PushDelivery.next_attempt_at, PushDelivery.id).limit(1)
        .with_for_update(skip_locked=True, of=PushDelivery))
    if delivery is None:
        db.rollback()
        return False
    notification = db.get(PushNotification, delivery.notification_id)
    device = db.scalar(select(PushDevice).where(PushDevice.id == delivery.device_id).with_for_update())
    post = db.get(Post, notification.post_id) if notification else None
    session = db.get(UserSession, device.session_id) if device else None
    eligible = bool(
        notification and device and post and session and device.enabled
        and device.user_id == notification.user_id and device.generation == delivery.device_generation
        and session.revoked_at is None and aware(session.expires_at) > now
        and post.deleted_at is None and post.status == "OPEN" and post.author_id != notification.user_id
        and aware(notification.created_at) + timedelta(seconds=settings.push_ttl_seconds) > now
    )
    if eligible:
        # A deleted/disabled condition or a later re-enable must not release old work.
        ids = [UUID(value) for value in notification.condition_ids]
        eligible = db.scalar(select(KeywordCondition.id).where(
            KeywordCondition.id.in_(ids), KeywordCondition.user_id == notification.user_id,
            KeywordCondition.notification_enabled.is_(True),
            KeywordCondition.notification_enabled_at <= post.created_at,
        ).limit(1)) is not None
    if not eligible:
        delivery.status = "CANCELLED"
        db.commit()
        return True
    from app.notifications.sender import PushSendError

    delivery.attempts += 1
    try:
        sender.send(device.fid, notification)
    except PushSendError as error:
        # Never store SDK messages: they may contain tokens or credential details.
        delivery.last_error = error.code[:64]
        if error.invalid_device:
            device.enabled = False
        if error.permanent or delivery.attempts >= settings.push_max_attempts:
            delivery.status = "FAILED"
        else:
            delay = max(error.retry_after, min(3600, 60 * 2 ** (delivery.attempts - 1)))
            delivery.next_attempt_at = now + timedelta(seconds=delay)
    else:
        delivery.status, delivery.sent_at, delivery.last_error = "SENT", now_utc(), None
    db.commit()
    return True
