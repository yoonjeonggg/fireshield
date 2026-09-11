from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal


class BlacklistCreateRequest(BaseModel):
    entry_type: Literal["org", "business"]
    name: str
    reason: str | None = None

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("이름은 공백일 수 없습니다.")
        return v


class BlacklistEntryResponse(BaseModel):
    id: str
    entry_type: str
    name: str
    reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class BlacklistListResponse(BaseModel):
    items: list[BlacklistEntryResponse]