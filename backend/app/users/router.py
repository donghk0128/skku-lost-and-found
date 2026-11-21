from fastapi import APIRouter, Depends, Query, Response
from uuid import UUID
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.users.model import FavoritePost, User
from app.users.schemas import UserResponse, ProfileUpdate, PasswordChange, FavoriteState
from app.users.service import UserService
from app.auth.schemas import MessageResponse
from app.core.errors import ApiError
from app.posts.model import Post
from app.posts.schemas import PostListResponse, PostType
from app.users.withdrawal import WithdrawalService
from app.users.schemas import (WithdrawalPassword, WithdrawalProof, WithdrawalEmail, WithdrawalConfirm,
                               WithdrawalStarted, WithdrawalCodeSent, WithdrawalVerified)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_profile(request: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService.update_nickname(db, user, request.nickname)


@router.post("/me/password", response_model=MessageResponse)
def change_password(request: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if request.password != request.password_confirmation:
        raise ApiError(422, "password_mismatch", "비밀번호가 일치하지 않습니다.")
    UserService.change_password(db, user, request.current_password, request.password)
    return MessageResponse(message="비밀번호가 변경되었습니다. 현재 로그인은 유지됩니다.")


@router.post("/me/withdrawal/password", response_model=WithdrawalStarted)
def withdrawal_password(request: WithdrawalPassword, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token, expires = WithdrawalService.start(db, user, request.current_password)
    return WithdrawalStarted(withdrawal_token=token, expires_at=expires)


@router.post("/me/withdrawal/send-code", response_model=WithdrawalCodeSent, status_code=202)
def withdrawal_send_code(request: WithdrawalProof, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expires, resend = WithdrawalService.send_code(db, user, request.withdrawal_token)
    return WithdrawalCodeSent(expires_at=expires, resend_available_at=resend)


@router.post("/me/withdrawal/verify-email", response_model=WithdrawalVerified)
def withdrawal_verify_email(request: WithdrawalEmail, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WithdrawalVerified(expires_at=WithdrawalService.verify_email(db, user, request.withdrawal_token, request.code))


@router.delete("/me", status_code=204)
def withdraw_account(request: WithdrawalConfirm, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not request.confirmed:
        raise ApiError(422, "withdrawal_confirmation_required", "탈퇴 시 처리 내용을 확인하고 동의해 주세요.")
    WithdrawalService.withdraw(db, user, request.withdrawal_token)
    return Response(status_code=204)


@router.get("/me/posts", response_model=PostListResponse)
def my_posts(post_type: PostType | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = UserService.post_list(db, user, post_type, False, limit, offset)
    return PostListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/me/favorites", response_model=PostListResponse)
def favorite_posts(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = UserService.post_list(db, user, None, True, limit, offset)
    return PostListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/me/favorites/{post_id}", response_model=FavoriteState)
def favorite_state(post_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    return FavoriteState(saved=post is not None and post.deleted_at is None and post.author_id != user.id
        and db.get(FavoritePost, (user.id, post_id)) is not None)


@router.post("/me/favorites/{post_id}", status_code=204)
def save_favorite(post_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    UserService.favorite_post(db, user, post_id, True)
    return Response(status_code=204)


@router.delete("/me/favorites/{post_id}", status_code=204)
def remove_favorite(post_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    UserService.favorite_post(db, user, post_id, False)
    return Response(status_code=204)
