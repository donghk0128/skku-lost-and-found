"""Chat rules. All mutations lock post first, then room, in a single transaction."""

from pathlib import Path
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chat.model import ChatMessage, ChatMessageImage, ChatRoom, ChatRoomMember, ReturnPair
from app.chat.schemas import MessageImageResponse, MessageResponse, RoomResponse, ReturnPairResponse
from app.core.config import get_settings
from app.core.errors import ApiError
from app.posts.model import Post, now_utc
from app.posts.storage import LocalPostImageStorage
from app.users.model import User


def get_chat_image_storage() -> LocalPostImageStorage:
    # A private subdirectory of the existing persistent image volume.
    return LocalPostImageStorage(Path(get_settings().post_image_dir) / "chat")


def lock_post(db: Session, post_id: UUID) -> Post:
    post = db.scalar(select(Post).where(Post.id == post_id).with_for_update().execution_options(populate_existing=True))
    if post is None:
        raise ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다.")
    return post


def close_post_rooms(db: Session, post_id: UUID, reason: str = "POST_COMPLETED") -> None:
    for room in db.scalars(select(ChatRoom).where(ChatRoom.post_id == post_id, ChatRoom.status == "ACTIVE").with_for_update()):
        room.status, room.close_reason, room.closed_at = "CLOSED", reason, now_utc()
        pending = db.scalar(select(ReturnPair).where(ReturnPair.room_id == room.id, ReturnPair.status == "PENDING"))
        if pending is not None:
            db.delete(pending)


def message_response(message: ChatMessage) -> MessageResponse:
    images = [MessageImageResponse(
        id=image.id, position=image.position, content_type=image.content_type,
        image_url=f"/api/v1/chat/rooms/{message.room_id}/messages/{message.id}/images/{image.id}",
    ) for image in message.images]
    return MessageResponse(
        **{name: getattr(message, name) for name in ("id", "room_id", "sender_id", "sequence", "message_type", "content", "created_at", "client_message_id")},
        images=images, image_url=images[0].image_url if images else None,
        image_content_type=images[0].content_type if images else None,
    )


