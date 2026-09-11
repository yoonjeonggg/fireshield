from app.core.config import settings

# claim_type 자체에 사기 의심 문구 카테고리 3개(긴급성 압박/금전 요구/처벌 위협)를 포함시켜
# 법제처 API 호출 없이(claim_type != "law_amendment") 매번 danger 등급이 나오도록 구성한다.
HIGH_RISK_CLAIM_TYPE = "긴급 영업정지 대상이니 오늘까지 계좌로 즉시 입금하세요"


def _payload(account_number: str | None, target_business: str = "존재하지않는가짜소방업체"):
    return {
        "claimed_org": "서울소방서",
        "claimed_person": "김소방",
        "claim_type": HIGH_RISK_CLAIM_TYPE,
        "target_business": target_business,
        "account_number": account_number,
    }


async def test_verify_without_account_number_has_no_fraud_evidence(client):
    res = await client.post("/api/v1/verify", json=_payload(None))
    assert res.status_code == 200
    body = res.json()

    sources = [e["source"] for e in body["evidence"]]
    assert "계좌번호 사기 신고 이력" not in sources
    account_evidence = next(e for e in body["evidence"] if e["source"] == "계좌번호 요구 위험도 분석")
    assert account_evidence["result"] == "계좌번호 요구 없음"


async def test_verify_with_unreported_account_shows_no_history(client):
    res = await client.post("/api/v1/verify", json=_payload("110-999-000001"))
    assert res.status_code == 200
    body = res.json()

    fraud_evidence = next(e for e in body["evidence"] if e["source"] == "계좌번호 사기 신고 이력")
    assert fraud_evidence["matched"] is False
    assert "반복 접수 기록이 없습니다" in fraud_evidence["result"]


async def test_verify_flags_repeatedly_reported_account(client):
    account_number = "110-999-000002"

    # 임계치만큼 같은 계좌로 위험 판정을 쌓는다 (HIGH_RISK_CLAIM_TYPE이라 매번 danger).
    for _ in range(settings.fraud_check_report_threshold):
        prior = await client.post("/api/v1/verify", json=_payload(account_number))
        assert prior.json()["risk_level"] == "danger"

    # 표기 방식(하이픈 위치)이 달라도 같은 계좌로 인식되어야 한다.
    reformatted_account_number = account_number.replace("-", "")
    res = await client.post("/api/v1/verify", json=_payload(reformatted_account_number))
    assert res.status_code == 200
    body = res.json()

    fraud_evidence = next(e for e in body["evidence"] if e["source"] == "계좌번호 사기 신고 이력")
    assert fraud_evidence["matched"] is True
    assert "사기 계좌일 가능성이 매우 높습니다" in fraud_evidence["result"]
    assert body["score"] == 100
    assert body["risk_level"] == "danger"


async def test_verify_different_account_number_is_unaffected(client):
    reported_account = "110-999-000003"
    other_account = "220-111-222222"

    for _ in range(settings.fraud_check_report_threshold):
        await client.post("/api/v1/verify", json=_payload(reported_account))

    res = await client.post("/api/v1/verify", json=_payload(other_account))
    body = res.json()

    fraud_evidence = next(e for e in body["evidence"] if e["source"] == "계좌번호 사기 신고 이력")
    assert fraud_evidence["matched"] is False
