import uuid
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.models.verify_log import Base


class BlacklistEntry(Base):
    __tablename__ = "blacklist_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_type = Column(String, nullable=False)  # "org" (기관명) | "business" (업체명)
    name = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())