"""Cross-process KIS OAuth reuse without storing bearer tokens in plaintext."""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import KisOAuthTokenCache

KIS_SHARED_FAILURE_RETRY_SECONDS = 65
KIS_TOKEN_EXPIRY_MARGIN = timedelta(minutes=1)


def _cipher(app_secret: str) -> Fernet:
    # The database alone cannot decrypt the bearer; the existing KIS secret
    # remains in the application secret store, not in this table or logs.
    key = hashlib.sha256(b"kis-oauth-cache-v1\0" + app_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def get_or_issue_shared_token(
    session_factory: Callable[[], Session],
    *,
    identity: str,
    app_secret: str,
    issue: Callable[[], tuple[str, int]],
    now: Callable[[], datetime] = datetime.utcnow,
) -> tuple[str, datetime]:
    """Serialize tokenP across PostgreSQL workers and reuse the encrypted result.

    The transaction-scoped advisory lock covers the read, possible HTTP
    issuance, and write. Waiting workers re-read after the first commit.
    """

    cipher = _cipher(app_secret)
    with session_factory() as db:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            lock_key = int.from_bytes(bytes.fromhex(identity[:16]), "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
        current = now()
        row = db.get(KisOAuthTokenCache, identity)
        if row and row.expires_at and row.expires_at > current + KIS_TOKEN_EXPIRY_MARGIN:
            if row.ciphertext:
                try:
                    return cipher.decrypt(row.ciphertext).decode("utf-8"), row.expires_at
                except (InvalidToken, UnicodeDecodeError):
                    # Key rotation or corrupt data is not a usable credential.
                    pass
        if row and row.retry_after and row.retry_after > current:
            raise RuntimeError("KIS token temporarily unavailable")
        try:
            token, expires_in = issue()
            if not token or int(expires_in) <= 60:
                raise RuntimeError("KIS token response is invalid")
        except Exception:
            if row is None:
                row = KisOAuthTokenCache(identity=identity)
                db.add(row)
            row.ciphertext = None
            row.expires_at = None
            row.retry_after = now() + timedelta(seconds=KIS_SHARED_FAILURE_RETRY_SECONDS)
            db.commit()
            raise
        expires_at = now() + timedelta(seconds=int(expires_in))
        if row is None:
            row = KisOAuthTokenCache(identity=identity)
            db.add(row)
        row.ciphertext = cipher.encrypt(token.encode("utf-8"))
        row.expires_at = expires_at
        row.retry_after = None
        db.commit()
        return token, expires_at
