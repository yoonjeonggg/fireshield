import os
import tempfile
from pathlib import Path

import pytest

# 앱 모듈(app.core.config)이 import되기 전에 테스트 전용 DB를 지정해야
# 실제 개발/운영 DB(.env의 DATABASE_URL)를 건드리지 않는다.
_tmp_dir = tempfile.TemporaryDirectory()
_db_path = Path(_tmp_dir.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path.as_posix()}"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.fire_business import FireBusiness  # noqa: E402
from app.models.verify_log import Base, VerifyLog  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    _tmp_dir.cleanup()


@pytest.fixture(autouse=True)
async def _clean_tables():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(VerifyLog))
        await session.execute(delete(FireBusiness))
        await session.commit()


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
