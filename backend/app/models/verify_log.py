import uuid
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class VerifyLog(Base):
    __tablename__ = "verify_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claimed_org = Column(String)
    claimed_person = Column(String)
    claim_type = Column(String)
    target_business = Column(String)
    account_number = Column(String)  # AES-256-GCM 암호화 저장
    account_hash = Column(String, index=True)  # 결정적 키 해시 — 같은 계좌 반복 신고 집계용
    risk_level = Column(String)
    score = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())