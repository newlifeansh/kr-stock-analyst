from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.collectors import briefing
from app.collectors.briefing import KisRestBriefingProvider
from app.config import Settings
from app.integrations.kis_token_cache import get_or_issue_shared_token
from app.models import KisOAuthTokenCache


def _cache_session_factory():
    engine = create_engine("sqlite:///:memory:")
    KisOAuthTokenCache.__table__.create(engine)
    return sessionmaker(bind=engine)


def test_shared_kis_token_is_encrypted_and_reused_by_a_second_worker():
    sessions = _cache_session_factory()
    issued = []
    current = datetime(2026, 10, 8, 9, 0)

    def issue():
        issued.append(1)
        return "bearer-secret-example", 86400

    first = get_or_issue_shared_token(
        sessions, identity="a" * 64, app_secret="test-app-secret", issue=issue,
        now=lambda: current,
    )
    second = get_or_issue_shared_token(
        sessions, identity="a" * 64, app_secret="test-app-secret", issue=issue,
        now=lambda: current + timedelta(seconds=5),
    )
    assert first == second == ("bearer-secret-example", current + timedelta(days=1))
    assert issued == [1]
    with sessions() as db:
        stored = db.get(KisOAuthTokenCache, "a" * 64)
        assert stored.ciphertext != b"bearer-secret-example"
        assert b"bearer-secret-example" not in stored.ciphertext


def test_shared_kis_token_failure_backoff_survives_worker_restart():
    sessions = _cache_session_factory()
    current = [datetime(2026, 10, 8, 9, 0)]
    attempts = []

    def issue():
        attempts.append(current[0])
        if len(attempts) == 1:
            raise requests.HTTPError("temporary tokenP 403")
        return "recovered-token", 86400

    def lookup():
        return get_or_issue_shared_token(
            sessions, identity="b" * 64, app_secret="test-app-secret", issue=issue,
            now=lambda: current[0],
        )

    with pytest.raises(requests.HTTPError):
        lookup()
    current[0] += timedelta(seconds=64)
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        lookup()
    assert len(attempts) == 1
    current[0] += timedelta(seconds=1)
    assert lookup()[0] == "recovered-token"
    assert len(attempts) == 2


def test_shared_kis_token_corrupt_ciphertext_never_returns_old_bearer():
    sessions = _cache_session_factory()
    current = datetime(2026, 10, 8, 9, 0)
    with sessions() as db:
        db.add(KisOAuthTokenCache(
            identity="c" * 64, ciphertext=b"invalid-ciphertext",
            expires_at=current + timedelta(days=1), retry_after=None,
        ))
        db.commit()
    token, _ = get_or_issue_shared_token(
        sessions, identity="c" * 64, app_secret="test-app-secret",
        issue=lambda: ("replacement-token", 86400), now=lambda: current,
    )
    assert token == "replacement-token"


def test_postgres_provider_uses_shared_cache_before_token_endpoint(monkeypatch):
    monkeypatch.setattr(briefing, "engine", SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql")
    ))
    calls = []

    def shared(_sessions, *, identity, app_secret, issue):
        calls.append((identity, app_secret))
        return "shared-token", datetime.utcnow() + timedelta(days=1)

    monkeypatch.setattr(briefing, "get_or_issue_shared_token", shared)
    monkeypatch.setattr(briefing.requests, "post", lambda *_a, **_k: pytest.fail(
        "cached token must not issue tokenP"
    ))
    provider = KisRestBriefingProvider(Settings(
        kis_app_key="shared-key-rc36", kis_app_secret="shared-secret-rc36"
    ))
    assert provider._ensure_token() == "shared-token"
    assert len(calls) == 1
    assert calls[0][1] == "shared-secret-rc36"
