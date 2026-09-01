from typing import Optional
from pydantic import BaseModel, field_validator
import re


class VerifyRequest(BaseModel):
    claimed_org: str
    claimed_person: str
    claim_type: str
    target_business: str
    account_number: Optional[str] = None
    law_name: Optional[str] = None

    @field_validator("claimed_org", "claimed_person", "target_business")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("공백만으로는 입력할 수 없습니다.")
        return v

    @field_validator("claim_type")
    @classmethod
    def claim_type_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("요구 사유를 정확히 입력해주세요.")
        return v

    @field_validator("account_number")
    @classmethod
    def account_number_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        v = v.strip()
        if not re.fullmatch(r"[0-9-]{6,25}", v):
            raise ValueError("계좌번호는 숫자와 하이픈(-)만 입력 가능합니다.")
        return v


class Evidence(BaseModel):
    source: str
    result: str
    matched: bool


class VerifyResponse(BaseModel):
    risk_level: str
    score: int
    evidence: list[Evidence]
    recommendation: str