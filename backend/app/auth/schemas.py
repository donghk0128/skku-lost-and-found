from pydantic import BaseModel, Field

from app.users.schemas import UserResponse


class EmailSendCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class EmailVerifyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(pattern=r"^\d{6}$")


class SignUpRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    nickname: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthResponse(AccessTokenResponse):
    refresh_token: str
    user: UserResponse
