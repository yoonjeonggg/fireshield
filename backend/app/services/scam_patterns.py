"""
전형적인 소방기관 사칭 사기 문구 패턴 탐지 서비스.
"""

# 카테고리별 사기 의심 키워드
SCAM_PATTERNS = {
    "긴급성 압박": ["즉시", "오늘까지", "당일", "긴급", "지금 바로", "미납 시"],
    "금전 요구": ["입금", "송금", "현장 결제", "계좌로", "완납"],
    "처벌 위협": ["과태료", "영업정지", "허가 취소", "벌금", "형사고발"],
    "이익 유인": ["환급", "보조금", "전액 지원", "무료 지원"],
}


def detect_scam_phrases(text: str) -> dict[str, list[str]]:
    """
    입력 텍스트에서 카테고리별로 매칭된 사기 의심 문구를 반환합니다.

    Returns:
        {"긴급성 압박": ["즉시", "오늘까지"], "금전 요구": ["입금"]} 형태.
        매칭이 없는 카테고리는 결과에 포함되지 않습니다.
    """
    if not text:
        return {}

    result = {}
    for category, keywords in SCAM_PATTERNS.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            result[category] = matched
    return result