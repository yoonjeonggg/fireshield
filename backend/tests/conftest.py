"""테스트 공통 설정.

FastAPI 앱을 임포트하기 전에 필수 환경변수를 채워 넣어
로컬 .env(운영용 postgres 등)에 의존하지 않고 테스트가 돌도록 한다.
"""

import base64
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LAW_API_KEY", "test-law-key")
os.environ.setdefault("LAW_API_BASE_URL", "https://example.test/law")
os.environ.setdefault(
    "ENCRYPTION_KEY", base64.urlsafe_b64encode(b"0" * 32).decode()
)
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("AI_ENABLED", "false")
# 요청 횟수 제한은 전용 테스트에서만 켠다 (다른 테스트는 같은 클라이언트로 연속 호출)
os.environ.setdefault("VERIFY_RATE_LIMIT_PER_MINUTE", "0")
