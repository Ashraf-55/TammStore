"""Application-level encryption for tenant integration secrets.

Production requires CODELA_ENCRYPTION_KEY to be a Fernet key. Secrets are
stored with an explicit version prefix so future key rotation formats can be
introduced without ambiguity. Plaintext fallback is development-only.
"""
import os
from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"

def _fernet():
    key = os.getenv("CODELA_ENCRYPTION_KEY")
    if not key:
        if os.getenv("CODELA_ENV", "development") == "production":
            raise RuntimeError("CODELA_ENCRYPTION_KEY is required in production")
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)

def encryption_key_available():
    return bool(os.getenv("CODELA_ENCRYPTION_KEY"))

def encrypt_secret(value, require_key=False):
    if value is None or value == "":
        return value
    if str(value).startswith(_PREFIX):
        return value
    f = _fernet()
    if f is None:
        if require_key:
            raise RuntimeError("CODELA_ENCRYPTION_KEY is required to encrypt an integration secret")
        return str(value)
    return _PREFIX + f.encrypt(str(value).encode()).decode()

def decrypt_secret(value):
    if value is None or value == "":
        return value
    value = str(value)
    if not value.startswith(_PREFIX):
        if os.getenv("CODELA_ENV", "development") == "production":
            raise RuntimeError("Refusing to use plaintext integration secret in production")
        return value
    f = _fernet()
    if f is None:
        raise RuntimeError("Encryption key required to decrypt secret")
    try:
        return f.decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt integration secret") from exc
