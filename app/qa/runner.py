from __future__ import annotations

import asyncio
import html as html_lib
import json
import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any, Literal
from urllib.parse import urljoin, urlparse
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx

from app.qa.catalog import load_qa_catalog

KST = ZoneInfo("Asia/Seoul")
QaMode = Literal["gate", "live", "e2e"]
QaStatus = Literal["pass", "warn", "fail", "skip"]
SECRET_KEY_RE = re.compile(
    r"(authorization|token|secret|password|api[_-]?key|app[_-]?key|app[_-]?secret|approval[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(bearer\s+)[^\s,;]+|((?:api|app|secret|token)[_-]?key=)[^&\s]+"
)
QUOTE_STREAM_META_RE = re.compile(
    r"""<meta\b
    (?=[^>]*\bname\s*=\s*["']secret-note-quote-stream-url["'])
    (?=[^>]*\bcontent\s*=\s*["']([^"']+)["'])
    [^>]*>""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class QaCheckResult:
    id: str
    priority: str
    status: QaStatus
    duration_ms: int
    evidence: dict[str, Any]
    message: str


class QaFailure(AssertionError):
    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


class QaWarning(RuntimeError):
    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


def redact(value: Any) -> Any:
    """Return a JSON-safe value with credentials and prepared URLs removed."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY_RE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return SECRET_VALUE_RE.sub(
            lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", value
        )
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class ResultCollector:
    def __init__(self, catalog: dict[str, Any]):
        self._cases = {case["id"]: case for case in catalog["cases"]}
        self.results: list[QaCheckResult] = []

    def add(
        self,
        case_id: str,
        status: QaStatus,
        message: str,
        *,
        evidence: dict[str, Any] | None = None,
        duration_ms: int = 0,
    ) -> None:
        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(f"Unknown QA case: {case_id}")
        candidate = QaCheckResult(
            id=case_id,
            priority=case["priority"],
            status=status,
            duration_ms=max(0, int(duration_ms)),
            evidence=redact(evidence or {}),
            message=str(redact(message)),
        )
        existing = next((item for item in self.results if item.id == case_id), None)
        if existing is None:
            self.results.append(candidate)
            return
        severity = {"pass": 0, "skip": 1, "warn": 2, "fail": 3}
        existing.status = max(
            (existing.status, candidate.status), key=severity.__getitem__
        )
        existing.duration_ms += candidate.duration_ms
        existing.evidence = {
            "probes": [
                *(existing.evidence.get("probes") or [existing.evidence]),
                candidate.evidence,
            ]
        }
        if candidate.message not in existing.message:
            existing.message = f"{existing.message} / {candidate.message}"

    def check(
        self,
        case_id: str,
        callback: Callable[[], dict[str, Any] | None],
        *,
        pass_message: str,
    ) -> None:
        started = monotonic()
        try:
            evidence = callback() or {}
        except QaWarning as exc:
            self.add(
                case_id,
                "warn",
                str(exc),
                evidence=exc.evidence,
                duration_ms=round((monotonic() - started) * 1000),
            )
        except (QaFailure, AssertionError) as exc:
            self.add(
                case_id,
                "fail",
                str(exc),
                evidence=getattr(exc, "evidence", {}),
                duration_ms=round((monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - QA must convert every exception into evidence.
            self.add(
                case_id,
                "fail",
                f"{type(exc).__name__}: {exc}",
                duration_ms=round((monotonic() - started) * 1000),
            )
        else:
            self.add(
                case_id,
                "pass",
                pass_message,
                evidence=evidence,
                duration_ms=round((monotonic() - started) * 1000),
            )


def _assert(condition: Any, message: str, **evidence: Any) -> None:
    if not condition:
        raise QaFailure(message, evidence)


def _environment_name(base_url: str) -> str:
    host = (urlparse(base_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "testserver"}:
        return "local"
    if "staging" in host:
        return "staging"
    return "remote"


def _same_origin_quote_stream_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws/quotes"


def _resolve_public_quote_stream_url(
    base_url: str, timeout: float
) -> tuple[str, str]:
    """Resolve the exact quote stream a dashboard browser will connect to."""
    fallback_url = _same_origin_quote_stream_url(base_url)
    dashboard_url = urljoin(f"{base_url.rstrip('/')}/", "dashboard/005930")
    try:
        response = httpx.get(
            dashboard_url,
            follow_redirects=True,
            timeout=timeout,
            headers={"Accept": "text/html"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return fallback_url, "same_origin"

    match = QUOTE_STREAM_META_RE.search(response.text)
    if match is None:
        return fallback_url, "same_origin"
    candidate = html_lib.unescape(match.group(1)).strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        return fallback_url, "same_origin"
    return candidate, "dashboard_meta"


def _market_state(*payloads: Any) -> str | None:
    keys = (
        "market_state",
        "market_status",
        "market_session",
        "market_session_label",
        "session",
        "status_label",
    )
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for child_key in ("quote", "current", "market", "session"):
            child = payload.get(child_key)
            if isinstance(child, dict):
                found = _market_state(child)
                if found:
                    return found
    return None


def _stream_timestamp(value: Any, field: str) -> datetime:
    raw = str(value or "").strip()
    _assert(bool(raw), f"WebSocket {field} 시각이 없습니다.", field=field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise QaFailure(
            f"WebSocket {field} 시각을 해석할 수 없습니다.",
            {"field": field, "value": raw},
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_signal_revision_frame(
    frame: dict[str, Any], *, require_initial: bool | None = None
) -> dict[str, Any]:
    _assert(frame.get("type") == "signal_revision", "signal_revision 프레임이 아닙니다.")
    revision = frame.get("revision")
    _assert(
        isinstance(revision, int) and not isinstance(revision, bool) and revision >= 0,
        "signal_revision revision이 음이 아닌 정수가 아닙니다.",
        revision=revision,
    )
    changed_codes = frame.get("changed_codes")
    _assert(
        isinstance(changed_codes, list)
        and all(re.fullmatch(r"\d{6}", str(code or "")) for code in changed_codes),
        "signal_revision changed_codes가 6자리 종목코드 배열이 아닙니다.",
        changed_codes=changed_codes,
    )
    if require_initial is not None:
        _assert(
            frame.get("initial") is require_initial,
            "signal_revision initial 표시가 연결 상태와 다릅니다.",
            initial=frame.get("initial"),
            expected=require_initial,
        )
    as_of = _stream_timestamp(frame.get("as_of"), "signal_revision.as_of")
    return {
        "revision": revision,
        "as_of": as_of.isoformat(),
        "changed_codes": [str(code) for code in changed_codes],
        "initial": frame.get("initial") is True,
    }


def _validate_public_quote_frame(
    frame: dict[str, Any], *, expected_code: str
) -> dict[str, Any]:
    _assert(frame.get("type") == "quote", "quote 프레임이 아닙니다.")
    _assert(
        str(frame.get("code") or "") == expected_code,
        "quote 종목코드가 구독 종목과 다릅니다.",
        expected_code=expected_code,
        code=frame.get("code"),
    )
    quote = frame.get("quote")
    _assert(isinstance(quote, dict), "quote 본문이 객체가 아닙니다.")
    price = quote.get("price")
    _assert(
        isinstance(price, (int, float))
        and not isinstance(price, bool)
        and float(price) > 0,
        "quote 현재가가 양수가 아닙니다.",
        price=price,
    )
    sequence = frame.get("sequence")
    _assert(
        isinstance(sequence, int)
        and not isinstance(sequence, bool)
        and sequence >= 1,
        "quote sequence가 양의 정수가 아닙니다.",
        sequence=sequence,
    )
    observed_at = _stream_timestamp(frame.get("observed_at"), "quote.observed_at")
    published_at = _stream_timestamp(frame.get("published_at"), "quote.published_at")
    _assert(
        observed_at <= published_at,
        "quote published_at이 observed_at보다 빠릅니다.",
        observed_at=observed_at,
        published_at=published_at,
    )
    return {
        "code": expected_code,
        "price": price,
        "sequence": sequence,
        "observed_at": observed_at.isoformat(),
        "published_at": published_at.isoformat(),
        "source": frame.get("source"),
    }


def _validate_quote_status_frame(frame: dict[str, Any]) -> dict[str, Any]:
    _assert(frame.get("type") == "status", "status 프레임이 아닙니다.")
    _assert(
        re.fullmatch(r"\d{6}", str(frame.get("code") or "")) is not None,
        "status 종목코드가 없거나 잘못됐습니다.",
        code=frame.get("code"),
    )
    status = str(frame.get("status") or "").strip().lower()
    _assert(
        status in {"connected", "fallback", "recovered"},
        "status 상태가 connected·fallback·recovered 계약과 다릅니다.",
        status=status,
    )
    _assert(bool(str(frame.get("source") or "").strip()), "status 출처가 비었습니다.")
    message = str(frame.get("message") or "").strip()
    _assert(
        "appkey" not in message.lower()
        and re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            message,
            re.IGNORECASE,
        )
        is None,
        "status 메시지에 KIS 인증정보 또는 원문 appkey 오류가 노출됐습니다.",
        status_message=message,
    )
    return {
        "code": str(frame.get("code")),
        "status": status,
        "source": str(frame.get("source")),
        "has_message": bool(message),
    }


class ReadOnlyApi:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/") + "/"
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "analyst-data-signal-qa/1.0",
            },
        )

    def close(self) -> None:
        self.client.close()

    def get(self, path: str, **params: Any) -> tuple[Any, dict[str, Any]]:
        started = monotonic()
        response = self.client.get(
            urljoin(self.base_url, path.lstrip("/")), params=params or None
        )
        latency_ms = round((monotonic() - started) * 1000)
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
        }
        if response.status_code >= 400:
            raise QaFailure(f"GET {path} returned HTTP {response.status_code}", meta)
        try:
            payload = response.json()
        except ValueError as exc:
            raise QaFailure(f"GET {path} did not return JSON", meta) from exc
        return payload, meta

    def get_text(self, path: str, **params: Any) -> tuple[str, dict[str, Any]]:
        started = monotonic()
        response = self.client.get(
            urljoin(self.base_url, path.lstrip("/")), params=params or None
        )
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
        }
        if response.status_code >= 400:
            raise QaFailure(f"GET {path} returned HTTP {response.status_code}", meta)
        return response.text, meta

    def post_json(
        self, path: str, payload: dict[str, Any]
    ) -> tuple[int, Any, dict[str, Any]]:
        started = monotonic()
        response = self.client.post(
            urljoin(self.base_url, path.lstrip("/")), json=payload
        )
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
        }
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None
        return response.status_code, response_payload, meta


def _pytest_evidence(pytest_junit: Path | str | None) -> dict[str, Any] | None:
    if pytest_junit is None:
        return None
    path = Path(pytest_junit)
    if not path.is_file():
        raise QaFailure("pytest JUnit 증거 파일이 없습니다.", {"pytest_junit": path})
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {
        key: sum(int(float(suite.attrib.get(key, "0"))) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    totals["path"] = str(path)
    return totals


def _gate_checks(
    collector: ResultCollector,
    catalog: dict[str, Any],
    *,
    pytest_junit: Path | str | None,
) -> None:
    from app.services import quant_signals as qs

    def catalog_contract() -> dict[str, Any]:
        ids = [case["id"] for case in catalog["cases"]]
        _assert(len(ids) >= 50, "QA 카탈로그 항목이 예상보다 적습니다.", count=len(ids))
        _assert(len(ids) == len(set(ids)), "QA ID가 중복되었습니다.")
        return {"catalog_version": catalog["catalog_version"], "case_count": len(ids)}

    collector.check(
        "DATA-COM-003",
        catalog_contract,
        pass_message="단일 QA 카탈로그의 필수 필드와 고유 ID를 확인했습니다.",
    )

    def redaction_contract() -> dict[str, Any]:
        sample = redact(
            {
                "authorization": "Bearer super-secret",
                "nested": {"api_key": "abc", "url": "https://x.test/?token_key=abc"},
            }
        )
        encoded = json.dumps(sample, ensure_ascii=False)
        _assert(
            "super-secret" not in encoded and "abc" not in encoded,
            "비밀값 마스킹에 실패했습니다.",
        )
        return sample

    collector.check(
        "DATA-COM-001",
        redaction_contract,
        pass_message="보고서의 인증정보 마스킹 계약을 확인했습니다.",
    )

    def strategy_contract() -> dict[str, Any]:
        _assert(
            qs.STRATEGY_VERSION == catalog["strategy_version"],
            "전략 버전이 QA 카탈로그와 다릅니다.",
        )
        return {"strategy_version": qs.STRATEGY_VERSION}

    collector.check(
        "SIG-VERSION-002",
        strategy_contract,
        pass_message="전략 버전과 QA 카탈로그 버전이 일치합니다.",
    )

    def input_contract() -> dict[str, Any]:
        _assert(qs.MIN_HISTORY_ROWS == 125, "최소 완전 일봉 계약이 변경되었습니다.")
        return {"minimum_complete_daily_bars": qs.MIN_HISTORY_ROWS}

    collector.check(
        "SIG-INPUT-001",
        input_contract,
        pass_message="최소 125개 완전 일봉 입력 계약을 확인했습니다.",
    )

    bar = qs.PriceBar(date(2026, 9, 4), 100, 103, 99, 102, 2_000_000, 10_000_000_000)
    common = {
        "atr_percent": 0.04,
        "ema20_extension_atr": 2.0,
        "average_trading_value": 6_000_000_000.0,
        "ema10": 101.0,
        "ema20": 100.0,
        "ema60": 99.0,
        "ema10_slope": 0.01,
        "ema20_slope": 0.01,
        "momentum5": 0.03,
        "momentum20": 0.02,
        "volume_ratio": 1.2,
        "high_distance": -0.02,
    }

    def entry_boundaries() -> dict[str, Any]:
        # Keep this fixture above the separate early-turn participation gate,
        # so it isolates the v7.4 established-trend score boundary.
        below = {**common, "score": qs.ENTRY_SCORE - 0.01, "volume_ratio": 1.0}
        exact = {**common, "score": qs.ENTRY_SCORE, "volume_ratio": 1.0}
        _assert(
            qs._entry_setup_kind(bar, below) is None,
            "64점 직전 기존 추세가 진입했습니다.",
        )
        _assert(
            qs._entry_setup_kind(bar, exact) == "trend_continuation",
            "64점 동일값 진입이 거절됐습니다.",
        )
        return {"threshold": qs.ENTRY_SCORE, "below": qs.ENTRY_SCORE - 0.01}

    collector.check(
        "SIG-ENTRY-001",
        entry_boundaries,
        pass_message="v7.4 기존 추세 64점 경계값을 확인했습니다.",
    )

    def early_boundaries() -> dict[str, Any]:
        early_bar = qs.PriceBar(
            date(2026, 9, 4), 99, 103, 98, 101.5, 2_000_000, 10_000_000_000
        )
        early = {
            **common,
            "score": qs.EARLY_ENTRY_SCORE,
            "ema10": 101.0,
            "ema20": 100.0,
            "ema60": 100.4,
            "ema20_slope": -0.001,
            "momentum20": 0.0,
        }
        _assert(
            qs._entry_setup_kind(early_bar, early) == "early_turn",
            "64점 조기 전환이 거절됐습니다.",
        )
        _assert(
            qs._entry_setup_kind(
                early_bar, {**early, "score": qs.EARLY_ENTRY_SCORE - 0.01}
            )
            is None,
            "64점 직전 조기 전환이 진입했습니다.",
        )
        return {"threshold": qs.EARLY_ENTRY_SCORE}

    collector.check(
        "SIG-ENTRY-002",
        early_boundaries,
        pass_message="v7.4 조기 전환 64점 경계값을 확인했습니다.",
    )

    def quality_guards() -> dict[str, Any]:
        _assert(
            qs._entry_quality_allowed(bar, {**common, "score": 70}),
            "정상 공통 품질 조건이 거절됐습니다.",
        )
        for field, value in (
            ("atr_percent", qs.MAX_ENTRY_ATR_PERCENT + 0.0001),
            ("ema20_extension_atr", qs.MAX_ENTRY_EXTENSION_ATR + 0.001),
            ("average_trading_value", qs.MIN_AVERAGE_TRADING_VALUE - 1),
            ("momentum5", -0.0001),
            ("volume_ratio", 0.79),
        ):
            _assert(
                not qs._entry_quality_allowed(
                    bar, {**common, "score": 70, field: value}
                ),
                f"{field} 품질 제한이 작동하지 않습니다.",
            )
        return {
            "atr_max": qs.MAX_ENTRY_ATR_PERCENT,
            "ema20_extension_atr_max": qs.MAX_ENTRY_EXTENSION_ATR,
            "average_trading_value_min": qs.MIN_AVERAGE_TRADING_VALUE,
            "pre_entry_score": qs.PRE_ENTRY_SCORE,
        }

    collector.check(
        "SIG-ENTRY-003",
        quality_guards,
        pass_message="v7.4 예비 포착 및 변동성·이격·모멘텀·참여·거래대금 품질 가드를 확인했습니다.",
    )

    def execution_gap() -> dict[str, Any]:
        pending = {"signal_price": 100.0, "atr": 2.0}
        _assert(
            qs._entry_execution_allowed(103.0, pending),
            "1.5ATR 동일값 체결이 거절됐습니다.",
        )
        _assert(
            not qs._entry_execution_allowed(103.01, pending),
            "1.5ATR 초과 갭이 체결됐습니다.",
        )
        return {
            "atr_multiple": qs.MAX_ENTRY_GAP_ATR,
            "absolute_percent_max": qs.MAX_ENTRY_GAP_PERCENT,
        }

    collector.check(
        "SIG-EXECUTION-002",
        execution_gap,
        pass_message="진입 갭 1.5ATR·5% 제한 경계값을 확인했습니다.",
    )

    def cost_contract() -> dict[str, Any]:
        for raw in (-1.0, 0.003, 1.0):
            cost = qs._execution_cost({"volume_ratio": 1.0, "atr_percent": raw})
            _assert(
                qs.MIN_EXECUTION_COST_PER_SIDE
                <= cost
                <= qs.MAX_EXECUTION_COST_PER_SIDE,
                "체결비용 범위를 벗어났습니다.",
                cost=cost,
            )
        return {
            "minimum": qs.MIN_EXECUTION_COST_PER_SIDE,
            "maximum": qs.MAX_EXECUTION_COST_PER_SIDE,
        }

    collector.check(
        "SIG-EXECUTION-003",
        cost_contract,
        pass_message="편도 체결비용 0.125~0.50% 제한을 확인했습니다.",
    )

    def ladder_contract() -> dict[str, Any]:
        legacy = qs._profit_ladder_steps(date(2026, 8, 23))
        preservation = qs._profit_ladder_steps(date(2026, 8, 24))
        tactical = qs._profit_ladder_steps(date(2026, 8, 25))
        current = qs._profit_ladder_steps(date(2026, 9, 4))
        _assert(
            legacy == qs.LEGACY_PROFIT_LADDER_STEPS,
            "2026-08-24 이전 규칙이 바뀌었습니다.",
        )
        _assert(
            preservation == qs.PROFIT_PRESERVATION_LADDER_STEPS,
            "v7.1 규칙이 바뀌었습니다.",
        )
        _assert(tactical == qs.TACTICAL_PROFIT_LADDER_STEPS, "v7.3 수익확정 규칙이 바뀌었습니다.")
        _assert(
            current == qs.PROFIT_LADDER_STEPS
            and round(sum(step[1] for step in current), 8) == 1.0,
            "v7.4 +3%/+5% 전체 확정 계약이 깨졌습니다.",
        )
        stable_position = {"entry_price": 100.0, "initial_risk": 2.0}
        resolved = qs._resolved_profit_ladder_steps(stable_position, date(2026, 9, 4))
        _assert(resolved[0][0] == 1.5 and resolved[1][0] == 2.5, "고정 목표가의 R 변환이 바뀌었습니다.")
        return {
            "legacy": legacy,
            "v7_1": preservation,
            "v7_3": tactical,
            "v7_4": current,
            "runner": qs.MIN_RUNNER_FRACTION,
        }

    collector.check(
        "SIG-EXIT-001",
        ladder_contract,
        pass_message="역사적 사다리와 v7.4 +3%/+5% 수익확정을 확인했습니다.",
    )
    collector.check(
        "SIG-VERSION-001",
        ladder_contract,
        pass_message="결정일별 과거·현행 전략 규칙 보존을 확인했습니다.",
    )

    def lifecycle_contract() -> dict[str, Any]:
        _assert(qs.REENTRY_COOLDOWN_BARS == 10, "재진입 유예 기간이 변경되었습니다.")
        _assert(qs.EXIT_SCORE == 42.0, "일반 이탈 점수가 변경되었습니다.")
        return {"cooldown_bars": qs.REENTRY_COOLDOWN_BARS, "exit_score": qs.EXIT_SCORE}

    collector.check(
        "SIG-LIFECYCLE-002",
        lifecycle_contract,
        pass_message="전량 매도 후 10거래일 재진입 유예를 확인했습니다.",
    )
    collector.check(
        "SIG-EXIT-004",
        lifecycle_contract,
        pass_message="일반 추세 이탈 점수 계약을 확인했습니다.",
    )

    def pending_contract() -> dict[str, Any]:
        payload = {
            "action": "entry_pending",
            "is_current_holding": False,
            "entry_price": 100,
            "target_sell_price": 120,
            "return_rate": 0.2,
            "current": {
                "action": "entry_pending",
                "position_open": False,
                "entry_price": 100,
                "target_sell_price": 120,
                "unrealized_return": 0.2,
            },
        }
        sanitized = qs.sanitize_pending_entry_signal_payload(payload)
        _assert(
            all(
                sanitized.get(key) is None
                for key in ("entry_price", "target_sell_price", "return_rate")
            ),
            "예비 신호에 거래정보가 남았습니다.",
        )
        _assert(
            sanitized["current"]["entry_price"] is None,
            "예비 신호 current에 매수가가 남았습니다.",
        )
        return {"cleared_fields": ["entry_price", "target_sell_price", "return_rate"]}

    collector.check(
        "SIG-CONTRACT-001",
        pending_contract,
        pass_message="예비 신호의 매수가·목표가·수익률 비노출 계약을 확인했습니다.",
    )

    # Remaining gate-only cases are executed in pytest fixtures. A JUnit file
    # is the machine-verifiable evidence; without it P0 cases remain skipped
    # and therefore block a gate report.
    try:
        pytest_result = _pytest_evidence(pytest_junit)
    except QaFailure as exc:
        pytest_result = {"error": str(exc), **exc.evidence}
    pytest_ok = bool(
        pytest_result
        and not pytest_result.get("error")
        and int(pytest_result.get("tests") or 0) > 0
        and int(pytest_result.get("failures") or 0) == 0
        and int(pytest_result.get("errors") or 0) == 0
    )
    executed = {item.id for item in collector.results}
    for case in catalog["cases"]:
        if "gate" not in case["modes"] or case["id"] in executed:
            continue
        collector.add(
            case["id"],
            "pass" if pytest_ok else "fail" if pytest_result else "skip",
            (
                "pytest JUnit 증거에서 고정 픽스처·계약 테스트 통과를 확인했습니다."
                if pytest_ok
                else "pytest 실행이 실패했습니다."
                if pytest_result
                else "pytest JUnit 증거가 없어 고정 픽스처·계약 테스트를 확인하지 못했습니다."
            ),
            evidence={
                "automation": case["automation"],
                "delegated_to": "pytest",
                "pytest": pytest_result,
            },
        )


def _dataset_state(
    payload: dict[str, Any],
    name: str,
    *,
    allow_caution: bool = False,
    allow_not_applicable: bool = False,
) -> dict[str, Any]:
    dataset = (payload.get("datasets") or {}).get(name)
    _assert(isinstance(dataset, dict), f"{name} 데이터셋 상태가 없습니다.")
    state = str(dataset.get("state") or "unavailable")
    evidence = {
        "dataset": name,
        "state": state,
        "source": dataset.get("source") or (dataset.get("api") or {}).get("source"),
        "target_date": dataset.get("target_date") or dataset.get("signal_date"),
        "latest_date": dataset.get("latest_date"),
        "coverage_rate": dataset.get("coverage_rate"),
        "last_success_at": dataset.get("last_success_at")
        or (dataset.get("api") or {}).get("last_success_at"),
    }
    if state == "ready" or (allow_not_applicable and state == "not_applicable"):
        return evidence
    if allow_caution and state == "caution":
        raise QaWarning(f"{name} 커버리지가 caution입니다.", evidence)
    raise QaFailure(f"{name} 상태가 {state}입니다.", evidence)


def _live_checks(
    collector: ResultCollector,
    catalog: dict[str, Any],
    *,
    base_url: str,
    timeout: float,
    direct_kis: bool,
) -> tuple[str | None, dict[str, Any]]:
    api = ReadOnlyApi(base_url, timeout)
    context: dict[str, Any] = {}
    try:

        def health_contract() -> dict[str, Any]:
            health, meta = api.get("/health")
            ready, ready_meta = api.get("/readyz")
            _assert(
                health.get("status") == "ok", "health 상태가 ok가 아닙니다.", **meta
            )
            _assert(
                ready.get("status") == "ok" and ready.get("database_ok") is True,
                "readyz 또는 DB가 준비되지 않았습니다.",
                **ready_meta,
            )
            _assert(
                health.get("strategy_version") == catalog["strategy_version"],
                "health 전략 버전이 다릅니다.",
                strategy_version=health.get("strategy_version"),
            )
            context["health"] = health
            return {
                "health": meta,
                "readyz": ready_meta,
                "strategy_version": health.get("strategy_version"),
            }

        collector.check(
            "DATA-COM-002",
            health_contract,
            pass_message="헬스·준비 상태와 HTTP 타임아웃 계약을 확인했습니다.",
        )

        def staging_page_summary_contract() -> dict[str, Any]:
            summary_case = next(
                (case for case in catalog["cases"] if case.get("id") == "SIG-UI-017"),
                {},
            )
            expected_prompt_version = str(
                summary_case.get("inputs", {}).get("prompt_version") or ""
            )
            dashboard, dashboard_meta = api.get_text("/dashboard", view="home")
            is_staging = (
                '<meta name="secret-note-environment" content="staging" />'
                in dashboard
            )
            request_payload = {
                "page_type": "recommendation_detail",
                "facts": {
                    "code": "005930",
                    "name": "삼성전자",
                    "buy_condition_met": True,
                    "recommendation_state": "entry_confirmed",
                    "customer_state": "new-buy-wait",
                    "customer_state_label": "신규 매수 대기",
                    "customer_state_note": "아직 매수 전",
                    "additional_buy_label": "보유 전",
                    "signal_action": "entry_pending",
                    "position_open": False,
                    "sources": [
                        {
                            "id": "buy-condition",
                            "label": "추천 기준 확인",
                            "value": "신규 매수 대기",
                        }
                    ],
                },
                "fallback": {
                    "headline": "삼성전자, 신규 매수를 기다리는 단계예요",
                    "summary": "추천 기준은 통과했지만 아직 매수 전이에요.",
                    "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료가 기준을 통과했어요.",
                    "action_title": "지금은 새로 살 가격이 기준 안인지 확인할 때예요",
                    "next_check": "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요.",
                    "evidence_refs": ["buy-condition"],
                },
            }
            status_code, payload, response_meta = api.post_json(
                "/ai/page-summary",
                request_payload,
            )
            _assert(
                status_code == 200,
                "쉬운 설명 API가 정상 응답하지 않았습니다.",
                http_status=status_code,
                latency_ms=response_meta["latency_ms"],
            )
            _assert(
                isinstance(payload, dict),
                "스테이징 쉬운 설명 API가 JSON 객체를 반환하지 않았습니다.",
                **response_meta,
            )
            required_copy = {
                "headline",
                "summary",
                "reason",
                "action_title",
                "next_check",
                "evidence_refs",
            }
            _assert(
                required_copy.issubset(payload)
                and all(str(payload.get(key) or "").strip() for key in required_copy - {"evidence_refs"})
                and isinstance(payload.get("evidence_refs"), list)
                and payload.get("generation_mode") in {"openai", "rules"}
                and expected_prompt_version
                and payload.get("prompt_version") == expected_prompt_version,
                "쉬운 설명 응답 스키마가 잘못됐습니다.",
                response_fields=sorted(payload),
                generation_mode=payload.get("generation_mode"),
                prompt_version=payload.get("prompt_version"),
                expected_prompt_version=expected_prompt_version,
            )
            return {
                "environment_meta": "staging" if is_staging else "production",
                "http_status": status_code,
                "latency_ms": response_meta["latency_ms"],
                "dashboard_http_status": dashboard_meta["http_status"],
                "generation_mode": payload.get("generation_mode"),
                "model_name": payload.get("model_name"),
                "prompt_version": payload.get("prompt_version"),
                "expected_prompt_version": expected_prompt_version,
                "cache_hit": payload.get("cache_hit"),
                "token_usage": {
                    "input": payload.get("input_tokens"),
                    "output": payload.get("output_tokens"),
                    "total": payload.get("total_tokens"),
                },
                "estimated_cost_usd": payload.get("estimated_cost_usd"),
            }

        collector.check(
            "SIG-UI-017",
            staging_page_summary_contract,
            pass_message="쉬운 설명 응답과 안전 폴백 계약을 확인했습니다.",
        )

        def staging_briefing_summary_contract() -> dict[str, Any]:
            briefing_case = next(
                (case for case in catalog["cases"] if case.get("id") == "SIG-UI-018"),
                {},
            )
            expected_prompt_version = str(
                briefing_case.get("inputs", {}).get("prompt_version") or ""
            )
            dashboard, dashboard_meta = api.get_text("/dashboard", view="news")
            is_staging = (
                '<meta name="secret-note-environment" content="staging" />'
                in dashboard
            )
            request_payload = {
                "page_type": "briefing_edition",
                "facts": {
                    "edition": "midday",
                    "edition_key": "qa-live:midday",
                    "edition_label": "점심판",
                    "publication_date": datetime.now(KST).date().isoformat(),
                    "selected_news_count": 1,
                    "opportunity_count": 1,
                    "caution_count": 0,
                    "sources": [
                        {
                            "id": "briefing-market-live-1",
                            "label": "시장 흐름",
                            "value": "공개 시장 소식을 확인했어요.",
                            "evidence": "장중 흐름을 확인할 공개 자료예요.",
                        }
                    ],
                },
                "fallback": {
                    "headline": "오전 핵심을 새로 정리했어요",
                    "summary": "공개 시장 소식을 짧게 확인해요.",
                    "reason": "장중 흐름을 확인할 공개 자료예요.",
                    "action_title": "이번 점심판에서 먼저 볼 내용",
                    "next_check": "원문과 최신 시세를 함께 확인하세요.",
                    "evidence_refs": ["briefing-market-live-1"],
                },
            }
            status_code, payload, response_meta = api.post_json(
                "/ai/page-summary",
                request_payload,
            )
            _assert(
                status_code == 200 and isinstance(payload, dict),
                "브리핑 GPT 문구 정리 API가 정상 응답하지 않았습니다.",
                http_status=status_code,
                latency_ms=response_meta["latency_ms"],
            )
            required_copy = {
                "headline",
                "summary",
                "reason",
                "action_title",
                "next_check",
                "evidence_refs",
            }
            _assert(
                required_copy.issubset(payload)
                and payload.get("generation_mode") in {"openai", "rules"}
                and payload.get("prompt_version") == expected_prompt_version
                and set(payload.get("evidence_refs") or {})
                <= {"briefing-market-live-1"},
                "브리핑 구조화 요약 계약이 잘못됐습니다.",
                response_fields=sorted(payload),
                generation_mode=payload.get("generation_mode"),
                prompt_version=payload.get("prompt_version"),
                evidence_refs=payload.get("evidence_refs"),
            )
            return {
                "environment_meta": "staging" if is_staging else "production",
                "http_status": status_code,
                "latency_ms": response_meta["latency_ms"],
                "dashboard_http_status": dashboard_meta["http_status"],
                "generation_mode": payload.get("generation_mode"),
                "model_name": payload.get("model_name"),
                "prompt_version": payload.get("prompt_version"),
                "cache_hit": payload.get("cache_hit"),
                "token_usage": {
                    "input": payload.get("input_tokens"),
                    "output": payload.get("output_tokens"),
                    "total": payload.get("total_tokens"),
                },
                "estimated_cost_usd": payload.get("estimated_cost_usd"),
            }

        collector.check(
            "SIG-UI-018",
            staging_briefing_summary_contract,
            pass_message="세 브리핑의 구조화 문구 정리와 안전 폴백 계약을 확인했습니다.",
        )

        def integrations_contract() -> dict[str, Any]:
            payload, meta = api.get("/meta/integrations")
            _assert(
                isinstance(payload, list) and payload,
                "연동 메타데이터가 비어 있습니다.",
                **meta,
            )
            secret_fields: list[str] = []
            for index, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                for key, value in item.items():
                    # ``required_settings: [KIS_APP_SECRET]`` documents a
                    # variable name and is safe. Only secret-shaped response
                    # fields containing an actual value are forbidden.
                    if SECRET_KEY_RE.search(str(key)) and value not in (
                        None,
                        "",
                        False,
                        [],
                        {},
                    ):
                        secret_fields.append(f"{index}:{key}")
            _assert(
                not secret_fields,
                "연동 메타데이터에 인증정보 값이 노출됐습니다.",
                secret_fields=secret_fields,
            )
            context["integrations"] = payload
            return {
                **meta,
                "integrations": [
                    {"name": item.get("name"), "configured": item.get("configured")}
                    for item in payload
                ],
            }

        collector.check(
            "DATA-COM-001",
            integrations_contract,
            pass_message="연동 상태에 인증정보가 노출되지 않았습니다.",
        )

        def quality_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/meta/signal-data-quality", probe="true", sample_code="005930"
            )
            _assert(
                isinstance(payload, dict), "데이터 품질 응답이 객체가 아닙니다.", **meta
            )
            # Preserve the response for the layer-specific checks even when
            # this top-level version contract itself fails.
            context["quality"] = payload
            _assert(
                payload.get("strategy_version") == catalog["strategy_version"],
                "데이터 품질 전략 버전이 다릅니다.",
                strategy_version=payload.get("strategy_version"),
            )
            _assert(payload.get("as_of"), "데이터 품질 기준 시각이 없습니다.")
            return {
                **meta,
                "status": payload.get("status"),
                "as_of": payload.get("as_of"),
                "strategy_version": payload.get("strategy_version"),
            }

        collector.check(
            "DATA-COM-004",
            quality_contract,
            pass_message="기준 시각·전략 버전·품질 상태 응답을 확인했습니다.",
        )
        quality = context.get("quality") or {}

        core_map = (
            ("DATA-KRX-NAVER-002", "price", False, False),
            ("DATA-KRX-NAVER-005", "investor_flow", False, False),
            ("DATA-GLOBAL-001", "market_index", False, False),
            ("DATA-FUND-RESEARCH-001", "fundamentals", True, False),
            ("DATA-FUND-RESEARCH-002", "research", False, False),
            ("DATA-DART-002", "disclosure", False, False),
            ("SIG-EVIDENCE-003", "entry_evidence_snapshot", False, True),
        )
        for case_id, name, allow_caution, allow_na in core_map:
            collector.check(
                case_id,
                lambda name=name, allow_caution=allow_caution, allow_na=allow_na: (
                    _dataset_state(
                        quality,
                        name,
                        allow_caution=allow_caution,
                        allow_not_applicable=allow_na,
                    )
                ),
                pass_message=f"{name} 저장 데이터의 최신성과 커버리지를 확인했습니다.",
            )

        def coherence_contract() -> dict[str, Any]:
            coherence = quality.get("coherence") or {}
            evidence = {
                "state": coherence.get("state"),
                "signal_window_orphans": coherence.get(
                    "signal_window_orphan_stock_codes"
                ),
                "future_dated_rows": coherence.get("future_dated_rows"),
                "malformed_fundamentals": coherence.get(
                    "malformed_fundamental_snapshots"
                ),
                "flow_normalization": coherence.get("flow_normalization"),
            }
            _assert(
                coherence.get("state") == "ready",
                "저장 데이터 시점·매핑 정합성이 깨졌습니다.",
                **evidence,
            )
            return evidence

        collector.check(
            "SIG-INPUT-002",
            coherence_contract,
            pass_message="미래 데이터·미매핑·파싱 정합성을 확인했습니다.",
        )

        def source_probes() -> dict[str, Any]:
            probe = quality.get("api_probe") or {}
            items = probe.get("items") if isinstance(probe, dict) else None
            _assert(
                isinstance(items, list) and items, "외부 원천 probe 결과가 없습니다."
            )
            states = {
                str(item.get("key")): str(item.get("state"))
                for item in items
                if isinstance(item, dict)
            }
            failed = [key for key, state in states.items() if state != "ready"]
            if failed:
                raise QaWarning(
                    "일부 외부 원천 직접 probe가 실패했지만 저장 데이터 상태를 별도로 판정했습니다.",
                    {"states": states, "failed": failed},
                )
            return {"states": states}

        collector.check(
            "DATA-GLOBAL-003",
            source_probes,
            pass_message="외부 원천 읽기 전용 probe 응답 형식을 확인했습니다.",
        )

        def market_feed_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/market/quant-signals", universe_limit=100, limit=100, recent_days=30
            )
            _assert(
                isinstance(payload, dict), "시장 시그널 응답이 객체가 아닙니다.", **meta
            )
            _assert(
                payload.get("strategy_version") == catalog["strategy_version"],
                "시장 시그널 전략 버전이 다릅니다.",
                strategy_version=payload.get("strategy_version"),
            )
            status = str(payload.get("status") or "")
            _assert(
                status not in {"preparing", "unavailable", "error"},
                f"시장 시그널 상태가 {status}입니다.",
                **meta,
            )
            signal_revision = payload.get("signal_revision")
            _assert(
                isinstance(signal_revision, int)
                and not isinstance(signal_revision, bool)
                and signal_revision >= 0,
                "시장 시그널 signal_revision이 음이 아닌 정수가 아닙니다.",
                signal_revision=signal_revision,
            )
            signal_revision_as_of = _stream_timestamp(
                payload.get("signal_revision_as_of"),
                "market-signals.signal_revision_as_of",
            )
            _assert(
                payload.get("signal_revision_scope") == "canonical_market_feed",
                "시장 시그널 리비전 scope가 canonical market feed가 아닙니다.",
                signal_revision_scope=payload.get("signal_revision_scope"),
            )
            items = payload.get("items") or []
            _assert(isinstance(items, list), "시장 시그널 items가 배열이 아닙니다.")
            keys = [
                (item.get("code"), item.get("signal_date"), item.get("action"))
                for item in items
                if isinstance(item, dict)
            ]
            _assert(
                len(keys) == len(set(keys)),
                "동일 종목·날짜·상태 시그널이 중복됐습니다.",
            )
            pending_leaks = []
            for item in items:
                if not isinstance(item, dict) or item.get("action") not in {
                    "entry_watch",
                    "entry_pending",
                }:
                    continue
                for key in ("entry_price", "target_sell_price", "return_rate"):
                    if item.get(key) is not None:
                        pending_leaks.append(f"{item.get('code')}:{key}")
            _assert(
                not pending_leaks,
                "예비 시그널에 거래정보가 노출됐습니다.",
                leaks=pending_leaks,
            )
            context["market_signals"] = payload
            return {
                **meta,
                "status": status,
                "count": len(items),
                "as_of": payload.get("as_of"),
                "snapshot_state": payload.get("snapshot_state"),
                "signal_revision": signal_revision,
                "signal_revision_as_of": signal_revision_as_of.isoformat(),
                "signal_revision_scope": payload.get("signal_revision_scope"),
            }

        collector.check(
            "SIG-VERSION-002",
            market_feed_contract,
            pass_message="시장 시그널 버전·상태·중복·예비정보 계약을 확인했습니다.",
        )
        if context.get("market_signals"):
            collector.check(
                "SIG-LIFECYCLE-003",
                market_feed_contract,
                pass_message="동일 날짜 중복 시그널이 없음을 확인했습니다.",
            )
            collector.check(
                "SIG-CONTRACT-001",
                market_feed_contract,
                pass_message="예비 시그널 거래정보 비노출을 확인했습니다.",
            )

            def recommendation_eligibility_contract() -> dict[str, Any]:
                recommendations, meta = api.get(
                    "/market/recommendations",
                    limit=20,
                    candidate_limit=100,
                )
                _assert(
                    isinstance(recommendations, dict),
                    "종목 추천 응답이 객체가 아닙니다.",
                    **meta,
                )
                _assert(
                    recommendations.get("selection_rule")
                    == "confirmed_entry_pending_or_entered_today",
                    "종목 추천의 매수 조건 자격 규칙이 다릅니다.",
                    selection_rule=recommendations.get("selection_rule"),
                )
                items = recommendations.get("items") or []
                _assert(isinstance(items, list), "종목 추천 items가 배열이 아닙니다.")
                recommendation_date = str(recommendations.get("as_of") or "")[:10]
                invalid: list[dict[str, Any]] = []
                state_counts = {"entry_confirmed": 0, "entered_today": 0}
                for item in items:
                    if not isinstance(item, dict):
                        invalid.append({"item": "not_object"})
                        continue
                    signal = item.get("ai_trade_signal")
                    current = (
                        signal.get("current")
                        if isinstance(signal, dict)
                        and isinstance(signal.get("current"), dict)
                        else {}
                    )
                    state = str(item.get("recommendation_state") or "")
                    lifecycle = current.get("lifecycle")
                    transition = (
                        lifecycle.get("latest_transition")
                        if isinstance(lifecycle, dict)
                        and isinstance(lifecycle.get("latest_transition"), dict)
                        else {}
                    )
                    confirmation = current.get("entry_confirmation")
                    pending_valid = bool(
                        state == "entry_confirmed"
                        and item.get("action") == "신규 매수 대기"
                        and current.get("action") == "entry_pending"
                        and current.get("position_open") is False
                    )
                    entered_today_valid = bool(
                        state == "entered_today"
                        and item.get("action") == "보유 유지"
                        and current.get("action") in {"entered", "holding"}
                        and current.get("position_open") is True
                        and str(current.get("entry_date") or "")[:10] == recommendation_date
                        and str(transition.get("transition_date") or "")[:10]
                        == recommendation_date
                        and str(transition.get("side") or "").lower() == "buy"
                        and isinstance(confirmation, dict)
                        and confirmation.get("allowed") is True
                        and item.get("strategy_entry_price") == current.get("entry_price")
                    )
                    if (
                        item.get("buy_condition_met") is not True
                        or current.get("live_observation") is not False
                        or not (pending_valid or entered_today_valid)
                    ):
                        invalid.append(
                            {
                                "code": item.get("code"),
                                "action": item.get("action"),
                                "recommendation_state": item.get("recommendation_state"),
                                "buy_condition_met": item.get("buy_condition_met"),
                                "signal_action": current.get("action"),
                                "position_open": current.get("position_open"),
                                "live_observation": current.get("live_observation"),
                                "entry_date": current.get("entry_date"),
                                "transition": transition,
                            }
                        )
                    elif state in state_counts:
                        state_counts[state] += 1
                _assert(
                    not invalid,
                    "당일 진입이 아닌 관찰·과거 보유·매도·장중 예비 종목이 추천 목록에 포함됐습니다.",
                    invalid=invalid,
                )
                expected_ranks = list(range(1, len(items) + 1))
                ranks = [item.get("rank") for item in items if isinstance(item, dict)]
                _assert(
                    ranks == expected_ranks,
                    "매수 조건 통과 종목의 추천 순위가 연속적이지 않습니다.",
                    ranks=ranks,
                )
                qualified_count = int(recommendations.get("qualified_count") or 0)
                _assert(
                    qualified_count >= len(items),
                    "추천 자격 종목 수가 반환 목록보다 작습니다.",
                    qualified_count=qualified_count,
                    returned_count=len(items),
                )
                _assert(
                    int(recommendations.get("pending_count") or 0)
                    >= state_counts["entry_confirmed"],
                    "추천 응답의 진입 대기 수가 반환 상태보다 작습니다.",
                    pending_count=recommendations.get("pending_count"),
                    returned_pending=state_counts["entry_confirmed"],
                )
                _assert(
                    int(recommendations.get("entered_today_count") or 0)
                    >= state_counts["entered_today"],
                    "추천 응답의 오늘 시가 반영 수가 반환 상태보다 작습니다.",
                    entered_today_count=recommendations.get("entered_today_count"),
                    returned_entered_today=state_counts["entered_today"],
                )
                return {
                    **meta,
                    "selection_rule": recommendations.get("selection_rule"),
                    "qualified_count": qualified_count,
                    "pending_count": recommendations.get("pending_count"),
                    "entered_today_count": recommendations.get("entered_today_count"),
                    "returned_count": len(items),
                    "codes": [item.get("code") for item in items if isinstance(item, dict)],
                }

            collector.check(
                "SIG-CONTRACT-002",
                recommendation_eligibility_contract,
                pass_message="추천 목록이 조건 확정 종목을 오늘 시가 반영일까지 유지하고 오래된 보유 종목은 제외함을 확인했습니다.",
            )

            def signal_surface_contract() -> dict[str, Any]:
                payload = context["market_signals"]
                preliminary_mismatches: list[dict[str, Any]] = []
                return_mismatches: list[dict[str, Any]] = []
                checked_preliminary = 0
                checked_open_positions = 0
                checked_closed_trades = 0
                for item in payload.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    current = item.get("current") if isinstance(item.get("current"), dict) else {}
                    action = str(current.get("action") or item.get("action") or "")
                    preliminary = bool(
                        item.get("is_preliminary")
                        or item.get("status") == "preliminary"
                        or action
                        in {
                            "entry_watch",
                            "entry_pending",
                            "partial_exit_pending",
                            "full_exit_pending",
                        }
                    )
                    if preliminary:
                        checked_preliminary += 1
                        signal_date = str(item.get("signal_date") or "")[:10]
                        signal_at_date = str(item.get("signal_at") or "")[:10]
                        if (
                            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", signal_date)
                            or signal_at_date != signal_date
                        ):
                            preliminary_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "action": action,
                                    "signal_date": item.get("signal_date"),
                                    "signal_at": item.get("signal_at"),
                                    "current_as_of": current.get("as_of"),
                                    "live_observation": current.get("live_observation"),
                                }
                            )

                    holding = bool(
                        item.get("is_current_holding")
                        or current.get("position_open") is True
                    )
                    return_kind = str(item.get("display_return_kind") or "")
                    display_return = item.get("display_return_rate")
                    if holding:
                        checked_open_positions += 1
                        holding_context = (
                            item.get("holding_context")
                            if isinstance(item.get("holding_context"), dict)
                            else {}
                        )
                        return_basis = (
                            holding_context.get("return_basis")
                            if isinstance(holding_context.get("return_basis"), dict)
                            else current.get("return_basis")
                            if isinstance(current.get("return_basis"), dict)
                            else {}
                        )
                        basis_fields_ok = all(
                            _finite_number(return_basis.get(key)) is not None
                            for key in ("price", "return_rate", "return_rate_per_price")
                        )
                        if (
                            return_kind != "open_position"
                            or _finite_number(display_return) is None
                            or not basis_fields_ok
                        ):
                            return_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "state": "open_position",
                                    "display_return_kind": item.get("display_return_kind"),
                                    "display_return_rate": display_return,
                                    "return_basis": return_basis,
                                }
                            )
                    elif return_kind == "closed_trade":
                        checked_closed_trades += 1
                        recorded_return = item.get("return_rate")
                        display_number = _finite_number(display_return)
                        recorded_number = _finite_number(recorded_return)
                        same_return = display_number is not None and (
                            recorded_return is None
                            or (
                                recorded_number is not None
                                and abs(display_number - recorded_number) < 1e-9
                            )
                        )
                        if item.get("live_return_rate") is not None or not same_return:
                            return_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "state": "closed_trade",
                                    "display_return_rate": display_return,
                                    "return_rate": recorded_return,
                                    "live_return_rate": item.get("live_return_rate"),
                                }
                            )
                _assert(
                    not preliminary_mismatches,
                    "예비 시그널의 장 기준일과 발생 시각이 어긋났습니다.",
                    mismatches=preliminary_mismatches,
                )
                _assert(
                    not return_mismatches,
                    "열린 포지션 실시간 수익률 또는 완료 매매 고정 수익률 계약이 어긋났습니다.",
                    mismatches=return_mismatches,
                )
                return {
                    "checked_preliminary_signals": checked_preliminary,
                    "checked_open_positions": checked_open_positions,
                    "checked_closed_trades": checked_closed_trades,
                    "preliminary_mismatches": preliminary_mismatches,
                    "return_mismatches": return_mismatches,
                }

            collector.check(
                "SIG-CONTRACT-003",
                signal_surface_contract,
                pass_message="예비 장 기준일·열린 포지션 수익률·완료 매매 고정 손익 계약을 확인했습니다.",
            )

            def recent_signal_window_contract() -> dict[str, Any]:
                payload = context["market_signals"]
                reference_raw = str(payload.get("as_of") or "")
                try:
                    reference_date = datetime.fromisoformat(
                        reference_raw.replace("Z", "+00:00")
                    ).astimezone(KST).date()
                except ValueError:
                    raise QaFailure(
                        "시장 시그널 기준 시각을 해석할 수 없습니다.",
                        {"as_of": reference_raw},
                    ) from None
                recent_days = int(payload.get("recent_days") or 30)
                cutoff = reference_date - timedelta(days=recent_days)
                stale: list[dict[str, Any]] = []
                future: list[dict[str, Any]] = []
                checked = 0
                holding_exceptions = 0
                for item in payload.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    current = item.get("current") or {}
                    holding = bool(
                        item.get("is_current_holding")
                        or (isinstance(current, dict) and current.get("position_open"))
                    )
                    preliminary = bool(
                        item.get("is_preliminary")
                        or item.get("status") == "preliminary"
                        or item.get("action") in {"entry_watch", "entry_pending"}
                    )
                    raw_date = (
                        item.get("signal_date")
                        if preliminary
                        else item.get("execution_date") or item.get("signal_date")
                    )
                    if not raw_date:
                        continue
                    try:
                        candidate = date.fromisoformat(str(raw_date)[:10])
                    except ValueError:
                        raise QaFailure(
                            "시장 시그널 날짜를 해석할 수 없습니다.",
                            {"code": item.get("code"), "date": raw_date},
                        ) from None
                    checked += 1
                    if candidate > reference_date:
                        future.append({"code": item.get("code"), "date": str(raw_date)})
                    elif candidate < cutoff:
                        if holding:
                            holding_exceptions += 1
                        else:
                            stale.append({"code": item.get("code"), "date": str(raw_date)})
                _assert(
                    not future,
                    "미래 날짜 시장 시그널이 노출됐습니다.",
                    future=future,
                    reference_date=reference_date,
                )
                _assert(
                    not stale,
                    "최근 30일 범위를 벗어난 비보유 시그널이 노출됐습니다.",
                    stale=stale,
                    cutoff=cutoff,
                )
                return {
                    "recent_days": recent_days,
                    "reference_date": reference_date,
                    "cutoff": cutoff,
                    "checked": checked,
                    "holding_exceptions": holding_exceptions,
                }

            collector.check(
                "SIG-CONTRACT-004",
                recent_signal_window_contract,
                pass_message="최근 30일 시그널 경계와 장기 보유 예외를 확인했습니다.",
            )

        def representative_contract() -> dict[str, Any]:
            stock, stock_meta = api.get("/stocks/005930")
            dashboard, dashboard_meta = api.get(
                "/stocks/005930/dashboard",
                include_profile="false",
                include_live="false",
            )
            quote, quote_meta = api.get("/stocks/005930/quote")
            intraday, intraday_meta = api.get("/stocks/005930/intraday")
            signal, signal_meta = api.get("/stocks/005930/quant-signals")
            _assert(
                stock.get("code") == "005930", "대표 종목 코드가 일치하지 않습니다."
            )
            _assert(
                isinstance(dashboard, dict)
                and isinstance(quote, dict)
                and isinstance(signal, dict),
                "대표 종목 API 형식이 잘못됐습니다.",
            )
            points = intraday.get("points") if isinstance(intraday, dict) else intraday
            _assert(isinstance(points, list), "분봉 points가 배열이 아닙니다.")
            _assert(
                signal.get("strategy_version") == catalog["strategy_version"],
                "상세 시그널 버전이 다릅니다.",
            )
            context["quote"] = quote
            context["signal"] = signal
            return {
                "stock": {
                    "code": stock.get("code"),
                    "name": stock.get("name"),
                    "market": stock.get("market"),
                },
                "dashboard_http": dashboard_meta["http_status"],
                "quote_http": quote_meta["http_status"],
                "intraday_points": len(points),
                "signal_action": (signal.get("current") or {}).get("action")
                or signal.get("action"),
                "signal_as_of": signal.get("as_of"),
                "latency_ms": {
                    "stock": stock_meta["latency_ms"],
                    "dashboard": dashboard_meta["latency_ms"],
                    "quote": quote_meta["latency_ms"],
                    "intraday": intraday_meta["latency_ms"],
                    "signal": signal_meta["latency_ms"],
                },
            }

        collector.check(
            "DATA-KIS-002",
            representative_contract,
            pass_message="대표 종목 현재가·분봉·신호 API 계약을 확인했습니다.",
        )
        if context.get("signal"):
            collector.check(
                "SIG-INPUT-003",
                representative_contract,
                pass_message="대표 종목의 저장 일봉·실시간 시세 격리 계약을 확인했습니다.",
            )

        endpoint_cases = (
            ("DATA-KIS-003", "/market/indices", {"limit": 5}),
            (
                "DATA-KRX-NAVER-004",
                "/market/rankings",
                {"category": "market_cap", "limit": 15},
            ),
            (
                "DATA-FUND-RESEARCH-003",
                "/research-reports",
                {"stock_code": "005930", "limit": 5},
            ),
            ("DATA-DART-003", "/disclosures", {"stock_code": "005930", "limit": 5}),
            ("DATA-GLOBAL-002", "/market/global-assets", {"limit": 5}),
            ("DATA-CALENDAR-CONTENT-001", "/market/trends", {"days": 7}),
            ("DATA-CALENDAR-CONTENT-002", "/news-items", {"limit": 5}),
            ("DATA-CALENDAR-CONTENT-004", "/market/calendar", {"days": 14}),
            ("DATA-CALENDAR-CONTENT-005", "/briefings/morning-money", {}),
            ("DATA-ETF-001", "/stocks/069500/etf-profile", {}),
            (
                "DATA-FUND-ANALYSIS-001",
                "/stocks/005930/sector-operating-margins",
                {"limit": 5},
            ),
            ("DATA-FUND-ANALYSIS-002", "/stocks/000660/sga-analysis", {}),
        )
        for case_id, path, params in endpoint_cases:

            def endpoint_contract(
                path: str = path, params: dict[str, Any] = params
            ) -> dict[str, Any]:
                payload, meta = api.get(path, **params)
                _assert(payload is not None, f"{path} 응답이 비어 있습니다.", **meta)
                size = (
                    len(payload)
                    if isinstance(payload, list)
                    else len(payload.get("items") or [])
                    if isinstance(payload, dict)
                    else None
                )
                return {**meta, "item_count": size}

            collector.check(
                case_id,
                endpoint_contract,
                pass_message=f"{path} 읽기 전용 연동 계약을 확인했습니다.",
            )

        def us_contract() -> dict[str, Any]:
            payload, meta = api.get("/us/stocks/AAPL/dashboard")
            _assert(
                isinstance(payload, dict),
                "미국 대표 종목 API 형식이 잘못됐습니다.",
                **meta,
            )
            return {
                **meta,
                "symbol": payload.get("symbol") or payload.get("code"),
                "as_of": payload.get("as_of"),
            }

        collector.check(
            "DATA-GLOBAL-002",
            us_contract,
            pass_message="미국 대표 종목 데이터 계약을 확인했습니다.",
        )

        def realtime_status_contract() -> dict[str, Any]:
            payload, meta = api.get("/realtime/status")
            channels = payload.get("public_quote_channels") or {}
            unique_codes = int(channels.get("unique_codes") or 0)
            kis_realtime_codes = int(channels.get("kis_realtime_codes") or 0)
            fallback_codes = int(channels.get("fallback_codes") or 0)
            session_codes = int(channels.get("kis_session_codes") or 0)
            _assert(
                int(channels.get("max_codes_per_client") or 0) > 0,
                "실시간 구독 제한값이 없습니다.",
                **meta,
            )
            _assert(
                0 <= kis_realtime_codes <= 40,
                "KIS 실시간 종목 수가 40개 안전 상한을 벗어났습니다.",
                kis_realtime_codes=kis_realtime_codes,
            )
            _assert(
                fallback_codes >= 0
                and kis_realtime_codes + fallback_codes == unique_codes,
                "실시간·REST 폴백 종목 수가 전체 구독 종목 수와 다릅니다.",
                unique_codes=unique_codes,
                kis_realtime_codes=kis_realtime_codes,
                fallback_codes=fallback_codes,
            )
            _assert(
                session_codes >= kis_realtime_codes
                and isinstance(channels.get("idle_grace_active"), bool)
                and int(channels.get("idle_grace_seconds") or 0) > 0
                and int(channels.get("contention_backoff_seconds") or 0) > 0,
                "KIS 단일 세션 idle grace 상태 계약이 잘못됐습니다.",
                session_codes=session_codes,
                idle_grace_active=channels.get("idle_grace_active"),
                idle_grace_seconds=channels.get("idle_grace_seconds"),
                contention_backoff_seconds=channels.get(
                    "contention_backoff_seconds"
                ),
            )
            _assert(
                isinstance(channels.get("min_broadcast_interval_ms"), int)
                and not isinstance(channels.get("min_broadcast_interval_ms"), bool)
                and int(channels["min_broadcast_interval_ms"]) >= 0,
                "실시간 시세 방송 최소 간격이 잘못됐습니다.",
                min_broadcast_interval_ms=channels.get("min_broadcast_interval_ms"),
            )
            return {
                **meta,
                "public_quote_channels": channels,
                "connections": payload.get("connections"),
            }

        collector.check(
            "DATA-KIS-006",
            realtime_status_contract,
            pass_message="실시간 구독 제한과 REST 폴백 상태를 확인했습니다.",
        )

        _public_websocket_check(
            collector,
            base_url,
            timeout,
            expected_signal_revision=(context.get("market_signals") or {}).get(
                "signal_revision"
            ),
        )
        if direct_kis:
            _direct_kis_checks(collector)
        else:
            for case_id in ("DATA-KIS-001", "DATA-KIS-004", "DATA-KIS-007"):
                collector.add(
                    case_id,
                    "skip",
                    "--direct-kis 옵션이 없어 KIS 원천 직접 호출을 생략했습니다.",
                    evidence={"direct_kis": False},
                )
    finally:
        api.close()

    return _market_state(context.get("quote"), context.get("quality")), context


