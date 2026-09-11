from app.core.crypto import account_fingerprint, decrypt, encrypt


def test_account_fingerprint_is_deterministic():
    a = account_fingerprint("110-123-456789")
    b = account_fingerprint("110-123-456789")
    assert a == b


def test_account_fingerprint_ignores_formatting():
    # 하이픈 유무 등 표기 방식이 달라도 같은 계좌는 같은 지문이어야 반복 신고 집계가 된다.
    assert account_fingerprint("110-123-456789") == account_fingerprint("110123456789")
    assert account_fingerprint("110 123 456789") == account_fingerprint("110123456789")


def test_account_fingerprint_differs_for_different_accounts():
    assert account_fingerprint("110123456789") != account_fingerprint("110123456780")


def test_account_fingerprint_none_and_blank():
    assert account_fingerprint(None) is None
    assert account_fingerprint("---") is None


def test_account_fingerprint_is_one_way_not_reversible():
    # encrypt()와 달리 복호화 불가능한 해시여야 한다 (원문 계좌번호가 새어나가면 안 됨).
    fingerprint = account_fingerprint("110123456789")
    assert fingerprint != "110123456789"
    assert len(fingerprint) == 64  # sha256 hex digest


def test_encrypt_decrypt_roundtrip_still_works():
    # account_fingerprint 추가가 기존 암호화 저장 방식을 건드리지 않았는지 확인.
    encrypted = encrypt("110123456789")
    assert encrypted != "110123456789"
    assert decrypt(encrypted) == "110123456789"


def test_encrypt_decrypt_none():
    assert encrypt(None) is None
    assert decrypt(None) is None
