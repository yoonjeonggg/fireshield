import base64
import hashlib
import hmac
import os
import re
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


def _get_key() -> bytes:
    return base64.urlsafe_b64decode(settings.encryption_key)


def encrypt(plaintext: str | None) -> str | None:
    """
    문자열을 AES-256-GCM으로 암호화해서 base64 문자열로 반환합니다.
    None이 들어오면 None을 그대로 반환합니다.
    """
    if plaintext is None:
        return None

    key = _get_key()
    nonce = os.urandom(12)  # GCM 권장 nonce 길이
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # nonce + ciphertext를 합쳐서 base64로 인코딩 (복호화 시 nonce가 필요하기 때문)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt(encrypted: str | None) -> str | None:
    """
    encrypt()로 암호화된 base64 문자열을 원문으로 복호화합니다.
    """
    if encrypted is None:
        return None

    key = _get_key()
    raw = base64.urlsafe_b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def account_fingerprint(account_number: str | None) -> str | None:
    """
    계좌번호를 결정적(deterministic) 키 해시로 변환합니다.

    - 원본 계좌번호는 DB에 평문으로 남기지 않고, 이 지문(fingerprint)으로만
      "같은 계좌가 몇 번 신고됐는지"를 집계합니다.
    - 같은 계좌번호는 항상 같은 지문이 되므로 DB 조회/집계가 가능합니다.
    - encrypt()와 달리 복호화가 불가능한 단방향 해시입니다.
    - 하이픈/공백 등을 제거해 표기 방식이 달라도 같은 계좌로 인식합니다.
    """
    if account_number is None:
        return None

    normalized = re.sub(r"\D", "", account_number)
    if not normalized:
        return None

    key = _get_key()
    return hmac.new(key, f"acct:{normalized}".encode("utf-8"), hashlib.sha256).hexdigest()