def _public_websocket_check(
    collector: ResultCollector,
    base_url: str,
    timeout: float,
    *,
    expected_signal_revision: int | None = None,
) -> None:
    def websocket_contract() -> dict[str, Any]:
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise QaWarning(
                "websockets 동기 클라이언트가 없어 공개 실시간 채널을 생략했습니다."
            ) from exc
        ws_url, stream_resolution = _resolve_public_quote_stream_url(
            base_url, timeout
        )
        scheme = urlparse(ws_url).scheme

        def receive_required(
            socket: Any, required_types: set[str], *, maximum_frames: int = 12
        ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
            required = set(required_types)
            selected: dict[str, dict[str, Any]] = {}
            observed: list[dict[str, Any]] = []
            for _ in range(maximum_frames):
                frame = json.loads(socket.recv(timeout=timeout))
                _assert(isinstance(frame, dict), "WebSocket 프레임이 객체가 아닙니다.")
                observed.append(frame)
                frame_type = str(frame.get("type") or "")
                if frame_type == "status":
                    _validate_quote_status_frame(frame)
                elif frame_type == "error":
                    if frame.get("code") == "subscription_rate_limited":
                        _assert(
                            isinstance(frame.get("retry_after_ms"), int)
                            and int(frame["retry_after_ms"]) > 0,
                            "구독 속도 제한 error에 retry_after_ms가 없습니다.",
                            frame=frame,
                        )
                    raise QaFailure("WebSocket 구독 중 error 프레임을 받았습니다.", {"frame": frame})
                if frame_type in required and frame_type not in selected:
                    selected[frame_type] = frame
                    required.discard(frame_type)
                if not required:
                    return selected, observed
            raise QaFailure(
                "WebSocket 필수 프레임을 제한 개수 안에 받지 못했습니다.",
                {
                    "missing_types": sorted(required),
                    "observed_types": [frame.get("type") for frame in observed],
                },
            )

        with connect(ws_url, open_timeout=timeout, close_timeout=3) as socket:
            opening, opening_frames = receive_required(
                socket, {"ready", "signal_revision"}
            )
            ready = opening["ready"]
            revision = _validate_signal_revision_frame(
                opening["signal_revision"], require_initial=True
            )
            if expected_signal_revision is not None:
                _assert(
                    revision["revision"] == expected_signal_revision,
                    "WebSocket 초기 신호 리비전이 HTTP 스냅샷과 다릅니다.",
                    websocket_revision=revision["revision"],
                    http_revision=expected_signal_revision,
                )
            _assert(ready.get("transport") == "multiplex", "WebSocket transport가 multiplex가 아닙니다.")
            _assert(
                int(ready.get("max_codes") or 0) > 0,
                "WebSocket ready에 종목 구독 상한이 없습니다.",
            )
            socket.send(json.dumps({"type": "set", "codes": ["005930"]}))
            subscribed_frames, quote_frames = receive_required(
                socket, {"subscribed", "quote"}
            )
            subscribed = subscribed_frames["subscribed"]
            _assert(
                subscribed.get("type") == "subscribed" and subscribed.get("count") == 1,
                "WebSocket 구독 ACK가 올바르지 않습니다.",
            )
            _assert(
                subscribed.get("codes") == ["005930"]
                and isinstance(subscribed.get("rejected_codes"), list)
                and not subscribed.get("rejected_codes"),
                "WebSocket 구독 ACK의 codes·rejected_codes가 올바르지 않습니다.",
                subscribed=subscribed,
            )
            quote = _validate_public_quote_frame(
                subscribed_frames["quote"], expected_code="005930"
            )
            socket.send(json.dumps({"type": "set", "codes": []}))
            unsubscribe_frames, unsubscribe_observed = receive_required(
                socket, {"subscribed"}
            )
            unsubscribed = unsubscribe_frames["subscribed"]
            _assert(
                unsubscribed.get("count") == 0
                and unsubscribed.get("codes") == []
                and isinstance(unsubscribed.get("rejected_codes"), list),
                "WebSocket 구독 해제가 반영되지 않았습니다.",
            )
        with connect(ws_url, open_timeout=timeout, close_timeout=3) as socket:
            reconnected_frames, reconnect_observed = receive_required(
                socket, {"ready", "signal_revision"}
            )
            reconnected = reconnected_frames["ready"]
            reconnected_revision = _validate_signal_revision_frame(
                reconnected_frames["signal_revision"], require_initial=True
            )
            _assert(
                reconnected.get("type") == "ready",
                "WebSocket 재연결 ready 프레임이 없습니다.",
            )
        return {
            "transport": scheme,
            "stream_url": ws_url,
            "stream_resolution": stream_resolution,
            "subscribe_count": 1,
            "unsubscribe_count": 0,
            "reconnected": True,
            "ready": {
                "transport": ready.get("transport"),
                "max_codes": ready.get("max_codes"),
            },
            "signal_revision": revision,
            "reconnected_signal_revision": reconnected_revision,
            "quote": quote,
            "observed_frame_types": [
                frame.get("type")
                for frame in [
                    *opening_frames,
                    *quote_frames,
                    *unsubscribe_observed,
                    *reconnect_observed,
                ]
            ],
        }

    started = monotonic()
    try:
        evidence = websocket_contract()
    except (QaFailure, QaWarning) as exc:
        collector.add(
            "DATA-KIS-005",
            "warn" if isinstance(exc, QaWarning) else "fail",
            str(exc),
            evidence=getattr(exc, "evidence", {}),
            duration_ms=round((monotonic() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - network volatility is evidence, not a crash.
        collector.add(
            "DATA-KIS-005",
            "warn",
            f"공개 WebSocket 실연동 확인 실패: {type(exc).__name__}",
            evidence={"exception_type": type(exc).__name__},
            duration_ms=round((monotonic() - started) * 1000),
        )
    else:
        collector.add(
            "DATA-KIS-005",
            "pass",
            "WebSocket ready·신호 리비전·구독 ACK·순서 메타 시세·해제·재연결을 확인했습니다.",
            evidence=evidence,
            duration_ms=round((monotonic() - started) * 1000),
        )


def _direct_kis_checks(collector: ResultCollector) -> None:
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import get_settings
    from app.services.kis_realtime import KisRealtimeQuoteProvider

    settings = get_settings()
    provider = KisRestBriefingProvider(settings)
    realtime = KisRealtimeQuoteProvider(settings)
    if not provider.is_configured():
        for case_id in ("DATA-KIS-001", "DATA-KIS-003", "DATA-KIS-004", "DATA-KIS-007"):
            collector.add(
                case_id,
                "warn",
                "KIS 인증정보가 없어 원천 직접 호출을 수행하지 못했습니다.",
                evidence={"configured": False},
            )
        return

    def oauth_contract() -> dict[str, Any]:
        token = provider._ensure_token()
        _assert(bool(token), "KIS OAuth 토큰이 비어 있습니다.")
        return {"configured": True, "token_received": True, "token_length": len(token)}

    collector.check(
        "DATA-KIS-001",
        oauth_contract,
        pass_message="KIS OAuth 토큰 발급과 메모리 캐시를 확인했습니다.",
    )

    def quote_and_venue() -> dict[str, Any]:
        krx = provider._request_current_price("005930", "J")
        _assert(krx.get("stck_prpr"), "KIS KRX 현재가가 없습니다.")
        integrated = provider._request_current_price("005930", "UN")
        return {
            "krx_price_present": True,
            "integrated_price_present": bool(integrated.get("stck_prpr")),
        }

    collector.check(
        "DATA-KIS-007",
        quote_and_venue,
        pass_message="KIS KRX·통합 시세 응답과 신호용 KRX 분리를 확인했습니다.",
    )

    def market_data_contract() -> dict[str, Any]:
        indices = provider.fetch_market_indices()
        intraday = provider.fetch_intraday_chart("005930", max_points=5)
        orderbook = provider._get(
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            "FHKST01010200",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"},
        )
        _assert(
            len(indices) == 2, "KIS 지수 2종이 완성되지 않았습니다.", count=len(indices)
        )
        _assert(isinstance(intraday, list), "KIS 분봉 응답이 배열이 아닙니다.")
        _assert(
            bool(orderbook.get("output1") or orderbook.get("output")),
            "KIS 호가 응답이 비어 있습니다.",
        )
        return {
            "indices": [item.get("code") for item in indices],
            "intraday_points": len(intraday),
            "orderbook_present": True,
        }

    collector.check(
        "DATA-KIS-003",
        market_data_contract,
        pass_message="KIS 지수·분봉·호가 원천 응답을 확인했습니다.",
    )

    def ranking_contract() -> dict[str, Any]:
        gainers = provider._fetch_fluctuation("gainers", 3, "0", "300")
        losers = provider._fetch_fluctuation("losers", 3, "-300", "0")
        turnover = provider._fetch_turnover(3)
        _assert(
            all((item.change_rate or 0) >= 0 for item in gainers),
            "상승률 순위에 음수 종목이 섞였습니다.",
        )
        _assert(
            all((item.change_rate or 0) <= 0 for item in losers),
            "하락률 순위에 양수 종목이 섞였습니다.",
        )
        return {
            "gainers": len(gainers),
            "losers": len(losers),
            "turnover": len(turnover),
        }

    collector.check(
        "DATA-KIS-004",
        ranking_contract,
        pass_message="KIS 거래량·등락률 순위 방향성을 확인했습니다.",
    )

    if realtime.is_configured():

        def approval_contract() -> dict[str, Any]:
            approval = asyncio.run(realtime.approval_key())
            _assert(bool(approval), "KIS WebSocket approval key가 비어 있습니다.")
            return {
                "approval_received": True,
                "approval_length": len(approval),
                "configured_limit": settings.kis_realtime_max_codes,
            }

        collector.check(
            "DATA-KIS-005",
            approval_contract,
            pass_message="KIS WebSocket approval 발급을 확인했습니다.",
        )


def _summary(results: list[QaCheckResult], mode: QaMode) -> dict[str, Any]:
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("pass", "warn", "fail", "skip")
    }
    p0_failures = [
        result.id
        for result in results
        if result.priority == "P0" and result.status == "fail"
    ]
    p0_missing = [
        result.id
        for result in results
        if mode == "gate" and result.priority == "P0" and result.status == "skip"
    ]
    return {
        **counts,
        "total": len(results),
        "p0_failures": p0_failures,
        "p0_missing": p0_missing,
        "deployment_blocked": bool(p0_failures or p0_missing),
        "policy": "P0 failure or missing gate evidence blocks deployment; WARN records tolerated degradation",
        "mode": mode,
    }


def run_data_signal_qa(
    *,
    mode: QaMode,
    base_url: str = "https://dark-theme-preview-staging.up.railway.app",
    timeout: float = 20.0,
    artifact_dir: Path | str | None = None,
    direct_kis: bool = False,
    pytest_junit: Path | str | None = None,
) -> dict[str, Any]:
    if mode not in {"gate", "live", "e2e"}:
        raise ValueError("mode must be gate, live, or e2e")
    catalog = load_qa_catalog()
    collector = ResultCollector(catalog)
    market_state: str | None = None
    if mode == "gate":
        _gate_checks(collector, catalog, pytest_junit=pytest_junit)
    elif mode == "live":
        market_state, _ = _live_checks(
            collector,
            catalog,
            base_url=base_url,
            timeout=timeout,
            direct_kis=direct_kis,
        )
    else:
        from app.qa.e2e import run_e2e_checks

        e2e_results = run_e2e_checks(
            catalog=catalog,
            base_url=base_url,
            timeout=timeout,
            artifact_dir=artifact_dir,
        )
        for result in e2e_results:
            collector.add(**result)
        for result in e2e_results:
            evidence = result.get("evidence") or {}
            for theme in ("dark", "light"):
                api_stock = (evidence.get(theme) or {}).get("api_stock") or {}
                if api_stock.get("market_state"):
                    market_state = str(api_stock["market_state"])
                    break
            if market_state:
                break

    results = collector.results
    summary = _summary(results, mode)
    report = {
        "schema_version": "1.0",
        "run_id": f"qa-{datetime.now(KST).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}",
        "mode": mode,
        "environment": _environment_name(base_url),
        "base_url": base_url.rstrip("/"),
        "as_of": datetime.now(KST).isoformat(),
        "market_state": market_state,
        "strategy_version": catalog["strategy_version"],
        "catalog_version": catalog["catalog_version"],
        "catalog_case_count": len(catalog["cases"]),
        "checks": [asdict(result) for result in results],
        "summary": summary,
        "deployment_blocked": summary["deployment_blocked"],
    }
    return redact(report)


def write_qa_report(report: dict[str, Any], output: Path | str) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(redact(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
