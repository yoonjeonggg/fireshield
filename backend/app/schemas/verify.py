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


class AiAssessment(BaseModel):
    """로컬 LLM(딥러닝) 기반 사기 위험도 판정. 규칙 점수와 별도로 표시된다."""

    score: Optional[int]        # 0~100. 값이 폐기되면 None.
    status: str                 # ai_guardrail.AiStatus 값
    label: str                  # "AI: 위험" / "AI 판단 보류" 등
    detail: str                 # 사람이 읽는 설명
    used_in_verdict: bool       # 이 점수가 최종 판정에 반영되었는지


class VerifyResponse(BaseModel):
    risk_level: str
    score: int                 # 최종(보수적) 점수 — 하위호환 위해 이름 유지
    rule_score: int            # 공공데이터 규칙 기반 점수
    ai_assessment: Optional[AiAssessment] = None
    evidence: list[Evidence]
    recommendation: str