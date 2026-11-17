"""Authenticated HTTP and resumable WebSocket chat endpoints."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.chat.model import ChatMessage, ChatMessageImage
from app.chat.schemas import (MessageListResponse, MessageResponse, ReadUpdate, RoomClose, RoomCreate,
                              RoomListResponse, RoomResponse, TextMessageCreate, VisibilityUpdate)
from app.chat.service import ChatService, get_chat_image_storage, message_response
from app.core.database import get_db
from app.core.errors import ApiError
from app.users.model import User

router = APIRouter(prefix="/chat/rooms", tags=["chat"])


@router.post("", response_model=RoomResponse)
def create_room(request: RoomCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.create(db, request.post_id, user.id)


@router.get("", response_model=RoomListResponse)
def list_rooms(include_hidden: bool = False, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = ChatService.list_rooms(db, user.id, include_hidden, limit, offset)
    return RoomListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.room_response(db, *ChatService.member_room(db, room_id, user.id))


@router.post("/{room_id}/close", response_model=RoomResponse)
def close_room(room_id: UUID, request: RoomClose, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.close(db, room_id, user.id, request.reason)


@router.patch("/{room_id}/read", response_model=RoomResponse)
def read_room(room_id: UUID, request: ReadUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.read(db, room_id, user.id, request.sequence)


@router.patch("/{room_id}/visibility", response_model=RoomResponse)
def hide_room(room_id: UUID, request: VisibilityUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.visibility(db, room_id, user.id, request.is_hidden)


@router.get("/{room_id}/messages", response_model=MessageListResponse)
def list_messages(room_id: UUID, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = ChatService.messages(db, room_id, user.id, after, limit + 1)
    items = [message_response(row) for row in rows[:limit]]
    return MessageListResponse(items=items, next_after=items[-1].sequence if items else after, has_more=len(rows) > limit)


@router.post("/{room_id}/messages", response_model=MessageResponse, status_code=201)
def send_text(room_id: UUID, request: TextMessageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatService.send(db, room_id, user.id, request.content, client_message_id=request.client_message_id)


@router.post("/{room_id}/images", response_model=MessageResponse, status_code=201)
def send_image(room_id: UUID, files: list[UploadFile] | None = File(None), file: UploadFile | None = File(None),
               content: str | None = Form(None, max_length=2000), client_message_id: str | None = Form(None, min_length=1, max_length=64),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ChatService.member_room(db, room_id, user.id)
    if (files and file) or not (files or file):
        raise ApiError(422, "invalid_chat_images", "보낼 사진을 선택해 주세요.")
    images = []
    total = 0
    for upload in files or [file]:
        data = upload.file.read(ChatService.MAX_IMAGE_BYTES + 1)
        total += len(data)
        if total > ChatService.MAX_UPLOAD_BYTES:
            raise ApiError(422, "chat_images_too_large", "한 번에 보내는 사진은 총 50MiB 이하여야 합니다.")
        images.append((data, upload.content_type or ""))
    return ChatService.send(db, room_id, user.id, content=content, images=images, client_message_id=client_message_id)


@router.get("/{room_id}/messages/{message_id}/image")
def get_image(room_id: UUID, message_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ChatService.member_room(db, room_id, user.id)
    message = db.get(ChatMessage, message_id)
    if message is None or message.room_id != room_id or message.message_type != "IMAGE" or not message.images:
        raise ApiError(404, "chat_image_not_found", "사진을 찾을 수 없습니다.")
    return image_content(message.images[0])


def image_content(image: ChatMessageImage) -> Response:
    return Response(get_chat_image_storage().download(image.storage_key), media_type=image.content_type,
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{room_id}/messages/{message_id}/images/{image_id}")
def get_message_image(room_id: UUID, message_id: UUID, image_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ChatService.member_room(db, room_id, user.id)
    message = db.get(ChatMessage, message_id)
    image = db.get(ChatMessageImage, image_id)
    if message is None or message.room_id != room_id or image is None or image.message_id != message_id:
        raise ApiError(404, "chat_image_not_found", "사진을 찾을 수 없습니다.")
    return image_content(image)


def socket_step(db_factory, token: str, room_id: UUID, after: int, content: str | None = None, client_message_id: str | None = None):
    # Use the same dependency override as HTTP tests, and close each DB transaction
    # before awaiting network I/O. No connection is held for an idle socket.
    generator = db_factory()
    db = next(generator)
    try:
        user = get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db)
        if content is not None:
            ChatService.send(db, room_id, user.id, content, client_message_id=client_message_id)
        room, _ = ChatService.member_room(db, room_id, user.id)
        messages = ChatService.messages(db, room_id, user.id, after, 100)
        return [message_response(row).model_dump(mode="json") for row in messages], room.status, room.close_reason
    finally:
        generator.close()


@router.websocket("/{room_id}/ws")
async def room_socket(websocket: WebSocket, room_id: UUID, after: int = Query(0, ge=0)):
    """First frame: {"token": "access JWT"}. Subsequent frames: {"content": "..."}."""
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        if len(first) > 8192:
            raise ApiError(401, "invalid_token", "유효하지 않은 인증 정보입니다.")
        auth = json.loads(first)
        token = auth.get("token") if isinstance(auth, dict) else None
        if not isinstance(token, str) or not token:
            raise ApiError(401, "authentication_required", "로그인이 필요합니다.")
        db_factory = websocket.app.dependency_overrides.get(get_db, get_db)
        pending = None
        while True:
            messages, room_status, reason = await run_in_threadpool(
                socket_step, db_factory, token, room_id, after,
                pending.content if pending else None, pending.client_message_id if pending else None,
            )
            pending = None
            for message in messages:
                await websocket.send_json({"type": "message", "message": message})
                after = message["sequence"]
            if len(messages) == 100:
                continue
            if room_status == "CLOSED":
                await websocket.send_json({"type": "room_closed", "reason": reason})
                await websocket.close(code=1000)
                return
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                if len(raw) > 16384:
                    await websocket.close(code=1009)
                    return
                pending = TextMessageCreate.model_validate_json(raw)
            except asyncio.TimeoutError:
                continue
            except ValidationError:
                await websocket.send_json({"type": "error", "error": {"code": "validation_error", "message": "메시지는 content 필드에 1~2000자로 입력해 주세요."}})
    except WebSocketDisconnect:
        return
    except ApiError as error:
        await websocket.send_json({"type": "error", "error": {"code": error.code, "message": error.message}})
        await websocket.close(code=4401 if error.status_code == 401 else 4404 if error.status_code == 404 else 4409)
    except (asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(code=4401)
