import base64
import os
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