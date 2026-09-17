"""Real password hashing — PBKDF2-HMAC-SHA256, stdlib only.

Deliberately not bcrypt/passlib: this repo's own convention (see
app/rate_limit.py's docstring) is to reach for the stdlib over a new
dependency when it's genuinely sufficient, and `hashlib.pbkdf2_hmac` is a
real, standard, still-recommended KDF (the same family Django defaults
to) — a per-password random salt, a high iteration count, and a
constant-time comparison on verify are what actually matter here, not
the specific algorithm name.
"""
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Never raises on a malformed stored hash — treats it the same as a
    wrong password (a real user typo shouldn't ever surface as a 500)."""
    try:
        algorithm, iterations_str, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
