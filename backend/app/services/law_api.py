import httpx
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from app.core.config import settings


class LawApiError(Exception):
    """법제처 API 호출 실패 시 발생하는 예외"""
    pass


async def search_law_by_name(law_name: str) -> list[dict]:
    """
    법령명으로 현행법령(시행일 기준) 목록을 조회합니다.

    Args:
        law_name: 검색할 법령명 (예: "소방시설 설치 및 관리에 관한 법률")

    Returns:
        검색된 법령 정보 리스트. 각 항목은 dict로:
        - law_name: 법령명
        - status: 현행연혁코드 (현행/연혁/시행예정)
        - promulgation_date: 공포일자
        - enforcement_date: 시행일자
        - amendment_type: 제개정구분명
        - ministry: 소관부처명
        - detail_link: 법령상세링크 (전체 URL)
    """
    params = {
        "OC": settings.law_api_key,
        "target": "eflaw",  # 현행법령(시행일 기준) 목록조회
        "type": "XML",
        "query": law_name,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(settings.law_api_base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise LawApiError(f"법제처 API 호출 실패: {e}") from e

    return _parse_law_list_xml(response.text)


def _parse_law_list_xml(xml_text: str) -> list[dict]:
    """법제처 법령목록 조회 XML 응답을 파싱합니다."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise LawApiError(f"법제처 API 응답 파싱 실패: {e}") from e

    result_code = _text_or_none(root, "resultCode")
    if result_code and result_code != "00":
        result_msg = _text_or_none(root, "resultMsg")
        raise LawApiError(f"법제처 API 오류 응답: {result_code} - {result_msg}")

    results = []
    for law in root.findall("law"):
        detail_link = _text_or_none(law, "법령상세링크")
        results.append({
            "law_name": _text_or_none(law, "법령명한글"),
            "status": _text_or_none(law, "현행연혁코드"),
            "promulgation_date": _text_or_none(law, "공포일자"),
            "enforcement_date": _text_or_none(law, "시행일자"),
            "amendment_type": _text_or_none(law, "제개정구분명"),
            "ministry": _text_or_none(law, "소관부처명"),
            "detail_link": f"https://www.law.go.kr{detail_link}" if detail_link else None,
        })

    return results


def _text_or_none(element: ET.Element, tag: str) -> str | None:
    child = element.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip()


async def check_recent_amendment(law_name: str, days_threshold: int = 90) -> dict:
    """
    특정 법령이 최근 N일 이내에 개정(시행)되었는지 확인합니다.
    사칭범들이 "최근 법 개정으로 벌금 나옵니다" 하는 멘트를 검증하는 데 사용.

    '현행연혁코드'가 '현행'인 항목 중, 시행일자가 최근인지 확인합니다.

    Args:
        law_name: 확인할 법령명
        days_threshold: 최근으로 간주할 기준 일수 (기본 90일)

    Returns:
        {
            "found": 법령 검색 성공 여부,
            "is_recent": 최근 개정 여부,
            "current_law": 현행 법령 정보 (dict) 또는 None,
        }
    """
    results = await search_law_by_name(law_name)
    if not results:
        return {"found": False, "is_recent": False, "current_law": None}

    # 현행연혁코드가 '현행'인 항목 찾기
    current_law = next((law for law in results if law["status"] == "현행"), None)
    if current_law is None:
        return {"found": False, "is_recent": False, "current_law": None}

    is_recent = False
    enforcement_date = current_law.get("enforcement_date")
    if enforcement_date:
        try:
            law_date = datetime.strptime(enforcement_date, "%Y%m%d")
            cutoff = datetime.now() - timedelta(days=days_threshold)
            is_recent = law_date >= cutoff
        except ValueError:
            pass

    return {"found": True, "is_recent": is_recent, "current_law": current_law}