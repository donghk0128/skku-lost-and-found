from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.core.errors import ApiError
from app.core.config import get_settings
from app.matching.router import router as matching_router
from app.posts.router import categories_router, router as posts_router
from app.users.router import router as users_router
from app.users.keyword_conditions import router as keyword_conditions_router
from app.notifications.router import router as notifications_router
from app.events.router import router as events_router

app = FastAPI(title="찾자 API", version="0.1.0", openapi_url="/api/v1/openapi.json", docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "요청 형식이 올바르지 않습니다.", "details": jsonable_encoder(error.errors())}},
    )


@app.get("/api/v1/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(keyword_conditions_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(posts_router, prefix="/api/v1")
app.include_router(matching_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
