from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.collectors import briefing
from app.collectors.briefing import KisRestBriefingProvider
from app.config import Settings
from app.integrations.kis_token_cache import get_or_issue_shared_token, invalidate_rejected_shared_token
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


def test_rejected_shared_kis_token_is_evicted_only_when_it_is_still_current():
    sessions = _cache_session_factory()
    current = datetime(2026, 10, 30, 9, 0)
    issued = []

    def issue():
        token = f"token-{len(issued) + 1}"
        issued.append(token)
        return token, 86400

    kwargs = dict(identity="d" * 64, app_secret="test-app-secret")
    assert get_or_issue_shared_token(sessions, issue=issue, now=lambda: current, **kwargs)[0] == "token-1"
    assert not invalidate_rejected_shared_token(sessions, rejected_token="older-token", **kwargs)
    assert get_or_issue_shared_token(sessions, issue=issue, now=lambda: current, **kwargs)[0] == "token-1"
    assert invalidate_rejected_shared_token(sessions, rejected_token="token-1", **kwargs)
    assert get_or_issue_shared_token(sessions, issue=issue, now=lambda: current, **kwargs)[0] == "token-2"
    assert not invalidate_rejected_shared_token(sessions, rejected_token="token-1", **kwargs)
    assert get_or_issue_shared_token(sessions, issue=issue, now=lambda: current, **kwargs)[0] == "token-2"
    assert issued == ["token-1", "token-2"]


def test_kis_expired_token_500_refreshes_once_and_retries_original_request(monkeypatch):
    briefing._KIS_TOKEN_CACHE.clear()
    briefing._KIS_TOKEN_FAILURE_RETRY_AT.clear()
    monkeypatch.setattr(briefing, "engine", SimpleNamespace(
        dialect=SimpleNamespace(name="sqlite")
    ))
    provider = KisRestBriefingProvider(Settings(
        kis_app_key="expired-key", kis_app_secret="expired-secret",
    ))
    provider._token = "expired-token"
    provider._token_expires_at = datetime.utcnow() + timedelta(hours=1)
    monkeypatch.setattr(provider, "_wait_for_request_slot", lambda: None)
    issued = []
    used = []

    def response(status, payload):
        result = requests.Response()
        result.status_code = status
        result._content = __import__("json").dumps(payload).encode()
        result.url = "https://openapi.koreainvestment.com:9443/test"
        return result

    def get(_url, *, headers, **_kwargs):
        used.append(headers["authorization"])
        if len(used) == 1:
            return response(500, {"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "기간이 만료된 token 입니다."})
        return response(200, {"rt_cd": "0", "output": {"stck_prpr": "100"}})

    def post(*_args, **_kwargs):
        issued.append(1)
        return response(200, {"access_token": "replacement-token", "expires_in": 86400})

    monkeypatch.setattr(briefing.requests, "get", get)
    monkeypatch.setattr(briefing.requests, "post", post)
    assert provider._request_current_price("005930")["stck_prpr"] == "100"
    assert used == ["Bearer expired-token", "Bearer replacement-token"]
    assert issued == [1]
    assert provider._ensure_token() == "replacement-token"


def test_kis_non_auth_500_keeps_bounded_transport_retries(monkeypatch):
    briefing._KIS_TOKEN_CACHE.clear()
    provider = KisRestBriefingProvider(Settings(
        kis_app_key="transport-key", kis_app_secret="transport-secret",
    ))
    provider._token = "valid-token"
    provider._token_expires_at = datetime.utcnow() + timedelta(hours=1)
    monkeypatch.setattr(provider, "_wait_for_request_slot", lambda: None)
    monkeypatch.setattr(briefing.time_module, "sleep", lambda _: None)
    calls = []

    def get(_url, **_kwargs):
        calls.append(1)
        result = requests.Response()
        result.status_code = 500
        result._content = b'{"rt_cd":"1","msg_cd":"OTHER"}'
        result.url = "https://openapi.koreainvestment.com:9443/test"
        return result

    monkeypatch.setattr(briefing.requests, "get", get)
    with pytest.raises(requests.HTTPError):
        provider._request_current_price("005930")
    assert len(calls) == len(briefing.KIS_TRANSIENT_RETRY_DELAYS) + 1
    assert provider._token == "valid-token"


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
