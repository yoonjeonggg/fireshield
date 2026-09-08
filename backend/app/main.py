from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.api.v1.risk_map import router as risk_map_router
import logging
from app.api.v1.admin import router as admin_router

from app.api.v1.verify import router as verify_router
from app.core.database import engine
from app.core.config import settings
from app.models.verify_log import Base


logger = logging.getLogger("fireshield")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Alembic 미도입 프로젝트 — 신규 컬럼은 기동 시 멱등 ALTER로 반영
        for column_ddl in (
            "ADD COLUMN IF NOT EXISTS rule_score INTEGER",
            "ADD COLUMN IF NOT EXISTS ai_score INTEGER",
            "ADD COLUMN IF NOT EXISTS ai_status VARCHAR",
        ):
            await conn.execute(text(f"ALTER TABLE verify_logs {column_ddl}"))
    yield


app = FastAPI(title="FireShield API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# --- 요청 값 검증 실패 (422) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"검증 실패: {exc.errors()}")

    # Pydantic validator가 던진 커스텀 메시지가 있으면 그걸 우선 사용
    first_error = exc.errors()[0] if exc.errors() else None
    detail = first_error["msg"].replace("Value error, ", "") if first_error else "요청 값이 올바르지 않습니다."

    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_request",
            "detail": detail,
        },
    )


# --- 그 외 모든 예상치 못한 예외 (500) ---
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"처리되지 않은 예외 발생: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "detail": "일시적인 서버 오류입니다. 잠시 후 다시 시도해주세요.",
        },
    )


app.include_router(verify_router)
app.include_router(risk_map_router)
app.include_router(admin_router)

@app.get("/health")
async def health():
    return {"status": "ok"}