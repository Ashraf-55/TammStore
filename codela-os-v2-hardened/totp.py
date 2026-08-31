"""
Minimal RFC 6238 TOTP (Time-based One-Time Password) implementation.
Used for 2FA. No external dependencies (pyotp is not available in every
environment) — built directly on Python's stdlib hmac/hashlib/base64.

Compatible with any standard authenticator app (Google Authenticator, Authy,
1Password, etc.) since it follows the same spec they implement.
"""
import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse


def generate_secret():
    """20 random bytes, base32-encoded — the standard TOTP secret format."""
    return base64.b32encode(os.urandom(20)).decode("utf-8")


def _hotp(secret_b32, counter, digits=6):
    key = base64.b32decode(secret_b32.upper() + "=" * ((8 - len(secret_b32) % 8) % 8))
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_now(secret_b32, step=30, digits=6):
    counter = int(time.time() // step)
    return _hotp(secret_b32, counter, digits)


def verify_totp(secret_b32, code, step=30, digits=6, window=1):
    """window=1 allows the code from one step before/after, to tolerate clock drift."""
    if not code or not code.isdigit():
        return False
    counter = int(time.time() // step)
    for offset in range(-window, window + 1):
        if _hotp(secret_b32, counter + offset, digits) == code.zfill(digits):
            return True
    return False


def provisioning_uri(secret_b32, account_name, issuer="Codela OS"):
    """otpauth:// URI that authenticator apps consume, typically via a QR code.
    The frontend generates the actual QR code image client-side from this URI."""
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    params = urllib.parse.urlencode({"secret": secret_b32, "issuer": issuer})
    return f"otpauth://totp/{label}?{params}"
