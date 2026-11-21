"""Password -> email proof -> hard account removal with retained peer chats."""
import logging
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.auth.service import MAX_VERIFICATION_ATTEMPTS
from app.chat.model import ChatMessage, ChatMessageImage, ChatRoom, ChatRoomMember
from app.chat.service import get_chat_image_storage
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import hash_secret, utc_now, verify_secret
from app.email.service import EmailService
from app.matching.model import PostEmbedding, RecommendationItem, RecommendationRun
from app.posts.model import Post, PostImage
from app.posts.storage import LocalPostImageStorage, get_post_image_storage
from app.users.model import EmailVerification, FavoritePost, PasswordReset, User, UserSession, WithdrawalChallenge

logger = logging.getLogger(__name__)
DeletionTarget = tuple[LocalPostImageStorage, str, str]


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=utc_now().tzinfo) if value.tzinfo is None else value


class WithdrawalService:
    @staticmethod
    def start(db: Session, user: User, password: str) -> tuple[str, datetime]:
        if not verify_secret(password, user.password_hash):
            raise ApiError(400, "invalid_current_password", "현재 비밀번호가 올바르지 않습니다.")
        token = secrets.token_urlsafe(32)
        db.execute(delete(WithdrawalChallenge).where(WithdrawalChallenge.user_id == user.id))
        expires = utc_now() + timedelta(minutes=10)
        db.add(WithdrawalChallenge(user_id=user.id, token_hash=sha256(token.encode()).hexdigest(),
            credential_digest=sha256(user.password_hash.encode()).hexdigest(), expires_at=expires))
        db.commit()
        return token, expires

    @staticmethod
    def challenge(db: Session, user: User, token: str) -> WithdrawalChallenge:
        proof = db.scalar(select(WithdrawalChallenge).where(
            WithdrawalChallenge.user_id == user.id,
            WithdrawalChallenge.token_hash == sha256(token.encode()).hexdigest(),
        ).with_for_update())
        if (proof is None or aware(proof.expires_at) <= utc_now()
                or proof.credential_digest != sha256(user.password_hash.encode()).hexdigest()):
            raise ApiError(400, "invalid_withdrawal_proof", "비밀번호 확인이 만료되었거나 유효하지 않습니다. 처음부터 다시 진행해 주세요.")
        return proof

    @staticmethod
    def send_code(db: Session, user: User, token: str) -> tuple[datetime, datetime]:
        proof = WithdrawalService.challenge(db, user, token)
        now = utc_now()
        cooldown = get_settings().email_verification_resend_seconds
        if proof.code_sent_at and (now - aware(proof.code_sent_at)).total_seconds() < cooldown:
            raise ApiError(429, "verification_resend_cooldown", "잠시 후 인증 코드를 다시 요청해 주세요.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        EmailService().send_verification_code(user.email, code)
        proof.code_hash = hash_secret(code)
        proof.code_sent_at = now
        proof.code_expires_at = min(aware(proof.expires_at), now + timedelta(minutes=get_settings().email_verification_expire_minutes))
        proof.verified_at = None
        proof.attempt_count = 0
        db.commit()
        return proof.code_expires_at, now + timedelta(seconds=cooldown)

    @staticmethod
    def verify_email(db: Session, user: User, token: str, code: str) -> datetime:
        proof = WithdrawalService.challenge(db, user, token)
        if not proof.code_hash or not proof.code_expires_at or aware(proof.code_expires_at) <= utc_now():
            raise ApiError(400, "verification_expired", "사용할 수 있는 인증 코드가 없습니다. 새 코드를 요청해 주세요.")
        if proof.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            raise ApiError(429, "verification_attempts_exceeded", "인증 시도 횟수를 초과했습니다. 새 코드를 요청해 주세요.")
        if not verify_secret(code, proof.code_hash):
            proof.attempt_count += 1
            db.commit()
            raise ApiError(400, "invalid_verification_code", "인증 코드가 올바르지 않습니다.")
        proof.verified_at = utc_now()
        db.commit()
        return proof.code_expires_at

    @staticmethod
    def withdraw(db: Session, user: User, token: str) -> None:
        proof = WithdrawalService.challenge(db, user, token)
        if not proof.verified_at or not proof.code_expires_at or aware(proof.code_expires_at) <= utc_now():
            raise ApiError(400, "withdrawal_email_not_verified", "이메일 인증을 완료한 뒤 탈퇴해 주세요.")
        try:
            files = WithdrawalService.remove_rows(db, user)
            WithdrawalService.commit_with_photo_deletion(db, files)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def remove_rows(db: Session, user: User) -> list[DeletionTarget]:
        uid, email = user.id, user.email
        related = or_(ChatRoom.owner_id == uid, ChatRoom.requester_id == uid)
        related_post_ids = select(ChatRoom.post_id).where(related)
        # Preserve the existing post -> room lock order across all affected posts.
        posts = list(db.scalars(select(Post).where(or_(Post.author_id == uid, Post.id.in_(related_post_ids)))
            .order_by(Post.id).with_for_update()))
        owned_ids = [post.id for post in posts if post.author_id == uid]
        rooms = list(db.scalars(select(ChatRoom).where(or_(related, ChatRoom.post_id.in_(owned_ids)))
            .order_by(ChatRoom.id).with_for_update().execution_options(populate_existing=True)))
        room_ids = [room.id for room in rooms]
        now = utc_now()
        for room in rooms:
            if room.status == "ACTIVE":
                room.status, room.close_reason, room.closed_at = "CLOSED", "GENERAL", now
            if room.post_id in owned_ids:
                room.post_id = None
            if room.owner_id == uid:
                room.owner_id = None
            if room.requester_id == uid:
                room.requester_id = None
        db.flush()
        db.execute(update(ChatMessage).where(ChatMessage.sender_id == uid)
            .values(sender_id=None, client_message_id=None, upload_fingerprint=None))
        db.execute(delete(ChatRoomMember).where(ChatRoomMember.user_id == uid))

        orphan_rooms = list(db.scalars(select(ChatRoom.id).where(ChatRoom.id.in_(room_ids),
            ~select(ChatRoomMember.room_id).where(ChatRoomMember.room_id == ChatRoom.id).exists())))
        orphan_messages = select(ChatMessage.id).where(ChatMessage.room_id.in_(orphan_rooms))
        chat_photos = list(db.scalars(select(ChatMessageImage).where(ChatMessageImage.message_id.in_(orphan_messages))))
        post_photos = list(db.scalars(select(PostImage).where(PostImage.post_id.in_(owned_ids))))
        files = []
        if post_photos:
            storage = get_post_image_storage()
            files.extend((storage, image.storage_key, image.content_type) for image in post_photos)
        if chat_photos:
            storage = get_chat_image_storage()
            files.extend((storage, image.storage_key, image.content_type) for image in chat_photos)
        # No counterpart remains in these rooms, so there is no retained history to serve.
        db.execute(delete(ChatMessageImage).where(ChatMessageImage.message_id.in_(orphan_messages)))
        db.execute(delete(ChatMessage).where(ChatMessage.room_id.in_(orphan_rooms)))
        db.execute(delete(ChatRoom).where(ChatRoom.id.in_(orphan_rooms)))

        affected_runs = list(db.scalars(select(RecommendationRun.id).where(or_(
            RecommendationRun.source_post_id.in_(owned_ids),
            RecommendationRun.id.in_(select(RecommendationItem.run_id).where(RecommendationItem.candidate_post_id.in_(owned_ids))),
        ))))
        db.execute(delete(RecommendationItem).where(RecommendationItem.run_id.in_(affected_runs)))
        db.execute(delete(RecommendationRun).where(RecommendationRun.id.in_(affected_runs)))
        db.execute(delete(FavoritePost).where(or_(FavoritePost.user_id == uid, FavoritePost.post_id.in_(owned_ids))))
        db.execute(delete(PostEmbedding).where(PostEmbedding.post_id.in_(owned_ids)))
        db.execute(delete(PostImage).where(PostImage.post_id.in_(owned_ids)))
        db.execute(delete(Post).where(Post.id.in_(owned_ids)))
        db.execute(delete(EmailVerification).where(EmailVerification.email == email))
        db.execute(delete(PasswordReset).where(PasswordReset.email == email))
        db.execute(delete(WithdrawalChallenge).where(WithdrawalChallenge.user_id == uid))
        db.execute(delete(UserSession).where(UserSession.user_id == uid))
        db.execute(delete(User).where(User.id == uid))
        return files

    @staticmethod
    def commit_with_photo_deletion(db: Session, files: list[DeletionTarget]) -> None:
        # DB and filesystem cannot share a transaction. Keep bounded, private disk
        # backups until commit; restore deleted files on a storage/DB failure.
        with TemporaryDirectory(prefix="withdrawal-photos-") as directory:
            backups = []
            try:
                db.flush()
                for index, (storage, key, content_type) in enumerate(files):
                    try:
                        data = storage.download(key)
                    except ApiError as error:
                        if error.status_code == 404:
                            continue
                        raise
                    backup = Path(directory) / str(index)
                    backup.write_bytes(data)
                    backups.append((storage, key, content_type, backup))
                for storage, key, _ in files:
                    storage.delete(key)
                db.commit()
            except Exception:
                db.rollback()
                restore_failed = False
                for storage, key, content_type, backup in backups:
                    try:
                        storage.upload(key, backup.read_bytes(), content_type)
                    except ApiError as error:
                        if error.status_code != 409:
                            restore_failed = True
                            logger.exception("Failed to restore a photo after withdrawal rollback")
                if restore_failed:
                    raise ApiError(502, "withdrawal_photo_restore_failed", "탈퇴는 취소됐지만 사진 복구에 실패했습니다. 관리자에게 문의해 주세요.")
                raise
