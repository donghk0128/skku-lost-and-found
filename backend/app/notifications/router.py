"""Register only devices attached to a live, proven login session."""

from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session
from typing import Literal

from app.auth.service import AuthService, get_current_user, _is_after_or_equal_now
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.security import verify_secret
from app.notifications.model import PushDevice
from app.users.model import User, UserSession, now_utc

router = APIRouter(prefix="/users/me/push-devices", tags=["notifications"])


class DeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: UUID
    platform: Literal["android", "ios"]
    fid: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$", repr=False)
    refresh_token: str = Field(min_length=1, max_length=4096, repr=False)


@router.post("", status_code=204)
def register_device(
    request: DeviceRegistration, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    payload = AuthService._decode_refresh_token(request.refresh_token)
    session = db.get(UserSession, UUID(payload["sid"]))
    if (session is None or session.user_id != user.id or session.revoked_at is not None
        or not _is_after_or_equal_now(session.expires_at)
        or not verify_secret(request.refresh_token, session.refresh_token_hash)):
        raise ApiError(401, "invalid_refresh_token", "로그인 세션이 만료되었거나 유효하지 않습니다.")
    digest = sha256(request.fid.encode()).hexdigest()
    # Serialize concurrent registrations of the same installation/token across accounts.
    if db.bind.dialect.name == "postgresql":
        keys = sorted({str(request.installation_id), digest})
        for key in keys:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
    duplicate = db.scalar(select(PushDevice).where(PushDevice.fid_hash == digest).with_for_update())
    if duplicate is not None and duplicate.id != request.installation_id:
        db.delete(duplicate)
        db.flush()
    row = db.scalar(select(PushDevice).where(PushDevice.id == request.installation_id).with_for_update())
    if row is None:
        row = PushDevice(id=request.installation_id)
        db.add(row)
    if row.fid_hash != digest or row.user_id != user.id or row.session_id != session.id or not row.enabled:
        row.generation = uuid4()
    row.user_id, row.session_id = user.id, session.id
    row.fid, row.fid_hash, row.platform = request.fid, digest, request.platform
    row.enabled, row.updated_at = True, now_utc()
    db.commit()
    return Response(status_code=204)


@router.delete("/{installation_id}", status_code=204)
def unregister_device(
    installation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    db.execute(delete(PushDevice).where(PushDevice.id == installation_id, PushDevice.user_id == user.id))
    db.commit()
    return Response(status_code=204)