class ChatService:
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_UPLOAD_BYTES = 50 * 1024 * 1024

    @staticmethod
    def member_room(db: Session, room_id: UUID, user_id: UUID, *, lock: bool = False) -> tuple[ChatRoom, ChatRoomMember]:
        room = db.get(ChatRoom, room_id)
        member = db.get(ChatRoomMember, (room_id, user_id))
        if room is None or member is None or user_id not in (room.owner_id, room.requester_id):
            raise ApiError(404, "chat_room_not_found", "채팅방을 찾을 수 없습니다.")
        if lock:
            # Withdrawal may remove the post while we wait. Re-read the room after
            # the post lock instead of rejecting the surviving member's history.
            if room.post_id is not None:
                db.scalar(select(Post).where(Post.id == room.post_id).with_for_update())
            room = db.scalar(select(ChatRoom).where(ChatRoom.id == room_id).with_for_update().execution_options(populate_existing=True))
            db.refresh(member, with_for_update=True)
        return room, member

    @staticmethod
    def room_response(db: Session, room: ChatRoom, member: ChatRoomMember) -> RoomResponse:
        post = db.get(Post, room.post_id) if room.post_id else None
        other_id = room.requester_id if member.user_id == room.owner_id else room.owner_id
        other = db.get(User, other_id) if other_id else None
        post_deleted = post is None or post.deleted_at is not None
        latest = db.scalar(select(ChatMessage).where(ChatMessage.room_id == room.id).order_by(ChatMessage.sequence.desc()).limit(1))
        unread = db.scalar(select(func.count()).select_from(ChatMessage).where(
            ChatMessage.room_id == room.id, or_(ChatMessage.sender_id.is_(None), ChatMessage.sender_id != member.user_id),
            ChatMessage.sequence > member.last_read_sequence,
        )) or 0
        return RoomResponse(
            **{name: getattr(room, name) for name in ("id", "post_id", "owner_id", "requester_id", "status", "close_reason", "closed_at", "created_at")},
            last_read_sequence=member.last_read_sequence, last_read_at=member.last_read_at,
            post_title="삭제된 게시물입니다." if post_deleted else post.title,
            post_deleted=post_deleted, other_withdrawn=other is None,
            other_nickname="탈퇴한 사용자" if other is None else other.nickname,
            is_hidden=member.is_hidden, unread_count=unread,
            last_message=message_response(latest) if latest else None,
            return_pair=(ReturnPairResponse.model_validate({
                "id": pair.id, "lost_post_id": pair.lost_post_id, "found_post_id": pair.found_post_id,
                "counterpart_post_title": (counterpart.title if (counterpart := db.get(
                    Post, pair.found_post_id if post and post.post_type == "LOST" else pair.lost_post_id
                )) else "삭제된 게시물입니다."),
                "proposed_by_id": pair.proposed_by_id, "status": pair.status, "confirmed_at": pair.confirmed_at,
            }) if (pair := db.scalar(select(ReturnPair).where(ReturnPair.room_id == room.id))) else None),
        )

    @staticmethod
    def create(db: Session, post_id: UUID, user_id: UUID) -> RoomResponse:
        post = lock_post(db, post_id)
        if post.deleted_at is not None:
            raise ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다.")
        if post.author_id == user_id:
            raise ApiError(422, "self_chat", "본인 게시글에는 채팅을 시작할 수 없습니다.")
        existing = db.scalar(select(ChatRoom).where(ChatRoom.post_id == post_id, ChatRoom.requester_id == user_id))
        if existing is not None:
            member = db.get(ChatRoomMember, (existing.id, user_id))
            member.is_hidden = False
            db.commit()
            return ChatService.room_response(db, existing, member)
        if post.status != "OPEN":
            raise ApiError(409, "post_completed", "완료된 게시글에는 채팅을 시작할 수 없습니다.")
        room = ChatRoom(post_id=post_id, owner_id=post.author_id, requester_id=user_id)
        db.add(room)
        db.flush()
        members = [ChatRoomMember(room_id=room.id, user_id=uid) for uid in (post.author_id, user_id)]
        db.add_all(members)
        db.commit()
        return ChatService.room_response(db, room, members[1])

    @staticmethod
    def list_rooms(db: Session, user_id: UUID, include_hidden: bool, limit: int, offset: int) -> tuple[list[RoomResponse], int]:
        filters = [ChatRoomMember.user_id == user_id]
        if not include_hidden:
            filters.append(ChatRoomMember.is_hidden.is_(False))
        total = db.scalar(select(func.count()).select_from(ChatRoomMember).where(*filters)) or 0
        last_sent = select(func.max(ChatMessage.created_at)).where(ChatMessage.room_id == ChatRoom.id).correlate(ChatRoom).scalar_subquery()
        rows = db.execute(select(ChatRoom, ChatRoomMember).join(ChatRoomMember).where(*filters)
            .order_by(func.coalesce(last_sent, ChatRoom.created_at).desc(), ChatRoom.id.desc()).limit(limit).offset(offset)).all()
        return [ChatService.room_response(db, room, member) for room, member in rows], total

    @staticmethod
    def messages(db: Session, room_id: UUID, user_id: UUID, after: int, limit: int) -> list[ChatMessage]:
        ChatService.member_room(db, room_id, user_id)
        return list(db.scalars(select(ChatMessage).where(ChatMessage.room_id == room_id, ChatMessage.sequence > after)
            .order_by(ChatMessage.sequence).limit(limit)).all())

    @staticmethod
    def send(db: Session, room_id: UUID, user_id: UUID, content: str | None = None,
             image: bytes | None = None, content_type: str | None = None,
             images: list[tuple[bytes, str]] | None = None, client_message_id: str | None = None) -> MessageResponse:
        room, _ = ChatService.member_room(db, room_id, user_id, lock=True)
        uploads = images if images is not None else ([(image, content_type or "")] if image is not None else [])
        content = content.strip() if content is not None else None
        content = content or None
        if content is not None and len(content) > 2000:
            raise ApiError(422, "invalid_message", "메시지는 1~2000자로 입력해 주세요.")
        if not uploads and content is None:
            raise ApiError(422, "invalid_message", "메시지 또는 사진을 선택해 주세요.")
        if sum(len(data) for data, _ in uploads) > ChatService.MAX_UPLOAD_BYTES:
            raise ApiError(422, "chat_images_too_large", "한 번에 보내는 사진은 총 50MiB 이하여야 합니다.")
        from app.posts.service import PostService
        validated = []
        fingerprint = sha256((content or "").encode())
        for data, mime in uploads:
            image_type = PostService.IMAGE_TYPES.get(mime)
            if not data or len(data) > ChatService.MAX_IMAGE_BYTES or image_type is None or not image_type[1](data):
                raise ApiError(422, "invalid_chat_image", "JPEG, PNG, WebP 사진(장당 최대 5MiB)을 선택해 주세요.")
            fingerprint.update(mime.encode())
            fingerprint.update(len(data).to_bytes(8, "big"))
            fingerprint.update(data)
            validated.append((data, mime, image_type[0]))
        digest = fingerprint.hexdigest()
        if client_message_id is not None:
            if not 1 <= len(client_message_id) <= 64:
                raise ApiError(422, "invalid_client_message_id", "전송 식별자가 올바르지 않습니다.")
            existing = db.scalar(select(ChatMessage).where(
                ChatMessage.room_id == room_id, ChatMessage.sender_id == user_id,
                ChatMessage.client_message_id == client_message_id,
            ))
            if existing is not None:
                if existing.upload_fingerprint != digest:
                    raise ApiError(409, "message_payload_conflict", "전송 내용이 변경되었습니다. 다시 전송해 주세요.")
                return message_response(existing)
        if room.status != "ACTIVE":
            raise ApiError(409, "chat_room_closed", "종료된 채팅방에는 메시지를 보낼 수 없습니다.")
        sequence = (db.scalar(select(func.max(ChatMessage.sequence)).where(ChatMessage.room_id == room_id)) or 0) + 1
        message = ChatMessage(
            room_id=room_id, sender_id=user_id, sequence=sequence,
            message_type="IMAGE" if uploads else "TEXT", content=content,
            client_message_id=client_message_id, upload_fingerprint=digest if client_message_id else None,
        )
        storage = get_chat_image_storage() if uploads else None
        written = []
        try:
            for position, (data, mime, extension) in enumerate(validated):
                key = f"{room_id}/{uuid4()}{extension}"
                storage.upload(key, data, mime)
                written.append(key)
                message.images.append(ChatMessageImage(storage_key=key, content_type=mime, position=position))
            db.add(message)
            db.flush()
            from app.notifications.service import enqueue_chat_notification
            enqueue_chat_notification(db, room, message)
            db.commit()
        except Exception:
            db.rollback()
            for key in written:
                try:
                    storage.delete(key)
                except ApiError:
                    pass
            raise
        return message_response(message)

    @staticmethod
    def close(db: Session, room_id: UUID, user_id: UUID, reason: str) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        pending = db.scalar(select(ReturnPair).where(ReturnPair.room_id == room_id, ReturnPair.status == "PENDING"))
        if pending is not None:
            raise ApiError(409, "return_pair_pending", "반환 게시글 확인 요청을 먼저 처리해 주세요.")
        if room.status == "CLOSED":
            if room.close_reason != reason:
                raise ApiError(409, "chat_room_closed", "이미 다른 사유로 종료된 채팅방입니다.")
        else:
            room.status, room.close_reason, room.closed_at = "CLOSED", reason, now_utc()
            if reason == "RETURNED":
                db.get(Post, room.post_id).status = "COMPLETED"
                db.flush()
                close_post_rooms(db, room.post_id)
        db.commit()
        return ChatService.room_response(db, room, member)

    @staticmethod
    def pair_candidates(db: Session, room_id: UUID, user_id: UUID) -> list[Post]:
        room, _ = ChatService.member_room(db, room_id, user_id)
        primary = db.get(Post, room.post_id) if room.post_id else None
        if room.status != "ACTIVE" or primary is None or primary.status != "OPEN":
            return []
        return list(db.scalars(select(Post).where(
            Post.author_id == room.requester_id, Post.post_type != primary.post_type,
            Post.status == "OPEN", Post.deleted_at.is_(None), Post.id != primary.id,
        ).order_by(Post.created_at.desc()).limit(100)))

    @staticmethod
    def propose_pair(db: Session, room_id: UUID, user_id: UUID, counterpart_post_id: UUID) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        if room.status != "ACTIVE":
            raise ApiError(409, "chat_room_closed", "종료된 채팅방입니다.")
        existing = db.scalar(select(ReturnPair).where(ReturnPair.room_id == room_id))
        if existing is not None:
            primary = db.get(Post, room.post_id)
            existing_counterpart_id = existing.found_post_id if primary.post_type == "LOST" else existing.lost_post_id
            if existing.proposed_by_id == user_id and counterpart_post_id == existing_counterpart_id:
                return ChatService.room_response(db, room, member)
            raise ApiError(409, "return_pair_pending", "이미 확인 요청이 있습니다.")
        if counterpart_post_id not in {p.id for p in ChatService.pair_candidates(db, room_id, user_id)}:
            raise ApiError(422, "invalid_return_pair", "상대방의 진행 중인 반대 유형 게시글을 선택해 주세요.")
        primary = db.get(Post, room.post_id)
        pair = ReturnPair(
            room_id=room_id, proposed_by_id=user_id,
            lost_post_id=primary.id if primary.post_type == "LOST" else counterpart_post_id,
            found_post_id=primary.id if primary.post_type == "FOUND" else counterpart_post_id,
        )
        db.add(pair)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ApiError(409, "return_pair_pending", "이미 확인 요청이 있습니다.")
        return ChatService.room_response(db, room, member)

    @staticmethod
    def reject_pair(db: Session, room_id: UUID, user_id: UUID) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        pair = db.scalar(select(ReturnPair).where(ReturnPair.room_id == room_id, ReturnPair.status == "PENDING"))
        if pair is None:
            raise ApiError(404, "return_pair_not_found", "확인 요청이 없습니다.")
        db.delete(pair)
        db.commit()
        return ChatService.room_response(db, room, member)

    @staticmethod
    def confirm_pair(db: Session, room_id: UUID, user_id: UUID) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        pair = db.scalar(select(ReturnPair).where(ReturnPair.room_id == room_id).with_for_update())
        if pair is None:
            raise ApiError(404, "return_pair_not_found", "확인 요청이 없습니다.")
        if pair.status == "CONFIRMED":
            return ChatService.room_response(db, room, member)
        if user_id == pair.proposed_by_id:
            raise ApiError(403, "self_confirmation", "상대방의 확인이 필요합니다.")
        primary = db.get(Post, room.post_id)
        counterpart_id = pair.found_post_id if primary.post_type == "LOST" else pair.lost_post_id
        counterpart = lock_post(db, counterpart_id)
        if (room.status != "ACTIVE" or primary.status != "OPEN" or counterpart.status != "OPEN"
                or counterpart.deleted_at is not None):
            raise ApiError(409, "return_pair_unavailable", "게시글 상태가 변경되어 확인할 수 없습니다.")
        if {primary.author_id, counterpart.author_id} != {room.owner_id, room.requester_id}:
            raise ApiError(409, "return_pair_unavailable", "채팅 참여자의 게시글이 아닙니다.")
        now = now_utc()
        pair.status, pair.confirmed_at = "CONFIRMED", now
        primary.status = counterpart.status = "COMPLETED"
        room.status, room.close_reason, room.closed_at = "CLOSED", "RETURNED", now
        db.flush()
        close_post_rooms(db, primary.id)
        close_post_rooms(db, counterpart.id)
        db.commit()
        return ChatService.room_response(db, room, member)

    @staticmethod
    def read(db: Session, room_id: UUID, user_id: UUID, sequence: int) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        latest = db.scalar(select(func.max(ChatMessage.sequence)).where(ChatMessage.room_id == room_id)) or 0
        if sequence > latest:
            raise ApiError(422, "invalid_read_sequence", "존재하는 메시지까지만 읽음 처리할 수 있습니다.")
        if sequence > member.last_read_sequence:
            member.last_read_sequence, member.last_read_at = sequence, now_utc()
        db.commit()
        return ChatService.room_response(db, room, member)

    @staticmethod
    def visibility(db: Session, room_id: UUID, user_id: UUID, hidden: bool) -> RoomResponse:
        room, member = ChatService.member_room(db, room_id, user_id, lock=True)
        if hidden and room.status != "CLOSED":
            raise ApiError(409, "active_chat_room", "채팅방을 종료한 후 숨길 수 있습니다.")
        member.is_hidden = hidden
        db.commit()
        return ChatService.room_response(db, room, member)
