from datetime import datetime
import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalize_nickname(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    if not 2 <= len(value) <= 30:
        raise ValueError("닉네임은 2~30자로 입력해 주세요.")
    return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nickname: str
    email_verified_at: datetime
    created_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nickname: str = Field(min_length=2, max_length=30)
    _normalize = field_validator("nickname")(normalize_nickname)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)


class FavoriteState(BaseModel):
    saved: bool


class WithdrawalPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)


class WithdrawalProof(BaseModel):
    model_config = ConfigDict(extra="forbid")
    withdrawal_token: str = Field(min_length=20, max_length=100)


class WithdrawalEmail(WithdrawalProof):
    code: str = Field(pattern=r"^\d{6}$")


class WithdrawalConfirm(WithdrawalProof):
    confirmed: bool


class WithdrawalStarted(BaseModel):
    withdrawal_token: str
    expires_at: datetime


class WithdrawalCodeSent(BaseModel):
    expires_at: datetime
    resend_available_at: datetime


class WithdrawalVerified(BaseModel):
    expires_at: datetime
