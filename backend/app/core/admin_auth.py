import secrets

from fastapi import Header, HTTPException
from app.core.config import settings


async def verify_admin_key(x_admin_key: str | None = Header(default=None)):
    expected = settings.admin_api_key
    # 관리자 키가 설정되지 않았거나, 헤더가 없거나, 값이 일치하지 않으면 거부.
    # 타이밍 공격 방지를 위해 상수 시간 비교(secrets.compare_digest) 사용.
    if not expected or not x_admin_key or not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=403, detail="관리자 인증에 실패했습니다.")
