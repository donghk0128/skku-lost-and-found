from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import (
    AccessTokenResponse,
    AuthResponse,
    EmailSendCodeRequest,
    EmailVerifyRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    SignUpRequest,
)
from app.auth.service import AuthService
from app.core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/email/send-code", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def send_code(request: EmailSendCodeRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService().send_verification_code(db, request.email)
    return MessageResponse(message="인증 코드를 이메일로 전송했습니다.")


@router.post("/email/verify", response_model=MessageResponse)
def verify_code(request: EmailVerifyRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService().verify_email_code(db, request.email, request.code)
    return MessageResponse(message="이메일 인증이 완료되었습니다.")


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignUpRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user, access_token, refresh_token = AuthService().signup(db, request)
    return AuthResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user, access_token, refresh_token = AuthService().login(db, request)
    return AuthResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    access_token = AuthService().refresh(db, request.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
def logout(request: RefreshRequest, db: Session = Depends(get_db)) -> MessageResponse:
    AuthService().logout(db, request.refresh_token)
    return MessageResponse(message="로그아웃되었습니다.")
