from typing import Optional
from pydantic import BaseModel, field_validator, model_validator
import re

# 의미 있는 글자: 한글 음절 / 한자 / 영문 / 숫자
_MEANINGFUL_CHAR = re.compile(r"[가-힣一-鿿0-9A-Za-z]")
_HANGUL_SYLLABLE = re.compile(r"[가-힣]")


def _reject_implausible(value: str, *, label: str, require_hangul: bool) -> str:
    """
    사람이 실제로 입력한 이름/명칭으로 보이지 않으면 ValueError.

    "존재하지 않는 가짜 법령·업체명"(그럴듯하게 생김)은 통과시키고,
    "ㄹ", "ㅋㅋㅋ", "----" 같은 명백한 무의미 입력만 걸러낸다.
    """
    s = value.strip()
    compact = s.replace(" ", "")

    if len(compact) < 2:
        raise ValueError(f"{label}을(를) 2자 이상 정확히 입력해주세요.")
    if len(set(compact)) == 1:  # "aaaa", "ㅋㅋㅋ", "----"
        raise ValueError(f"{label}이(가) 올바르지 않습니다. 실제 받은 내용을 정확히 입력해주세요.")
    if not _MEANINGFUL_CHAR.search(compact):  # 자모만("ㄹㅇ"), 특수문자만("!@#")
        raise ValueError(f"{label}이(가) 올바르지 않습니다. 실제 받은 내용을 정확히 입력해주세요.")
    if require_hangul and not _HANGUL_SYLLABLE.search(compact):
        raise ValueError(f"{label}은(는) 한글로 정확히 입력해주세요.")
    return s


class VerifyRequest(BaseModel):
    claimed_org: str
    claimed_person: str
    claim_type: str
    target_business: str
    account_number: Optional[str] = None
    law_name: Optional[str] = None

    @field_validator("claimed_org")
    @classmethod
    def validate_claimed_org(cls, v: str) -> str:
        return _reject_implausible(v, label="발신 기관명", require_hangul=True)

    @field_validator("claimed_person")
    @classmethod
    def validate_claimed_person(cls, v: str) -> str:
        return _reject_implausible(v, label="담당자명", require_hangul=False)

    @field_validator("target_business")
    @classmethod
    def validate_target_business(cls, v: str) -> str:
        return _reject_implausible(v, label="대상 업체명", require_hangul=False)

    @field_validator("law_name")
    @classmethod
    def validate_law_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return _reject_implausible(v, label="법령명", require_hangul=True)

    @field_validator("claim_type")
    @classmethod
    def claim_type_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("요구 사유를 정확히 입력해주세요.")
        return v

    @model_validator(mode="after")
    def fields_must_be_distinct(self) -> "VerifyRequest":
        """
        기관명·담당자명·업체명(+법령명)에 모두 같은 값을 넣은 경우는
        실제 신고가 아니라 테스트/장난 입력으로 보고 판정하지 않는다.
        """
        def norm(s: Optional[str]) -> Optional[str]:
            if s is None:
                return None
            return s.strip().replace(" ", "").lower()

        values = [norm(self.claimed_org), norm(self.claimed_person), norm(self.target_business)]
        if norm(self.law_name):
            values.append(norm(self.law_name))

        if len(set(values)) == 1:
            raise ValueError(
                "모든 칸에 같은 값이 들어가 있습니다. "
                "받으신 연락 내용을 항목별로 구분해서 입력해주세요."
            )
        return self

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