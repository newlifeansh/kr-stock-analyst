from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import unquote, urlencode
from zoneinfo import ZoneInfo

import httpx

from app.qa.runner import QaFailure, QaWarning, redact

KST = ZoneInfo("Asia/Seoul")
MOBILE_VIEWPORT = {"width": 458, "height": 872}
E2E_CASE_IDS = (
    "SIG-CONTRACT-003",
    "SIG-UI-001",
    "SIG-UI-002",
    "SIG-UI-003",
    "SIG-UI-005",
    "SIG-UI-006",
    "SIG-UI-007",
    "SIG-UI-008",
    "SIG-UI-009",
    "SIG-UI-010",
    "SIG-UI-011",
    "SIG-UI-012",
    "SIG-UI-013",
    "SIG-UI-014",
    "SIG-UI-015",
    "SIG-UI-016",
    "SIG-UI-017",
    "SIG-UI-018",
    "SIG-UI-019",
    "SIG-UI-020",
    "SIG-UI-021",
)


def _page_url(base_url: str, path: str, **query: str) -> str:
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{base_url.rstrip('/')}{path}{suffix}"


def _safe_name(case_id: str, theme: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", f"{case_id}-{theme}")


def _is_playwright_timeout(exc: Exception) -> bool:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError:  # pragma: no cover - run_e2e_checks reports this first.
        PlaywrightTimeoutError = TimeoutError
    return isinstance(exc, (TimeoutError, PlaywrightTimeoutError))


def _navigate_page(
    page: Any,
    url: str | None = None,
    *,
    wait_until: str = "commit",
    attempts: int = 2,
    ready_selector: str | None = None,
) -> Any:
    """Retry only a document commit timeout, then wait once for app readiness.

    A committed document can legitimately keep loading non-critical resources.
    Retrying after commit would also replay sessionStorage-driven product
    behavior, so the optional app selector is intentionally outside the retry
    loop.
    """

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if wait_until != "commit":
        raise ValueError("E2E navigation retries are only valid before document commit")
    action = "goto" if url is not None else "reload"
    retry_evidence: list[dict[str, Any]] = []
    response: Any = None
    for attempt in range(1, attempts + 1):
        try:
            if url is None:
                response = page.reload(wait_until=wait_until)
            else:
                response = page.goto(url, wait_until=wait_until)
            break
        except Exception as exc:
            if not _is_playwright_timeout(exc):
                raise
            retry_evidence.append(
                {
                    "action": action,
                    "attempt": attempt,
                    "wait_until": wait_until,
                    "reason": "navigation_timeout",
                }
            )
            existing_evidence = list(
                getattr(page, "_qa_navigation_retry_evidence", [])
            )
            try:
                setattr(
                    page,
                    "_qa_navigation_retry_evidence",
                    [*existing_evidence, retry_evidence[-1]],
                )
            except Exception:  # noqa: BLE001,S110 - evidence must not block recovery.
                pass
            if attempt >= attempts:
                raise QaFailure(
                    "운영 페이지 문서 연결 시간이 반복 초과됐습니다.",
                    {
                        "action": action,
                        "attempts": attempts,
                        "wait_until": wait_until,
                        "expected_url": url,
                        "current_url": getattr(page, "url", None),
                        "navigation_retries": list(
                            getattr(
                                page,
                                "_qa_navigation_retry_evidence",
                                retry_evidence,
                            )
                        ),
                    },
                ) from exc
    if ready_selector:
        try:
            page.wait_for_selector(ready_selector, state="attached")
        except Exception as exc:
            if not _is_playwright_timeout(exc):
                raise
            raise QaFailure(
                "문서는 연결됐지만 앱 준비 상태를 확인하지 못했습니다.",
                {
                    "action": action,
                    "ready_selector": ready_selector,
                    "expected_url": url,
                    "current_url": getattr(page, "url", None),
                    "navigation_retries": list(
                        getattr(page, "_qa_navigation_retry_evidence", [])
                    ),
                },
            ) from exc
    return response


def _result(
    catalog_by_id: dict[str, dict[str, Any]],
    case_id: str,
    status: str,
    message: str,
    started: float,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": status,
        "message": message,
        "evidence": redact(evidence or {}),
        "duration_ms": round((monotonic() - started) * 1000),
    }


def _stock_contract(base_url: str, timeout: float, code: str) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        stock_response = client.get(f"{base_url.rstrip('/')}/stocks/{code}")
        quote_response = client.get(f"{base_url.rstrip('/')}/stocks/{code}/quote")
        signal_response = client.get(
            f"{base_url.rstrip('/')}/stocks/{code}/quant-signals"
        )
    if any(
        response.status_code >= 400
        for response in (stock_response, quote_response, signal_response)
    ):
        raise QaFailure(
            f"{code} API 계약을 준비하지 못했습니다.",
            {
                "stock_http": stock_response.status_code,
                "quote_http": quote_response.status_code,
                "signal_http": signal_response.status_code,
            },
        )
    stock = stock_response.json()
    quote_payload = quote_response.json()
    quote = quote_payload.get("quote") or quote_payload
    signal = signal_response.json()
    current = signal.get("current") or {}
    price = quote.get("price") or quote.get("current_price") or quote.get("current")
    if isinstance(price, dict):
        price = price.get("price") or price.get("value")
    return {
        "code": code,
        "name": stock.get("name"),
        "market": stock.get("market"),
        "price": price,
        "change_rate": quote.get("change_rate"),
        "market_state": quote.get("market_session")
        or quote_payload.get("market_state")
        or quote_payload.get("market_status"),
        "market_state_label": quote.get("market_session_label"),
        "quote_as_of": quote_payload.get("as_of") or quote.get("trade_date"),
        "signal_as_of": signal.get("as_of"),
        "signal_action": current.get("action"),
        "signal_label": current.get("label"),
        "signal_return_rate": signal.get("display_return_rate"),
        "signal_return_date": signal.get("display_return_event_date"),
        "signal_transition_date": (
            (current.get("lifecycle") or {}).get("latest_transition") or {}
        ).get("transition_date"),
    }


def _market_signal_contract(base_url: str, timeout: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(
            f"{base_url.rstrip('/')}/market/quant-signals",
            params={"universe_limit": 150, "limit": 0, "recent_days": 30},
        )
    if response.status_code >= 400:
        raise QaFailure(
            "시장 AI 시그널 API 계약을 준비하지 못했습니다.",
            {"http_status": response.status_code},
        )
    payload = response.json()
    items = payload.get("items") or []
    history = payload.get("preliminary_history") or []
    current_codes = {
        str(item.get("code") or item.get("name") or "").strip()
        for item in items
        if item.get("code") or item.get("name")
    }
    released_history = [
        item for item in history if item.get("preliminary_active") is False
    ]
    signal_revision = payload.get("signal_revision")
    if (
        not isinstance(signal_revision, int)
        or isinstance(signal_revision, bool)
        or signal_revision < 0
    ):
        raise QaFailure(
            "시장 AI 시그널 리비전 계약이 없습니다.",
            {"signal_revision": signal_revision},
        )
    if payload.get("signal_revision_scope") != "canonical_market_feed":
        raise QaFailure(
            "시장 AI 시그널 리비전 scope가 canonical feed가 아닙니다.",
            {"signal_revision_scope": payload.get("signal_revision_scope")},
        )
    return {
        "strategy_version": payload.get("strategy_version"),
        "status": payload.get("status"),
        "snapshot_state": payload.get("snapshot_state"),
        "current_count": len(current_codes),
        "history_count": len(released_history),
        "as_of": payload.get("as_of"),
        "signal_revision": signal_revision,
        "signal_revision_as_of": payload.get("signal_revision_as_of"),
        "signal_revision_scope": payload.get("signal_revision_scope"),
    }


def _button_count(button: Any) -> int:
    count = button.locator("span").inner_text()
    digits = re.sub(r"[^0-9]", "", count)
    if not digits:
        raise QaFailure("필터 건수를 숫자로 읽지 못했습니다.", {"text": count})
    return int(digits)


def _select_tab(button: Any) -> None:
    button.evaluate(
        """el => new Promise(resolve => {
          el.click();
          const startedAt = performance.now();
          const waitForSelection = () => {
            if (el.getAttribute('aria-selected') === 'true' || performance.now() - startedAt >= 3000) {
              resolve();
              return;
            }
            requestAnimationFrame(waitForSelection);
          };
          requestAnimationFrame(waitForSelection);
        })"""
    )
    if button.get_attribute("aria-selected") != "true":
        raise QaFailure(
            "클릭한 탭의 선택 상태가 반영되지 않았습니다.",
            {"text": button.inner_text()},
        )


_NO_WAIT_ARGUMENT = object()


def _wait_for_ui_contract(
    page: Any,
    expression: str,
    *,
    stage: str,
    timeout_ms: int,
    arg: Any = _NO_WAIT_ARGUMENT,
) -> None:
    """Wait for a browser contract and preserve the stalled UI state on timeout."""

    try:
        kwargs: dict[str, Any] = {"timeout": timeout_ms}
        if arg is not _NO_WAIT_ARGUMENT:
            kwargs["arg"] = arg
        page.wait_for_function(expression, **kwargs)
    except Exception as exc:
        if not _is_playwright_timeout(exc):
            raise
        try:
            snapshot = page.evaluate(
                """() => {
                  const response = document.querySelector('#staging-ai-stock-response-view');
                  const latestSummary = (window.__qaStockSummaryRequests || [])
                    .filter(request => request.page_type === 'stock_response').at(-1);
                  return {
                    url: location.href,
                    view: document.body?.dataset.view || '',
                    responseDisplay: response?.dataset.responseDisplay || '',
                    responseLoaded: response?.dataset.responseLoaded || '',
                    investorState: response?.dataset.investorState || '',
                    summaryMode: response?.dataset.summaryMode || '',
                    latestPositionMode: latestSummary?.facts?.position_mode || '',
                    stockText: document.querySelector('#stock-view')?.innerText?.slice(0, 800) || '',
                  };
                }"""
            )
        except Exception:  # noqa: BLE001 - diagnostics must not mask the timeout.
            snapshot = {"url": getattr(page, "url", "")}
        raise QaFailure(
            f"{stage} 상태가 제한 시간 안에 완성되지 않았습니다.",
            {"stage": stage, "ui_snapshot": snapshot},
        ) from exc


def _assert_stock_quote_text(text: str, stock: dict[str, Any]) -> None:
    if stock.get("name") and stock["name"] not in text:
        raise QaFailure(
            "API 종목명이 상세 화면과 다릅니다.", {"api_name": stock["name"]}
        )
    market_label = stock.get("market_state_label")
    if market_label and market_label not in text:
        raise QaFailure(
            "API 장 상태가 상세 화면과 다릅니다.",
            {"api_market_state_label": market_label},
        )


def _assert_page_shell(page: Any, *, theme: str) -> dict[str, Any]:
    page.wait_for_selector("body", state="visible", timeout=20_000)
    loading = page.locator("#page-loading")
    if loading.count():
        loading.wait_for(state="hidden", timeout=30_000)
    gate = page.locator("#login-gate")
    if gate.count():
        gate.wait_for(state="hidden", timeout=30_000)
    push_sheet = page.locator("#push-notification-sheet")
    if push_sheet.count() and push_sheet.is_visible():
        try:
            page.evaluate(
                """() => {
                  const dismiss = document.querySelector('#push-notification-sheet-snooze-button');
                  const close = document.querySelector('#push-notification-sheet-close');
                  const visible = element => Boolean(
                    element && !element.hidden && element.getClientRects().length
                  );
                  if (visible(dismiss)) dismiss.click();
                  else if (visible(close)) close.click();
                }"""
            )
        except Exception:  # noqa: BLE001,S110 - transient UI can disappear during navigation.
            pass
    page.wait_for_timeout(300)
    script = """() => ({
      theme: document.documentElement.dataset.stagingTheme || document.body?.dataset.stagingTheme || null,
      viewport: window.innerWidth,
      rootWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body?.scrollWidth || 0,
      title: document.title,
      textLength: (document.body?.innerText || '').trim().length
    })"""
    state: dict[str, Any] = {}
    for _attempt in range(3):
        try:
            state = page.evaluate(script)
        except Exception:  # noqa: BLE001 - the browser may invalidate execution context during navigation.
            page.wait_for_selector("body", state="visible", timeout=20_000)
            continue
        if state["bodyWidth"] > 0 and state["textLength"] >= 20:
            break
        page.wait_for_timeout(500)
    if state["theme"] != theme:
        raise QaFailure("요청한 테마가 적용되지 않았습니다.", state)
    if (
        state["rootWidth"] > state["viewport"] + 2
        or state["bodyWidth"] > state["viewport"] + 2
    ):
        raise QaFailure("모바일 뷰포트에서 루트 가로 오버플로가 발생했습니다.", state)
    if state["textLength"] < 20:
        raise QaFailure("화면 본문이 비어 있습니다.", state)
    return state


def _run_page_case(
    *,
    browser: Any,
    catalog_by_id: dict[str, dict[str, Any]],
    case_id: str,
    base_url: str,
    timeout: float,
    artifact_dir: Path,
    callback: Callable[[Any, str], dict[str, Any]],
    storage_state: dict[str, Any] | None,
    share_id: str,
    dismiss_service_update: bool = True,
    reduced_motion: str = "reduce",
) -> dict[str, Any]:
    started = monotonic()
    theme_evidence: dict[str, Any] = {}
    navigation_retry_evidence: list[dict[str, Any]] = []
    try:
        for theme in ("dark", "light"):
            context = browser.new_context(
                viewport=MOBILE_VIEWPORT,
                color_scheme=theme,
                locale="ko-KR",
                timezone_id="Asia/Seoul",
                reduced_motion=reduced_motion,
                storage_state=storage_state,
                service_workers="block",
            )
            context.add_init_script(
                f"localStorage.setItem('analyst.watchlistId', {json.dumps(share_id)});"
            )
            normalized_share_id = share_id.strip().lower()
            context.add_init_script(
                "localStorage.setItem("
                f"{json.dumps(f'analyst.recommendationPushPromptDecision.v1.{normalized_share_id}')}, "
                "'dismissed');"
            )
            if dismiss_service_update:
                context.add_init_script(
                    "localStorage.setItem("
                    f"{json.dumps(f'analyst.pushEntryPromptSnoozedDate.{normalized_share_id}')}, "
                    f"{json.dumps(datetime.now(KST).date().isoformat())});"
                )
            context.route(
                "**/session/dashboard-access",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "required": True,
                            "authorized": True,
                            "newly_registered": False,
                            "registered_count": None,
                            "limit": None,
                        }
                    ),
                ),
            )
            if dismiss_service_update:
                context.add_init_script(
                    "localStorage.setItem('secret-note-service-update-dismissed:20260829-chart-analysis-v1', '1');"
                )
            else:
                context.add_init_script(
                    """
                    if (sessionStorage.getItem('qa-service-update-state-cleaned') !== '1') {
                      localStorage.removeItem('secret-note-service-update-dismissed:20260829-chart-analysis-v1');
                      sessionStorage.removeItem('secret-note-service-update-session:20260829-chart-analysis-v1');
                      sessionStorage.setItem('qa-service-update-state-cleaned', '1');
                    }
                    """
                )
            page = context.new_page()
            page.set_default_timeout(int(timeout * 1000))
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.on(
                "response",
                lambda response, errors=errors: (
                    errors.append(f"HTTP {response.status} {response.url}")
                    if response.status >= 500
                    else None
                ),
            )
            try:
                evidence = callback(page, theme)
                navigation_retries = list(
                    getattr(page, "_qa_navigation_retry_evidence", [])
                )
                if navigation_retries:
                    evidence = {
                        **evidence,
                        "navigation_retries": navigation_retries,
                    }
                if errors:
                    raise QaFailure(
                        "브라우저 콘솔 오류가 발생했습니다.", {"errors": errors[:10]}
                    )
                theme_evidence[theme] = evidence
            except Exception:
                navigation_retry_evidence.extend(
                    list(getattr(page, "_qa_navigation_retry_evidence", []))
                )
                artifact_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(
                        path=str(artifact_dir / f"{_safe_name(case_id, theme)}.png"),
                        full_page=True,
                        timeout=5_000,
                    )
                except Exception:  # noqa: BLE001,S110 - preserve the original QA failure.
                    # Screenshot capture is supporting evidence. A stalled renderer
                    # must not replace the actual QA failure that led us here.
                    pass
                raise
            finally:
                context.close()
    except QaWarning as exc:
        return _result(catalog_by_id, case_id, "warn", str(exc), started, exc.evidence)
    except (QaFailure, AssertionError) as exc:
        failure_evidence = dict(getattr(exc, "evidence", {}))
        if navigation_retry_evidence and "navigation_retries" not in failure_evidence:
            failure_evidence["navigation_retries"] = navigation_retry_evidence
        return _result(
            catalog_by_id,
            case_id,
            "fail",
            str(exc),
            started,
            {
                **failure_evidence,
                "artifact_dir": str(artifact_dir),
            },
        )
    except Exception as exc:  # noqa: BLE001 - turn browser failures into QA evidence.
        failure_evidence: dict[str, Any] = {"artifact_dir": str(artifact_dir)}
        if navigation_retry_evidence:
            failure_evidence["navigation_retries"] = navigation_retry_evidence
        return _result(
            catalog_by_id,
            case_id,
            "fail",
            f"{type(exc).__name__}: {exc}",
            started,
            failure_evidence,
        )
    return _result(
        catalog_by_id,
        case_id,
        "pass",
        "모바일 다크·라이트 화면 계약을 확인했습니다.",
        started,
        theme_evidence,
    )


def _browser_auth_state(
    browser: Any,
    *,
    base_url: str,
    timeout: float,
    invite_code: str,
) -> dict[str, Any] | None:
    context = browser.new_context()
    try:
        status = context.request.get(
            f"{base_url.rstrip('/')}/session/invite-status",
            timeout=timeout * 1000,
        )
        if not status.ok:
            raise QaFailure(
                "스테이징 초대 상태를 확인하지 못했습니다.",
                {"http_status": status.status},
            )
        payload = status.json()
        if payload.get("required") is not True:
            return context.storage_state()
        if not invite_code:
            raise QaFailure(
                "스테이징 E2E에 QA_DASHBOARD_INVITE_CODE가 필요합니다.",
                {"invite_required": True},
            )
        access = context.request.post(
            f"{base_url.rstrip('/')}/session/invite-access",
            data={"invite_code": invite_code},
            timeout=timeout * 1000,
        )
        if not access.ok:
            raise QaFailure(
                "스테이징 초대 인증에 실패했습니다.", {"http_status": access.status}
            )
        return context.storage_state()
    finally:
        context.close()


def run_e2e_checks(
    *,
    catalog: dict[str, Any],
    base_url: str,
    timeout: float,
    artifact_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    catalog_by_id = {case["id"]: case for case in catalog["cases"]}
    output_dir = Path(artifact_dir or "artifacts/qa-data-signal/e2e")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        message = "Playwright가 설치되지 않았습니다. `pip install -e '.[qa]'` 후 `playwright install chromium`을 실행하세요."
        return [
            _result(catalog_by_id, case_id, "fail", message, monotonic())
            for case_id in E2E_CASE_IDS
        ]

    contract_started = monotonic()
    try:
        samsung = _stock_contract(base_url, timeout, "005930")
        etf = _stock_contract(base_url, timeout, "069500")
        market_signals = _market_signal_contract(base_url, timeout)
    except Exception as exc:  # noqa: BLE001 - convert preparation failures into a complete QA report.
        message = f"E2E API 사전조건 확인 실패: {type(exc).__name__}: {exc}"
        evidence = getattr(exc, "evidence", {})
        return [
            _result(
                catalog_by_id,
                case_id,
                "fail",
                message,
                contract_started,
                evidence,
            )
            for case_id in E2E_CASE_IDS
        ]
    results: list[dict[str, Any]] = []
    try:
        from app.config import get_settings

        configured_invite = str(get_settings().dashboard_invite_code or "").strip()
    except Exception:  # noqa: BLE001 - environment-backed settings are optional for public staging.
        configured_invite = ""
    invite_code = str(
        os.environ.get("QA_DASHBOARD_INVITE_CODE")
        or os.environ.get("DASHBOARD_INVITE_CODE")
        or configured_invite
    ).strip()
    share_id = str(os.environ.get("QA_DASHBOARD_SHARE_ID") or "qa-automation").strip()
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001 - report a missing/incompatible browser as QA evidence.
            message = (
                "Chromium을 시작하지 못했습니다. `playwright install chromium`을 실행하세요. "
                f"({type(exc).__name__})"
            )
            return [
                _result(catalog_by_id, case_id, "fail", message, monotonic())
                for case_id in E2E_CASE_IDS
            ]
        try:
            try:
                storage_state = _browser_auth_state(
                    browser,
                    base_url=base_url,
                    timeout=timeout,
                    invite_code=invite_code,
                )
            except QaFailure as exc:
                return [
                    _result(
                        catalog_by_id,
                        case_id,
                        "fail",
                        str(exc),
                        monotonic(),
                        exc.evidence,
                    )
                    for case_id in E2E_CASE_IDS
                ]

            def search_stock_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="search",
                        theme=theme,
                        qa_run=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                    ready_selector="body[data-view='search']",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#search-view", state="visible")
                search_input = page.locator("#discovery-search-input")
                search_input.fill("삼성전자")
                page.wait_for_selector(
                    "#discovery-search-suggestions:not([hidden]) .discovery-suggestion-item",
                    state="visible",
                    timeout=int(timeout * 1000),
                )
                suggestion_item = page.locator(
                    "#discovery-search-suggestions .discovery-suggestion-item"
                ).first
                suggestion_contrast = suggestion_item.evaluate(
                    """element => {
                      const label = element.querySelector('strong') || element;
                      const itemStyle = getComputedStyle(element);
                      const labelStyle = getComputedStyle(label);
                      const rgb = value => {
                        const channels = String(value).match(/[0-9.]+/g)?.slice(0, 3).map(Number) || [];
                        return channels.length === 3 ? channels : [0, 0, 0];
                      };
                      const luminance = value => rgb(value)
                        .map(channel => channel / 255)
                        .map(channel => channel <= 0.04045
                          ? channel / 12.92
                          : Math.pow((channel + 0.055) / 1.055, 2.4))
                        .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
                      const foreground = labelStyle.color;
                      const background = itemStyle.backgroundColor;
                      const lighter = Math.max(luminance(foreground), luminance(background));
                      const darker = Math.min(luminance(foreground), luminance(background));
                      return {
                        foreground,
                        background,
                        ratio: Number(((lighter + 0.05) / (darker + 0.05)).toFixed(2)),
                        label: label.textContent?.trim() || '',
                      };
                    }"""
                )
                if suggestion_contrast["ratio"] < 4.5:
                    raise QaFailure(
                        "종목 검색 자동완성 글자 대비가 4.5:1보다 낮습니다.",
                        {"theme": theme, "suggestion_contrast": suggestion_contrast},
                    )
                page.evaluate(
                    """() => {
                      window.__qaStockEntryFrames = [];
                      const snapshot = () => {
                        const priceText = document.querySelector('#quote-price')?.textContent?.trim() || '';
                        const rateText = document.querySelector('#quote-change')?.textContent?.trim() || '';
                        const currentCode = String(state.currentStock?.code || '');
                        const readyCode = String(state.stockQuoteReadyCode || '');
                        const numeric = text => /[0-9]/.test(text) && text !== '-';
                        window.__qaStockEntryFrames.push({
                          priceText,
                          rateText,
                          currentCode,
                          readyCode,
                          hasNumericQuote: numeric(priceText) || numeric(rateText),
                        });
                      };
                      const observer = new MutationObserver(snapshot);
                      for (const selector of ['#quote-price', '#quote-change']) {
                        const node = document.querySelector(selector);
                        if (node) observer.observe(node, { childList: true, characterData: true, subtree: true });
                      }
                      window.__qaStockEntryObserver = observer;
                      snapshot();
                    }"""
                )
                search_input.press("Enter")
                page.wait_for_selector("#stock-view", state="visible")
                page.wait_for_function(
                    "name => document.querySelector('#stock-view')?.innerText?.includes(name)",
                    arg=samsung["name"],
                    timeout=int(timeout * 1000),
                )
                try:
                    # Quote and market-session fields can change while this
                    # production E2E is running. Read the client snapshot and
                    # its DOM projection in one browser task instead of
                    # comparing against a pre-run HTTP value.
                    page.wait_for_function(
                        """() => {
                          const quote = state.currentDashboard?.quote || {};
                          const price = Number(quote.price);
                          const rate = Number(quote.change_rate);
                          const sessionLabel = String(quote.market_session_label || '').trim();
                          const displayedPrice = Number(
                            (document.querySelector('#quote-price')?.textContent || '').replace(/[^0-9.-]/g, '')
                          );
                          const displayedRate = Number(
                            (document.querySelector('#quote-change')?.textContent || '').replace(/[^0-9.-]/g, '')
                          );
                          const displayedSession = String(
                            document.querySelector('#stock-market-status-label')?.textContent || ''
                          ).trim();
                          return Number.isFinite(price)
                            && Number.isFinite(rate)
                            && Boolean(sessionLabel)
                            && displayedPrice === price
                            && Math.abs(displayedRate - rate) < 0.001
                            && displayedSession.includes(sessionLabel);
                        }""",
                        timeout=int(timeout * 1000),
                    )
                except Exception as exc:
                    raise QaFailure(
                        "현재 시세 스냅샷의 가격·등락률·장 상태가 상세 화면에 함께 반영되지 않았습니다.",
                        {
                            "api_precondition": samsung,
                            "client_and_dom": page.evaluate(
                                """() => ({
                                  quote: state.currentDashboard?.quote || {},
                                  displayed_price: document.querySelector('#quote-price')?.textContent?.trim() || '',
                                  displayed_rate: document.querySelector('#quote-change')?.textContent?.trim() || '',
                                  displayed_session: document.querySelector('#stock-market-status-label')?.textContent?.trim() || '',
                                })"""
                            ),
                        },
                    ) from exc
                observed_quote = page.evaluate(
                    """() => ({
                      price: Number(state.currentDashboard?.quote?.price),
                      change_rate: Number(state.currentDashboard?.quote?.change_rate),
                      market_session: state.currentDashboard?.quote?.market_session || '',
                      market_session_label: state.currentDashboard?.quote?.market_session_label || '',
                      source: state.currentDashboard?.source || '',
                      as_of: state.currentDashboard?.as_of || '',
                      displayed_price: document.querySelector('#quote-price')?.textContent?.trim() || '',
                      displayed_rate: document.querySelector('#quote-change')?.textContent?.trim() || '',
                    })"""
                )
                entry_frames = page.evaluate(
                    """() => {
                      window.__qaStockEntryObserver?.disconnect();
                      return window.__qaStockEntryFrames || [];
                    }"""
                )
                premature_numeric_frames = [
                    frame
                    for frame in entry_frames
                    if frame.get("hasNumericQuote")
                    and frame.get("currentCode")
                    and frame.get("readyCode") != frame.get("currentCode")
                ]
                if premature_numeric_frames:
                    raise QaFailure(
                        "현재 시세 준비 전에 이전 가격·등락률이 먼저 노출됐습니다.",
                        {
                            "entry_frames": entry_frames,
                            "premature_numeric_frames": premature_numeric_frames,
                        },
                    )
                detail_text = page.locator("#stock-view").inner_text()
                _assert_stock_quote_text(detail_text, samsung)
                resolved_url = unquote(page.url)
                if (
                    samsung["code"] not in resolved_url
                    and samsung["name"] not in resolved_url
                ):
                    raise QaFailure(
                        "삼성전자 검색 결과가 상세 URL로 연결되지 않았습니다.",
                        {"url": page.url},
                    )
                return {
                    **shell,
                    "query": "삼성전자",
                    "suggestion_contrast": suggestion_contrast,
                    "detail_url": page.url,
                    "api_stock": samsung,
                    "observed_quote": observed_quote,
                    "entry_frames": entry_frames,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-001",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=search_stock_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def signal_filter_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="ai-signals",
                        theme=theme,
                        qa_run=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#ai-signals-view", state="visible")
                page.wait_for_function(
                    """() => {
                      const tabs = [...document.querySelectorAll('[data-ai-signal-stage]')];
                      const count = tab => Number(
                        (tab.querySelector('span')?.textContent || '').replace(/[^0-9]/g, '')
                      );
                      const current = Number(
                        (document.querySelector('#ai-signal-mode-current span')?.textContent || '')
                          .replace(/[^0-9]/g, '')
                      );
                      const loading = document.querySelector('#ai-signals-page-list')?.textContent
                        ?.includes('불러오는 중입니다.');
                      return tabs.length === 5
                        && !loading
                        && count(tabs[0]) === current
                        && tabs.slice(1).reduce((sum, tab) => sum + count(tab), 0) === current;
                    }""",
                    timeout=int(timeout * 1000),
                )
                page.evaluate(
                    """() => {
                      // Hold the loaded revision stable while the test walks
                      // each filter. The live socket contract is exercised
                      // below with deterministic ordered frames.
                      state.homeAiSignalsRequestId += 1;
                      state.aiSignalLoadSequence += 1;
                      window.clearTimeout(state.homeAiSignalsRetryTimer);
                      window.clearTimeout(state.aiSignalsPageRetryTimer);
                      window.clearTimeout(state.aiSignalRevisionTimer);
                      window.clearTimeout(state.aiSignalReconcileTimer);
                      state.homeAiSignalsRetryTimer = null;
                      state.aiSignalsPageRetryTimer = null;
                      state.aiSignalRevisionTimer = null;
                      state.aiSignalReconcileTimer = null;
                      state.quoteStreamSignalControlActive = false;
                      closeAiSignalQuoteStreams();
                      pauseQuoteStreamConnection('checking');
                    }"""
                )
                mode_tabs = page.locator("[data-ai-signal-mode]")
                stage_tabs = page.locator("[data-ai-signal-stage]")
                history_tabs = page.locator("[data-ai-signal-history-side]")
                if mode_tabs.count() != 2 or stage_tabs.count() != 5:
                    raise QaFailure(
                        "AI 시그널 필터 구성이 계약과 다릅니다.",
                        {
                            "mode_tabs": mode_tabs.count(),
                            "stage_tabs": stage_tabs.count(),
                        },
                    )
                ui_signal_snapshot = page.evaluate(
                    """() => {
                      const buttonCount = button => Number(
                        (button?.querySelector('span')?.textContent || '').replace(/[^0-9]/g, '')
                      );
                      const stageCounts = Object.fromEntries(
                        [...document.querySelectorAll('[data-ai-signal-stage]')]
                          .map(button => [button.dataset.aiSignalStage, buttonCount(button)])
                      );
                      return {
                        revision: Number.isSafeInteger(state.aiSignalRevision)
                          && state.aiSignalRevision >= 0
                          ? state.aiSignalRevision
                          : null,
                        status: state.aiSignalMarketStatus || '',
                        modeCounts: aiSignalModeCounts(state.aiSignalItems),
                        itemCount: Array.isArray(state.aiSignalItems) ? state.aiSignalItems.length : -1,
                        domModeCounts: {
                          current: buttonCount(document.querySelector('[data-ai-signal-mode="current"]')),
                          history: buttonCount(document.querySelector('[data-ai-signal-mode="history"]')),
                        },
                        stageCounts,
                      };
                    }"""
                )
                current_count = ui_signal_snapshot["domModeCounts"]["current"]
                history_count = ui_signal_snapshot["domModeCounts"]["history"]
                stage_counts = ui_signal_snapshot["stageCounts"]
                if (
                    ui_signal_snapshot["modeCounts"]
                    != ui_signal_snapshot["domModeCounts"]
                    or isinstance(ui_signal_snapshot.get("revision"), bool)
                    or not isinstance(ui_signal_snapshot.get("revision"), int)
                    or ui_signal_snapshot["revision"] < 0
                ):
                    raise QaFailure(
                        "AI 시그널 스냅샷과 화면 필터 건수가 같은 리비전으로 표시되지 않습니다.",
                        {
                            "ui_current": current_count,
                            "ui_history": history_count,
                            "snapshot": ui_signal_snapshot,
                            "api_precondition": market_signals,
                        },
                    )
                if stage_counts["all"] != sum(
                    count for stage, count in stage_counts.items() if stage != "all"
                ):
                    raise QaFailure(
                        "단계별 건수 합계가 전체 건수와 다릅니다.", stage_counts
                    )
                for index in range(stage_tabs.count()):
                    tab = stage_tabs.nth(index)
                    _select_tab(tab)
                    expected_rows = _button_count(tab)
                    actual_rows = page.locator(
                        "#ai-signals-page-list .home-ai-signal-row"
                    ).count()
                    if actual_rows != expected_rows:
                        raise QaFailure(
                            "단계 필터의 카드 수가 뱃지 건수와 다릅니다.",
                            {
                                "stage": tab.get_attribute("data-ai-signal-stage"),
                                "badge": expected_rows,
                                "rows": actual_rows,
                            },
                        )
                live_return_contract = page.evaluate(
                    """() => {
                      const list = document.querySelector('#ai-signals-page-list');
                      const statusNode = document.querySelector('#ai-signals-live-status');
                      if (!list || !statusNode) throw new Error('AI signal live DOM is missing');

                      state.aiSignalLoadSequence += 1;
                      state.homeAiSignalsRequestId += 1;
                      window.clearTimeout(state.aiSignalRevisionTimer);
                      window.clearTimeout(state.aiSignalReconcileTimer);
                      if (state.quoteStreamSocket?.close) {
                        state.quoteStreamSocket.onclose = null;
                        state.quoteStreamSocket.close();
                      }
                      state.quoteStreamSocket = { readyState: WebSocket.CONNECTING, send() {}, close() {} };
                      state.quoteStreamEpoch = 91;
                      state.quoteStreamScopes.clear();
                      state.quoteStreamLatestByCode.clear();
                      state.aiSignalLiveQuotes.clear();
                      state.aiSignalQuoteStatuses.clear();
                      state.quoteStreamRejectedCodes = new Set();
                      state.quoteStreamOverflowCodes = new Set();
                      state.quoteStreamConnectionState = 'checking';
                      state.aiSignalMode = 'current';
                      state.aiSignalStage = 'all';

                      const snapshotAt = new Date().toISOString();
                      const fixtureRevision = Number.isSafeInteger(Number(state.aiSignalRevision))
                        ? Number(state.aiSignalRevision)
                        : 0;
                      const fixtures = [
                        {
                          code: '005930', name: '삼성전자', side: 'buy',
                          signal_date: '2026-08-28', execution_date: '2026-08-28',
                          entry_price: 100000, display_return_rate: 5,
                          display_return_kind: 'open_position', is_current_holding: true,
                          current: {
                            action: 'entered', position_open: true, entry_price: 100000,
                            price: 105000, unrealized_return: 5, as_of: snapshotAt,
                          },
                          holding_context: {
                            entry_price: 100000, price: 105000, unrealized_return: 5,
                            return_basis: { price: 105000, return_rate: 5, return_rate_per_price: 0.001 },
                          },
                        },
                        {
                          code: '000660', name: 'SK하이닉스', side: 'sell',
                          signal_date: '2026-08-31', signal_at: snapshotAt,
                          entry_price: 50000, display_return_rate: 10,
                          display_return_kind: 'open_position', is_current_holding: true,
                          status: 'preliminary', is_preliminary: true,
                          current: {
                            action: 'full_exit_pending', position_open: true,
                            live_observation: true, entry_price: 50000,
                            price: 55000, unrealized_return: 10, as_of: snapshotAt,
                          },
                          holding_context: {
                            entry_price: 50000, price: 55000, unrealized_return: 10,
                            return_basis: { price: 55000, return_rate: 10, return_rate_per_price: 0.001 },
                          },
                        },
                        {
                          code: '035420', name: 'NAVER', side: 'sell',
                          signal_date: '2026-08-28', execution_date: '2026-08-28',
                          entry_price: 100000, price: 120000, return_rate: 20,
                          display_return_rate: 20, display_return_kind: 'closed_trade',
                          is_current_holding: false,
                          current: {
                            action: 'exited', position_open: false, entry_price: 100000,
                            price: 120000, as_of: snapshotAt,
                            lifecycle: { latest_transition: {
                              label: '전량 매도', side: 'sell', transition_date: '2026-08-28',
                              signal_at: '2026-08-28T15:40:00+09:00', return_rate: 20,
                            } },
                          },
                        },
                      ];
                      if (!commitAiSignalSnapshot(fixtures, {
                        status: 'ready', signal_revision: fixtureRevision,
                        signal_revision_as_of: snapshotAt,
                        snapshot_generated_at: snapshotAt, as_of: snapshotAt,
                      })) throw new Error('fixture snapshot was rejected');
                      list.replaceChildren(...state.aiSignalItems.map(
                        item => createHomeAiSignalRow(item, { detail: true }),
                      ));
                      connectAiSignalQuoteStreams(state.aiSignalItems);
                      dispatchQuoteStreamPayload({
                        type: 'subscribed', codes: ['000660', '005930'], count: 2, rejected_codes: [],
                      });

                      const base = Date.now();
                      const quote = (code, sequence, price, offset, source = 'kis_realtime') => {
                        const observedAt = new Date(base + offset).toISOString();
                        return {
                          type: 'quote', code, source, sequence,
                          observed_at: observedAt,
                          published_at: new Date(base + offset + 1).toISOString(),
                          quote: {
                            price, trade_date: '2026-08-31', market_session: 'krx_regular',
                          },
                        };
                      };
                      const readRow = code => {
                        const row = list.querySelector(`.home-ai-signal-row[data-code="${code}"]`);
                        const value = row?.querySelector('[data-field="ai_signal_return"]');
                        const label = value?.closest('[data-metric="return"]')
                          ?.querySelector('.home-ai-signal-metric-label');
                        const badge = row?.querySelector('[data-field="ai_signal_freshness"]');
                        const sellPrice = row?.querySelector('[data-metric="sell-price"] .home-ai-signal-metric-value');
                        return {
                          value: Number(value?.dataset.rawValue),
                          text: value?.textContent?.trim() || '',
                          label: label?.textContent?.trim() || '',
                          returnKind: value?.dataset.returnKind || '',
                          freshnessState: value?.dataset.freshnessState || '',
                          badgeState: badge?.dataset.state || '',
                          badgeAria: badge?.getAttribute('aria-label') || '',
                          badgeHidden: badge ? badge.hidden : true,
                          rowAria: row?.getAttribute('aria-label') || '',
                          sellPrice: sellPrice?.textContent?.trim() || '',
                        };
                      };
                      const readStatus = () => ({
                        state: statusNode.dataset.state || '',
                        mixed: statusNode.dataset.mixed || '',
                        label: document.querySelector('#ai-signals-live-status-label')?.textContent?.trim() || '',
                        detail: document.querySelector('#ai-signals-live-status-detail')?.textContent?.trim() || '',
                        ariaLabel: statusNode.getAttribute('aria-label') || '',
                        hidden: statusNode.hidden,
                        role: statusNode.getAttribute('role') || '',
                        ariaLive: statusNode.getAttribute('aria-live') || '',
                        ariaAtomic: statusNode.getAttribute('aria-atomic') || '',
                      });

                      dispatchQuoteStreamPayload(quote('005930', 10, 105000, 0));
                      dispatchQuoteStreamPayload(quote('000660', 10, 55000, 0));
                      dispatchQuoteStreamPayload(quote('005930', 11, 106000, 10));
                      dispatchQuoteStreamPayload(quote('000660', 11, 56000, 10));
                      const accepted = {
                        holding: readRow('005930'),
                        pendingSell: readRow('000660'),
                        closed: readRow('035420'),
                        status: readStatus(),
                      };

                      dispatchQuoteStreamPayload(quote('005930', 9, 109000, 20));
                      dispatchQuoteStreamPayload(quote('000660', 9, 59000, 20));
                      dispatchQuoteStreamPayload(quote('005930', 12, 99000, -1000));
                      dispatchQuoteStreamPayload(quote('000660', 12, 49000, -1000));
                      dispatchQuoteStreamPayload(quote('035420', 10, 150000, 20));
                      const staleRejected = {
                        holding: readRow('005930'),
                        pendingSell: readRow('000660'),
                        closed: readRow('035420'),
                        latestSequences: {
                          holding: state.quoteStreamLatestByCode.get('005930')?.payload?.sequence,
                          pendingSell: state.quoteStreamLatestByCode.get('000660')?.payload?.sequence,
                        },
                      };

                      dispatchQuoteStreamPayload({
                        type: 'status', code: '000660', source: 'kis_realtime', status: 'fallback',
                        message: 'qa deterministic fallback',
                      });
                      const mixedFallback = {
                        holding: readRow('005930'),
                        pendingSell: readRow('000660'),
                        closed: readRow('035420'),
                        status: readStatus(),
                      };
                      dispatchQuoteStreamPayload({
                        type: 'status', code: '005930', source: 'kis_realtime', status: 'fallback',
                        message: 'qa deterministic fallback',
                      });
                      const fallback = {
                        holding: readRow('005930'),
                        pendingSell: readRow('000660'),
                        closed: readRow('035420'),
                        status: readStatus(),
                      };

                      dispatchQuoteStreamPayload(quote('005930', 13, 107000, 30));
                      dispatchQuoteStreamPayload(quote('000660', 13, 57000, 30));
                      for (const code of ['005930', '000660']) {
                        dispatchQuoteStreamPayload({
                          type: 'status', code, source: 'kis_realtime', status: 'recovered',
                          message: 'qa deterministic recovery',
                        });
                      }
                      const recovered = {
                        holding: readRow('005930'),
                        pendingSell: readRow('000660'),
                        closed: readRow('035420'),
                        status: readStatus(),
                      };

                      dispatchQuoteStreamPayload({
                        type: 'subscribed', codes: ['005930'], count: 1,
                        rejected_codes: ['000660'],
                      });
                      const rejectedAck = readStatus();
                      dispatchQuoteStreamPayload({
                        type: 'subscribed', codes: ['000660', '005930'], count: 2,
                        rejected_codes: [],
                      });
                      const restoredAck = readStatus();
                      state.aiSignalMode = 'history';
                      renderAiSignalLiveStatus();
                      const historyStatus = readStatus();
                      state.aiSignalMode = 'current';
                      renderAiSignalLiveStatus();

                      const currentRevision = state.aiSignalRevision;
                      const initialAccepted = handleAiSignalRevisionFrame({
                        type: 'signal_revision', revision: currentRevision,
                        as_of: snapshotAt, changed_codes: [], initial: true,
                      });
                      const nextRevision = currentRevision + 1;
                      const changedAccepted = handleAiSignalRevisionFrame({
                        type: 'signal_revision', revision: nextRevision,
                        as_of: snapshotAt, changed_codes: ['005930'], initial: false,
                      });
                      const scheduledTimer = state.aiSignalRevisionTimer;
                      const duplicateAccepted = handleAiSignalRevisionFrame({
                        type: 'signal_revision', revision: nextRevision,
                        as_of: snapshotAt, changed_codes: ['005930'], initial: false,
                      });
                      const keptSingleTimer = scheduledTimer === state.aiSignalRevisionTimer;
                      window.clearTimeout(state.aiSignalRevisionTimer);
                      state.aiSignalRevisionTimer = null;
                      state.aiSignalPendingRevision = null;
                      state.aiSignalReconcilePending = false;

                      return {
                        accepted, staleRejected, mixedFallback, fallback, recovered,
                        rejectedAck, restoredAck, historyStatus,
                        revision: {
                          initialAccepted, changedAccepted, duplicateAccepted,
                          keptSingleTimer, scheduled: Boolean(scheduledTimer),
                        },
                        snapshotFrozen: state.aiSignalItems.every(item => Object.isFrozen(item)),
                      };
                    }"""
                )
                accepted = live_return_contract["accepted"]
                stale_rejected = live_return_contract["staleRejected"]
                mixed_fallback = live_return_contract["mixedFallback"]
                fallback = live_return_contract["fallback"]
                recovered = live_return_contract["recovered"]
                if (
                    accepted["holding"]["value"] != 6
                    or accepted["pendingSell"]["value"] != 11
                    or accepted["holding"]["label"] != "실시간 평가수익률"
                    or accepted["pendingSell"]["label"] != "실시간 평가수익률"
                    or accepted["status"]["state"] != "realtime"
                    or accepted["status"]["mixed"] != "false"
                    or accepted["status"]["label"] != "보유 2개 모두 실시간"
                    or accepted["holding"]["badgeHidden"] is not True
                    or accepted["pendingSell"]["badgeHidden"] is not True
                ):
                    raise QaFailure(
                        "열린 포지션의 최신 시세·평가수익률 표시가 잘못됐습니다.",
                        accepted,
                    )
                if (
                    stale_rejected["holding"]["value"] != 6
                    or stale_rejected["pendingSell"]["value"] != 11
                    or stale_rejected["latestSequences"]
                    != {"holding": 11, "pendingSell": 11}
                ):
                    raise QaFailure(
                        "이전 sequence·observed_at 시세가 최신 수익률을 덮어썼습니다.",
                        stale_rejected,
                    )
                closed_states = [
                    accepted["closed"],
                    stale_rejected["closed"],
                    fallback["closed"],
                    recovered["closed"],
                ]
                if any(
                    item["value"] != 20
                    or item["label"] != "확정 수익률"
                    or item["returnKind"] != "closed_trade"
                    or item["sellPrice"] != "120,000원"
                    for item in closed_states
                ):
                    raise QaFailure(
                        "완료 매도의 확정 수익률·매도가가 실시간 시세로 변했습니다.",
                        {"closed_states": closed_states},
                    )
                if (
                    mixed_fallback["holding"]["badgeHidden"] is not True
                    or mixed_fallback["pendingSell"]["badgeHidden"] is not False
                    or mixed_fallback["pendingSell"]["badgeState"]
                    not in {"delayed", "closed"}
                    or mixed_fallback["status"]["mixed"] != "true"
                    or "실시간 1" not in mixed_fallback["status"]["label"]
                    or not any(
                        label in mixed_fallback["status"]["label"]
                        for label in ("약 10초 지연 1", "장 마감 1")
                    )
                ):
                    raise QaFailure(
                        "혼합 시세 상태에서 정상 배지는 숨고 예외 종목만 표시되지 않았습니다.",
                        mixed_fallback,
                    )
                if (
                    fallback["holding"]["value"] != 6
                    or fallback["pendingSell"]["value"] != 11
                    or fallback["holding"]["label"] != "보유 평가수익률"
                    or fallback["status"]["state"] not in {"delayed", "closed"}
                    or fallback["status"]["mixed"] != "false"
                    or fallback["holding"]["badgeHidden"] is not True
                    or fallback["pendingSell"]["badgeHidden"] is not True
                    or recovered["holding"]["value"] != 7
                    or recovered["pendingSell"]["value"] != 12
                    or recovered["holding"]["label"] != "실시간 평가수익률"
                    or recovered["status"]["state"] != "realtime"
                    or recovered["status"]["label"] != "보유 2개 모두 실시간"
                    or recovered["holding"]["badgeHidden"] is not True
                    or recovered["pendingSell"]["badgeHidden"] is not True
                ):
                    raise QaFailure(
                        "폴백·복구 상태에서 수익률·신선도 표시가 잘못됐습니다.",
                        {"fallback": fallback, "recovered": recovered},
                    )
                accessibility = accepted["status"]
                if (
                    accessibility["role"] != "status"
                    or accessibility["ariaLive"] != "polite"
                    or accessibility["ariaAtomic"] != "false"
                    or accessibility["hidden"] is not False
                    or "현재 목록" not in accessibility["ariaLabel"]
                    or "실시간" not in accessibility["ariaLabel"]
                    or mixed_fallback["pendingSell"]["badgeHidden"] is not False
                    or not any(
                        label in mixed_fallback["pendingSell"]["badgeAria"]
                        for label in ("약 10초 지연", "장 마감")
                    )
                    or "실시간 평가수익률" not in accepted["holding"]["rowAria"]
                    or live_return_contract["rejectedAck"]["state"] != "checking"
                    or live_return_contract["restoredAck"]["state"] != "realtime"
                    or live_return_contract["historyStatus"]["hidden"] is not True
                ):
                    raise QaFailure(
                        "실시간·ACK 상태의 접근성 텍스트가 잘못됐습니다.",
                        {
                            "accessibility": accessibility,
                            "holding": accepted["holding"],
                            "rejected_ack": live_return_contract["rejectedAck"],
                            "restored_ack": live_return_contract["restoredAck"],
                            "history_status": live_return_contract["historyStatus"],
                        },
                    )
                revision = live_return_contract["revision"]
                if revision != {
                    "initialAccepted": False,
                    "changedAccepted": True,
                    "duplicateAccepted": False,
                    "keptSingleTimer": True,
                    "scheduled": True,
                } or live_return_contract["snapshotFrozen"] is not True:
                    raise QaFailure(
                        "신호 리비전 중복 억제·불변 스냅샷 계약이 잘못됐습니다.",
                        {
                            "revision": revision,
                            "snapshot_frozen": live_return_contract["snapshotFrozen"],
                        },
                    )
                signal_label_contract = page.evaluate(
                    """async () => {
                      const list = document.querySelector('#ai-signals-page-list');
                      if (!list) throw new Error('AI signal list is missing');
                      const fixtures = [
                        {
                          code: '005830', name: 'DB손해보험', side: 'sell',
                          current: {
                            action: 'partial_exit_pending', position_open: true,
                            pending_profit_stage: 2, profit_stage: 1,
                          },
                        },
                        {
                          code: '009540', name: 'HD한국조선해양', side: 'sell',
                          current: { action: 'full_exit_pending', position_open: true },
                        },
                        {
                          code: '001450', name: '현대해상', side: 'sell',
                          current: {
                            action: 'partially_exited', position_open: true, profit_stage: 2,
                          },
                        },
                        {
                          code: '103140', name: '풍산', side: 'sell',
                          current: { action: 'exited', position_open: false },
                        },
                      ];
                      list.replaceChildren(...fixtures.map(
                        item => createHomeAiSignalRow(item, { detail: true }),
                      ));
                      await new Promise(resolve => requestAnimationFrame(
                        () => requestAnimationFrame(resolve)
                      ));
                      return fixtures.map(item => {
                        const row = list.querySelector(
                          '.home-ai-signal-row[data-code="' + item.code + '"]'
                        );
                        return {
                          code: item.code,
                          label: row?.querySelector('.home-ai-signal-state')?.textContent?.trim() || '',
                          fullLabel: row?.querySelector('.home-ai-signal-state')
                            ?.dataset.stagingFullLabel || '',
                          stage: aiSignalStageKey(item),
                          ariaLabel: row?.getAttribute('aria-label') || '',
                        };
                      });
                    }"""
                )
                expected_signal_labels = [
                    ("005830", "부분 매도 대기(2차)", "preliminary-sell"),
                    ("009540", "전량 매도 대기", "preliminary-sell"),
                    ("001450", "부분 수익 확정(2차)", "recent-sell"),
                    ("103140", "전량 매도 확정", "recent-sell"),
                ]
                for actual, (code, label, stage) in zip(
                    signal_label_contract, expected_signal_labels, strict=True
                ):
                    if (
                        actual.get("code") != code
                        or actual.get("label") != label
                        or actual.get("fullLabel") != label
                        or actual.get("stage") != stage
                        or label not in str(actual.get("ariaLabel") or "")
                    ):
                        raise QaFailure(
                            "매도 대기·확정 또는 부분·전량 상태 문구가 합쳐졌습니다.",
                            {
                                "expected": expected_signal_labels,
                                "actual": signal_label_contract,
                            },
                        )
                weekend_basis = page.evaluate(
                    """() => {
                      const item = {
                        code: '373220',
                        name: 'LG에너지솔루션',
                        side: 'buy',
                        action: 'entry_watch',
                        status: 'preliminary',
                        is_preliminary: true,
                        signal_date: '2026-08-28',
                        signal_at: '2026-08-30T12:38:41+09:00',
                        updated_at: '2026-08-30T12:38:41+09:00',
                        last_seen_at: '2026-08-30T12:38:41+09:00',
                        current: {
                          action: 'entry_watch',
                          live_observation: false,
                          position_open: false,
                          as_of: '2026-08-30T12:38:41+09:00',
                          score: 81.83,
                          reasons: ['금요일 종가 기준'],
                        },
                      };
                      const row = createHomeAiSignalRow(item, { detail: true });
                      return {
                        basis: row?.querySelector('.home-ai-signal-meta')?.textContent?.trim() || '',
                        activityBadge: row?.querySelector('.home-ai-signal-activity-badge')?.textContent?.trim() || '',
                      };
                    }"""
                )
                if (
                    weekend_basis.get("basis") != "2026.08.28 장 마감 기준"
                    or weekend_basis.get("activityBadge")
                ):
                    raise QaFailure(
                        "휴장 예비 신호의 장 마감 기준일 표시가 잘못됐습니다.",
                        weekend_basis,
                    )
                _select_tab(page.locator('[data-ai-signal-mode="history"]'))
                for index in range(history_tabs.count()):
                    _select_tab(history_tabs.nth(index))

                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_copy=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#home-view", state="visible")
                normalized = re.sub(r"\s+", "", page.locator("body").inner_text())
                if "시총100위내매매신호를확인하세요" not in normalized:
                    raise QaFailure("AI 시그널 안내 문구가 계약과 다릅니다.")
                news_positive = page.locator(
                    '#trend-live-filters [data-trend-news-filter="positive"]'
                )
                news_positive.evaluate("el => el.click()")
                if news_positive.get_attribute("aria-selected") != "true":
                    raise QaFailure("시장 뉴스 필터 선택 상태가 반영되지 않았습니다.")
                notification_sheet = page.locator("#push-notification-sheet")
                if notification_sheet.is_visible():
                    page.locator("#push-notification-sheet-close").click()
                    notification_sheet.wait_for(state="hidden")
                page.wait_for_selector(
                    "#home-market-signal-window .home-market-signal-row",
                    state="visible",
                )
                signal_cta = page.locator(".staging-home-signal-chevron")
                signal_cta.wait_for(state="visible")
                cta_contract = signal_cta.evaluate(
                    """button => {
                      const rect = element => {
                        const bounds = element.getBoundingClientRect();
                        return {
                          x: bounds.x,
                          y: bounds.y,
                          width: bounds.width,
                          height: bounds.height,
                          centerY: bounds.y + (bounds.height / 2),
                        };
                      };
                      const name = document.querySelector(
                        '#home-ai-signals .home-market-signal-name'
                      );
                      const action = document.querySelector(
                        '#home-ai-signals .home-market-signal-action'
                      );
                      return {
                        tagName: button.tagName,
                        href: button.getAttribute('href') || '',
                        ariaLabel: button.getAttribute('aria-label') || '',
                        button: rect(button),
                        name: rect(name),
                        action: rect(action),
                      };
                    }"""
                )
                button_bounds = cta_contract.get("button") or {}
                name_bounds = cta_contract.get("name") or {}
                action_bounds = cta_contract.get("action") or {}
                button_center = float(button_bounds.get("centerY") or 0)
                content_centers = (
                    float(name_bounds.get("centerY") or 0),
                    float(action_bounds.get("centerY") or 0),
                )
                if (
                    cta_contract.get("tagName") != "A"
                    or cta_contract.get("href") != "/dashboard?view=ai-signals"
                    or cta_contract.get("ariaLabel") != "AI 시그널 전체 목록 보기"
                    or float(button_bounds.get("width") or 0) < 44
                    or float(button_bounds.get("height") or 0) < 44
                    or button_center < min(content_centers) - 1
                    or button_center > max(content_centers) + 1
                ):
                    raise QaFailure(
                        "홈 AI 시그널 버튼의 동작·터치영역·수직 위치가 계약과 다릅니다.",
                        cta_contract,
                    )
                page.evaluate(
                    """() => {
                      window.__qaSignalEntryFrames = [];
                      const snapshot = () => {
                        if (document.body.dataset.view !== 'ai-signals') return;
                        const rows = [...document.querySelectorAll(
                          '#ai-signals-page-list .home-ai-signal-row[data-code]'
                        )];
                        const openRows = rows.filter(
                          row => row.aiSignalSnapshotItem?.current?.position_open === true
                        );
                        const returnTexts = openRows.map(row =>
                          row.querySelector('[data-field="ai_signal_return"]')?.textContent?.trim() || ''
                        );
                        window.__qaSignalEntryFrames.push({
                          listText: document.querySelector('#ai-signals-page-list')?.textContent
                            ?.replace(/\\s+/g, ' ').trim() || '',
                          counts: [...document.querySelectorAll(
                            '#ai-signal-mode-tabs span, #ai-signal-stage-tabs span'
                          )].map(node => node.textContent?.trim() || ''),
                          openRowCount: openRows.length,
                          pendingReturnCount: returnTexts.filter(
                            text => text.includes('현재가 확인 중') || text.includes('연결 후 확인')
                          ).length,
                          numericReturnCount: returnTexts.filter(text => /%/.test(text)).length,
                          returnTexts,
                        });
                      };
                      const observer = new MutationObserver(snapshot);
                      const list = document.querySelector('#ai-signals-page-list');
                      if (list) observer.observe(list, { childList: true, characterData: true, subtree: true });
                      observer.observe(document.body, { attributes: true, attributeFilter: ['data-view'] });
                      window.__qaSignalEntryObserver = observer;
                      snapshot();
                    }"""
                )
                signal_cta.click()
                page.wait_for_function(
                    "() => document.body.dataset.view === 'ai-signals'",
                    timeout=int(timeout * 1000),
                )
                if "view=ai-signals" not in page.url:
                    raise QaFailure(
                        "홈 AI 시그널 버튼이 전체 목록 URL로 이동하지 않았습니다.",
                        {"url": page.url, "cta": cta_contract},
                    )
                page.wait_for_function(
                    """() => !document.querySelector('#ai-signals-page-list')?.textContent
                      ?.includes('불러오는 중입니다.')""",
                    timeout=int(timeout * 1000),
                )
                signal_entry_frames = page.evaluate(
                    """() => {
                      window.__qaSignalEntryObserver?.disconnect();
                      return window.__qaSignalEntryFrames || [];
                    }"""
                )
                first_open_frame = next(
                    (
                        frame
                        for frame in signal_entry_frames
                        if int(frame.get("openRowCount") or 0) > 0
                    ),
                    None,
                )
                if first_open_frame and (
                    int(first_open_frame.get("numericReturnCount") or 0) > 0
                    or int(first_open_frame.get("pendingReturnCount") or 0)
                    != int(first_open_frame.get("openRowCount") or 0)
                ):
                    raise QaFailure(
                        "AI 시그널 최초 행에 이전 스냅샷 수익률이 먼저 노출됐습니다.",
                        {
                            "first_open_frame": first_open_frame,
                            "signal_entry_frames": signal_entry_frames,
                        },
                    )
                return {
                    **shell,
                    "api": market_signals,
                    "mode_counts": {
                        "current": current_count,
                        "history": history_count,
                    },
                    "ui_snapshot": ui_signal_snapshot,
                    "stage_counts": stage_counts,
                    "signal_label_contract": signal_label_contract,
                    "live_return_contract": live_return_contract,
                    "weekend_close_basis": weekend_basis,
                    "home_copy": "시총 100위내 매매신호를 확인하세요",
                    "home_cta": cta_contract,
                    "signal_entry_frames": signal_entry_frames,
                }

            signal_ui_result = _run_page_case(
                browser=browser,
                catalog_by_id=catalog_by_id,
                case_id="SIG-UI-002",
                base_url=base_url,
                timeout=timeout,
                artifact_dir=output_dir,
                callback=signal_filter_case,
                storage_state=storage_state,
                share_id=share_id,
            )
            results.append(signal_ui_result)
            signal_label_result = dict(signal_ui_result)
            signal_label_result["case_id"] = "SIG-UI-021"
            signal_label_result["evidence"] = {
                "shared_e2e_case": "SIG-UI-002",
                **{
                    theme: {
                        "signal_label_contract": dict(theme_evidence or {}).get(
                            "signal_label_contract"
                        )
                    }
                    for theme, theme_evidence in dict(
                        signal_ui_result.get("evidence") or {}
                    ).items()
                    if theme in {"dark", "light"}
                },
            }
            if signal_label_result["status"] == "pass":
                signal_label_result["message"] = (
                    "매도 대기·확정과 부분·전량 상태 문구를 "
                    "승격된 모바일 DOM에서 구분했습니다."
                )
            results.append(signal_label_result)
            signal_contract_result = dict(signal_ui_result)
            signal_contract_result["case_id"] = "SIG-CONTRACT-003"
            signal_contract_result["evidence"] = {
                "shared_e2e_case": "SIG-UI-002",
                **dict(signal_ui_result.get("evidence") or {}),
            }
            if signal_contract_result["status"] == "pass":
                signal_contract_result["message"] = (
                    "AI 시그널 스냅샷·실시간 수익률·완료 매매 고정 계약을 "
                    "대표 화면에서 확인했습니다."
                )
            results.append(signal_contract_result)

            def stock_case(page: Any, theme: str) -> dict[str, Any]:
                fixtures: list[dict[str, Any]] = []
                latest_shell: dict[str, Any] = {}
                for stock in (samsung, etf):
                    _navigate_page(
                        page,
                        _page_url(
                            base_url,
                            f"/dashboard/{stock['code']}",
                            theme=theme,
                            qa_run=datetime.now(KST).strftime("%H%M%S"),
                        ),
                    wait_until="commit",
                    )
                    latest_shell = _assert_page_shell(page, theme=theme)
                    page.wait_for_selector("#stock-view", state="visible")
                    _wait_for_ui_contract(
                        page,
                        """() => Boolean(
                          document.querySelector('[data-staging-stock-change-context]')
                            ?.dataset.stagingQuoteDate
                        )""",
                        stage=f"{stock['code']} 거래일 비교 문구",
                        timeout_ms=int(timeout * 1000),
                    )
                    change_context = page.evaluate(
                        """() => {
                          const node = document.querySelector('[data-staging-stock-change-context]');
                          return {
                            label: node?.textContent?.trim() || '',
                            mode: node?.dataset.stagingChangeContext || '',
                            quoteDate: node?.dataset.stagingQuoteDate || '',
                            referenceDate: node?.dataset.stagingReferenceDate || '',
                          };
                        }"""
                    )
                    change_label = str(change_context.get("label") or "")
                    change_mode = str(change_context.get("mode") or "")
                    current_copy_ok = change_mode == "current-session" and bool(
                        re.fullmatch(r"어제보다|(?:월|화|수|목|금)요일보다|지난 장보다", change_label)
                    )
                    completed_copy_ok = change_mode == "completed-session" and bool(
                        re.fullmatch(r"어제 장에서|(?:월|화|수|목|금)요일 장에서|최근 장에서", change_label)
                    )
                    if not (current_copy_ok or completed_copy_ok):
                        raise QaFailure(
                            "종목 등락 문구가 실제 거래일 상태와 맞지 않습니다.",
                            {"code": stock["code"], "change_context": change_context},
                        )
                    text = page.locator("#stock-view").inner_text()
                    redundant = f"{stock['code']} · {stock['market']}"
                    if redundant in text:
                        raise QaFailure(
                            "티커번호·시장 중복 조합이 상세 화면에 노출됐습니다.",
                            {"text": redundant, "code": stock["code"]},
                        )
                    if "Ollama AI 분석 완료" in text:
                        raise QaFailure(
                            "내부 AI 완료 배지가 종목 화면에 노출됐습니다.",
                            {"code": stock["code"]},
                        )
                    page.wait_for_selector(
                        "#stock-title-logo:not([hidden]) .stock-title-logo-frame",
                        state="visible",
                        timeout=int(timeout * 1000),
                    )
                    title_logo = page.evaluate(
                        """() => {
                          const logo = document.querySelector('#stock-title-logo');
                          const titleRow = logo?.closest('.staging-stock-hero-name-row, .stock-v3-name-row');
                          const title = titleRow?.querySelector('[data-staging-stock-name], #stock-name');
                          const frame = logo?.querySelector('.stock-title-logo-frame');
                          const image = logo?.querySelector('.stock-list-logo-image');
                          const fallback = logo?.querySelector('.stock-list-logo-fallback');
                          const bounds = element => {
                            const rect = element?.getBoundingClientRect();
                            return rect ? {
                              top: rect.top,
                              right: rect.right,
                              bottom: rect.bottom,
                              left: rect.left,
                              width: rect.width,
                              height: rect.height,
                            } : null;
                          };
                          return {
                            code: logo?.dataset.stockCode || '',
                            hidden: logo?.hidden ?? true,
                            bounds: bounds(logo),
                            rowBounds: bounds(titleRow),
                            titleBounds: bounds(title),
                            rowClass: titleRow?.className || '',
                            titleText: title?.textContent?.trim() || '',
                            insideChart: Boolean(logo?.closest('.stock-v3-chart-pane')),
                            frameClass: frame?.className || '',
                            imageSrc: image?.getAttribute('src') || '',
                            fallbackPresent: Boolean(fallback),
                            pointerEvents: logo ? getComputedStyle(logo).pointerEvents : '',
                            rootScrollWidth: document.documentElement.scrollWidth,
                            viewportWidth: innerWidth,
                          };
                        }"""
                    )
                    logo_bounds = title_logo.get("bounds") or {}
                    row_bounds = title_logo.get("rowBounds") or {}
                    title_bounds = title_logo.get("titleBounds") or {}
                    logo_failures = []
                    if title_logo.get("code") != stock["code"] or title_logo.get("hidden"):
                        logo_failures.append("selected_stock_identity")
                    if (
                        round(float(logo_bounds.get("width") or 0)) != 36
                        or round(float(logo_bounds.get("height") or 0)) != 36
                    ):
                        logo_failures.append("staging_logo_size")
                    if (
                        "staging-stock-hero-name-row" not in str(title_logo.get("rowClass") or "")
                        or title_logo.get("titleText") != stock["name"]
                        or title_logo.get("insideChart")
                    ):
                        logo_failures.append("title_row_identity")
                    logo_center_y = (
                        float(logo_bounds.get("top") or 0)
                        + float(logo_bounds.get("bottom") or 0)
                    ) / 2
                    title_center_y = (
                        float(title_bounds.get("top") or 0)
                        + float(title_bounds.get("bottom") or 0)
                    ) / 2
                    if (
                        float(logo_bounds.get("left") or 0) < float(row_bounds.get("left") or 0) - 1
                        or float(logo_bounds.get("right") or 0) > float(title_bounds.get("left") or 0)
                        or abs(logo_center_y - title_center_y) > 1.5
                    ):
                        logo_failures.append("title_alignment")
                    if title_logo.get("pointerEvents") != "none":
                        logo_failures.append("title_interaction_passthrough")
                    if (
                        title_logo.get("imageSrc")
                        and f"/stock-logos/{stock['code']}.png" not in title_logo["imageSrc"]
                    ):
                        logo_failures.append("logo_url")
                    if not title_logo.get("imageSrc") and not title_logo.get("fallbackPresent"):
                        logo_failures.append("fallback")
                    if int(title_logo.get("rootScrollWidth") or 0) > int(title_logo.get("viewportWidth") or 0) + 1:
                        logo_failures.append("horizontal_overflow")
                    if logo_failures:
                        raise QaFailure(
                            "종목 상세 로고가 종목명 옆 정렬·이미지·폴백 계약을 지키지 않았습니다.",
                            {
                                "code": stock["code"],
                                "failed_contracts": logo_failures,
                                "title_logo": title_logo,
                            },
                        )
                    tabs = page.locator(".stock-detail-tabs button")
                    _wait_for_ui_contract(
                        page,
                        "() => document.querySelectorAll('.stock-detail-tabs button').length === 5",
                        stage=f"{stock['code']} 상세 탭",
                        timeout_ms=int(timeout * 1000),
                    )
                    if tabs.count() != 5:
                        raise QaFailure(
                            "종목 상세 탭 구성이 계약과 다릅니다.",
                            {"count": tabs.count(), "code": stock["code"]},
                        )
                    tab_labels: list[str] = []
                    disabled_tabs: list[str] = []
                    for index in range(tabs.count()):
                        tab = tabs.nth(index)
                        label = tab.inner_text().strip()
                        tab_labels.append(label)
                        if not tab.is_enabled():
                            disabled_tabs.append(label)
                            continue
                        _select_tab(tab)
                    news_tab = page.locator('[data-stock-tab="news"]')
                    _select_tab(news_tab)
                    page.wait_for_selector(
                        "#stock-news-section",
                        state="visible",
                        timeout=int(timeout * 1000),
                    )
                    news_ui = page.evaluate(
                        """() => {
                          const section = document.querySelector('#stock-news-section');
                          const list = section?.querySelector('#news-list');
                          return {
                            heading: section?.querySelector('h2')?.textContent?.trim() || '',
                            modeControlCount: section?.querySelectorAll('[data-news-mode]').length || 0,
                            tablistCount: section?.querySelectorAll('[role="tablist"]').length || 0,
                            hasBreakingCopy: section?.innerText.includes('AI 속보') || false,
                            listPresent: Boolean(list),
                            listLive: list?.getAttribute('aria-live') || '',
                          };
                        }"""
                    )
                    if news_ui != {
                        "heading": "종목뉴스",
                        "modeControlCount": 0,
                        "tablistCount": 0,
                        "hasBreakingCopy": False,
                        "listPresent": True,
                        "listLive": "polite",
                    }:
                        raise QaFailure(
                            "종목 소식 화면에 AI 속보 탭이 남아 있거나 종목뉴스 목록 계약이 깨졌습니다.",
                            {"code": stock["code"], "news_ui": news_ui},
                        )
                    signal_tab = page.locator('[data-stock-tab="strategy"]')
                    _select_tab(signal_tab)
                    expected_stage = {
                        "exited": "전량 매도 후 대기중",
                    }.get(stock.get("signal_action"), stock.get("signal_label"))
                    if expected_stage:
                        _wait_for_ui_contract(
                            page,
                            "expected => document.querySelector('#stock-view')?.innerText.includes(expected)",
                            arg=expected_stage,
                            stage=f"{stock['code']} 현재 AI 시그널 단계",
                            timeout_ms=int(timeout * 1000),
                        )
                    transition_date = stock.get("signal_transition_date")
                    if transition_date and stock.get("signal_action") == "exited":
                        _wait_for_ui_contract(
                            page,
                            "expected => document.querySelector('#stock-view')?.innerText.includes(expected)",
                            arg=transition_date,
                            stage=f"{stock['code']} 완료 매매 전환일",
                            timeout_ms=int(timeout * 1000),
                        )
                    return_rate = stock.get("signal_return_rate")
                    if return_rate is not None:
                        expected_return_rate = f"{float(return_rate):+.2f}%"
                        _wait_for_ui_contract(
                            page,
                            "expected => document.querySelector('#stock-view')?.innerText.includes(expected)",
                            arg=expected_return_rate,
                            stage=f"{stock['code']} 완료 매매 수익률",
                            timeout_ms=int(timeout * 1000),
                        )
                    action_icons = page.evaluate(
                        """() => {
                          const round = value => Math.round(value * 10) / 10;
                          const geometry = selector => {
                            const element = document.querySelector(selector);
                            const bounds = element.getBoundingClientRect();
                            const style = getComputedStyle(element);
                            const pseudo = getComputedStyle(element, '::before');
                            return {
                              rect: {
                                x: round(bounds.x),
                                y: round(bounds.y),
                                width: round(bounds.width),
                                height: round(bounds.height),
                                centerX: round(bounds.x + (bounds.width / 2)),
                                centerY: round(bounds.y + (bounds.height / 2)),
                              },
                              alignSelf: style.alignSelf,
                              pseudo: {
                                display: pseudo.display,
                                content: pseudo.content,
                                width: pseudo.width,
                                height: pseudo.height,
                                transform: pseudo.transform,
                                maskImage: pseudo.maskImage,
                                maskPosition: pseudo.maskPosition,
                                maskSize: pseudo.maskSize,
                              },
                            };
                          };
                          const searchGlyph = document.querySelector(
                            '.stock-v3-search > button > svg.staging-stock-search-glyph'
                          );
                          const searchGlyphBounds = searchGlyph.getBoundingClientRect();
                          const searchGlyphStyle = getComputedStyle(searchGlyph);
                          const stockView = document.querySelector('#stock-view');
                          const stockStyle = getComputedStyle(stockView);
                          return {
                            search: geometry('.stock-v3-search > button'),
                            heart: geometry('.stock-v3-star'),
                            searchGlyph: {
                              rect: {
                                x: round(searchGlyphBounds.x),
                                y: round(searchGlyphBounds.y),
                                width: round(searchGlyphBounds.width),
                                height: round(searchGlyphBounds.height),
                                centerX: round(searchGlyphBounds.x + (searchGlyphBounds.width / 2)),
                                centerY: round(searchGlyphBounds.y + (searchGlyphBounds.height / 2)),
                              },
                              className: searchGlyph.getAttribute('class'),
                              markup: searchGlyph.innerHTML,
                              display: searchGlyphStyle.display,
                              position: searchGlyphStyle.position,
                              transform: searchGlyphStyle.transform,
                              fill: searchGlyphStyle.fill,
                              stroke: searchGlyphStyle.stroke,
                              strokeWidth: searchGlyphStyle.strokeWidth,
                              strokeLinecap: searchGlyphStyle.strokeLinecap,
                              strokeLinejoin: searchGlyphStyle.strokeLinejoin,
                            },
                            masks: {
                              heart: stockStyle.getPropertyValue('--staging-stock-heart-mask').trim(),
                            },
                          };
                        }"""
                    )
                    search_icon = action_icons.get("search") or {}
                    heart_icon = action_icons.get("heart") or {}
                    search_rect = search_icon.get("rect") or {}
                    heart_rect = heart_icon.get("rect") or {}
                    search_pseudo = search_icon.get("pseudo") or {}
                    heart_pseudo = heart_icon.get("pseudo") or {}
                    search_glyph = action_icons.get("searchGlyph") or {}
                    search_glyph_rect = search_glyph.get("rect") or {}
                    masks = action_icons.get("masks") or {}
                    icon_failures = []
                    for name, rect in (("search", search_rect), ("heart", heart_rect)):
                        if rect.get("width") != 44 or rect.get("height") != 44:
                            icon_failures.append(f"{name}_touch_target")
                    if abs(float(search_rect.get("centerY") or 0) - float(heart_rect.get("centerY") or 0)) > 0.5:
                        icon_failures.append("vertical_center")
                    if search_pseudo.get("display") != "none" or search_pseudo.get("content") != "none":
                        icon_failures.append("search_legacy_mask_visible")
                    if search_glyph_rect.get("width") != 32 or search_glyph_rect.get("height") != 32:
                        icon_failures.append("search_glyph_box")
                    if abs(float(search_glyph_rect.get("centerY") or 0) - float(heart_rect.get("centerY") or 0)) > 0.5:
                        icon_failures.append("search_glyph_vertical_center")
                    if search_glyph.get("className") != "staging-stock-search-glyph":
                        icon_failures.append("search_glyph_source")
                    if '<circle cx="11" cy="11" r="8"></circle>' not in str(search_glyph.get("markup") or ""):
                        icon_failures.append("search_glyph_geometry")
                    for name, actual, expected in (
                        ("display", search_glyph.get("display"), "block"),
                        ("position", search_glyph.get("position"), "static"),
                        ("transform", search_glyph.get("transform"), "none"),
                        ("fill", search_glyph.get("fill"), "none"),
                        ("stroke_width", search_glyph.get("strokeWidth"), "2.5px"),
                        ("stroke_linecap", search_glyph.get("strokeLinecap"), "round"),
                        ("stroke_linejoin", search_glyph.get("strokeLinejoin"), "round"),
                    ):
                        if actual != expected:
                            icon_failures.append(f"search_{name}")
                    if heart_pseudo.get("width") != "32px" or heart_pseudo.get("height") != "32px":
                        icon_failures.append("heart_glyph_box")
                    if heart_pseudo.get("transform") != "none":
                        icon_failures.append("heart_transform")
                    if heart_pseudo.get("maskPosition") != "50% 50%":
                        icon_failures.append("heart_mask_center")
                    if heart_pseudo.get("maskSize") != "32px 32px":
                        icon_failures.append("heart_mask_size")
                    heart_mask = str(masks.get("heart") or "")
                    if "image/svg+xml" not in heart_mask or "stroke-width='2.5'" not in heart_mask:
                        icon_failures.append("heart_stroke_mask")
                    if icon_failures:
                        raise QaFailure(
                            "종목 상세 검색과 관심 아이콘의 중심 또는 선 두께가 일치하지 않습니다.",
                            {
                                "code": stock["code"],
                                "failed_contracts": icon_failures,
                                "action_icons": action_icons,
                            },
                        )
                    trading_hours = None
                    if stock["code"] == "005930":
                        market_status = page.locator(".staging-stock-market-status")
                        market_status.wait_for(state="visible", timeout=int(timeout * 1000))
                        market_status.click()
                        sheet = page.locator("#stock-trading-hours-sheet")
                        sheet.wait_for(state="visible", timeout=int(timeout * 1000))
                        trading_hours = page.evaluate(
                            """() => {
                              const round = value => Math.round(value * 100) / 100;
                              const metrics = (selector, clipSelector) => {
                                const element = document.querySelector(selector);
                                const clip = document.querySelector(clipSelector);
                                const bounds = element.getBoundingClientRect();
                                const clipBounds = clip.getBoundingClientRect();
                                const range = document.createRange();
                                range.selectNodeContents(element);
                                const textBounds = range.getBoundingClientRect();
                                const style = getComputedStyle(element);
                                return {
                                  bounds: {
                                    top: round(bounds.top),
                                    right: round(bounds.right),
                                    bottom: round(bounds.bottom),
                                    left: round(bounds.left),
                                  },
                                  textBounds: {
                                    top: round(textBounds.top),
                                    right: round(textBounds.right),
                                    bottom: round(textBounds.bottom),
                                    left: round(textBounds.left),
                                  },
                                  clipBounds: {
                                    top: round(clipBounds.top),
                                    right: round(clipBounds.right),
                                    bottom: round(clipBounds.bottom),
                                    left: round(clipBounds.left),
                                  },
                                  marginTop: style.marginTop,
                                  paddingTop: style.paddingTop,
                                  paddingBottom: style.paddingBottom,
                                  fontSize: style.fontSize,
                                  lineHeight: style.lineHeight,
                                };
                              };
                              return {
                                title: metrics(
                                  '#stock-trading-hours-title',
                                  '.stock-trading-hours-head'
                                ),
                                summary: metrics(
                                  '#stock-trading-hours-summary',
                                  '.stock-trading-hours-body'
                                ),
                              };
                            }"""
                        )
                        typography_failures = []
                        for name in ("title", "summary"):
                            metric = trading_hours.get(name) or {}
                            text_bounds = metric.get("textBounds") or {}
                            clip_bounds = metric.get("clipBounds") or {}
                            if (
                                float(text_bounds.get("top") or 0)
                                < float(clip_bounds.get("top") or 0) - 0.5
                            ):
                                typography_failures.append(f"{name}_top_clip")
                            if (
                                float(text_bounds.get("right") or 0)
                                > float(clip_bounds.get("right") or 0) + 0.5
                            ):
                                typography_failures.append(f"{name}_right_clip")
                        summary_metric = trading_hours.get("summary") or {}
                        if summary_metric.get("marginTop") != "0px":
                            typography_failures.append("summary_negative_margin")
                        if (
                            summary_metric.get("paddingTop") != "2px"
                            or summary_metric.get("paddingBottom") != "2px"
                        ):
                            typography_failures.append("summary_font_safety_padding")
                        if typography_failures:
                            raise QaFailure(
                                "국내주식 거래시간 안내의 제목 또는 설명 문구가 잘립니다.",
                                {
                                    "failed_contracts": typography_failures,
                                    "trading_hours": trading_hours,
                                },
                            )
                        page.locator("#stock-trading-hours-confirm").click()
                        sheet.wait_for(state="hidden", timeout=int(timeout * 1000))
                    fixtures.append(
                        {
                            "code": stock["code"],
                            "tabs": tab_labels,
                            "disabled_tabs": disabled_tabs,
                            "signal_action": stock.get("signal_action"),
                            "signal_stage_text": expected_stage,
                            "transition_date": transition_date,
                            "change_context": change_context,
                            "title_logo": title_logo,
                            "action_icons": action_icons,
                            "trading_hours": trading_hours,
                            "news_ui": news_ui,
                        }
                    )
                return {
                    **latest_shell,
                    "fixtures": fixtures,
                }

            stock_result = _run_page_case(
                browser=browser,
                catalog_by_id=catalog_by_id,
                case_id="SIG-UI-003",
                base_url=base_url,
                timeout=timeout,
                artifact_dir=output_dir,
                callback=stock_case,
                storage_state=storage_state,
                share_id=share_id,
            )
            results.append(stock_result)

            def stock_title_logo_case(page: Any, theme: str) -> dict[str, Any]:
                fixtures: list[dict[str, Any]] = []
                for code, expected_kind in (
                    ("005930", "collected"),
                    ("278470", "official"),
                    ("014950", "fallback"),
                ):
                    page.set_viewport_size({"width": 320, "height": 844})
                    _navigate_page(
                        page,
                        _page_url(
                            base_url,
                            f"/dashboard/{code}",
                            theme=theme,
                            qa_title_logo=datetime.now(KST).strftime("%H%M%S%f"),
                        ),
                        wait_until="commit",
                    )
                    _assert_page_shell(page, theme=theme)
                    page.wait_for_selector(
                        "#stock-title-logo:not([hidden]) .stock-title-logo-frame",
                        state="visible",
                        timeout=int(timeout * 1000),
                    )
                    viewport_evidence: dict[str, Any] = {}
                    for viewport_label, viewport_size in (
                        ("320px", {"width": 320, "height": 844}),
                        ("458px", {"width": 458, "height": 872}),
                    ):
                        page.set_viewport_size(viewport_size)
                        page.wait_for_timeout(100)
                        snapshot = page.evaluate(
                            """() => {
                              const logo = document.querySelector('#stock-title-logo');
                              const titleRow = logo?.closest('.staging-stock-hero-name-row, .stock-v3-name-row');
                              const title = titleRow?.querySelector('[data-staging-stock-name], #stock-name');
                              const frame = logo?.querySelector('.stock-title-logo-frame');
                              const image = logo?.querySelector('.stock-list-logo-image');
                              const fallback = logo?.querySelector('.stock-list-logo-fallback');
                              const bounds = element => {
                                const rect = element?.getBoundingClientRect();
                                return rect ? {
                                  top: rect.top,
                                  right: rect.right,
                                  bottom: rect.bottom,
                                  left: rect.left,
                                  width: rect.width,
                                  height: rect.height,
                                } : null;
                              };
                              return {
                                code: logo?.dataset.stockCode || '',
                                hidden: logo?.hidden ?? true,
                                logoCount: document.querySelectorAll('#stock-title-logo').length,
                                bounds: bounds(logo),
                                rowBounds: bounds(titleRow),
                                titleBounds: bounds(title),
                                rowClass: titleRow?.className || '',
                                titleText: title?.textContent?.trim() || '',
                                insideChart: Boolean(logo?.closest('.stock-v3-chart-pane')),
                                frameClass: frame?.className || '',
                                imageSrc: image?.getAttribute('src') || '',
                                imageNaturalWidth: image?.naturalWidth || 0,
                                fallbackPresent: Boolean(fallback),
                                pointerEvents: logo ? getComputedStyle(logo).pointerEvents : '',
                                rootScrollWidth: document.documentElement.scrollWidth,
                                viewportWidth: innerWidth,
                              };
                            }"""
                        )
                        logo_bounds = snapshot.get("bounds") or {}
                        row_bounds = snapshot.get("rowBounds") or {}
                        title_bounds = snapshot.get("titleBounds") or {}
                        image_src = str(snapshot.get("imageSrc") or "")
                        frame_class = str(snapshot.get("frameClass") or "")
                        failures = []
                        if (
                            snapshot.get("code") != code
                            or snapshot.get("hidden")
                            or int(snapshot.get("logoCount") or 0) != 1
                        ):
                            failures.append("selected_stock_identity")
                        expected_size = 34 if viewport_label == "320px" else 36
                        if (
                            round(float(logo_bounds.get("width") or 0)) != expected_size
                            or round(float(logo_bounds.get("height") or 0)) != expected_size
                        ):
                            failures.append("staging_logo_size")
                        logo_center_y = (
                            float(logo_bounds.get("top") or 0)
                            + float(logo_bounds.get("bottom") or 0)
                        ) / 2
                        title_center_y = (
                            float(title_bounds.get("top") or 0)
                            + float(title_bounds.get("bottom") or 0)
                        ) / 2
                        title_gap = (
                            float(title_bounds.get("left") or 0)
                            - float(logo_bounds.get("right") or 0)
                        )
                        if (
                            "staging-stock-hero-name-row" not in str(snapshot.get("rowClass") or "")
                            or not snapshot.get("titleText")
                            or snapshot.get("insideChart")
                        ):
                            failures.append("title_row_identity")
                        if (
                            float(logo_bounds.get("left") or 0) < float(row_bounds.get("left") or 0) - 1
                            or title_gap < 4
                            or title_gap > 12
                            or abs(logo_center_y - title_center_y) > 1.5
                        ):
                            failures.append("title_alignment")
                        if snapshot.get("pointerEvents") != "none":
                            failures.append("title_interaction_passthrough")
                        if image_src and not (
                            f"/stock-logos/{code}.png" in image_src
                            or image_src.startswith("data:image/")
                        ):
                            failures.append("logo_url")
                        if expected_kind == "fallback":
                            if (
                                "is-fallback" not in frame_class
                                or not snapshot.get("fallbackPresent")
                            ):
                                failures.append("fallback")
                        elif (
                            "is-fallback" in frame_class
                            or int(snapshot.get("imageNaturalWidth") or 0) <= 0
                        ):
                            failures.append("logo_image")
                        if int(snapshot.get("rootScrollWidth") or 0) > int(snapshot.get("viewportWidth") or 0) + 1:
                            failures.append("horizontal_overflow")
                        if failures:
                            raise QaFailure(
                                "종목 상세 종목명 옆 로고가 전환·폴백·반응형 정렬 계약을 지키지 않았습니다.",
                                {
                                    "code": code,
                                    "theme": theme,
                                    "viewport": viewport_label,
                                    "expected_kind": expected_kind,
                                    "failed_contracts": failures,
                                    "title_logo": snapshot,
                                },
                            )
                        viewport_evidence[viewport_label] = snapshot
                    fixtures.append(
                        {
                            "code": code,
                            "expected_kind": expected_kind,
                            "viewports": viewport_evidence,
                        }
                    )
                page.set_viewport_size(MOBILE_VIEWPORT)
                return {"theme": theme, "fixtures": fixtures}

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-020",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=stock_title_logo_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def interest_loading_case(page: Any, theme: str) -> dict[str, Any]:
                watchlist_responses: list[dict[str, Any]] = []

                def record_watchlist_response(response: Any) -> None:
                    if "/watchlists/" not in response.url:
                        return
                    watchlist_responses.append(
                        {"status": response.status, "url": response.url.split("?", 1)[0]}
                    )

                page.on("response", record_watchlist_response)
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_interest=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#home-view", state="visible")
                # The opt-in notification sheet is allowed to appear after the
                # shell settles. Dismiss it so this case isolates the global
                # page-loading overlay regression instead of a deliberate modal.
                page.wait_for_timeout(900)
                push_sheet = page.locator("#push-notification-sheet")
                if push_sheet.count() and push_sheet.is_visible():
                    snooze = page.locator("#push-notification-sheet-snooze-button")
                    close = page.locator("#push-notification-sheet-close")
                    if snooze.count() and snooze.is_visible():
                        snooze.click()
                    elif close.count() and close.is_visible():
                        close.click()
                    push_sheet.wait_for(state="hidden", timeout=5_000)

                interest_tab = page.locator(
                    "#bottom-nav [data-app-view='portfolio']"
                )
                if interest_tab.count() != 1:
                    raise QaFailure(
                        "하단 관심 탭을 하나로 식별하지 못했습니다.",
                        {"count": interest_tab.count()},
                    )
                # A real pointer click is intentional: the original regression left
                # a full-screen loading layer over the navigation and intercepted it.
                interest_tab.click(timeout=int(timeout * 1000))
                page.wait_for_selector("#portfolio-view", state="visible")
                page.locator("#page-loading").wait_for(
                    state="hidden", timeout=int(timeout * 1000)
                )
                page.wait_for_function(
                    """() => {
                      const visible = element => Boolean(
                        element
                        && !element.hidden
                        && getComputedStyle(element).display !== 'none'
                        && getComputedStyle(element).visibility !== 'hidden'
                        && element.getClientRects().length
                      );
                      const view = document.querySelector('#portfolio-view');
                      const overlay = document.querySelector('#page-loading');
                      const busy = [...document.querySelectorAll(
                        '#portfolio-view [aria-busy="true"], #portfolio-view .inline-loading-spinner, #portfolio-view [class*="spinner"]'
                      )].some(visible);
                      const bodyBusy = document.body.getAttribute('aria-busy') === 'true';
                      const rendered = Boolean(document.querySelector('#watchlist-body')?.children.length);
                      return visible(view) && !visible(overlay) && !busy && !bodyBusy && rendered;
                    }""",
                    timeout=int(timeout * 1000),
                )
                page.wait_for_timeout(250)
                state = page.evaluate(
                    """() => {
                      const visible = element => Boolean(
                        element
                        && !element.hidden
                        && getComputedStyle(element).display !== 'none'
                        && getComputedStyle(element).visibility !== 'hidden'
                        && element.getClientRects().length
                      );
                      const overlay = document.querySelector('#page-loading');
                      const view = document.querySelector('#portfolio-view');
                      const interest = document.querySelector(
                        '#bottom-nav [data-app-view="portfolio"]'
                      );
                      const visibleBusy = [...document.querySelectorAll(
                        '#portfolio-view [aria-busy="true"], #portfolio-view .inline-loading-spinner, #portfolio-view [class*="spinner"]'
                      )].filter(visible);
                      return {
                        url: window.location.href,
                        route: new URL(window.location.href).searchParams.get('view'),
                        interest_active: interest?.classList.contains('active') || false,
                        interest_current: interest?.getAttribute('aria-current'),
                        portfolio_visible: visible(view),
                        loading_hidden: overlay?.hidden === true,
                        loading_visible_class: overlay?.classList.contains('visible') || false,
                        loading_computed_display: overlay ? getComputedStyle(overlay).display : null,
                        body_busy: document.body.getAttribute('aria-busy'),
                        visible_busy_count: visibleBusy.length,
                        watchlist_child_count: document.querySelector('#watchlist-body')?.children.length || 0,
                        visible_copy: (view?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 300),
                      };
                    }"""
                )
                failures = {
                    "route": state["route"] != "portfolio",
                    "interest_active": not state["interest_active"],
                    "interest_current": state["interest_current"] != "page",
                    "portfolio_visible": not state["portfolio_visible"],
                    "loading_hidden": not state["loading_hidden"],
                    "loading_visible_class": state["loading_visible_class"],
                    "loading_computed_display": state["loading_computed_display"] != "none",
                    "body_busy": state["body_busy"] == "true",
                    "visible_busy_count": state["visible_busy_count"] != 0,
                    "watchlist_child_count": state["watchlist_child_count"] < 1,
                }
                failed_contracts = [name for name, failed in failures.items() if failed]
                if failed_contracts:
                    raise QaFailure(
                        "관심 탭 전환 후 로딩 레이어가 정상 종료되지 않았습니다.",
                        {"failed_contracts": failed_contracts, "state": state},
                    )
                if not watchlist_responses:
                    raise QaFailure(
                        "관심종목 데이터 응답을 확인하지 못했습니다.",
                        {"state": state},
                    )
                failed_responses = [
                    item for item in watchlist_responses if item["status"] >= 400
                ]
                if failed_responses:
                    raise QaFailure(
                        "관심종목 API가 오류를 반환했습니다.",
                        {"responses": failed_responses},
                    )
                return {
                    **shell,
                    "loading_contract": state,
                    "watchlist_responses": watchlist_responses,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-006",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=interest_loading_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def feed_root_navigation_case(page: Any, theme: str) -> dict[str, Any]:
                publication_date = datetime.now(KST).date().isoformat()
                midday_fixture = {
                    "title": "오늘의 돈이 되는 소식",
                    "edition": "midday",
                    "edition_key": f"{publication_date}:midday",
                    "edition_label": "오전판",
                    "publication_date": publication_date,
                    "timezone": "Asia/Seoul",
                    "window_start": f"{publication_date}T09:00:00+09:00",
                    "window_end": f"{publication_date}T12:00:00+09:00",
                    "published_at": f"{publication_date}T12:00:00+09:00",
                    "next_publication_at": f"{publication_date}T16:00:00+09:00",
                    "popup_start": f"{publication_date}T12:00:00+09:00",
                    "popup_end": f"{publication_date}T16:00:00+09:00",
                    "generated_at": f"{publication_date}T12:00:00+09:00",
                    "total_news_count": 2,
                    "selected_news_count": 2,
                    "opportunity_count": 1,
                    "caution_count": 0,
                    "highlights": [
                        {"id": 1, "title": "오전 시장 흐름", "status": "확인", "why_it_matters": "장중 흐름"},
                    ],
                    "categories": [
                        {
                            "key": "market",
                            "label": "시장 흐름",
                            "icon": "📈",
                            "description": "오전 핵심",
                            "count": 1,
                            "items": [
                                {"id": 1, "title": "오전 시장 흐름", "status": "확인", "why_it_matters": "장중 흐름"},
                            ],
                        },
                    ],
                    "empty_message": None,
                }
                signal_fixture = {
                    "status": "ready",
                    "strategy_version": "position-lifecycle-v7.3",
                    "as_of": f"{publication_date}T13:30:00+09:00",
                    "items": [],
                    "preliminary_history": [
                        {
                            "code": "111111",
                            "name": "신규포착주",
                            "side": "buy",
                            "signal": "예비 매수",
                            "signal_date": publication_date,
                            "signal_at": f"{publication_date}T10:10:00+09:00",
                            "first_seen_at": f"{publication_date}T10:10:00+09:00",
                            "last_seen_at": f"{publication_date}T11:50:00+09:00",
                            "score": 74.2,
                            "reason": "오전 거래대금과 단기 추세 조건이 새로 충족됐어요.",
                            "action": "entry_pending",
                            "active": True,
                        },
                        {
                            "code": "222222",
                            "name": "업데이트주",
                            "side": "buy",
                            "signal": "예비 포착",
                            "signal_date": publication_date,
                            "signal_at": f"{publication_date}T08:30:00+09:00",
                            "first_seen_at": f"{publication_date}T08:30:00+09:00",
                            "last_seen_at": f"{publication_date}T11:40:00+09:00",
                            "score": 68.5,
                            "reason": "오전 가격 조건이 갱신돼 예비 포착을 유지했어요.",
                            "action": "entry_watch",
                            "active": True,
                        },
                        {
                            "code": "333333",
                            "name": "해제주",
                            "side": "buy",
                            "signal_date": publication_date,
                            "first_seen_at": f"{publication_date}T10:20:00+09:00",
                            "last_seen_at": f"{publication_date}T10:40:00+09:00",
                            "action": "entry_pending",
                            "active": False,
                        },
                        {
                            "code": "444444",
                            "name": "예비매도주",
                            "side": "sell",
                            "signal_date": publication_date,
                            "first_seen_at": f"{publication_date}T10:30:00+09:00",
                            "action": "full_exit_pending",
                            "active": True,
                        },
                        {
                            "code": "555555",
                            "name": "오후포착주",
                            "side": "buy",
                            "signal_date": publication_date,
                            "first_seen_at": f"{publication_date}T13:10:00+09:00",
                            "action": "entry_pending",
                            "active": True,
                        },
                    ],
                }
                page.route(
                    "**/briefings/morning-money/history?days=7",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        body=json.dumps([midday_fixture], ensure_ascii=False),
                    ),
                )
                page.route(
                    "**/market/quant-signals?*",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        body=json.dumps(signal_fixture, ensure_ascii=False),
                    ),
                )
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_feed=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#home-view", state="visible")
                page.wait_for_timeout(900)
                push_sheet = page.locator("#push-notification-sheet")
                if push_sheet.count() and push_sheet.is_visible():
                    snooze = page.locator("#push-notification-sheet-snooze-button")
                    close = page.locator("#push-notification-sheet-close")
                    if snooze.count() and snooze.is_visible():
                        snooze.click()
                    elif close.count() and close.is_visible():
                        close.click()
                    push_sheet.wait_for(state="hidden", timeout=5_000)
                feed_tab = page.locator("#bottom-nav [data-app-view='news']")
                if feed_tab.count() != 1:
                    raise QaFailure(
                        "하단 피드 탭을 하나로 식별하지 못했습니다.",
                        {"count": feed_tab.count()},
                    )
                feed_tab.click(timeout=int(timeout * 1000))
                page.wait_for_selector('body[data-view="news"]')
                page.wait_for_selector("#news-view", state="visible")
                page.locator("#page-loading").wait_for(
                    state="hidden",
                    timeout=int(timeout * 1000),
                )
                page.wait_for_selector(".app-topbar", state="visible")
                page.wait_for_selector("#bottom-nav", state="visible")
                page.wait_for_selector(".staging-feed-modes", state="visible")
                page.wait_for_timeout(300)

                state_script = """() => {
                  const inspect = selector => {
                    const element = document.querySelector(selector);
                    if (!element) return null;
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return {
                      display: style.display,
                      visibility: style.visibility,
                      position: style.position,
                      top: Math.round(rect.top * 10) / 10,
                      bottom: Math.round(rect.bottom * 10) / 10,
                      height: Math.round(rect.height * 10) / 10,
                      in_viewport: rect.bottom > 0 && rect.top < window.innerHeight,
                    };
                  };
                  const active = document.querySelector('#bottom-nav [aria-current="page"]');
                  return {
                    view: document.body.dataset.view,
                    heading: document.querySelector('[data-staging-heading]')?.textContent?.trim(),
                    active_view: active?.dataset.appView,
                    active_label: active?.textContent?.trim(),
                    feed_modes: [...document.querySelectorAll('.staging-feed-modes button')]
                      .map(button => button.textContent.trim()),
                    scroll_y: Math.round(window.scrollY),
                    viewport_height: window.innerHeight,
                    topbar: inspect('.app-topbar'),
                    bottom_nav: inspect('#bottom-nav'),
                  };
                }"""

                top_state = page.evaluate(state_script)
                page.evaluate(
                    """() => window.scrollTo({
                      top: Math.min(
                        Math.max(0, document.documentElement.scrollHeight - window.innerHeight),
                        900,
                      ),
                      behavior: 'instant',
                    })"""
                )
                page.wait_for_timeout(250)
                scrolled_state = page.evaluate(state_script)

                def state_failures(state: dict[str, Any]) -> list[str]:
                    failures: list[str] = []
                    if state.get("view") != "news":
                        failures.append("view")
                    if state.get("heading") != "피드":
                        failures.append("heading")
                    if state.get("active_view") != "news" or state.get("active_label") != "피드":
                        failures.append("active_feed")
                    if state.get("feed_modes") != ["뉴스", "콘텐츠", "일정"]:
                        failures.append("feed_modes")
                    topbar = state.get("topbar") or {}
                    if (
                        topbar.get("display") == "none"
                        or topbar.get("visibility") == "hidden"
                        or not topbar.get("in_viewport")
                        or topbar.get("position") not in {"sticky", "fixed"}
                    ):
                        failures.append("topbar")
                    bottom_nav = state.get("bottom_nav") or {}
                    if (
                        bottom_nav.get("display") == "none"
                        or bottom_nav.get("visibility") == "hidden"
                        or not bottom_nav.get("in_viewport")
                        or bottom_nav.get("position") != "fixed"
                        or float(bottom_nav.get("bottom") or 0)
                        > float(state.get("viewport_height") or 0) + 1
                    ):
                        failures.append("bottom_nav")
                    return failures

                failed_contracts = sorted(
                    set(state_failures(top_state) + state_failures(scrolled_state))
                )
                if failed_contracts:
                    raise QaFailure(
                        "피드에서 글로벌 헤더 또는 하단 내비게이션이 유지되지 않습니다.",
                        {
                            "failed_contracts": failed_contracts,
                            "top": top_state,
                            "scrolled": scrolled_state,
                        },
                    )
                page.locator('[data-staging-feed-mode="content"]').click()
                page.wait_for_selector(".staging-editorial-preliminary-buys", state="visible")
                preliminary_preview = page.evaluate(
                    """() => {
                      const section = document.querySelector('.staging-editorial-preliminary-buys');
                      const rows = [...(section?.querySelectorAll('[data-staging-preliminary-buy-code]') || [])];
                      return {
                        codes: rows.map(row => row.dataset.stagingPreliminaryBuyCode),
                        labels: rows.map(row => row.querySelector('span')?.textContent?.trim()),
                        count_label: section?.querySelector('header strong')?.textContent?.trim(),
                        note: section?.querySelector('.staging-editorial-preliminary-buy-note')?.textContent?.trim(),
                        overflow: section ? section.scrollWidth > section.clientWidth + 1 : true,
                      };
                    }"""
                )
                expected_codes = ["111111", "222222"]
                if (
                    preliminary_preview.get("codes") != expected_codes
                    or preliminary_preview.get("labels") != ["신규 · 74점", "업데이트 · 69점"]
                    or preliminary_preview.get("count_label") != "신규·업데이트 2종목"
                    or preliminary_preview.get("note") != "장 마감 전에는 신호가 바뀔 수 있어요."
                    or preliminary_preview.get("overflow") is not False
                ):
                    raise QaFailure(
                        "점심판의 신규·업데이트 예비 매수 요약이 시그널 계약과 다릅니다.",
                        {"preview": preliminary_preview, "expected_codes": expected_codes},
                    )

                page.locator("[data-staging-content-open]").first.click()
                page.wait_for_selector('body[data-view="morning-briefing"]')
                page.wait_for_selector(".staging-article-preliminary-buys", state="visible")
                preliminary_detail = page.evaluate(
                    """() => {
                      const section = document.querySelector('.staging-article-preliminary-buys');
                      const rows = [...(section?.querySelectorAll('.staging-article-preliminary-buy') || [])];
                      return {
                        title: section?.querySelector('h3')?.textContent?.trim(),
                        description: section?.querySelector('header p')?.textContent?.trim(),
                        codes: rows.map(row => row.getAttribute('href')?.split('/').pop()),
                        reasons: rows.map(row => row.querySelector(':scope > p')?.textContent?.trim()),
                        overflow: section ? section.scrollWidth > section.clientWidth + 1 : true,
                      };
                    }"""
                )
                if (
                    preliminary_detail.get("title") != "신규·업데이트 예비 매수"
                    or preliminary_detail.get("codes") != expected_codes
                    or not all(preliminary_detail.get("reasons") or [])
                    or "장 마감 전에는 바뀔 수 있어요." not in str(preliminary_detail.get("description") or "")
                    or preliminary_detail.get("overflow") is not False
                ):
                    raise QaFailure(
                        "점심판 상세의 예비 매수 링크·근거·안내가 완전하지 않습니다.",
                        {"detail": preliminary_detail, "expected_codes": expected_codes},
                    )
                return {
                    **shell,
                    "top": top_state,
                    "scrolled": scrolled_state,
                    "preliminary_preview": preliminary_preview,
                    "preliminary_detail": preliminary_detail,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-007",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=feed_root_navigation_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def safe_area_navigation_case(page: Any, theme: str) -> dict[str, Any]:
                fixtures: list[dict[str, Any]] = []
                for view, contextual in (
                    ("home", False),
                    ("portfolio", False),
                    ("search", False),
                    ("recommend-detail", True),
                    ("chart", True),
                    ("chart-study", True),
                ):
                    page_kwargs: dict[str, Any] = {
                        "view": view,
                        "theme": theme,
                        "qa_safe_area": datetime.now(KST).strftime("%H%M%S"),
                    }
                    if view == "recommend-detail":
                        page_kwargs["code"] = "278470"
                    _navigate_page(
                        page,
                        _page_url(
                            base_url,
                            "/dashboard",
                            **page_kwargs,
                        ),
                        wait_until="commit",
                    )
                    shell = _assert_page_shell(page, theme=theme)
                    page.wait_for_selector(f'body[data-view="{view}"]')
                    header_selector = ".app-topbar"
                    page.wait_for_selector(header_selector, state="visible")
                    baseline = page.evaluate(
                        "selector => document.querySelector(selector).getBoundingClientRect().height",
                        header_selector,
                    )
                    page.evaluate(
                        """() => document.documentElement.setAttribute(
                          'data-staging-ios-standalone',
                          '',
                        )"""
                    )
                    expected_baseline = 68 if contextual else 78
                    expected_height = expected_baseline + 47
                    page.wait_for_function(
                        """({ selector, expected }) => Math.abs(
                          document.querySelector(selector).getBoundingClientRect().height - expected
                        ) <= 1""",
                        arg={"selector": header_selector, "expected": expected_height},
                        timeout=2_000,
                    )
                    state = page.evaluate(
                        """({ view, contextual, headerSelector }) => {
                          const rect = selector => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const bounds = element.getBoundingClientRect();
                            return {
                              top: Math.round(bounds.top * 10) / 10,
                              bottom: Math.round(bounds.bottom * 10) / 10,
                              height: Math.round(bounds.height * 10) / 10,
                            };
                          };
                          const safeAreaProbe = document.createElement('div');
                          safeAreaProbe.style.cssText = [
                            'position:fixed',
                            'visibility:hidden',
                            'pointer-events:none',
                            'padding-top:var(--tc-safe-area-top)',
                          ].join(';');
                          document.body.appendChild(safeAreaProbe);
                          const resolvedSafeArea = parseFloat(
                            getComputedStyle(safeAreaProbe).paddingTop,
                          );
                          safeAreaProbe.remove();
                          const contentSelector = contextual
                            ? '.staging-contextual-topbar :is(button, h1)'
                            : '.staging-market-context';
                          const pageSelector = {
                            'recommend-detail': '#recommend-detail-page',
                            chart: '#chart-view',
                            'chart-study': '#chart-study-view',
                          }[view] || null;
                          return {
                            safe_area: getComputedStyle(document.body)
                              .getPropertyValue('--tc-safe-area-top').trim(),
                            resolved_safe_area: Math.round(resolvedSafeArea * 10) / 10,
                            ios_standalone_fallback: document.documentElement
                              .hasAttribute('data-staging-ios-standalone'),
                            header: rect(headerSelector),
                            content: rect(contentSelector),
                            page: pageSelector ? rect(pageSelector) : null,
                            header_display: getComputedStyle(
                              document.querySelector(headerSelector)
                            ).display,
                          };
                        }""",
                        {
                            "view": view,
                            "contextual": contextual,
                            "headerSelector": header_selector,
                        },
                    )
                    failed = []
                    if abs(float(baseline) - expected_baseline) > 1:
                        failed.append("baseline_height")
                    if abs(float(state.get("resolved_safe_area") or 0) - 47) > 1:
                        failed.append("safe_area_fallback")
                    if not state.get("ios_standalone_fallback"):
                        failed.append("ios_standalone_marker")
                    if abs(float((state.get("header") or {}).get("height") or 0) - expected_height) > 1:
                        failed.append("safe_header_height")
                    if float((state.get("content") or {}).get("top") or 0) < 47:
                        failed.append("content_above_safe_boundary")
                    if contextual and state.get("header_display") == "none":
                        failed.append("contextual_header_hidden")
                    if contextual and abs(
                        float((state.get("page") or {}).get("top") or 0)
                        - float((state.get("header") or {}).get("bottom") or 0)
                    ) > 1:
                        failed.append("contextual_page_overlap")
                    if failed:
                        raise QaFailure(
                            "상단 내비게이션이 iOS safe area 아래에 배치되지 않습니다.",
                            {
                                "view": view,
                                "failed_contracts": failed,
                                "baseline": baseline,
                                "state": state,
                            },
                        )
                    fixtures.append(
                        {
                            "view": view,
                            "contextual": contextual,
                            "baseline_height": round(float(baseline), 1),
                            **state,
                            "viewport": shell.get("viewport"),
                        }
                    )
                return {"fixtures": fixtures}

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-008",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=safe_area_navigation_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def compact_content_flow_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        f"/dashboard/{samsung['code']}",
                        theme=theme,
                        qa_content_flow=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#stock-view", state="visible")
                page.wait_for_function(
                    "() => document.querySelectorAll('#stock-view [data-stock-tab]').length === 5",
                    timeout=int(timeout * 1000),
                )
                tab_fixtures: list[dict[str, Any]] = []
                for tab_key in ("summary", "strategy", "news", "company", "community"):
                    tab = page.locator(f'[data-stock-tab="{tab_key}"]')
                    _select_tab(tab)
                    page.wait_for_timeout(150)
                    state = page.evaluate(
                        """tabKey => {
                          const stock = document.querySelector('#stock-view');
                          const footer = document.querySelector('.service-footer');
                          const chartStudy = document.querySelector('#chart-study-view');
                          const tab = document.querySelector(`[data-stock-tab="${tabKey}"]`);
                          const panel = document.getElementById(tab?.getAttribute('aria-controls') || '');
                          const stockRect = stock?.getBoundingClientRect();
                          const footerRect = footer?.getBoundingClientRect();
                          return {
                            tab: tabKey,
                            tabSelected: tab?.getAttribute('aria-selected'),
                            panelHidden: panel?.hidden,
                            panelDisplay: panel ? getComputedStyle(panel).display : null,
                            stockMinHeight: stock ? getComputedStyle(stock).minHeight : null,
                            footerGap: stockRect && footerRect
                              ? Math.round((footerRect.top - stockRect.bottom) * 10) / 10
                              : null,
                            hiddenChartStudy: {
                              hidden: chartStudy?.hidden,
                              display: chartStudy ? getComputedStyle(chartStudy).display : null,
                              height: chartStudy
                                ? Math.round(chartStudy.getBoundingClientRect().height * 10) / 10
                                : null,
                            },
                          };
                        }""",
                        tab_key,
                    )
                    failed = []
                    if state.get("tabSelected") != "true":
                        failed.append("tab_selection")
                    if state.get("panelHidden") is not False or state.get("panelDisplay") == "none":
                        failed.append("active_panel_visibility")
                    if state.get("stockMinHeight") not in {"0", "0px"}:
                        failed.append("stock_min_height")
                    gap = state.get("footerGap")
                    if not isinstance(gap, (int, float)) or gap < 0 or gap > 32:
                        failed.append("footer_gap")
                    chart_state = state.get("hiddenChartStudy") or {}
                    if (
                        chart_state.get("hidden") is not True
                        or chart_state.get("display") != "none"
                        or float(chart_state.get("height") or 0) != 0
                    ):
                        failed.append("hidden_chart_study_layout")
                    if failed:
                        raise QaFailure(
                            "종목 상세 마지막 콘텐츠와 서비스 유의사항 사이에 과도한 빈 영역이 남습니다.",
                            {"failed_contracts": failed, "state": state},
                        )
                    tab_fixtures.append(state)

                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="chart-study",
                        theme=theme,
                        qa_content_flow=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#chart-study-view", state="visible")
                chart_study = page.evaluate(
                    """() => {
                      const view = document.querySelector('#chart-study-view');
                      const footer = document.querySelector('.service-footer');
                      const viewRect = view?.getBoundingClientRect();
                      const footerRect = footer?.getBoundingClientRect();
                      return {
                        hidden: view?.hidden,
                        display: view ? getComputedStyle(view).display : null,
                        minHeight: view ? getComputedStyle(view).minHeight : null,
                        footerGap: viewRect && footerRect
                          ? Math.round((footerRect.top - viewRect.bottom) * 10) / 10
                          : null,
                      };
                    }"""
                )
                chart_gap = chart_study.get("footerGap")
                if (
                    chart_study.get("hidden") is not False
                    or chart_study.get("display") == "none"
                    or chart_study.get("minHeight") not in {"0", "0px"}
                    or not isinstance(chart_gap, (int, float))
                    or chart_gap < 0
                    or chart_gap > 32
                ):
                    raise QaFailure(
                        "차트 공부 마지막 콘텐츠와 서비스 유의사항 사이에 과도한 빈 영역이 남습니다.",
                        chart_study,
                    )
                return {
                    **shell,
                    "stock_tabs": tab_fixtures,
                    "chart_study": chart_study,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-009",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=compact_content_flow_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def community_mobile_shortcut_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        f"/dashboard/{samsung['code']}",
                        theme=theme,
                        qa_community_shortcut=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#stock-view", state="visible")
                page.wait_for_function(
                    "() => document.querySelectorAll('#stock-view [data-stock-tab]').length === 5",
                    timeout=int(timeout * 1000),
                )
                _select_tab(page.locator('[data-stock-tab="community"]'))
                state = page.evaluate(
                    """code => {
                      renderStockCommunity({
                        code,
                        providers: [{
                          key: 'naver_board',
                          label: '네이버',
                          items: [{
                            post_id: '426298204',
                            author_name: 'QA 사용자',
                            title: '모바일 바로가기 확인',
                            text: '모바일 바로가기 확인',
                            impact: '중립',
                            url: `https://finance.naver.com/item/board_read.naver?code=${code}&nid=426298204`,
                          }],
                        }],
                      });
                      const shortcut = document.querySelector('.stock-community-shortcut');
                      const rect = shortcut?.getBoundingClientRect();
                      return {
                        text: shortcut?.textContent?.trim(),
                        ariaLabel: shortcut?.getAttribute('aria-label'),
                        href: shortcut?.href,
                        target: shortcut?.target,
                        rel: shortcut?.rel,
                        childElementCount: shortcut?.childElementCount,
                        height: rect ? Math.round(rect.height * 10) / 10 : null,
                        visible: Boolean(rect?.width && rect?.height),
                        legacyActionCount: document.querySelectorAll('.stock-community-original').length,
                      };
                    }""",
                    samsung["code"],
                )
                expected_href = (
                    f"https://m.stock.naver.com/domestic/stock/{samsung['code']}"
                    "/discussion/426298204"
                )
                failed = []
                if state.get("text") != "바로가기":
                    failed.append("text_only_label")
                if state.get("ariaLabel") != "네이버 게시물 바로가기":
                    failed.append("accessible_name")
                if state.get("href") != expected_href:
                    failed.append("mobile_href")
                if state.get("target") != "_blank" or "noopener" not in str(state.get("rel") or ""):
                    failed.append("safe_new_tab")
                if state.get("childElementCount") != 0 or state.get("legacyActionCount") != 0:
                    failed.append("text_only_structure")
                if state.get("visible") is not True or float(state.get("height") or 0) < 44:
                    failed.append("mobile_touch_target")
                if failed:
                    raise QaFailure(
                        "커뮤니티 바로가기가 텍스트 전용 모바일 링크 계약을 충족하지 않습니다.",
                        {"failed_contracts": failed, "state": state},
                    )
                return {**shell, "shortcut": state}

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-013",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=community_mobile_shortcut_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def stacked_signal_controls_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="ai-signals",
                        theme=theme,
                        qa_sticky_controls=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("#ai-signals-view", state="visible")
                page.wait_for_function(
                    """() => {
                      const list = document.querySelector('#ai-signals-page-list');
                      if (!list) return false;
                      return !String(list.textContent || '').includes('불러오는 중입니다.');
                    }""",
                    timeout=int(timeout * 1000),
                )
                page.wait_for_timeout(900)
                notification_sheet = page.locator("#push-notification-sheet")
                if notification_sheet.is_visible():
                    page.locator("#push-notification-sheet-close").click()
                    notification_sheet.wait_for(state="hidden")
                page.evaluate(
                    """() => {
                      document.body.style.setProperty('--tc-safe-area-top', '47px', 'important');
                      document.documentElement.style.setProperty('scroll-behavior', 'auto', 'important');
                      document.body.style.setProperty('scroll-behavior', 'auto', 'important');
                      const list = document.querySelector('#ai-signals-page-list');
                      if (list) list.style.setProperty('min-height', 'calc(100vh + 1200px)', 'important');
                      window.scrollTo(0, 0);
                    }"""
                )

                initial_spacing = page.evaluate(
                    """() => {
                      const round = value => Math.round(value * 10) / 10;
                      const title = document.querySelector('#staging-ai-signals-title');
                      const modeTabs = document.querySelector('#ai-signal-mode-tabs');
                      const currentTab = document.querySelector('#ai-signal-mode-current');
                      const titleRect = title.getBoundingClientRect();
                      const modeRect = modeTabs.getBoundingClientRect();
                      const tabRect = currentTab.getBoundingClientRect();
                      return {
                        titleBottom: round(titleRect.bottom),
                        modeTop: round(modeRect.top),
                        modeHeight: round(modeRect.height),
                        tabTop: round(tabRect.top),
                        titleToTabsGap: round(modeRect.top - titleRect.bottom),
                        modePaddingTop: getComputedStyle(modeTabs).paddingTop,
                      };
                    }"""
                )
                initial_failures = []
                initial_gap = float(initial_spacing.get("titleToTabsGap") or 0)
                if initial_gap < 16 or initial_gap > 24:
                    initial_failures.append("title_tab_gap")
                if initial_spacing.get("modePaddingTop") != "0px":
                    initial_failures.append("safe_area_in_flow")
                if abs(float(initial_spacing.get("modeHeight") or 0) - 57) > 1:
                    initial_failures.append("mode_height")
                if abs(
                    float(initial_spacing.get("tabTop") or 0)
                    - float(initial_spacing.get("modeTop") or 0)
                ) > 1:
                    initial_failures.append("tab_inset")
                if initial_failures:
                    raise QaFailure(
                        "AI 시그널 타이틀과 모드 탭의 최초 간격이 너무 넓습니다.",
                        {
                            "failed_contracts": initial_failures,
                            "initial_spacing": initial_spacing,
                        },
                    )

                _select_tab(page.locator('[data-ai-signal-stage="recent-sell"]'))
                sell_disclaimer = page.locator("#ai-signal-sell-disclaimer")
                sell_disclaimer.wait_for(state="visible")
                sell_guidance = page.evaluate(
                    """() => {
                      const disclaimer = document.querySelector('#ai-signal-sell-disclaimer');
                      const filters = document.querySelector('#ai-signal-stage-tabs');
                      const list = document.querySelector('#ai-signals-page-list');
                      const disclaimerStyle = getComputedStyle(disclaimer);
                      const bodyStyle = getComputedStyle(document.body);
                      const disclaimerRect = disclaimer.getBoundingClientRect();
                      const filterRect = filters.getBoundingClientRect();
                      return {
                        text: String(disclaimer.textContent || '').trim().replace(/\s+/g, ' '),
                        hidden: disclaimer.hidden,
                        ariaDescribedBy: list.getAttribute('aria-describedby') || '',
                        top: Math.round(disclaimerRect.top * 10) / 10,
                        filterBottom: Math.round(filterRect.bottom * 10) / 10,
                        color: disclaimerStyle.color,
                        bodyColor: bodyStyle.color,
                        fontSize: disclaimerStyle.fontSize,
                        textAlign: disclaimerStyle.textAlign,
                      };
                    }"""
                )
                price_alignment = page.evaluate(
                    """() => {
                      const list = document.querySelector('#ai-signals-page-list');
                      const fixture = document.createElement('a');
                      fixture.className = 'home-ai-signal-row is-buy';
                      fixture.dataset.stagingListRow = 'true';
                      fixture.innerHTML = `
                        <span class="home-ai-signal-headline">
                          <span class="staging-ai-logo"></span>
                          <span class="home-ai-signal-identity"><strong class="home-ai-signal-name">정렬 확인</strong></span>
                          <span class="home-ai-signal-status"><strong class="home-ai-signal-state">매수 확정</strong></span>
                          <span class="staging-ai-chevron"></span>
                        </span>
                        <span class="home-ai-signal-supporting">
                          <small class="home-ai-signal-meta">신호 2026.08.28</small>
                          <span class="home-ai-signal-metrics">
                            <span class="home-ai-signal-metric is-price is-staging-visible is-staging-first" data-metric="price">
                              <span class="home-ai-signal-metric-label">전략 기준가</span>
                              <b class="home-ai-signal-metric-value">48,650원</b>
                            </span>
                          </span>
                        </span>`;
                      list.prepend(fixture);
                      const meta = fixture.querySelector('.home-ai-signal-meta');
                      const metrics = fixture.querySelector('.home-ai-signal-metrics');
                      const metric = fixture.querySelector('[data-metric="price"]');
                      const value = fixture.querySelector('.home-ai-signal-metric-value');
                      const result = {
                        metaLeft: Math.round(meta.getBoundingClientRect().left * 10) / 10,
                        metaBottom: Math.round(meta.getBoundingClientRect().bottom * 10) / 10,
                        priceLeft: Math.round(metric.getBoundingClientRect().left * 10) / 10,
                        priceTop: Math.round(metric.getBoundingClientRect().top * 10) / 10,
                        metricsJustify: getComputedStyle(metrics).justifyContent,
                        metricJustify: getComputedStyle(metric).justifyContent,
                        valueTextAlign: getComputedStyle(value).textAlign,
                      };
                      fixture.remove();
                      return result;
                    }"""
                )
                guidance_failures = []
                if sell_guidance.get("text") != "주의: AI의 매도 타이밍을 무조건 따라가지마세요!":
                    guidance_failures.append("disclaimer_copy")
                if sell_guidance.get("hidden") is not False:
                    guidance_failures.append("sell_visibility")
                if sell_guidance.get("ariaDescribedBy") != "ai-signal-sell-disclaimer":
                    guidance_failures.append("tabpanel_description")
                if float(sell_guidance.get("top") or 0) < float(sell_guidance.get("filterBottom") or 0) - 1:
                    guidance_failures.append("disclaimer_position")
                if sell_guidance.get("color") == sell_guidance.get("bodyColor"):
                    guidance_failures.append("disclaimer_not_subdued")
                if float(str(sell_guidance.get("fontSize") or "0").replace("px", "")) > 12:
                    guidance_failures.append("disclaimer_type_scale")
                if sell_guidance.get("textAlign") != "left":
                    guidance_failures.append("disclaimer_alignment")
                if abs(float(price_alignment.get("metaLeft") or 0) - float(price_alignment.get("priceLeft") or 0)) > 1:
                    guidance_failures.append("strategy_price_anchor")
                if float(price_alignment.get("priceTop") or 0) < float(price_alignment.get("metaBottom") or 0) - 1:
                    guidance_failures.append("strategy_price_vertical_order")
                if price_alignment.get("metricsJustify") != "flex-start":
                    guidance_failures.append("metrics_justification")
                if price_alignment.get("metricJustify") != "flex-start":
                    guidance_failures.append("strategy_price_justification")
                if price_alignment.get("valueTextAlign") != "left":
                    guidance_failures.append("strategy_price_text_alignment")
                if guidance_failures:
                    raise QaFailure(
                        "매도 확정 안내 또는 전략 기준가 왼쪽 정렬이 계약과 다릅니다.",
                        {
                            "failed_contracts": guidance_failures,
                            "sell_guidance": sell_guidance,
                            "price_alignment": price_alignment,
                        },
                    )
                _select_tab(page.locator('[data-ai-signal-stage="all"]'))
                sell_disclaimer.wait_for(state="hidden")
                if page.locator("#ai-signals-page-list").get_attribute("aria-describedby"):
                    raise QaFailure(
                        "매도 확정 외 필터에서도 매도 안내가 연결돼 있습니다.",
                        {"stage": "all"},
                    )

                def measure(mode: str, filter_selector: str) -> dict[str, Any]:
                    page.evaluate("window.scrollTo({ top: 500, behavior: 'instant' })")
                    page.wait_for_function(
                        """filterSelector => {
                          const modeTabs = document.querySelector('#ai-signal-mode-tabs');
                          const filters = document.querySelector(filterSelector);
                          if (!modeTabs || !filters) return false;
                          const modeRect = modeTabs.getBoundingClientRect();
                          const filterRect = filters.getBoundingClientRect();
                          const safeArea = parseFloat(getComputedStyle(document.body)
                            .getPropertyValue('--tc-safe-area-top')) || 0;
                          return window.scrollY >= 400
                            && Math.abs(modeRect.top - safeArea) <= 1
                            && Math.abs(filterRect.top - modeRect.bottom) <= 1;
                        }""",
                        arg=filter_selector,
                        timeout=5_000,
                    )
                    return page.evaluate(
                        """({ mode, filterSelector }) => {
                          const round = value => Math.round(value * 10) / 10;
                          const rect = element => {
                            const bounds = element.getBoundingClientRect();
                            return {
                              top: round(bounds.top),
                              bottom: round(bounds.bottom),
                              height: round(bounds.height),
                            };
                          };
                          const modeTabs = document.querySelector('#ai-signal-mode-tabs');
                          const filters = document.querySelector(filterSelector);
                          const list = document.querySelector('#ai-signals-page-list');
                          return {
                            mode,
                            scrollY: round(window.scrollY),
                            safeArea: getComputedStyle(document.body)
                              .getPropertyValue('--tc-safe-area-top').trim(),
                            modeTabs: rect(modeTabs),
                            filters: rect(filters),
                            list: rect(list),
                            modePosition: getComputedStyle(modeTabs).position,
                            modeTop: getComputedStyle(modeTabs).top,
                            filterPosition: getComputedStyle(filters).position,
                            filterTop: getComputedStyle(filters).top,
                          };
                        }""",
                        {"mode": mode, "filterSelector": filter_selector},
                    )

                current = measure("current", "#ai-signal-stage-tabs")
                _select_tab(page.locator('[data-ai-signal-mode="history"]'))
                page.wait_for_selector("#ai-signal-history-filters", state="visible")
                history = measure("history", "#ai-signal-history-filters")
                for state in (current, history):
                    failed = []
                    mode_rect = state.get("modeTabs") or {}
                    filter_rect = state.get("filters") or {}
                    if state.get("safeArea") != "47px":
                        failed.append("safe_area")
                    if state.get("modePosition") != "sticky" or state.get("modeTop") != "47px":
                        failed.append("mode_sticky")
                    if state.get("filterPosition") != "sticky" or state.get("filterTop") != "104px":
                        failed.append("filter_sticky")
                    if abs(float(mode_rect.get("top") or 0) - 47) > 1:
                        failed.append("mode_geometry")
                    if abs(float(filter_rect.get("top") or 0) - float(mode_rect.get("bottom") or 0)) > 1:
                        failed.append("stack_geometry")
                    if float((state.get("list") or {}).get("top") or 0) >= 0:
                        failed.append("list_not_scrolling")
                    if failed:
                        raise QaFailure(
                            "AI 시그널의 모드 탭과 단계 필터가 함께 고정되지 않습니다.",
                            {"failed_contracts": failed, "state": state},
                        )
                return {
                    **shell,
                    "initial_spacing": initial_spacing,
                    "sell_guidance": sell_guidance,
                    "price_alignment": price_alignment,
                    "current": current,
                    "history": history,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-010",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=stacked_signal_controls_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def home_market_carousel_motion_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_market_motion=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                carousel = page.locator("#home-market-carousel")
                carousel.wait_for(state="visible")
                page.wait_for_selector(
                    "#home-market-carousel.is-auto-scrolling [data-market-carousel-clone='true']",
                    state="attached",
                    timeout=int(timeout * 1000),
                )

                def measure() -> dict[str, Any]:
                    return page.evaluate(
                        """() => {
                          const carousel = document.querySelector('#home-market-carousel');
                          const tracks = [...carousel.querySelectorAll(':scope > .home-market-track')];
                          const track = tracks[0];
                          const originals = track ? [...track.children].filter(
                            card => card.classList.contains('home-index-card')
                              && card.dataset.marketCarouselClone !== 'true'
                          ) : [];
                          const clones = track ? [...track.children].filter(
                            card => card.dataset.marketCarouselClone === 'true'
                          ) : [];
                          const loopWidth = clones.length && originals.length
                            ? clones[0].offsetLeft - originals[0].offsetLeft
                            : 0;
                          const animations = track?.getAnimations() || [];
                          const animationTime = Number(animations[0]?.currentTime);
                          const compositorProgress = Number.isFinite(animationTime)
                            ? (animationTime * 10 / 1000)
                            : carousel.scrollLeft;
                          return {
                            sampledAtMs: performance.now(),
                            scrollLeft: carousel.scrollLeft,
                            loopWidth,
                            progress: loopWidth > 0 ? compositorProgress % loopWidth : compositorProgress,
                            visualLeft: originals[0]?.getBoundingClientRect().left ?? null,
                            originalCount: originals.length,
                            cloneCount: clones.length,
                            clonesHidden: clones.every(card => card.getAttribute('aria-hidden') === 'true'),
                            autoScrolling: carousel.classList.contains('is-auto-scrolling'),
                            nativeScrolling: carousel.classList.contains('is-user-scrolling'),
                            trackCount: tracks.length,
                            animationCount: animations.length,
                            trackTransform: track ? getComputedStyle(track).transform : 'none',
                            trackWillChange: track ? getComputedStyle(track).willChange : 'auto',
                          };
                        }"""
                    )

                cadence_samples: list[dict[str, Any]] = []
                for _sample in range(12):
                    page.wait_for_timeout(55)
                    cadence_samples.append(measure())
                visual_positions = [
                    float(sample["visualLeft"])
                    for sample in cadence_samples
                    if sample.get("visualLeft") is not None
                ]
                cadence_deltas = [
                    visual_positions[index] - visual_positions[index + 1]
                    for index in range(len(visual_positions) - 1)
                ]
                stationary_samples = sum(abs(delta) < 0.05 for delta in cadence_deltas)
                backward_samples = sum(delta < -0.05 for delta in cadence_deltas)
                unique_visual_positions = len({round(position, 2) for position in visual_positions})
                cadence_state = cadence_samples[-1] if cadence_samples else {}
                if (
                    len(visual_positions) != 12
                    or unique_visual_positions < 10
                    or stationary_samples > 1
                    or backward_samples > 0
                    or abs(float(cadence_state.get("scrollLeft") or 0)) > 0.01
                    or cadence_state.get("trackCount") != 1
                    or cadence_state.get("animationCount") != 1
                    or "transform" not in str(cadence_state.get("trackWillChange") or "")
                    or cadence_state.get("trackTransform") == "none"
                ):
                    raise QaFailure(
                        "지수 텍스트의 단일 합성 트랙이 프레임 사이에서 연속 이동하지 않습니다.",
                        {
                            "samples": cadence_samples,
                            "deltas": cadence_deltas,
                            "unique_positions": unique_visual_positions,
                            "stationary_samples": stationary_samples,
                            "backward_samples": backward_samples,
                        },
                    )

                moving_start = measure()
                page.wait_for_timeout(1_200)
                moving_end = measure()
                loop_width = float(moving_end.get("loopWidth") or 0)
                distance = (
                    float(moving_end.get("progress") or 0)
                    - float(moving_start.get("progress") or 0)
                    + loop_width
                ) % loop_width if loop_width > 0 else 0
                if (
                    moving_end.get("originalCount") != 8
                    or moving_end.get("cloneCount") != 8
                    or moving_end.get("clonesHidden") is not True
                    or moving_end.get("autoScrolling") is not True
                    or moving_end.get("trackCount") != 1
                    or moving_end.get("animationCount") != 1
                    or abs(float(moving_end.get("scrollLeft") or 0)) > 0.01
                    or not 5 <= distance <= 24
                ):
                    raise QaFailure(
                        "홈 시장 지수 스트립이 접근성을 유지하며 천천히 왼쪽으로 흐르지 않습니다.",
                        {"start": moving_start, "end": moving_end, "distance": distance},
                    )

                page.evaluate(
                    """() => {
                      renderHomeMarketIndices({
                        items: state.homeMarketIndexItems,
                        updated_at: new Date().toISOString(),
                      });
                    }"""
                )
                page.wait_for_selector(
                    "#home-market-carousel.is-auto-scrolling [data-market-carousel-clone='true']",
                    state="attached",
                    timeout=int(timeout * 1000),
                )
                page.wait_for_timeout(150)
                refreshed = measure()
                refresh_elapsed_ms = max(
                    0.0,
                    float(refreshed.get("sampledAtMs") or 0)
                    - float(moving_end.get("sampledAtMs") or 0),
                )
                refresh_distance = (
                    float(refreshed.get("progress") or 0)
                    - float(moving_end.get("progress") or 0)
                    + loop_width
                ) % loop_width if loop_width > 0 else 0
                refresh_distance_limit = max(
                    5.0,
                    min(30.0, refresh_elapsed_ms * 0.025 + 3.0),
                )
                if (
                    refreshed.get("originalCount") != 8
                    or refreshed.get("cloneCount") != 8
                    or refreshed.get("clonesHidden") is not True
                    or refreshed.get("autoScrolling") is not True
                    or refreshed.get("trackCount") != 1
                    or refreshed.get("animationCount") != 1
                    or abs(float(refreshed.get("scrollLeft") or 0)) > 0.01
                    or refresh_distance > refresh_distance_limit
                ):
                    raise QaFailure(
                        "시세 재렌더 뒤 지수 스트립의 복제 카드 또는 순환 위치가 끊깁니다.",
                        {
                            "before_refresh": moving_end,
                            "after_refresh": refreshed,
                            "distance": refresh_distance,
                            "elapsed_ms": refresh_elapsed_ms,
                            "distance_limit": refresh_distance_limit,
                        },
                    )

                handoff_before = measure()
                page.evaluate(
                    """() => {
                      const carousel = document.querySelector('#home-market-carousel');
                      carousel.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' }));
                    }"""
                )
                handoff_after = measure()
                handoff_visual_delta = abs(
                    float(handoff_after.get("visualLeft") or 0)
                    - float(handoff_before.get("visualLeft") or 0)
                )
                if (
                    handoff_visual_delta > 1
                    or handoff_after.get("nativeScrolling") is not True
                    or handoff_after.get("animationCount") != 0
                ):
                    raise QaFailure(
                        "자동 합성 트랙에서 사용자 스크롤로 인계할 때 지수 위치가 튑니다.",
                        {
                            "before": handoff_before,
                            "after": handoff_after,
                            "visual_delta": handoff_visual_delta,
                        },
                    )
                page.evaluate(
                    """() => {
                      const carousel = document.querySelector('#home-market-carousel');
                      carousel.scrollLeft += 40;
                      carousel.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, pointerType: 'touch' }));
                    }"""
                )
                held_start = measure()
                page.wait_for_timeout(700)
                held_end = measure()
                held_distance = abs(
                    float(held_end.get("progress") or 0)
                    - float(held_start.get("progress") or 0)
                )
                if (
                    held_distance > 1
                    or held_end.get("nativeScrolling") is not True
                    or held_end.get("animationCount") != 0
                ):
                    raise QaFailure(
                        "사용자 스와이프 직후 지수 자동 흐름이 대기하지 않습니다.",
                        {"start": held_start, "end": held_end, "distance": held_distance},
                    )

                page.emulate_media(reduced_motion="reduce")
                page.wait_for_timeout(150)
                reduced_start = measure()
                page.wait_for_timeout(700)
                reduced_end = measure()
                reduced_distance = abs(
                    float(reduced_end.get("progress") or 0)
                    - float(reduced_start.get("progress") or 0)
                )
                if (
                    reduced_distance > 1
                    or reduced_end.get("nativeScrolling") is not True
                    or reduced_end.get("animationCount") != 0
                ):
                    raise QaFailure(
                        "동작 줄이기 환경에서 지수 자동 흐름이 멈추지 않습니다.",
                        {"start": reduced_start, "end": reduced_end, "distance": reduced_distance},
                    )
                return {
                    **shell,
                    "moving_distance_px": round(distance, 2),
                    "refresh_position_delta_px": round(refresh_distance, 2),
                    "refresh_elapsed_ms": round(refresh_elapsed_ms, 2),
                    "manual_handoff_visual_delta_px": round(handoff_visual_delta, 3),
                    "interaction_hold_distance_px": round(held_distance, 2),
                    "reduced_motion_distance_px": round(reduced_distance, 2),
                    "loop_width_px": round(loop_width, 2),
                    "clone_count": moving_end.get("cloneCount"),
                    "cadence_unique_positions": unique_visual_positions,
                    "cadence_stationary_samples": stationary_samples,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-011",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=home_market_carousel_motion_case,
                    storage_state=storage_state,
                    share_id=share_id,
                    reduced_motion="no-preference",
                )
            )

            def home_watchlist_response_detail_case(page: Any, theme: str) -> dict[str, Any]:
                qa_remote_items: list[dict[str, Any]] = [
                    {
                        "code": "035720",
                        "name": "카카오",
                        "market": "KOSPI",
                        "investor_state": "not_holding",
                        "average_buy_price": None,
                    }
                ]
                qa_remote_sync_requests: list[dict[str, Any]] = []

                def qa_watchlist_route(route: Any) -> None:
                    method = str(route.request.method or "GET").upper()
                    if method == "PUT":
                        try:
                            request_payload = json.loads(route.request.post_data or "{}")
                        except json.JSONDecodeError:
                            request_payload = {}
                        items = request_payload.get("items") or []
                        qa_remote_items[:] = items if isinstance(items, list) else []
                        qa_remote_sync_requests.append(
                            {"method": method, "items": list(qa_remote_items)}
                        )
                    elif method != "GET":
                        route.fulfill(status=405, json={"detail": "method not allowed"})
                        return
                    route.fulfill(
                        status=200,
                        json={"share_id": share_id, "items": qa_remote_items},
                    )

                page.route(
                    re.compile(
                        rf".*/watchlists/{re.escape(share_id)}(?:\?.*)?$"
                    ),
                    qa_watchlist_route,
                )
                page.route(
                    re.compile(
                        rf".*/watchlists/{re.escape(share_id)}/recommendation-tracks(?:\?.*)?$"
                    ),
                    lambda route: route.fulfill(
                        status=200,
                        json={
                            "share_id": share_id,
                            "initialized": True,
                            "items": [],
                        },
                    ),
                )
                page.route(
                    re.compile(r".*/session/write-token(?:\?.*)?$"),
                    lambda route: route.fulfill(
                        status=200,
                        json={"write_token": "qa-e2e-write-token"},
                    ),
                )
                page.route(
                    "**/stocks/035720/quant-signals*",
                    lambda route: route.fulfill(
                        json={
                            "code": "035720",
                            "name": "카카오",
                            "sector": "인터넷",
                            "industry": "인터넷 서비스",
                            "as_of": "2026-08-29T10:30:00+09:00",
                            "data_state": "ready",
                            "confirmation": {
                                "entry_allowed": False,
                                "vetoes": [],
                                "evidence": [
                                    {
                                        "key": "flow",
                                        "available": True,
                                        "score": -50,
                                        "state": "caution",
                                        "summary": "외국인 -820억원 · 기관 +90억원",
                                        "source": "네이버금융 투자자별 매매동향",
                                        "as_of": "2026-08-28T15:30:00+09:00",
                                    },
                                    {
                                        "key": "disclosure",
                                        "available": True,
                                        "score": 0,
                                        "state": "neutral",
                                        "summary": "최근 90일 신규매수 차단 공시 없음",
                                        "source": "OpenDART 공시",
                                        "as_of": "2026-08-29T08:00:00+09:00",
                                    },
                                    {
                                        "key": "news",
                                        "available": True,
                                        "score": 40,
                                        "state": "supportive",
                                        "summary": "긍정 6건 · 부정 2건 · 중립 2건",
                                        "source": "저장 뉴스 + 네이버금융 종목뉴스",
                                        "as_of": "2026-08-29T09:20:00+09:00",
                                    },
                                    {
                                        "key": "research",
                                        "available": True,
                                        "score": 50,
                                        "state": "supportive",
                                        "summary": "최근 리포트 3건 · 목표가 상향 2건 · 투자의견 매수",
                                        "source": "증권사 발간 리포트",
                                        "as_of": "2026-08-29T07:30:00+09:00",
                                    },
                                ],
                            },
                            "current": {
                                "action": "entry_watch",
                                "label": "진입 관찰",
                                "price": 60_000,
                                "stop_reference": 55_000,
                                "partial_exit_reference": 66_000,
                                "next_confirmation": "외국인·기관 합산 순매수 전환 확인",
                            },
                        }
                    ),
                )
                page.route(
                    "**/stocks/035720/dashboard*",
                    lambda route: route.fulfill(
                        json={
                            "code": "035720",
                            "name": "카카오",
                            "as_of": "2026-08-29T10:30:00+09:00",
                            "quote": {
                                "price": 60_000,
                                "change_rate": 1.25,
                                "trade_date": "2026-08-28",
                                "as_of": "2026-08-29T10:30:00+09:00",
                                "market_session": "regular",
                                "is_live": True,
                            },
                            "coverage": {"price": True},
                            "company_profile": {"sector": "인터넷", "industry": "인터넷 서비스"},
                            "chart_analysis": {
                                "score": 74,
                                "trend": "상승 추세",
                                "setup": "돌파 대기",
                                "signals": ["현재가가 20일선 위"],
                                "risks": [],
                                "support": 58_000,
                                "resistance": 63_000,
                                "atr_percent": 3.0,
                            },
                            "revisions": {
                                "report_count_90d": 3,
                                "target_up_count": 2,
                                "target_down_count": 0,
                                "latest_opinion": "매수",
                                "latest_target_price": 75_000,
                            },
                            "flows": {},
                            "sentiment": {
                                "score": 40,
                                "positive_count": 6,
                                "negative_count": 2,
                                "neutral_count": 2,
                                "latest_items": [],
                            },
                        }
                    ),
                )
                page.route(
                    "**/stocks/035720/home-context*",
                    lambda route: route.fulfill(
                        json={
                            "code": "035720",
                            "name": "카카오",
                            "as_of": "2026-08-29T10:30:00+09:00",
                            "flows": [],
                            "disclosures": [],
                            "news_items": [],
                            "research_reports": [
                                {
                                    "broker_name": "QA증권",
                                    "opinion": "매수",
                                    "target_price": 75_000,
                                    "title": "이익 회복 기대",
                                    "published_at": "2026-08-29T07:30:00+09:00",
                                }
                            ],
                        }
                    ),
                )
                page.route(
                    "**/market/impact*",
                    lambda route: route.fulfill(
                        json={
                            "as_of": "2026-08-29T10:00:00+09:00",
                            "data_quality": "확인",
                            "market_status": "리스크 우위",
                            "summary": "금리와 투자심리 부담이 우세합니다.",
                            "good_weight": 30,
                            "bad_weight": 70,
                            "neutral_weight": 0,
                            "factors": [
                                {
                                    "key": "rate",
                                    "label": "금리",
                                    "percent": 30,
                                    "direction": "악재",
                                    "confidence": 80,
                                    "affected_sectors": ["인터넷"],
                                    "leader_stocks": ["NAVER", "카카오"],
                                },
                                {
                                    "key": "commodity",
                                    "label": "원자재",
                                    "percent": 20,
                                    "direction": "호재",
                                    "confidence": 60,
                                    "affected_sectors": ["화학"],
                                    "leader_stocks": ["LG화학"],
                                },
                            ],
                        }
                    ),
                )
                page.add_init_script(
                    """(() => {
                      const nativeFetch = window.fetch.bind(window);
                      window.__qaStockSummaryRequests = [];
                      window.fetch = (input, init = {}) => {
                        const url = String(input?.url || input || '');
                        if (!url.includes('/staging-ai/page-summary')) {
                          return nativeFetch(input, init);
                        }
                        const request = JSON.parse(String(init.body || '{}'));
                        window.__qaStockSummaryRequests.push(request);
                        const response = {
                          ...request.fallback,
                          generation_mode: 'rules',
                          model_name: null,
                          generation_note: 'qa delayed verified copy',
                          prompt_version: 'staging-page-summary-v11',
                          cache_hit: false,
                          input_tokens: null,
                          output_tokens: null,
                          total_tokens: null,
                          estimated_cost_usd: null,
                        };
                        return new Promise(resolve => window.setTimeout(() => resolve(
                          new Response(JSON.stringify(response), {
                            status: 200,
                            headers: { 'Content-Type': 'application/json' },
                          })
                        ), 450));
                      };
                    })();"""
                )
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_run=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                    ready_selector="body[data-view='home']",
                )
                shell = _assert_page_shell(page, theme=theme)
                response = page.locator("#home-ai-response")
                page.evaluate(
                    """() => {
                      const list = document.querySelector('#home-ai-response-personal-list');
                      const personal = document.querySelector(
                        '#home-ai-response .home-ai-response-personal'
                      );
                      const status = document.querySelector('#home-ai-response-summary');
                      if (!list || !personal) {
                        throw new Error('home AI response list unavailable');
                      }
                      // Freeze background signal work for this deterministic
                      // navigation/focus fixture. Otherwise a late home,
                      // market-index, trend, or revision response can replace
                      // the injected row while Playwright is interacting with it.
                      state.homeAiSignalsRequestId += 1;
                      state.aiSignalLoadSequence += 1;
                      window.clearTimeout(state.homeAiSignalsRetryTimer);
                      window.clearTimeout(state.aiSignalRevisionTimer);
                      window.clearTimeout(state.aiSignalReconcileTimer);
                      state.homeAiSignalsRetryTimer = null;
                      state.aiSignalRevisionTimer = null;
                      state.aiSignalReconcileTimer = null;
                      state.quoteStreamSignalControlActive = false;
                      closeAiSignalQuoteStreams();
                      pauseQuoteStreamConnection('checking');
                      const qaNativeReplaceQuoteStreamScope = window.replaceQuoteStreamScope;
                      window.__qaAiStockResponseQuoteScopes = [];
                      window.replaceQuoteStreamScope = (scope, entries = []) => {
                        if (scope !== 'staging-ai-stock-response') {
                          return qaNativeReplaceQuoteStreamScope(scope, entries);
                        }
                        window.__qaAiStockResponseQuoteScopes = entries.map(entry => entry.code);
                        for (const entry of entries) {
                          window.queueMicrotask(() => {
                            entry.handlers?.onStatus?.({ state: 'connected' });
                            entry.handlers?.onQuote?.({
                              quote: {
                                price: 60000,
                                change_rate: 1.25,
                                market_session: 'regular',
                                market_session_label: '장중',
                                is_live: true,
                                as_of: '2026-08-29T10:30:00+09:00',
                              },
                            });
                          });
                        }
                      };
                      loadHomeAiSignals = async () => false;
                      renderHomeAiResponse = () => {};
                      const watchlist = JSON.parse(localStorage.getItem('analyst.watchlist') || '[]');
                      const withoutQaStock = Array.isArray(watchlist)
                        ? watchlist.filter(item => String(item?.code || '') !== '035720')
                        : [];
                      withoutQaStock.push({
                        code: '035720',
                        name: '카카오',
                        market: 'KOSPI',
                        investor_state: 'not_holding',
                        average_buy_price: null,
                      });
                      localStorage.setItem('analyst.watchlist', JSON.stringify(withoutQaStock));
                      const row = document.createElement('a');
                      row.id = 'qa-ai-stock-response-row';
                      row.className = 'home-ai-interest-row is-negative';
                      row.href = '/dashboard/035720';
                      row.innerHTML = `
                        <span class="home-ai-interest-head"><strong>카카오</strong><em>직접 영향</em></span>
                        <p class="home-ai-interest-action">기업 호재만으로 추격하지 말고 거래대금과 외국인·기관 수급이 함께 이어지는지 확인하세요.</p>
                        <small class="home-ai-interest-basis">카카오X가 카뱅 품을 수 있는 이유 · 인터넷 연관 · AI 보유</small>
                      `;
                      list.replaceChildren(row);
                      personal.hidden = false;
                      list.hidden = false;
                      if (status) status.hidden = true;
                    }"""
                )
                response.wait_for(state="visible")
                personal = response.locator(".home-ai-response-personal")
                personal.wait_for(state="visible")
                row = page.locator("#qa-ai-stock-response-row")
                page.wait_for_selector(
                    "#qa-ai-stock-response-row[data-staging-ai-response-link='true']"
                )
                contract = response.evaluate(
                    """card => ({
                      factorListCount: card.querySelectorAll('#home-ai-response-factors').length,
                      rankCount: card.querySelectorAll('.home-ai-response-factor-rank').length,
                      preambleHeaderDisplay: getComputedStyle(
                        card.querySelector('.home-ai-response-personal > header')
                      ).display,
                      statusDisplay: getComputedStyle(
                        card.querySelector('#home-ai-response-summary')
                      ).display,
                      hasPersonalList: Boolean(card.querySelector('#home-ai-response-personal-list')),
                      personalBorderTopWidth: getComputedStyle(
                        card.querySelector('.home-ai-response-personal')
                      ).borderTopWidth,
                      firstRowBorderTopWidth: getComputedStyle(
                        card.querySelector('.home-ai-interest-row:first-child')
                      ).borderTopWidth,
                      rowLabel: card.querySelector('.home-ai-interest-row')?.getAttribute('aria-label') || '',
                    })"""
                )
                if (
                    contract.get("factorListCount")
                    or contract.get("rankCount")
                ):
                    raise QaFailure(
                        "홈 AI 대응 카드에 제거 대상인 1~3 순위 목록이 남아 있습니다.",
                        contract,
                    )
                if (
                    contract.get("preambleHeaderDisplay") != "none"
                    or contract.get("statusDisplay") != "none"
                    or not contract.get("hasPersonalList")
                ):
                    raise QaFailure(
                        "홈 AI 종목 대응의 반복 헤더나 설명 영역이 남아 있습니다.",
                        contract,
                    )
                border_top_width = float(
                    str(contract.get("personalBorderTopWidth") or "0").removesuffix("px")
                )
                first_row_border = float(
                    str(contract.get("firstRowBorderTopWidth") or "0").removesuffix("px")
                )
                if border_top_width > 0 or first_row_border > 0:
                    raise QaFailure(
                        "제거한 홈 표시 영역 자리에 불필요한 구분선이 남아 있습니다.",
                        contract,
                    )
                if contract.get("rowLabel") != "카카오 AI 종목 대응 보기":
                    raise QaFailure("종목 행의 목적이 전용 대응 화면으로 안내되지 않습니다.", contract)
                bounds = personal.bounding_box()
                viewport = page.viewport_size or MOBILE_VIEWPORT
                if (
                    not bounds
                    or bounds["x"] < 0
                    or bounds["x"] + bounds["width"] > viewport["width"] + 1
                ):
                    raise QaFailure(
                        "관심종목 영향도 섹션이 모바일 화면 폭을 벗어납니다.",
                        {"bounds": bounds, "viewport": viewport},
                    )
                row.click()
                page.wait_for_selector("body[data-view='ai-stock-response']")
                detail = page.locator("#staging-ai-stock-response-view")
                detail.wait_for(state="visible")
                page.wait_for_selector(
                    "#staging-ai-stock-response-view[data-response-display='loading']"
                )
                loading_contract = page.evaluate(
                    """() => {
                      const detail = document.querySelector('#staging-ai-stock-response-view');
                      const loader = detail?.querySelector('[data-staging-response-loader]');
                      const action = detail?.querySelector('.staging-ai-stock-response-action');
                      const selected = detail?.querySelector(
                        '[data-staging-response-investor-state][aria-pressed="true"]'
                      );
                      return {
                        ariaBusy: detail?.getAttribute('aria-busy'),
                        display: detail?.dataset.responseDisplay,
                        loaderDisplay: loader ? getComputedStyle(loader).display : '',
                        loaderText: loader?.textContent?.replace(/\s+/g, ' ').trim() || '',
                        actionDisplay: action ? getComputedStyle(action).display : '',
                        selectedState: selected?.getAttribute('data-staging-response-investor-state'),
                        optionCount: detail?.querySelectorAll('[data-staging-response-investor-state]').length || 0,
                      };
                    }"""
                )
                if (
                    loading_contract.get("ariaBusy") != "true"
                    or loading_contract.get("display") != "loading"
                    or loading_contract.get("loaderDisplay") == "none"
                    or "정리하고 있어요" not in str(loading_contract.get("loaderText") or "")
                    or loading_contract.get("actionDisplay") != "none"
                    or loading_contract.get("selectedState") != "not_holding"
                    or loading_contract.get("optionCount") != 2
                ):
                    raise QaFailure(
                        "종목 대응 설명이 완성되기 전 중간 본문이 노출됩니다.",
                        loading_contract,
                    )
                page.wait_for_selector(
                    "#staging-ai-stock-response-view[data-response-loaded='true']"
                )
                _wait_for_ui_contract(
                    page,
                    """() => ['openai', 'rules'].includes(
                      document.querySelector('#staging-ai-stock-response-view')?.dataset.summaryMode
                    )""",
                    stage="미보유 대응 설명",
                    timeout_ms=int(timeout * 1000),
                )
                detail_text = detail.inner_text()
                for required_text in (
                    "카카오",
                    "이 화면이 열린 이유",
                    "카카오X가 카뱅 품을 수 있는 이유",
                    "내 상황에 맞춰 볼게요",
                    "현재 이 종목을 보유하고 있나요?",
                    "미보유",
                    "보유 중",
                    "쉽게 풀어보면",
                    "왜 이렇게 보나요?",
                    "현재는 매수 관망이 필요해요",
                    "매수 관망",
                    "지금 판단",
                    "자료가 충분한가요?",
                    "확인한 자료",
                    "6개 모두",
                    "현재 주당 가격",
                    "60,000원",
                    "오늘 등락률",
                    "+1.25%",
                    "실제 계좌·주문 내역과 자동 연동되지 않아요",
                    "내 상황별 가격 가이드",
                    "가격이 내려올 때와 올라갈 때를 나눠 보세요",
                    "눌림목 확인 구간",
                    "상승 흐름 확인선",
                    "매수가 아님",
                    "관망을 이어갈 기준",
                    "앞으로 볼 것",
                    "앞으로 이렇게 확인하세요",
                    "가격이 내려올 때",
                    "가격이 올라갈 때",
                    "계속 기다릴 때",
                    "왜 이렇게 봤나요?",
                    "6가지 자료 자세히 보기",
                    "점수와 계산 방법 알아보기",
                    "종목 상세에서 차트 보기",
                ):
                    if required_text not in detail_text:
                        raise QaFailure(
                            "초보자용 AI 종목 대응 화면의 필수 내용이 누락됐습니다.",
                            {"missing": required_text, "detail_text": detail_text},
                        )
                if "판단 신뢰도" in detail_text or "종합점수" in detail_text:
                    raise QaFailure(
                        "적중 확률로 오해할 수 있는 기술 라벨이 첫 화면에 남아 있습니다.",
                        {"detail_text": detail_text},
                    )
                if (
                    "판단이 바뀌려면" in detail_text
                    or "매수 전환 확인 가격" in detail_text
                    or "관망하다가 다시 볼 매수 포인트예요" in detail_text
                ):
                    raise QaFailure(
                        "높은 확인 가격을 매수가로 오해하게 만드는 이전 문구가 남아 있습니다.",
                        {"detail_text": detail_text},
                    )
                page.get_by_text("6가지 자료 자세히 보기", exact=True).click()
                page.get_by_text("점수와 계산 방법 알아보기", exact=True).click()
                expanded_text = detail.inner_text()
                for required_text in (
                    "가격 흐름",
                    "74점",
                    "외국인·기관 매매",
                    "외국인 -820억원",
                    "회사 공식 공시",
                    "최근 90일 신규매수 차단 공시 없음",
                    "최근 뉴스 분위기",
                    "긍정 6건 · 부정 2건 · 중립 2건",
                    "증권사 리포트",
                    "최근 리포트 3건 · 목표가 상향 2건 · 투자의견 매수",
                    "금리·환율·업종 환경",
                    "종목·업종 관련 축",
                    "분석 점수 (-100~+100)",
                    "내부 근거 충실도",
                    "적중률이나 주가 상승 확률이 아니에요",
                    "현재 반영 100%",
                ):
                    if required_text not in expanded_text:
                        raise QaFailure(
                            "펼친 근거·계산 상세의 필수 내용이 누락됐습니다.",
                            {"missing": required_text, "detail_text": expanded_text},
                        )
                detail_contract = page.evaluate(
                    """() => ({
                      route: new URL(location.href).searchParams.get('view'),
                      code: new URL(location.href).searchParams.get('code'),
                      stockDetailHidden: document.querySelector('#stock-view')?.hidden,
                      bottomNavDisplay: getComputedStyle(document.querySelector('#bottom-nav')).display,
                      pageWidth: document.querySelector('#staging-ai-stock-response-view')?.getBoundingClientRect().width || 0,
                      pageScrollWidth: document.querySelector('#staging-ai-stock-response-view')?.scrollWidth || 0,
                      viewportWidth: innerWidth,
                      directionLabel: document.querySelector('.staging-ai-stock-response-overview dt')?.textContent?.trim(),
                      directionValue: document.querySelector('[data-staging-response-direction]')?.textContent?.trim(),
                      directionGuide: document.querySelector('[data-staging-response-direction-guide]')?.textContent?.trim(),
                      investorState: document.querySelector('#staging-ai-stock-response-view')?.dataset.investorState,
                      selectedInvestorState: document.querySelector(
                        '[data-staging-response-investor-state][aria-pressed="true"]'
                      )?.getAttribute('data-staging-response-investor-state'),
                      investorOptionHeights: [...document.querySelectorAll(
                        '[data-staging-response-investor-state]'
                      )].map(node => node.getBoundingClientRect().height),
                      averagePriceFieldHidden: document.querySelector(
                        '[data-staging-response-average-price-field]'
                      )?.hidden,
                      livePrice: document.querySelector(
                        '[data-staging-response-live-price]'
                      )?.textContent?.trim(),
                      liveRate: document.querySelector(
                        '[data-staging-response-live-rate]'
                      )?.textContent?.trim(),
                      liveQuoteState: document.querySelector(
                        '[data-staging-response-live-quote]'
                      )?.dataset.liveQuoteState,
                      liveStateText: document.querySelector(
                        '[data-staging-response-live-state]'
                      )?.textContent?.trim(),
                      liveQuoteScopeCodes: window.__qaAiStockResponseQuoteScopes || [],
                      guideKeys: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-guide-row'
                      )).map(node => node.dataset.guideKey),
                      guideLabels: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-guide-row h4'
                      )).map(node => node.textContent?.trim()),
                      guideStatuses: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-guide-row-head > div > span'
                      )).map(node => node.textContent?.trim()),
                      guideValues: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-guide-row strong'
                      )).map(node => node.textContent?.trim()),
                      decisionKeys: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-decision-step'
                      )).map(node => node.dataset.decisionKey),
                      decisionStatuses: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-decision-step-head > em'
                      )).map(node => node.textContent?.trim()),
                      decisionValues: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-decision-step > strong'
                      )).map(node => node.textContent?.trim()),
                      firstOverviewPaddingLeft: parseFloat(getComputedStyle(
                        document.querySelector('.staging-ai-stock-response-overview > div:first-child')
                      ).paddingLeft || '0'),
                      firstOverviewTextInset: (() => {
                        const card = document.querySelector('.staging-ai-stock-response-overview > div:first-child');
                        const label = card?.querySelector('dt');
                        return card && label
                          ? label.getBoundingClientRect().left - card.getBoundingClientRect().left
                          : 0;
                      })(),
                      metricCount: document.querySelectorAll('.staging-ai-stock-response-metric').length,
                      metricLabels: Array.from(document.querySelectorAll('.staging-ai-stock-response-metric h4')).map(node => node.textContent?.trim()),
                      metricStatuses: Array.from(document.querySelectorAll('.staging-ai-stock-response-metric-status')).map(node => node.textContent?.trim()),
                      sourceCount: Array.from(document.querySelectorAll('.staging-ai-stock-response-metric > footer > span:first-child')).filter(node => node.textContent?.trim()).length,
                      weightCount: Array.from(document.querySelectorAll('.staging-ai-stock-response-metric > footer > span:last-child')).filter(node => /^판단 반영 [0-9]+%$/.test(node.textContent?.trim() || '')).length,
                      firstScreenOrder: [
                        '.staging-ai-stock-response-context',
                        '.staging-ai-stock-response-investor-state',
                        '.staging-ai-stock-response-action',
                        '.staging-ai-stock-response-guide',
                        '.staging-ai-stock-response-next',
                        '.staging-ai-stock-response-evidence',
                        '.staging-ai-stock-response-method',
                      ].map(selector => document.querySelector(selector)?.offsetTop || 0),
                      metricLiveRegion: document.querySelector('[data-staging-response-metrics]')?.getAttribute('aria-live'),
                      announcementLiveRegion: document.querySelector('[data-staging-response-announcement]')?.getAttribute('aria-live'),
                      ariaBusy: document.querySelector('#staging-ai-stock-response-view')?.getAttribute('aria-busy'),
                      summaryMode: document.querySelector('#staging-ai-stock-response-view')?.dataset.summaryMode,
                      responseDisplay: document.querySelector('#staging-ai-stock-response-view')?.dataset.responseDisplay,
                      loaderDisplay: getComputedStyle(
                        document.querySelector('[data-staging-response-loader]')
                      ).display,
                      stockSummaryStates: (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response')
                        .map(request => request.facts?.investor_state),
                      stockSummaryModes: (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response')
                        .map(request => request.facts?.position_mode),
                      stockSummaryDecisionPlans: (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response')
                        .map(request => (request.facts?.decision_plan || []).map(item => item.key)),
                      summaryBadgeCount: document.querySelectorAll('[data-staging-summary-provenance]').length,
                      explanationLabel: document.querySelector('.staging-ai-stock-response-explanation > span')?.textContent?.trim(),
                      explanation: document.querySelector('[data-staging-response-reason]')?.textContent?.trim(),
                      visibleModelWords: /GPT|문구 정리|데이터 요약/.test(
                        document.querySelector('#staging-ai-stock-response-view')?.innerText || ''
                      ),
                    })"""
                )
                if (
                    detail_contract.get("route") != "ai-stock-response"
                    or detail_contract.get("code") != "035720"
                    or detail_contract.get("stockDetailHidden") is not True
                    or detail_contract.get("bottomNavDisplay") != "none"
                    or detail_contract.get("pageWidth", 0) > detail_contract.get("viewportWidth", 0) + 1
                    or detail_contract.get("pageScrollWidth", 0) > detail_contract.get("viewportWidth", 0) + 1
                    or detail_contract.get("directionLabel") != "지금 판단"
                    or detail_contract.get("directionValue") != "매수 관망"
                    or detail_contract.get("directionGuide") != "신호가 같은 방향으로 모이는지 기다려요"
                    or detail_contract.get("investorState") != "not_holding"
                    or detail_contract.get("selectedInvestorState") != "not_holding"
                    or detail_contract.get("averagePriceFieldHidden") is not True
                    or detail_contract.get("livePrice") != "60,000원"
                    or detail_contract.get("liveRate") != "+1.25%"
                    or detail_contract.get("liveQuoteState") != "connected"
                    or detail_contract.get("liveStateText") != "실시간으로 반영 중"
                    or detail_contract.get("liveQuoteScopeCodes") != ["035720"]
                    or detail_contract.get("guideKeys") != [
                        "watch_zone",
                        "buy_trigger",
                        "risk_line",
                    ]
                    or detail_contract.get("guideLabels") != [
                        "눌림목 확인 구간",
                        "상승 흐름 확인선",
                        "관망을 이어갈 기준",
                    ]
                    or detail_contract.get("guideStatuses") != [
                        "하락 멈춤 확인",
                        "매수가 아님",
                        "주의",
                    ]
                    or len(detail_contract.get("guideValues") or []) != 3
                    or (detail_contract.get("guideValues") or [None, None])[1]
                    != "63,000원"
                    or detail_contract.get("decisionKeys")
                    != ["pullback", "breakout", "wait"]
                    or (detail_contract.get("decisionStatuses") or [None, None])[1]
                    != "매수가 아님"
                    or (detail_contract.get("decisionValues") or [None, None])[1]
                    != "63,000원"
                    or not all(
                        float(height) >= 44
                        for height in detail_contract.get("investorOptionHeights") or []
                    )
                    or abs(float(detail_contract.get("firstOverviewPaddingLeft") or 0) - 12) > 0.5
                    or float(detail_contract.get("firstOverviewTextInset") or 0) < 11
                    or detail_contract.get("metricCount") != 6
                    or detail_contract.get("metricLabels") != [
                        "가격 흐름",
                        "외국인·기관 매매",
                        "회사 공식 공시",
                        "최근 뉴스 분위기",
                        "증권사 리포트",
                        "금리·환율·업종 환경",
                    ]
                    or len(detail_contract.get("metricStatuses") or []) != 6
                    or detail_contract.get("sourceCount") != 6
                    or detail_contract.get("weightCount") != 6
                    or detail_contract.get("firstScreenOrder") != sorted(
                        detail_contract.get("firstScreenOrder") or []
                    )
                    or detail_contract.get("metricLiveRegion") is not None
                    or detail_contract.get("announcementLiveRegion") != "polite"
                    or detail_contract.get("ariaBusy") != "false"
                    or detail_contract.get("summaryMode") not in {"openai", "rules"}
                    or detail_contract.get("responseDisplay") != "ready"
                    or detail_contract.get("loaderDisplay") != "none"
                    or (detail_contract.get("stockSummaryStates") or [])[-1:] != ["not_holding"]
                    or (detail_contract.get("stockSummaryModes") or [])[-1:] != ["watching"]
                    or (detail_contract.get("stockSummaryDecisionPlans") or [])[-1:]
                    != [["pullback", "breakout", "wait"]]
                    or detail_contract.get("summaryBadgeCount") != 0
                    or detail_contract.get("explanationLabel") != "왜 이렇게 보나요?"
                    or not detail_contract.get("explanation")
                    or detail_contract.get("visibleModelWords") is not False
                ):
                    raise QaFailure(
                        "초보자용 AI 종목 대응 화면의 라우팅·정보 위계 계약이 깨졌습니다.",
                        detail_contract,
                    )
                perspective_contract: dict[str, Any] = {}
                page.locator(
                    '[data-staging-response-investor-state="holding"]'
                ).click()
                page.wait_for_selector(
                    "#staging-ai-stock-response-view[data-response-display='loading']"
                )
                holding_loading_action_display = page.evaluate(
                    "getComputedStyle(document.querySelector('.staging-ai-stock-response-action')).display"
                )
                _wait_for_ui_contract(
                    page,
                    """() => {
                      const detail = document.querySelector('#staging-ai-stock-response-view');
                      const latest = (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response').at(-1);
                      return detail?.dataset.investorState === 'holding'
                        && detail?.dataset.responseDisplay === 'ready'
                        && latest?.facts?.position_mode === 'holding_unknown';
                    }""",
                    stage="평균 매수가 미입력 보유 대응",
                    timeout_ms=int(timeout * 1000),
                )
                holding_unknown = page.evaluate(
                    """() => ({
                      selected: document.querySelector(
                        '[data-staging-response-investor-state][aria-pressed="true"]'
                      )?.getAttribute('data-staging-response-investor-state'),
                      direction: document.querySelector('[data-staging-response-direction]')?.textContent?.trim(),
                      headline: document.querySelector('[data-staging-response-action]')?.textContent?.trim(),
                      averageFieldHidden: document.querySelector(
                        '[data-staging-response-average-price-field]'
                      )?.hidden,
                      request: (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response').at(-1)?.facts,
                      guideKeys: Array.from(document.querySelectorAll(
                        '.staging-ai-stock-response-guide-row'
                      )).map(node => node.dataset.guideKey),
                      ariaBusy: document.querySelector('#staging-ai-stock-response-view')?.getAttribute('aria-busy'),
                    })"""
                )
                holding_unknown["loading_action_display"] = holding_loading_action_display
                perspective_contract["holding_unknown"] = holding_unknown
                if (
                    holding_loading_action_display != "none"
                    or holding_unknown.get("selected") != "holding"
                    or holding_unknown.get("direction") != "매수가 입력 필요"
                    or holding_unknown.get("headline")
                    != "평균 매수가를 입력하면 보유 대응을 손익에 맞춰 볼 수 있어요"
                    or holding_unknown.get("averageFieldHidden") is not False
                    or (holding_unknown.get("request") or {}).get("position_mode")
                    != "holding_unknown"
                    or (holding_unknown.get("request") or {}).get("average_buy_price") is not None
                    or holding_unknown.get("guideKeys")
                    != ["current_price", "risk_line", "first_sell"]
                    or holding_unknown.get("ariaBusy") != "false"
                ):
                    raise QaFailure(
                        "평균 매수가 미입력 보유 상태의 안내가 올바르지 않습니다.",
                        holding_unknown,
                    )

                average_input = page.locator("[data-staging-response-average-price]")
                average_submit = page.locator(
                    "[data-staging-response-average-price-field] button[type='submit']"
                )
                for mode, average_price, expected_direction, expected_headline, expected_return in (
                    (
                        "holding_profit",
                        "50000",
                        "수익 관리",
                        "현재 수익권이라면 분할 매도로 이익을 지킬 구간을 볼 때예요",
                        20.0,
                    ),
                    (
                        "holding_loss",
                        "70000",
                        "손실 관리",
                        "현재 손실권이라면 가격별 손실 제한 기준을 먼저 세울 때예요",
                        -14.285714,
                    ),
                ):
                    average_input.fill(average_price)
                    average_submit.click()
                    page.wait_for_selector(
                        "#staging-ai-stock-response-view[data-response-display='loading']"
                    )
                    _wait_for_ui_contract(
                        page,
                        """mode => {
                          const detail = document.querySelector('#staging-ai-stock-response-view');
                          const latest = (window.__qaStockSummaryRequests || [])
                            .filter(request => request.page_type === 'stock_response').at(-1);
                          return detail?.dataset.responseDisplay === 'ready'
                            && latest?.facts?.position_mode === mode;
                        }""",
                        arg=mode,
                        stage=f"평균 매수가 입력 후 {mode} 대응",
                        timeout_ms=int(timeout * 1000),
                    )
                    measurement = page.evaluate(
                        """() => ({
                          selected: document.querySelector(
                            '[data-staging-response-investor-state][aria-pressed="true"]'
                          )?.getAttribute('data-staging-response-investor-state'),
                          direction: document.querySelector('[data-staging-response-direction]')?.textContent?.trim(),
                          headline: document.querySelector('[data-staging-response-action]')?.textContent?.trim(),
                          inputValue: document.querySelector(
                            '[data-staging-response-average-price]'
                          )?.value,
                          request: (window.__qaStockSummaryRequests || [])
                            .filter(request => request.page_type === 'stock_response').at(-1)?.facts,
                          guideKeys: Array.from(document.querySelectorAll(
                            '.staging-ai-stock-response-guide-row'
                          )).map(node => node.dataset.guideKey),
                          guideStatuses: Array.from(document.querySelectorAll(
                            '.staging-ai-stock-response-guide-row-head > div > span'
                          )).map(node => node.textContent?.trim()),
                          persistedAverage: window.SecretNoteWatchlistInvestorState
                            ?.readAverageBuyPrice('035720'),
                          ariaBusy: document.querySelector('#staging-ai-stock-response-view')
                            ?.getAttribute('aria-busy'),
                        })"""
                    )
                    perspective_contract[mode] = measurement
                    request_facts = measurement.get("request") or {}
                    expected_keys = (
                        ["return", "first_sell", "protect"]
                        if mode == "holding_profit"
                        else ["return", "risk_line", "recovery"]
                    )
                    expected_status = "수익권" if mode == "holding_profit" else "손실권"
                    if (
                        measurement.get("selected") != "holding"
                        or measurement.get("direction") != expected_direction
                        or measurement.get("headline") != expected_headline
                        or request_facts.get("investor_state") != "holding"
                        or request_facts.get("position_mode") != mode
                        or float(request_facts.get("average_buy_price") or 0)
                        != float(average_price)
                        or abs(
                            float(request_facts.get("personal_return_rate") or 0)
                            - expected_return
                        )
                        > 0.01
                        or measurement.get("guideKeys") != expected_keys
                        or (measurement.get("guideStatuses") or [None])[0]
                        != expected_status
                        or float(measurement.get("persistedAverage") or 0)
                        != float(average_price)
                        or measurement.get("ariaBusy") != "false"
                    ):
                        raise QaFailure(
                            "평균 매수가 기준 수익·손실 대응 가이드가 올바르지 않습니다.",
                            {"mode": mode, "measurement": measurement},
                        )

                summary_request_count_before_return = page.evaluate(
                    "(window.__qaStockSummaryRequests || []).filter(request => "
                    "request.page_type === 'stock_response').length"
                )
                page.locator(
                    '[data-staging-response-investor-state="not_holding"]'
                ).click()
                _wait_for_ui_contract(
                    page,
                    """expectedCount => {
                      const detail = document.querySelector('#staging-ai-stock-response-view');
                      const requests = (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response');
                      return detail?.dataset.responseDisplay === 'ready'
                        && detail?.dataset.investorState === 'not_holding'
                        && requests.length === expectedCount
                        && requests.some(request => request.facts?.position_mode === 'watching');
                    }""",
                    arg=summary_request_count_before_return,
                    stage="보유에서 미보유로 전환한 대응",
                    timeout_ms=int(timeout * 1000),
                )
                cleared_state = page.evaluate(
                    """() => ({
                      fieldHidden: document.querySelector(
                        '[data-staging-response-average-price-field]'
                      )?.hidden,
                      persistedAverage: window.SecretNoteWatchlistInvestorState
                        ?.readAverageBuyPrice('035720'),
                      summaryRequestCount: (window.__qaStockSummaryRequests || [])
                        .filter(request => request.page_type === 'stock_response').length,
                    })"""
                )
                perspective_contract["not_holding_after_holding"] = cleared_state
                if (
                    cleared_state.get("fieldHidden") is not True
                    or cleared_state.get("persistedAverage") is not None
                    or cleared_state.get("summaryRequestCount")
                    != summary_request_count_before_return
                ):
                    raise QaFailure(
                        "미보유 전환 후 평균 매수가가 남아 있습니다.",
                        cleared_state,
                    )
                reflow_contract: dict[str, Any] = {}
                for label, viewport_size in (
                    ("320px", {"width": 320, "height": 740}),
                    ("200_percent_equivalent", {"width": 229, "height": 436}),
                ):
                    page.set_viewport_size(viewport_size)
                    page.wait_for_timeout(80)
                    measurement = page.evaluate(
                        """() => {
                          const detail = document.querySelector('#staging-ai-stock-response-view');
                          return {
                            width: detail?.getBoundingClientRect().width || 0,
                            scrollWidth: detail?.scrollWidth || 0,
                            viewportWidth: innerWidth,
                            overviewColumns: getComputedStyle(
                              document.querySelector('.staging-ai-stock-response-overview')
                            ).gridTemplateColumns,
                            methodColumns: getComputedStyle(
                              document.querySelector('.staging-ai-stock-response-method dl > div')
                            ).gridTemplateColumns,
                          };
                        }"""
                    )
                    reflow_contract[label] = measurement
                    if (
                        measurement.get("width", 0) > measurement.get("viewportWidth", 0) + 1
                        or measurement.get("scrollWidth", 0)
                        > measurement.get("viewportWidth", 0) + 1
                    ):
                        raise QaFailure(
                            f"AI 종목 대응 화면이 {label} 리플로우에서 가로로 넘칩니다.",
                            measurement,
                        )
                page.set_viewport_size(MOBILE_VIEWPORT)
                page.wait_for_timeout(80)
                page.locator("[data-staging-contextual-back]").click()
                page.wait_for_selector("body[data-view='home']")
                page.wait_for_selector("#qa-ai-stock-response-row", state="visible")
                try:
                    # Product focus restoration retries after layout settles
                    # (rAF, 120 ms, 420 ms). Assert the outcome, not an earlier
                    # point-in-time sample that races those accessibility hooks.
                    page.wait_for_function(
                        "expected => document.activeElement?.id === expected",
                        arg="qa-ai-stock-response-row",
                        timeout=min(int(timeout * 1000), 3_000),
                    )
                except Exception as exc:
                    raise QaFailure(
                        "AI 종목 대응 화면에서 돌아왔을 때 원래 종목 행으로 포커스가 복원되지 않았습니다.",
                        {"active_element": page.evaluate("document.activeElement?.id || ''")},
                    ) from exc
                restored_focus = page.evaluate("document.activeElement?.id || ''")
                if restored_focus != "qa-ai-stock-response-row":
                    raise QaFailure(
                        "AI 종목 대응 화면에서 돌아왔을 때 원래 종목 행으로 포커스가 복원되지 않았습니다.",
                        {"active_element": restored_focus},
                    )
                return {
                    **shell,
                    **contract,
                    "bounds": bounds,
                    "detail": detail_contract,
                    "loading": loading_contract,
                    "perspectives": perspective_contract,
                    "watchlist_sync_requests": qa_remote_sync_requests,
                    "reflow": reflow_contract,
                    "restored_focus": restored_focus,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-012",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=home_watchlist_response_detail_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-019",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=home_watchlist_response_detail_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def home_notification_entry_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        qa_notification=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector("body[data-view='home']")

                def read_header_icon_contract(expected_names: list[str]) -> list[dict[str, Any]]:
                    contract = page.locator(".staging-top-actions").evaluate(
                        """nav => [...nav.querySelectorAll(':scope > button')].map(button => {
                          const icon = button.querySelector('svg.staging-top-action-icon');
                          const buttonRect = button.getBoundingClientRect();
                          if (!icon) {
                            return { missing: true, buttonWidth: buttonRect.width, buttonHeight: buttonRect.height };
                          }
                          const iconRect = icon.getBoundingClientRect();
                          const shapes = [...icon.querySelectorAll('path, circle')];
                          const shapeBoxes = shapes.map(shape => shape.getBBox());
                          const minX = Math.min(...shapeBoxes.map(box => box.x));
                          const minY = Math.min(...shapeBoxes.map(box => box.y));
                          const maxX = Math.max(...shapeBoxes.map(box => box.x + box.width));
                          const maxY = Math.max(...shapeBoxes.map(box => box.y + box.height));
                          const styles = shapes.map(shape => {
                            const style = getComputedStyle(shape);
                            return {
                              fill: style.fill,
                              stroke: style.stroke,
                              strokeWidth: parseFloat(style.strokeWidth),
                              strokeLinecap: style.strokeLinecap,
                              strokeLinejoin: style.strokeLinejoin,
                            };
                          });
                          const viewBox = icon.viewBox.baseVal;
                          return {
                            name: icon.dataset.stagingTopIcon,
                            buttonWidth: buttonRect.width,
                            buttonHeight: buttonRect.height,
                            iconWidth: iconRect.width,
                            iconHeight: iconRect.height,
                            centerDeltaX: (iconRect.left + iconRect.width / 2) - (buttonRect.left + buttonRect.width / 2),
                            centerDeltaY: (iconRect.top + iconRect.height / 2) - (buttonRect.top + buttonRect.height / 2),
                            viewBox: [viewBox.x, viewBox.y, viewBox.width, viewBox.height],
                            opticalBox: {
                              x: minX,
                              y: minY,
                              width: maxX - minX,
                              height: maxY - minY,
                              centerX: (minX + maxX) / 2,
                              centerY: (minY + maxY) / 2,
                            },
                            styles,
                          };
                        })"""
                    )
                    names = [item.get("name") for item in contract]
                    geometry_failed = names != expected_names
                    for item in contract:
                        optical = item.get("opticalBox") or {}
                        styles = item.get("styles") or []
                        geometry_failed = geometry_failed or bool(item.get("missing")) or any(
                            (
                                float(item.get("buttonWidth") or 0) < 44,
                                float(item.get("buttonHeight") or 0) < 44,
                                abs(float(item.get("iconWidth") or 0) - 26) > 0.25,
                                abs(float(item.get("iconHeight") or 0) - 26) > 0.25,
                                abs(float(item.get("centerDeltaX") or 0)) > 0.5,
                                abs(float(item.get("centerDeltaY") or 0)) > 0.5,
                                item.get("viewBox") != [0, 0, 36, 36],
                                not 22 <= float(optical.get("width") or 0) <= 28,
                                not 22 <= float(optical.get("height") or 0) <= 28,
                                abs(float(optical.get("centerX") or 0) - 18) > 2,
                                abs(float(optical.get("centerY") or 0) - 18) > 2,
                                not styles,
                                any(
                                    style.get("fill") != "none"
                                    or style.get("stroke") == "none"
                                    or abs(float(style.get("strokeWidth") or 0) - 2.6) > 0.01
                                    or style.get("strokeLinecap") != "round"
                                    or style.get("strokeLinejoin") != "round"
                                    for style in styles
                                ),
                            )
                        )
                    if geometry_failed:
                        raise QaFailure(
                            "루트 상단 액션 아이콘의 크기·선 두께·중심 계약이 다릅니다.",
                            {"expected_names": expected_names, "contract": contract},
                        )
                    return contract

                root_icon_contracts: dict[str, list[dict[str, Any]]] = {
                    "home": read_header_icon_contract(["bell", "search"]),
                }
                home_action = page.locator(
                    '.staging-top-actions [data-staging-top-action="notifications"]'
                )
                home_action.wait_for(state="visible")
                action_box = home_action.bounding_box()
                if (
                    not action_box
                    or action_box["width"] < 44
                    or action_box["height"] < 44
                    or home_action.locator("svg.staging-notification-bell").count() != 1
                ):
                    raise QaFailure(
                        "홈 상단 알림 벨의 아이콘 또는 터치 영역 계약이 다릅니다.",
                        {"bounds": action_box},
                    )

                home_action.click()
                sheet = page.locator("#push-notification-sheet")
                sheet.wait_for(state="visible", timeout=int(timeout * 1000))
                page.wait_for_timeout(200)
                contract = sheet.evaluate(
                    """sheet => {
                      const card = sheet.querySelector('.push-notification-sheet-card');
                      const body = sheet.querySelector('.push-notification-sheet-body');
                      const core = sheet.querySelector('.push-notification-core');
                      const optional = sheet.querySelector('.push-notification-optional');
                      const requiredInputs = [...core.querySelectorAll('input[data-push-condition]')];
                      const optionalInputs = [...optional.querySelectorAll('input[data-push-condition]')];
                      const status = sheet.querySelector('#push-notification-sheet-status');
                      const rect = card.getBoundingClientRect();
                      return {
                        title: sheet.querySelector('#push-notification-sheet-title')?.textContent?.trim() || '',
                        coreText: core.textContent.replace(/\s+/g, ' ').trim(),
                        coreAria: core.getAttribute('aria-label') || '',
                        requiredCount: requiredInputs.length,
                        requiredChecked: requiredInputs.every(input => input.checked),
                        optionalCount: optionalInputs.length,
                        optionalSummary: optional.querySelector('[data-push-optional-summary]')?.textContent?.trim() || '',
                        repeatedLockedCopyCount: (sheet.innerText.match(/항상 받기/g) || []).length,
                        lockedRowCount: sheet.querySelectorAll('.push-notification-condition.is-required').length,
                        statusHidden: status.hidden,
                        statusText: status.textContent.trim(),
                        focusedOnCard: document.activeElement === card,
                        bodyOverflowX: body.scrollWidth - body.clientWidth,
                        bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                      };
                    }"""
                )
                if (
                    contract.get("requiredCount") != 2
                    or contract.get("requiredChecked") is not True
                    or "돈이 되는 소식 · AI 시그널" not in contract.get("coreText", "")
                    or "항상 켜짐" not in contract.get("coreText", "")
                    or contract.get("optionalCount") != 6
                    or contract.get("optionalSummary") != "6/6 선택"
                    or contract.get("repeatedLockedCopyCount")
                    or contract.get("lockedRowCount")
                ):
                    raise QaFailure(
                        "필수 알림 요약 또는 선택 가능한 추가 알림 구조가 다릅니다.",
                        contract,
                    )
                bounds = contract.get("bounds") or {}
                viewport = page.viewport_size or MOBILE_VIEWPORT
                if (
                    float(contract.get("bodyOverflowX") or 0) > 1
                    or float(bounds.get("x") or 0) < -1
                    or float(bounds.get("width") or 0) > viewport["width"] + 1
                    or float(bounds.get("height") or 0) > viewport["height"] + 1
                    or contract.get("focusedOnCard") is not True
                ):
                    raise QaFailure(
                        "알림 설정 시트의 모바일 경계 또는 초기 포커스가 올바르지 않습니다.",
                        {"contract": contract, "viewport": viewport},
                    )

                sheet.locator("#push-notification-sheet-close").click()
                sheet.wait_for(state="hidden")
                page.wait_for_timeout(100)
                focus_returned = home_action.evaluate("button => document.activeElement === button")
                if not focus_returned:
                    raise QaFailure("알림 설정 시트를 닫은 뒤 홈 알림 벨로 포커스가 돌아오지 않았습니다.")

                for root_view in ("portfolio", "search", "news"):
                    page.locator(f"#bottom-nav [data-app-view='{root_view}']").click()
                    page.wait_for_selector(f"body[data-view='{root_view}']")
                    page.locator(
                        '.staging-top-actions [data-staging-top-action="ai-signals"]'
                    ).wait_for(state="visible")
                    root_icon_contracts[root_view] = read_header_icon_contract(["ai", "search"])

                optical_extents: dict[str, float] = {}
                for route_contract in root_icon_contracts.values():
                    for icon_contract in route_contract:
                        optical = icon_contract.get("opticalBox") or {}
                        extent = max(
                            float(optical.get("width") or 0),
                            float(optical.get("height") or 0),
                        )
                        optical_extents.setdefault(str(icon_contract.get("name") or ""), extent)
                if max(optical_extents.values()) - min(optical_extents.values()) > 3:
                    raise QaFailure(
                        "벨·AI·검색 아이콘의 광학 크기 차이가 허용 범위를 벗어났습니다.",
                        {"optical_extents": optical_extents, "routes": root_icon_contracts},
                    )

                other_action = page.locator(
                    '.staging-top-actions [data-staging-top-action="ai-signals"]'
                )
                other_action.wait_for(state="visible")
                other_contract = other_action.evaluate(
                    """button => ({
                      label: button.getAttribute('aria-label'),
                      view: button.dataset.stagingView,
                      hasBell: Boolean(button.querySelector('.staging-notification-bell')),
                      hasSignal: Boolean(button.querySelector('.staging-ai-signal-glyph')),
                    })"""
                )
                if other_contract != {
                    "label": "AI 시그널",
                    "view": "ai-signals",
                    "hasBell": False,
                    "hasSignal": True,
                }:
                    raise QaFailure(
                        "홈 밖의 첫 상단 액션이 AI 시그널로 복원되지 않았습니다.",
                        other_contract,
                    )
                return {
                    **shell,
                    "home_action_bounds": action_box,
                    "sheet": contract,
                    "focus_returned": focus_returned,
                    "other_root_action": other_contract,
                    "root_icon_contracts": root_icon_contracts,
                    "optical_extents": optical_extents,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-014",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=home_notification_entry_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def chart_pattern_integrity_case(page: Any, theme: str) -> dict[str, Any]:
                selected: dict[str, Any] | None = None
                api_evidence: list[dict[str, Any]] = []
                for code in ("005930", "000660", "035720"):
                    response = page.request.get(
                        _page_url(
                            base_url,
                            f"/stocks/{code}/dashboard",
                            refresh="true",
                            include_profile="false",
                            include_live="false",
                        ),
                        timeout=timeout * 1000,
                    )
                    if not response.ok:
                        raise QaFailure(
                            "차트 패턴 API를 확인하지 못했습니다.",
                            {"code": code, "http_status": response.status},
                        )
                    payload = response.json()
                    patterns = ((payload.get("chart_analysis") or {}).get("patterns") or [])
                    line_patterns = [
                        item for item in patterns
                        if item.get("family") == "수렴·추세"
                    ]
                    violations: list[str] = []
                    for item in patterns:
                        if item.get("score_kind") != "pattern_fit":
                            violations.append(f"{item.get('key')}:score_kind")
                        if item.get("family") != "캤들" and item.get("status") == "확인":
                            confirmation = item.get("confirmation") or {}
                            if not (
                                confirmation.get("price_crossed") is True
                                and confirmation.get("volume_confirmed") is True
                                and float(confirmation.get("volume_ratio") or 0) >= 1.15
                            ):
                                violations.append(f"{item.get('key')}:confirmation")
                    for item in line_patterns:
                        boundaries = item.get("boundaries") or {}
                        if (
                            int(boundaries.get("window_days") or 999) > 30
                            or int(boundaries.get("touch_count") or 0) < 5
                            or int(boundaries.get("upper_touch_count") or 0) < 2
                            or int(boundaries.get("lower_touch_count") or 0) < 2
                            or not boundaries.get("upper")
                            or not boundaries.get("lower")
                        ):
                            violations.append(f"{item.get('key')}:boundaries")
                    if violations:
                        raise QaFailure(
                            "차트 패턴 형성·확인 API 계약이 다릅니다.",
                            {"code": code, "violations": violations, "patterns": patterns},
                        )
                    api_evidence.append(
                        {
                            "code": code,
                            "pattern_count": len(patterns),
                            "line_pattern_count": len(line_patterns),
                            "keys": [item.get("key") for item in patterns],
                        }
                    )
                    if patterns and (selected is None or line_patterns):
                        selected = {"code": code, "patterns": patterns, "has_line": bool(line_patterns)}
                    if selected and selected["has_line"]:
                        break

                if not selected:
                    raise QaFailure(
                        "학습 화면을 검증할 최근 차트 패턴이 없습니다.",
                        {"api": api_evidence},
                    )

                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        f"/dashboard/{selected['code']}",
                        theme=theme,
                        qa_run=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                shell = _assert_page_shell(page, theme=theme)
                pattern_section = page.locator("#stock-home-chart-analysis .chart-pattern-analysis")
                pattern_section.wait_for(state="visible", timeout=int(timeout * 1000))
                pattern_text = re.sub(r"\s+", " ", pattern_section.inner_text()).strip()
                if "패턴 적합도" not in pattern_text or "신뢰도" in pattern_text:
                    raise QaFailure(
                        "차트 패턴 점수 설명이 적합도 계약과 다릅니다.",
                        {"text": pattern_text},
                    )
                study_button = pattern_section.locator(".chart-pattern-study-button")
                study_button.click()
                study = page.locator("#chart-study-view")
                study.wait_for(state="visible", timeout=int(timeout * 1000))
                study_text = re.sub(r"\s+", " ", study.inner_text()).strip()
                if not all(label in study_text for label in ("패턴 적합도", "돌파 거래량")):
                    raise QaFailure(
                        "차트 공부 화면의 적합도·돌파 거래량 설명이 누락됐습니다.",
                        {"text": study_text},
                    )
                boundary_count = study.locator(".chart-study-actual-boundary").count()
                if selected["has_line"] and boundary_count != 2:
                    raise QaFailure(
                        "수렴·추세형 실제 차트에 상단·하단 경계선이 모두 그려지지 않았습니다.",
                        {"boundary_count": boundary_count, "code": selected["code"]},
                    )
                return {
                    **shell,
                    "selected_code": selected["code"],
                    "has_line_pattern": selected["has_line"],
                    "boundary_count": boundary_count,
                    "api": api_evidence,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-015",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=chart_pattern_integrity_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def portfolio_production_screens_case(page: Any, theme: str) -> dict[str, Any]:
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/portfolio",
                        theme=theme,
                        qa_run=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                )
                page.wait_for_selector("body", state="visible", timeout=20_000)
                shell = page.evaluate(
                    """requestedTheme => ({
                      theme: requestedTheme,
                      prefersDark: matchMedia('(prefers-color-scheme: dark)').matches,
                      viewport: innerWidth,
                      rootWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth,
                      title: document.title,
                      textLength: (document.body.innerText || '').trim().length,
                    })""",
                    theme,
                )
                if shell["prefersDark"] is not (theme == "dark"):
                    raise QaFailure("포트폴리오 브라우저 색상 환경이 요청과 다릅니다.", shell)
                if (
                    shell["rootWidth"] > shell["viewport"] + 2
                    or shell["bodyWidth"] > shell["viewport"] + 2
                    or shell["textLength"] < 20
                ):
                    raise QaFailure("포트폴리오 모바일 셸에 넘침 또는 빈 본문이 있습니다.", shell)
                expected_ids = [
                    "feature-ai-signals",
                    "feature-feed-content",
                    "feature-company-health",
                    "feature-report-analysis",
                    "feature-chart-study",
                ]
                expected_assets = [
                    "feature-ai-signals-production.jpg",
                    "feature-feed-content-production.jpg",
                    "feature-sk-hynix-company-health-production.jpg",
                    "feature-sk-hynix-report-analysis-production.jpg",
                    "feature-sk-hynix-chart-study-production.jpg",
                ]
                stories = page.locator("main > article.feature-story")
                actual_ids = stories.evaluate_all(
                    "nodes => nodes.map(node => node.id)"
                )
                if actual_ids != expected_ids:
                    raise QaFailure(
                        "프로덕션 주요 화면이 요청한 다섯 장면과 순서대로 구성되지 않았습니다.",
                        {"expected": expected_ids, "actual": actual_ids},
                    )

                images = stories.locator(".phone-shot-production img")
                page.wait_for_function(
                    "selector => [...document.querySelectorAll(selector)].every(image => image.complete && image.naturalWidth > 0)",
                    arg="main > article.feature-story .phone-shot-production img",
                    timeout=int(timeout * 1000),
                )
                image_contract = images.evaluate_all(
                    "nodes => nodes.map(image => ({src: image.getAttribute('src'), alt: image.alt, width: image.naturalWidth, height: image.naturalHeight}))"
                )
                actual_assets = [
                    str(item.get("src") or "").rsplit("/", 1)[-1]
                    for item in image_contract
                ]
                if actual_assets != expected_assets:
                    raise QaFailure(
                        "프로덕션 캡처 자산이 다섯 장면과 일치하지 않습니다.",
                        {"expected": expected_assets, "actual": actual_assets},
                    )
                invalid_images = [
                    item
                    for item in image_contract
                    if item.get("width") != 390
                    or item.get("height") != 844
                    or not str(item.get("alt") or "").strip()
                ]
                if invalid_images:
                    raise QaFailure(
                        "프로덕션 캡처의 390×844 비율 또는 대체텍스트 계약이 다릅니다.",
                        {"images": invalid_images},
                    )
                first_alt = str(image_contract[0].get("alt") or "")
                if "매수 확정" not in first_alt or "수익률" not in first_alt:
                    raise QaFailure(
                        "AI 시그널 캡처가 매수 확정 종목별 수익률 상태를 설명하지 않습니다.",
                        {"alt": first_alt},
                    )

                page_text = re.sub(r"\s+", " ", page.locator("main").inner_text()).strip()
                for label in (
                    "현재 프로덕션 화면을 기준으로",
                    "AI 시그널",
                    "피드 콘텐츠",
                    "기업 체력",
                    "리포트 분석",
                    "차트 공부",
                    "SK하이닉스",
                    "iPhone 13 Pro · 390×844",
                    "매수 확정 종목의 전략 기준가와 수익률",
                    "2026.08.29",
                ):
                    if label not in page_text:
                        raise QaFailure(
                            "프로덕션 화면 소개의 필수 문구가 누락됐습니다.",
                            {"label": label},
                        )

                first_button = stories.first.locator(".phone-shot-production")
                first_button.focus()
                first_button.click()
                dialog = page.locator("#image-dialog")
                dialog.wait_for(state="visible", timeout=int(timeout * 1000))
                if not str(page.locator("#dialog-image").get_attribute("src") or "").endswith(
                    expected_assets[0]
                ):
                    raise QaFailure("확대 대화상자가 선택한 프로덕션 캡처를 열지 않았습니다.")
                page.keyboard.press("Escape")
                dialog.wait_for(state="hidden", timeout=int(timeout * 1000))
                if not first_button.evaluate("element => document.activeElement === element"):
                    raise QaFailure("확대 대화상자를 닫은 뒤 진입 버튼으로 포커스가 돌아오지 않았습니다.")

                page.set_viewport_size({"width": 1280, "height": 900})
                page.wait_for_timeout(200)
                desktop = page.evaluate(
                    """() => ({
                      viewport: innerWidth,
                      rootWidth: document.documentElement.scrollWidth,
                      bodyWidth: document.body.scrollWidth,
                      storyCount: document.querySelectorAll('main > article.feature-story').length,
                    })"""
                )
                if (
                    desktop["rootWidth"] > desktop["viewport"] + 2
                    or desktop["bodyWidth"] > desktop["viewport"] + 2
                    or desktop["storyCount"] != 5
                ):
                    raise QaFailure(
                        "데스크톱 포트폴리오 레이아웃에 가로 넘침 또는 장면 누락이 있습니다.",
                        desktop,
                    )
                return {
                    **shell,
                    "feature_ids": actual_ids,
                    "assets": actual_assets,
                    "mobile_image_sizes": [
                        [item["width"], item["height"]] for item in image_contract
                    ],
                    "desktop": desktop,
                    "lightbox_focus_returned": True,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-016",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=portfolio_production_screens_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def staging_gpt_detail_copy_case(page: Any, theme: str) -> dict[str, Any]:
                signal = {
                    "data_state": "ready",
                    "as_of": "2026-08-31T16:00:00+09:00",
                    "current": {
                        "action": "entry_pending",
                        "label": "매수 조건 확정",
                        "score": 89.19,
                        "price": 173300,
                        "position_open": False,
                        "live_observation": False,
                        "as_of": "2026-08-31T16:00:00+09:00",
                        "entry_confirmation": {
                            "allowed": True,
                            "state": "approved",
                            "required_supports": 1,
                            "supportive_count": 2,
                            "reason": "독립 우호 근거 2개 확인",
                        },
                        "levels": [
                            {
                                "key": "entry",
                                "label": "진입 확인선",
                                "price": 176900,
                                "condition": "장 마감 가격 조건 충족",
                            }
                        ],
                        "next_confirmation": "다음 거래일 시가의 갭 범위를 확인합니다.",
                        "lifecycle": {"latest_transition": {}},
                    },
                    "history": [],
                }
                item = {
                    "code": "105560",
                    "name": "KB금융",
                    "rank": 1,
                    "score": 69.01,
                    "price": 173300,
                    "condition_price": 173300,
                    "change_rate": 0.64,
                    "one_month_return": 11.17,
                    "three_month_return": 26.55,
                    "action": "신규 매수 대기",
                    "recommendation_state": "entry_confirmed",
                    "recommendation_label": "신규 매수 대기",
                    "buy_condition_met": True,
                    "buy_condition_as_of": "2026-08-31T15:40:00+09:00",
                    "decision_reason": "추천 기준과 가격 조건, 서로 다른 확인 자료를 모두 통과해 신규 매수를 기다리는 단계입니다.",
                    "reasons": ["차트 점수 88점", "3개월 흐름 +26.55%"],
                    "risks": ["현재 가격 변동성을 확인해야 합니다."],
                    "recommended_at": "2026-08-31T16:00:00+09:00",
                    "chart_analysis": {
                        "score": 88,
                        "trend": "상승 추세",
                        "support": 178400,
                        "resistance": 182000,
                    },
                    "ai_trade_signal": signal,
                }
                page.route_web_socket(
                    "**/ws/quotes",
                    lambda socket: socket.on_message(lambda _message: None),
                )
                page.route(
                    "**/stocks/quotes*",
                    lambda route: route.fulfill(
                        json={
                            "type": "quotes",
                            "as_of": "2026-08-31T16:00:00+09:00",
                            "items": [],
                            "rejected_codes": [],
                        }
                    ),
                )
                page.route(
                    "**/stocks/105560/quote*",
                    lambda route: route.abort(),
                )
                page.add_init_script(
                    "if (!sessionStorage.getItem('recommendation-detail-v1')) {"
                    "sessionStorage.setItem('recommendation-detail-v1', JSON.stringify("
                    + json.dumps(item, ensure_ascii=False)
                    + "));}"
                )
                page.route(
                    "**/stocks/105560/ai-analysis*",
                    lambda route: route.fulfill(
                        json={
                            "generation_mode": "rules",
                            "summary": item["decision_reason"],
                            "generation_note": "점수와 가격 기준은 데이터 규칙으로 계산합니다.",
                        }
                    ),
                )
                page.route(
                    "**/stocks/105560/quant-signals*",
                    lambda route: route.fulfill(json=signal),
                )

                summary_requests: list[dict[str, Any]] = []

                def fulfill_summary(route: Any) -> None:
                    request_payload = route.request.post_data_json
                    summary_requests.append(request_payload)
                    customer_state = request_payload.get("facts", {}).get("customer_state")
                    holding = customer_state in {"hold", "partial-hold"}
                    route.fulfill(
                        json={
                            "headline": (
                                "KB금융, 현재 AI 판단은 보유 유지예요"
                                if holding
                                else "KB금융, 신규 매수 대기 상태예요"
                            ),
                            "summary": (
                                "추천 기준을 통과한 뒤 이미 보유 중인 상태예요."
                                if holding
                                else "추천 기준은 통과했지만 아직 매수 전이에요."
                            ),
                            "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료 2개가 기준을 통과했어요.",
                            "action_title": (
                                "지금은 추가 매수보다 보유 기준을 확인할 때예요"
                                if holding
                                else "지금은 새로 살 가격이 기준 안인지 확인할 때예요"
                            ),
                            "next_check": (
                                "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요."
                                if holding
                                else "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요."
                            ),
                            "evidence_refs": ["buy-condition", "recommendation-score"],
                            "generation_mode": "openai",
                            "model_name": "gpt-4o-mini-2024-07-18",
                            "generation_note": "표시 문장만 쉽게 풀었으며 판단 값은 변경하지 않았습니다.",
                            "prompt_version": "staging-page-summary-v11",
                            "cache_hit": False,
                            "input_tokens": 1000,
                            "output_tokens": 100,
                            "total_tokens": 1100,
                            "estimated_cost_usd": 0.00021,
                        }
                    )

                page.route("**/staging-ai/page-summary", fulfill_summary)
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="recommend-detail",
                        code="105560",
                        theme=theme,
                        qa_gpt=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                    ready_selector="body[data-view='recommend-detail']",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.wait_for_selector(
                    "#recommend-detail-content[data-summary-mode='openai']",
                    timeout=int(timeout * 1000),
                )
                contract = page.evaluate(
                    """() => {
                      const content = document.querySelector('#recommend-detail-content');
                      const levels = [...content.querySelectorAll('.recommend-detail-metric')]
                        .map(row => ({
                          label: row.querySelector('span')?.textContent?.trim(),
                          value: row.querySelector('strong')?.textContent?.trim(),
                        }));
                      return {
                        view: document.body.dataset.view,
                        summaryMode: content?.dataset.summaryMode,
                        summaryDisplay: content?.dataset.summaryDisplay,
                        ariaBusy: content?.getAttribute('aria-busy'),
                        loaderDisplay: getComputedStyle(
                          content?.querySelector('[data-staging-recommend-detail-loader]')
                        ).display,
                        customerState: content?.dataset.customerState,
                        title: content?.querySelector('.staging-recommend-detail-hero h1')?.textContent?.trim(),
                        summary: content?.querySelector('.recommend-detail-verdict')?.textContent?.trim(),
                        actionTitle: content?.querySelector('.staging-recommend-detail-action > h2')?.textContent?.trim(),
                        reason: content?.querySelector('[data-staging-recommend-detail-reason]')?.textContent?.trim(),
                        nextCheck: content?.querySelector('.staging-recommend-detail-next-check strong')?.textContent?.trim(),
                        badgeCount: content?.querySelectorAll('.recommend-detail-ai-badge').length,
                        visibleModelWords: /GPT|문구 정리|데이터 요약/.test(content?.innerText || ''),
                        visibleOperatorWords: /오늘 시가 반영|시가 반영 완료|전략 반영|장 마감 매수 조건|독립 근거/.test(content?.innerText || ''),
                        scoreNow: content?.querySelector('.staging-recommend-detail-score-track')?.getAttribute('aria-valuenow'),
                        scoreLevel: content?.querySelector('.recommend-detail-score em')?.textContent?.trim(),
                        quickMetrics: [...content.querySelectorAll('.staging-recommend-detail-quick-metrics dd')]
                          .map(node => node.textContent?.trim()),
                        levels,
                        journeyStage: content?.querySelector('.staging-recommend-detail-journey .recommend-signal-stage')?.textContent?.trim(),
                        independence: content?.querySelector('.recommend-signal-independence')?.textContent?.trim(),
                        source: content?.querySelector('.recommend-detail-source')?.textContent?.trim(),
                        order: [
                          '.staging-recommend-detail-hero',
                          '.staging-recommend-detail-action',
                          '.staging-recommend-detail-levels',
                          '.staging-recommend-detail-evidence-section',
                          '.staging-recommend-detail-journey',
                        ].map(selector => content?.querySelector(selector)?.offsetTop || 0),
                        width: content?.getBoundingClientRect().width || 0,
                        scrollWidth: content?.scrollWidth || 0,
                        viewportWidth: innerWidth,
                      };
                    }"""
                )
                if (
                    contract.get("view") != "recommend-detail"
                    or contract.get("summaryMode") != "openai"
                    or contract.get("summaryDisplay") != "ready"
                    or contract.get("ariaBusy") != "false"
                    or contract.get("loaderDisplay") != "none"
                    or contract.get("customerState") != "new-buy-wait"
                    or contract.get("title") != "KB금융, 신규 매수 대기 상태예요"
                    or contract.get("summary") != "추천 기준은 통과했지만 아직 매수 전이에요."
                    or contract.get("reason") != "추천 점수와 가격 조건, 서로 다른 확인 자료 2개가 기준을 통과했어요."
                    or contract.get("actionTitle") != "지금은 새로 살 가격이 기준 안인지 확인할 때예요"
                    or contract.get("nextCheck") != "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요."
                    or contract.get("badgeCount") != 0
                    or contract.get("visibleModelWords") is not False
                    or contract.get("visibleOperatorWords") is not False
                    or contract.get("scoreNow") != "69.01"
                    or contract.get("scoreLevel") != "추천 기준 통과"
                    or contract.get("quickMetrics") != ["69점", "89점", "신규 매수 대기"]
                    or contract.get("journeyStage") != "신규 매수 대기"
                    or "지금 새로 살지·보유할지·팔지를" not in str(contract.get("independence") or "")
                    or "공개 시장 데이터를 기준" not in str(contract.get("source") or "")
                    or contract.get("order") != sorted(contract.get("order") or [])
                    or contract.get("width", 0) > contract.get("viewportWidth", 0) + 1
                    or contract.get("scrollWidth", 0) > contract.get("viewportWidth", 0) + 1
                ):
                    raise QaFailure(
                        "추천 상세에서 쉬운 설명과 고정 금융 데이터의 소유권이 분리되지 않았습니다.",
                        contract,
                    )
                level_map = {
                    str(row.get("label")): str(row.get("value"))
                    for row in contract.get("levels") or []
                }
                live_price_text = level_map.get("현재가") or ""
                if not (
                    level_map.get("추천 기준") == "통과"
                    and level_map.get("추천 당시 가격") == "173,300원"
                    and level_map.get("새로 살 기준 가격") == "176,900원"
                    and re.fullmatch(r"\d{1,3}(?:,\d{3})*원", live_price_text)
                    and level_map.get("확인한 자료") == "2개 · 기준 1개"
                    and level_map.get("지금 판단") == "신규 매수 대기"
                    and level_map.get("추가 매수") == "보유 전"
                ):
                    raise QaFailure(
                        "쉬운 설명 적용 뒤 추천 당시·신규 매수 기준 가격 또는 실시간 현재가가 누락됐습니다.",
                        {"levels": level_map},
                    )
                if (
                    len(summary_requests) != 1
                    or summary_requests[0].get("page_type") != "recommendation_detail"
                    or summary_requests[0].get("facts", {}).get("buy_condition_met") is not True
                    or summary_requests[0].get("facts", {}).get("customer_state") != "new-buy-wait"
                    or summary_requests[0].get("facts", {}).get("customer_state_label") != "신규 매수 대기"
                    or summary_requests[0].get("facts", {}).get("additional_buy_label") != "보유 전"
                    or summary_requests[0].get("facts", {}).get("current_price") != 173300
                    or set(summary_requests[0].get("fallback") or {})
                    != {"headline", "summary", "reason", "action_title", "next_check", "evidence_refs"}
                ):
                    raise QaFailure(
                        "추천 상세가 스테이징 구조화 요약 계약으로 한 번만 요청하지 않았습니다.",
                        {"requests": summary_requests},
                    )

                today_token = datetime.now(KST).date().isoformat()
                signal["current"].update(
                    {
                        "action": "entered",
                        "label": "전략상 진입 완료",
                        "score": 75.37,
                        "price": 171600,
                        "position_open": True,
                        "entry_date": today_token,
                        "entry_price": 169100,
                        "lifecycle": {
                            "latest_transition": {
                                "side": "buy",
                                "signal_date": "2026-08-31",
                                "transition_date": today_token,
                                "price": 169100,
                            }
                        },
                        "next_confirmation": "초기 위험선과 첫 수익 확인 기준을 매일 확인합니다.",
                    }
                )
                item.update(
                    {
                        "action": "보유 유지",
                        "recommendation_state": "entered_today",
                        "recommendation_label": "보유 유지",
                        "recommendation_entry_date": today_token,
                        "strategy_entry_price": 169100,
                        "price": 171600,
                        "decision_reason": "추천 기준을 통과한 뒤 AI 전략이 보유 중이며, 현재는 추가 매수보다 보유 기준을 확인하는 단계입니다.",
                        "ai_trade_signal": signal,
                    }
                )
                page.evaluate(
                    "payload => sessionStorage.setItem('recommendation-detail-v1', JSON.stringify(payload))",
                    item,
                )
                page.reload(wait_until="commit")
                page.wait_for_selector(
                    "#recommend-detail-content[data-recommendation-state='entered-today'][data-summary-mode='openai']",
                    timeout=int(timeout * 1000),
                )
                entered_today_contract = page.evaluate(
                    """() => {
                      const content = document.querySelector('#recommend-detail-content');
                      const levelRows = [...content.querySelectorAll('.staging-recommend-detail-levels .recommend-detail-metric')];
                      return {
                        state: content?.dataset.recommendationState,
                        customerState: content?.dataset.customerState,
                        title: content?.querySelector('.staging-recommend-detail-hero h1')?.textContent?.trim(),
                        summary: content?.querySelector('.recommend-detail-verdict')?.textContent?.trim(),
                        actionTitle: content?.querySelector('.staging-recommend-detail-action > h2')?.textContent?.trim(),
                        reason: content?.querySelector('[data-staging-recommend-detail-reason]')?.textContent?.trim(),
                        scoreLevel: content?.querySelector('.recommend-detail-score em')?.textContent?.trim(),
                        journeyStage: content?.querySelector('.staging-recommend-detail-journey .recommend-signal-stage')?.textContent?.trim(),
                        levels: Object.fromEntries(levelRows.map(row => [
                          row.querySelector('span')?.textContent?.trim(),
                          row.querySelector('strong')?.textContent?.trim(),
                        ])),
                      };
                    }"""
                )
                if (
                    entered_today_contract.get("state") != "entered-today"
                    or entered_today_contract.get("customerState") != "hold"
                    or entered_today_contract.get("title") != "KB금융, 현재 AI 판단은 보유 유지예요"
                    or "이미 보유 중인 상태" not in str(entered_today_contract.get("summary") or "")
                    or "추가 매수보다 보유 기준" not in str(entered_today_contract.get("actionTitle") or "")
                    or entered_today_contract.get("scoreLevel") != "추천 기준 통과"
                    or entered_today_contract.get("journeyStage") != "보유 유지"
                    or entered_today_contract.get("levels", {}).get("추천 기준") != "통과"
                    or entered_today_contract.get("levels", {}).get("추천 당시 가격") != "173,300원"
                    or entered_today_contract.get("levels", {}).get("AI 전략 매수가") != "169,100원"
                    or not re.fullmatch(
                        r"\d{1,3}(?:,\d{3})*원",
                        entered_today_contract.get("levels", {}).get("현재가") or "",
                    )
                    or entered_today_contract.get("levels", {}).get("확인한 자료") != "2개 · 기준 1개"
                    or entered_today_contract.get("levels", {}).get("지금 판단") != "보유 유지"
                    or entered_today_contract.get("levels", {}).get("추가 매수") != "신호 없음"
                    or len(summary_requests) != 2
                    or summary_requests[1].get("facts", {}).get("recommendation_state") != "entered_today"
                    or summary_requests[1].get("facts", {}).get("customer_state") != "hold"
                    or summary_requests[1].get("facts", {}).get("additional_buy_label") != "신호 없음"
                    or summary_requests[1].get("facts", {}).get("strategy_entry_price") != 169100
                    or summary_requests[1].get("facts", {}).get("condition_price") != 173300
                    or summary_requests[1].get("facts", {}).get("current_price") != 171600
                ):
                    raise QaFailure(
                        "AI 전략이 보유 중인 추천이 보유 유지와 추가 매수 신호 없음으로 이어지지 않았습니다.",
                        {"entered_today": entered_today_contract, "requests": summary_requests},
                    )

                reflow: dict[str, Any] = {}
                for label, viewport_size in (
                    ("320px", {"width": 320, "height": 740}),
                    ("200_percent_equivalent", {"width": 229, "height": 436}),
                ):
                    page.set_viewport_size(viewport_size)
                    page.wait_for_timeout(80)
                    measured = page.evaluate(
                        """() => {
                          const content = document.querySelector('#recommend-detail-content');
                          return {
                            width: content?.getBoundingClientRect().width || 0,
                            scrollWidth: content?.scrollWidth || 0,
                            rootScrollWidth: document.documentElement.scrollWidth,
                            viewportWidth: innerWidth,
                          };
                        }"""
                    )
                    reflow[label] = measured
                    if (
                        measured.get("width", 0) > measured.get("viewportWidth", 0) + 1
                        or measured.get("scrollWidth", 0) > measured.get("viewportWidth", 0) + 1
                        or measured.get("rootScrollWidth", 0) > measured.get("viewportWidth", 0) + 1
                    ):
                        raise QaFailure(
                            f"GPT 추천 상세가 {label}에서 가로로 넘칩니다.",
                            measured,
                        )

                prior_token = (datetime.now(KST).date() - timedelta(days=1)).isoformat()
                signal["current"].update(
                    {
                        "action": "holding",
                        "label": "보유 기준 확인",
                        "entry_date": prior_token,
                        "lifecycle": {
                            "latest_transition": {
                                "side": "buy",
                                "signal_date": "2026-08-30",
                                "transition_date": prior_token,
                                "price": 169100,
                            }
                        },
                    }
                )
                item.update(
                    {
                        "recommendation_entry_date": prior_token,
                        "ai_trade_signal": signal,
                    }
                )
                page.evaluate(
                    "payload => sessionStorage.setItem('recommendation-detail-v1', JSON.stringify(payload))",
                    item,
                )
                page.set_viewport_size({"width": 390, "height": 844})
                page.reload(wait_until="commit")
                page.wait_for_function(
                    """() => {
                      const content = document.querySelector('#recommend-detail-content');
                      return content?.dataset.recommendationState === 'changed'
                        && content?.dataset.summaryDisplay === 'ready'
                        && Boolean(content.querySelector('.staging-recommend-detail-hero h1')?.textContent?.trim());
                    }""",
                    timeout=int(timeout * 1000),
                )
                changed_contract = page.evaluate(
                    """() => {
                      const content = document.querySelector('#recommend-detail-content');
                      const levelRows = [...content.querySelectorAll('.staging-recommend-detail-levels .recommend-detail-metric')];
                      return {
                        state: content?.dataset.recommendationState,
                        customerState: content?.dataset.customerState,
                        title: content?.querySelector('.staging-recommend-detail-hero h1')?.textContent?.trim(),
                        summary: content?.querySelector('.recommend-detail-verdict')?.textContent?.trim(),
                        actionTitle: content?.querySelector('.staging-recommend-detail-action > h2')?.textContent?.trim(),
                        reason: content?.querySelector('[data-staging-recommend-detail-reason]')?.textContent?.trim(),
                        journeyStage: content?.querySelector('.staging-recommend-detail-journey .recommend-signal-stage')?.textContent?.trim(),
                        conditionState: levelRows.find(row => row.querySelector('span')?.textContent?.trim() === '추천 기준')
                          ?.querySelector('strong')?.textContent?.trim(),
                      };
                    }"""
                )
                if (
                    changed_contract.get("state") != "changed"
                    or changed_contract.get("customerState") != "hold"
                    or changed_contract.get("title") != "KB금융, 현재 AI 판단은 보유 유지예요"
                    or "오늘의 신규 추천 목록에는 포함되지 않아요" not in str(changed_contract.get("summary") or "")
                    or "추가 매수보다 보유 기준" not in str(changed_contract.get("actionTitle") or "")
                    or "현재는 보유 상태를 점검" not in str(changed_contract.get("reason") or "")
                    or changed_contract.get("journeyStage") != "보유 유지"
                    or changed_contract.get("conditionState") != "추천 당시 통과"
                    or len(summary_requests) != 2
                ):
                    raise QaFailure(
                        "당일이 지난 보유 상태가 신규 매수 추천으로 남아 있습니다.",
                        {"changed": changed_contract, "summary_request_count": len(summary_requests)},
                    )
                return {
                    **shell,
                    "recommendation": contract,
                    "entered_today_recommendation": entered_today_contract,
                    "changed_recommendation": changed_contract,
                    "request_page_type": summary_requests[0]["page_type"],
                    "summary_request_count": len(summary_requests),
                    "reflow": reflow,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-017",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=staging_gpt_detail_copy_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def staging_gpt_briefing_copy_case(page: Any, theme: str) -> dict[str, Any]:
                publication_date = datetime.now(KST).date().isoformat()
                previous_date = (datetime.now(KST).date() - timedelta(days=1)).isoformat()

                def briefing_fixture(
                    edition: str,
                    label: str,
                    hour: int,
                    title: str,
                    *,
                    date_value: str = publication_date,
                ) -> dict[str, Any]:
                    category_key = f"{edition}-market"
                    item_id = f"{edition}-news-1"
                    item = {
                        "id": item_id,
                        "title": title,
                        "summary": f"{title}의 공개 배경을 확인했어요.",
                        "status": "확인",
                        "why_it_matters": "시장 흐름에 영향을 줄 수 있는 공개 소식이에요.",
                        "detail_url": f"https://example.com/{edition}-news-1",
                        "category_key": category_key,
                        "category_label": "시장 흐름",
                    }
                    payload: dict[str, Any] = {
                        "title": "오늘의 돈이 되는 소식",
                        "edition": edition,
                        "edition_key": f"{date_value}:{hour:02d}",
                        "edition_label": label,
                        "publication_date": date_value,
                        "timezone": "Asia/Seoul",
                        "window_start": f"{date_value}T{max(0, hour - 3):02d}:00:00+09:00",
                        "window_end": f"{date_value}T{hour:02d}:00:00+09:00",
                        "published_at": f"{date_value}T{hour:02d}:00:00+09:00",
                        "next_publication_at": f"{date_value}T23:59:00+09:00",
                        "generated_at": f"{date_value}T{hour:02d}:00:00+09:00",
                        "total_news_count": 2,
                        "selected_news_count": 2,
                        "opportunity_count": 1,
                        "caution_count": 0,
                        "highlights": [item],
                        "categories": [
                            {
                                "key": category_key,
                                "label": "시장 흐름",
                                "icon": "📈",
                                "description": "공개 시장 소식",
                                "count": 1,
                                "items": [item],
                            }
                        ],
                        "empty_message": None,
                    }
                    if edition == "midday" and date_value == publication_date:
                        payload.update(
                            {
                                "preliminary_buys_available": True,
                                "preliminary_buys": [
                                    {
                                        "code": "111111",
                                        "name": "예비포착주",
                                        "side": "buy",
                                        "signal_date": publication_date,
                                        "first_seen_at": f"{publication_date}T09:30:00+09:00",
                                        "score": 74.2,
                                        "reason": "오전 거래대금과 추세 조건이 새로 충족됐어요.",
                                        "action": "entry_pending",
                                        "active": True,
                                    }
                                ],
                            }
                        )
                    if edition == "afternoon" and date_value == publication_date:
                        payload["confirmed_buys"] = [
                            {
                                "code": "222222",
                                "name": "확정매수주",
                                "side": "buy",
                                "signal_date": publication_date,
                                "execution_date": publication_date,
                                "score": 82.0,
                                "reason": "종가 기준 추세와 거래대금 조건을 확인했어요.",
                                "action": "holding",
                            }
                        ]
                    return payload

                latest = [
                    briefing_fixture("afternoon", "장 마감판", 16, "장 마감 뒤 환율 흐름"),
                    briefing_fixture("midday", "점심판", 12, "오전 수급 변화"),
                    briefing_fixture("morning", "아침판", 6, "밤사이 미국 시장 흐름"),
                ]
                older = briefing_fixture(
                    "morning",
                    "아침판",
                    6,
                    "어제 아침 시장 흐름",
                    date_value=previous_date,
                )
                current_hour = datetime.now(KST).hour
                if current_hour >= 16:
                    current_payload = latest[0]
                elif current_hour >= 12:
                    current_payload = latest[1]
                elif current_hour >= 6:
                    current_payload = latest[2]
                else:
                    current_payload = briefing_fixture(
                        "afternoon",
                        "장 마감판",
                        16,
                        "어제 장 마감 뒤 환율 흐름",
                        date_value=previous_date,
                    )
                briefing_requests: list[str] = []

                def fulfill_briefings(route: Any) -> None:
                    briefing_requests.append(route.request.url)
                    payload: Any = [*latest, older] if "/history" in route.request.url else current_payload
                    route.fulfill(
                        status=200,
                        content_type="application/json; charset=utf-8",
                        body=json.dumps(payload, ensure_ascii=False),
                    )

                page.route(
                    re.compile(r".*/briefings/morning-money/history(?:\?.*)?$"),
                    fulfill_briefings,
                )
                page.route(
                    re.compile(r".*/briefings/morning-money(?:\?.*)?$"),
                    fulfill_briefings,
                )
                page.route(
                    "**/market/quant-signals?*",
                    lambda route: route.fulfill(json={"status": "ready", "items": []}),
                )
                page.route(
                    "**/market/trends?*",
                    lambda route: route.fulfill(json={"events": [], "past_events": []}),
                )
                page.route(
                    "**/market/calendar?*",
                    lambda route: route.fulfill(json={"events": [], "past_events": []}),
                )

                summary_requests: list[dict[str, Any]] = []
                generated_copy = {
                    "morning": {
                        "headline": "아침 시장 핵심을 짧게 봐요",
                        "summary": "밤사이 시장 흐름을 먼저 확인해요.",
                    },
                    "midday": {
                        "headline": "점심에 볼 오전 핵심이에요",
                        "summary": "오전 수급 흐름을 짧게 정리했어요.",
                    },
                    "afternoon": {
                        "headline": "장 마감 뒤 핵심을 확인해요",
                        "summary": "마감 뒤 환율 흐름을 차분히 살펴봐요.",
                    },
                }

                def fulfill_summary(route: Any) -> None:
                    request = route.request.post_data_json
                    summary_requests.append(request)
                    if request.get("page_type") != "briefing_edition":
                        route.fulfill(status=400, json={"error": "unexpected page type"})
                        return
                    edition = str(request.get("facts", {}).get("edition") or "")
                    sources = request.get("facts", {}).get("sources") or []
                    refs = [
                        str(source.get("id"))
                        for source in sources
                        if isinstance(source, dict) and source.get("id")
                    ][:2]
                    copy = generated_copy.get(edition, generated_copy["morning"])
                    route.fulfill(
                        json={
                            **copy,
                            "reason": "제공된 공개 소식만 바탕으로 문구를 정리했어요.",
                            "action_title": f"이번 {edition} 브리핑에서 먼저 볼 내용",
                            "next_check": "원문과 최신 시세를 함께 확인해요.",
                            "evidence_refs": refs,
                            "generation_mode": "openai",
                            "model_name": "gpt-4o-mini-2024-07-18",
                            "generation_note": "GPT는 브리핑 문구만 정리했습니다.",
                            "prompt_version": "staging-page-summary-v11",
                            "cache_hit": False,
                            "input_tokens": 400,
                            "output_tokens": 80,
                            "total_tokens": 480,
                            "estimated_cost_usd": 0.000108,
                        }
                    )

                page.route("**/staging-ai/page-summary", fulfill_summary)
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="home",
                        theme=theme,
                        money_briefing_preview="1",
                        qa_gpt_briefing=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                    ready_selector="body[data-view='home']",
                )
                shell = _assert_page_shell(page, theme=theme)
                page.locator("#bottom-nav [data-app-view='news']").click()
                page.wait_for_selector('body[data-view="news"]')
                page.wait_for_selector(".staging-feed-modes", state="visible")
                page.locator('[data-staging-feed-mode="content"]').click()
                page.wait_for_function(
                    """() => document.querySelectorAll(
                      '.staging-editorial-post[data-summary-mode="openai"]'
                    ).length === 3""",
                    timeout=int(timeout * 1000),
                )
                page.wait_for_timeout(120)

                feed_contract = page.evaluate(
                    """() => ({
                      cards: [...document.querySelectorAll('.staging-editorial-post')].map(card => ({
                        edition: card.dataset.stagingEdition,
                        summaryMode: card.dataset.summaryMode || '',
                        title: card.querySelector('h3')?.textContent?.trim(),
                        summary: card.querySelector('.staging-editorial-summary')?.textContent?.trim(),
                        badge: card.querySelector('[data-staging-briefing-summary-provenance]')?.textContent?.trim(),
                        badgeMode: card.querySelector('[data-staging-briefing-summary-provenance]')?.dataset.summaryMode,
                        footer: card.querySelector('footer')?.textContent?.replace(/\s+/g, ' ').trim(),
                      })),
                      preliminaryCodes: [...document.querySelectorAll('[data-staging-preliminary-buy-code]')]
                        .map(node => node.dataset.stagingPreliminaryBuyCode),
                      confirmedCodes: [...document.querySelectorAll('[data-staging-confirmed-buy-code]')]
                        .map(node => node.dataset.stagingConfirmedBuyCode),
                      rootScrollWidth: document.documentElement.scrollWidth,
                      viewportWidth: innerWidth,
                    })"""
                )
                latest_cards = {
                    str(card.get("edition")): card
                    for card in feed_contract.get("cards") or []
                    if str(card.get("edition", "")).startswith(publication_date)
                }
                expected_titles = {
                    f"{publication_date}:06": generated_copy["morning"]["headline"],
                    f"{publication_date}:12": generated_copy["midday"]["headline"],
                    f"{publication_date}:16": generated_copy["afternoon"]["headline"],
                }
                old_card = next(
                    (
                        card
                        for card in feed_contract.get("cards") or []
                        if card.get("edition") == f"{previous_date}:06"
                    ),
                    {},
                )
                if (
                    set(latest_cards) != set(expected_titles)
                    or any(
                        latest_cards[key].get("title") != title
                        or latest_cards[key].get("summaryMode") != "openai"
                        or latest_cards[key].get("badge") != "GPT 문구 정리"
                        or latest_cards[key].get("badgeMode") != "openai"
                        or "핵심 소식 2건 전체 읽기" not in str(latest_cards[key].get("footer") or "")
                        for key, title in expected_titles.items()
                    )
                    or old_card.get("title") != "밤사이 핵심만 빠르게"
                    or old_card.get("badge") != "열면 GPT 정리"
                    or old_card.get("badgeMode") != "deferred"
                    or feed_contract.get("preliminaryCodes") != ["111111"]
                    or feed_contract.get("confirmedCodes") != ["222222"]
                    or feed_contract.get("rootScrollWidth", 0) > feed_contract.get("viewportWidth", 0) + 1
                ):
                    raise QaFailure(
                        "세 브리핑의 GPT 문구, 과거 판 지연 생성 또는 고정 시그널 계약이 다릅니다.",
                        feed_contract,
                    )
                request_editions = [
                    request.get("facts", {}).get("edition") for request in summary_requests
                ]
                if len(summary_requests) != 3 or set(request_editions) != {
                    "morning",
                    "midday",
                    "afternoon",
                }:
                    raise QaFailure(
                        "최신 발행일 브리핑이 최대 세 번의 구조화 요약으로 제한되지 않았습니다.",
                        {"request_editions": request_editions, "requests": summary_requests},
                    )

                midday_key = f"{publication_date}:12"
                page.locator(
                    f'[data-staging-edition="{midday_key}"] [data-staging-content-open]'
                ).click()
                page.wait_for_selector('body[data-view="morning-briefing"]')
                page.wait_for_selector(
                    '#morning-money-briefing-view[data-summary-mode="openai"]',
                    timeout=int(timeout * 1000),
                )
                page.wait_for_timeout(120)
                detail_contract = page.evaluate(
                    """() => {
                      const view = document.querySelector('#morning-money-briefing-view');
                      return {
                        title: view?.querySelector('#morning-money-overview-title')?.textContent?.trim(),
                        intro: view?.querySelector('#morning-money-overview-intro')?.textContent?.trim(),
                        digestTitle: view?.querySelector('#morning-money-digest-title')?.textContent?.trim(),
                        nextCheck: view?.querySelector('.staging-briefing-ai-next strong')?.textContent?.trim(),
                        badge: view?.querySelector('[data-staging-briefing-summary-provenance]')?.textContent?.trim(),
                        meta: view?.querySelector('.staging-article-meta')?.textContent?.trim(),
                        editionTitle: view?.querySelector('.morning-money-command-title h1')?.textContent?.trim(),
                        categoryTitles: [...view.querySelectorAll('.morning-money-category-head h2')]
                          .map(node => node.textContent?.trim()),
                        newsTitles: [...view.querySelectorAll('.morning-money-news-title')]
                          .map(node => node.textContent?.trim()),
                        sourceLinks: [...view.querySelectorAll('.morning-money-news-title a')]
                          .map(node => node.getAttribute('href')),
                        preliminaryCodes: [...view.querySelectorAll('.staging-article-preliminary-buy')]
                          .map(node => node.getAttribute('href')?.split('/').pop()),
                        contentText: view?.querySelector('#morning-money-briefing-content')?.textContent
                          ?.replace(/\s+/g, ' ').trim(),
                        errorText: view?.querySelector('.morning-money-error-state')?.textContent
                          ?.replace(/\s+/g, ' ').trim(),
                        rootScrollWidth: document.documentElement.scrollWidth,
                        viewportWidth: innerWidth,
                      };
                    }"""
                )
                if (
                    len(summary_requests) != 3
                    or detail_contract.get("title") != generated_copy["midday"]["headline"]
                    or detail_contract.get("intro") != generated_copy["midday"]["summary"]
                    or detail_contract.get("digestTitle") != "이번 midday 브리핑에서 먼저 볼 내용"
                    or detail_contract.get("nextCheck") != "원문과 최신 시세를 함께 확인해요."
                    or detail_contract.get("badge") != "GPT 문구 정리"
                    or detail_contract.get("editionTitle") != "점심에 보는 돈이 되는 소식"
                    or "핵심 소식 2건" not in str(detail_contract.get("meta") or "")
                    or detail_contract.get("categoryTitles") != ["시장 흐름"]
                    or detail_contract.get("newsTitles") != ["오전 수급 변화"]
                    or detail_contract.get("sourceLinks") != ["https://example.com/midday-news-1"]
                    or detail_contract.get("preliminaryCodes") != ["111111"]
                    or detail_contract.get("rootScrollWidth", 0) > detail_contract.get("viewportWidth", 0) + 1
                ):
                    raise QaFailure(
                        "브리핑 상세가 캐시된 GPT 문구와 원문 뉴스·시그널을 함께 보존하지 않았습니다.",
                        {
                            "detail": detail_contract,
                            "request_count": len(summary_requests),
                            "briefing_requests": briefing_requests,
                        },
                    )

                reflow: dict[str, Any] = {}
                for label, viewport_size in (
                    ("320px", {"width": 320, "height": 740}),
                    ("200_percent_equivalent", {"width": 229, "height": 436}),
                ):
                    page.set_viewport_size(viewport_size)
                    page.wait_for_timeout(80)
                    measured = page.evaluate(
                        """() => ({
                          rootScrollWidth: document.documentElement.scrollWidth,
                          viewScrollWidth: document.querySelector('#morning-money-briefing-view')?.scrollWidth || 0,
                          viewportWidth: innerWidth,
                        })"""
                    )
                    reflow[label] = measured
                    if (
                        measured.get("rootScrollWidth", 0) > measured.get("viewportWidth", 0) + 1
                        or measured.get("viewScrollWidth", 0) > measured.get("viewportWidth", 0) + 1
                    ):
                        raise QaFailure(f"GPT 브리핑 상세가 {label}에서 가로로 넘칩니다.", measured)
                return {
                    **shell,
                    "briefing_requests": briefing_requests,
                    "request_editions": request_editions,
                    "feed": feed_contract,
                    "detail": detail_contract,
                    "reflow": reflow,
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-018",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=staging_gpt_briefing_copy_case,
                    storage_state=storage_state,
                    share_id=share_id,
                )
            )

            def service_update_case(page: Any, theme: str) -> dict[str, Any]:
                page.add_init_script(
                    """
                    for (const key of Object.keys(localStorage)) {
                      if (
                        key.startsWith('analyst.recommendationPushPromptDecision.v1')
                        || key.startsWith('analyst.pushEntryPromptSnoozedDate')
                      ) localStorage.removeItem(key);
                    }
                    """
                )
                _navigate_page(
                    page,
                    _page_url(
                        base_url,
                        "/dashboard",
                        view="search",
                        theme=theme,
                        qa_update=datetime.now(KST).strftime("%H%M%S"),
                    ),
                    wait_until="commit",
                    ready_selector="body[data-view='search']",
                )
                shell = _assert_page_shell(page, theme=theme)
                dialog = page.locator("#staging-service-update-dialog")
                dialog.wait_for(state="visible", timeout=5_000)
                card = dialog.locator(".staging-service-update-card")
                bounds = None
                for _attempt in range(3):
                    card.wait_for(state="visible", timeout=int(timeout * 1000))
                    page.wait_for_timeout(300)
                    bounds = card.bounding_box()
                    if bounds:
                        break
                if not bounds:
                    raise QaFailure("서비스 업데이트 팝업 크기를 측정하지 못했습니다.")
                viewport = page.viewport_size or MOBILE_VIEWPORT
                card_center_x = bounds["x"] + bounds["width"] / 2
                card_bottom_gap = viewport["height"] - (bounds["y"] + bounds["height"])
                if bounds["width"] < viewport["width"] - 2:
                    raise QaFailure(
                        "서비스 업데이트 하단 시트가 모바일 화면 폭을 채우지 않습니다.",
                        {"bounds": bounds, "viewport": viewport},
                    )
                if (
                    abs(card_center_x - viewport["width"] / 2) > 4
                    or abs(card_bottom_gap) > 4
                ):
                    raise QaFailure(
                        "서비스 업데이트 안내가 화면 하단에 안정적으로 정렬되지 않았습니다.",
                        {"bounds": bounds, "viewport": viewport},
                    )
                if (
                    card.get_attribute("role") != "dialog"
                    or card.get_attribute("aria-modal") != "true"
                ):
                    raise QaFailure(
                        "서비스 업데이트 팝업의 대화상자 접근성 계약이 누락됐습니다."
                    )
                popup_text = re.sub(r"\s+", " ", card.inner_text()).strip()
                for label in (
                    "비밀노트가 새로워졌어요",
                    "차트 분석",
                    "AI 신호 근거",
                    "하루 3번 브리핑",
                    "다시 보지 않기",
                    "닫기",
                ):
                    if label not in popup_text:
                        raise QaFailure(
                            "서비스 업데이트 핵심 문구가 누락됐습니다.",
                            {"label": label},
                        )

                publishing_window = page.evaluate(
                    """() => ({
                      release: window.secretNoteServiceUpdateGate?.release,
                      startsAt: window.secretNoteServiceUpdateGate?.startsAt,
                      endsAt: window.secretNoteServiceUpdateGate?.endsAt,
                      isPublishing: window.secretNoteServiceUpdateGate?.isPublishing?.(),
                      blocksNotificationPrompt: window.secretNoteServiceUpdateGate?.blocksNotificationPrompt?.(),
                    })"""
                )
                if publishing_window != {
                    "release": "20260829-chart-analysis-v1",
                    "startsAt": "2026-08-29T00:00:00+09:00",
                    "endsAt": "2026-09-05T00:00:00+09:00",
                    "isPublishing": True,
                    "blocksNotificationPrompt": True,
                }:
                    raise QaFailure(
                        "서비스 업데이트 7일 게시 기간 또는 알림 우선순위 계약이 다릅니다.",
                        publishing_window,
                    )

                push_sheet = page.locator("#push-notification-sheet")
                if push_sheet.is_visible():
                    raise QaFailure("업데이트 안내보다 알림 동의 팝업이 먼저 표시됐습니다.")
                if page.locator("#login-gate").is_visible():
                    raise QaFailure("서비스 업데이트 안내가 로그인 게이트 위에 중첩됐습니다.")
                if page.locator("body[data-view='search']").count() != 1:
                    raise QaFailure(
                        "비홈 최초 진입에서 서비스 업데이트 안내를 검증하지 못했습니다.",
                        {"url": page.url},
                    )
                dialog.locator("[data-service-update-close]").click()
                dialog.wait_for(state="hidden")
                page.wait_for_timeout(700)
                if push_sheet.is_visible():
                    raise QaFailure("업데이트 안내를 닫은 직후 알림 동의 팝업이 표시됐습니다.")

                page.locator("#bottom-nav [data-app-view='home']").click()
                page.wait_for_selector("body[data-view='home']")
                push_sheet.wait_for(
                    state="visible",
                    timeout=int(timeout * 1000),
                )
                push_mode = push_sheet.get_attribute("data-mode")
                if push_mode not in {"entry", "recommendation-entry"}:
                    raise QaFailure(
                        "다음 홈 진입에서 알림 동의 안내가 올바른 모드로 열리지 않았습니다.",
                        {"mode": push_mode},
                    )
                push_sheet.locator("#push-notification-sheet-close").click()
                push_sheet.wait_for(state="hidden")

                page.evaluate(
                    "sessionStorage.removeItem('secret-note-service-update-session:20260829-chart-analysis-v1')"
                )
                _navigate_page(page, ready_selector="body[data-view='home']")
                _assert_page_shell(page, theme=theme)
                dialog.wait_for(state="visible", timeout=5_000)

                dialog.locator("[data-service-update-detail]").click()
                intro = page.locator("#staging-service-update-page")
                intro.wait_for(state="visible")
                intro_text = re.sub(r"\s+", " ", intro.inner_text()).strip()
                if "view=service-update" not in page.url:
                    raise QaFailure(
                        "자세히 보기가 서비스 업데이트 소개 경로로 연결되지 않았습니다.",
                        {"url": page.url},
                    )
                for label in (
                    "차트 분석 페이지가 추가됐어요",
                    "AI 매매 신호를 더 쉽게 읽을 수 있어요",
                    "돈이 되는 소식이 시간대별로 나뉘었어요",
                    "종목 상세와 홈의 정보 구조를 다듬었어요",
                ):
                    if label not in intro_text:
                        raise QaFailure(
                            "서비스 업데이트 소개 내용이 누락됐습니다.",
                            {"label": label},
                        )

                intro.locator("[data-service-update-home]").evaluate(
                    "button => button.click()"
                )
                page.wait_for_function(
                    """() => (
                      new URL(window.location.href).searchParams.get('view') === 'home'
                      && document.querySelector('#staging-service-update-page')?.hidden === true
                    )""",
                    timeout=int(timeout * 1000),
                )
                page.evaluate("""() => {
                  localStorage.removeItem('secret-note-service-update-dismissed:20260829-chart-analysis-v1');
                  sessionStorage.removeItem('secret-note-service-update-session:20260829-chart-analysis-v1');
                }""")
                _navigate_page(page, ready_selector="body[data-view='home']")
                _assert_page_shell(page, theme=theme)
                dialog.wait_for(state="visible", timeout=5_000)
                dialog.locator("[data-service-update-dismiss]").click()
                dialog.wait_for(state="hidden")
                _navigate_page(page, ready_selector="body[data-view='home']")
                _assert_page_shell(page, theme=theme)
                page.wait_for_timeout(900)
                if dialog.is_visible():
                    raise QaFailure(
                        "다시 보지 않기 이후 동일 업데이트 팝업이 재노출됐습니다."
                    )
                dismissed = page.evaluate(
                    "localStorage.getItem('secret-note-service-update-dismissed:20260829-chart-analysis-v1')"
                )
                if dismissed != "1":
                    raise QaFailure(
                        "다시 보지 않기 상태가 업데이트 버전 키로 저장되지 않았습니다."
                    )
                return {
                    **shell,
                    "popup_bounds": bounds,
                    "popup_bottom_gap": round(card_bottom_gap, 3),
                    "publishing_window": publishing_window,
                    "initial_entry_view": "search",
                    "push_prompt_on_next_home": push_mode,
                    "intro_route": "service-update",
                    "dismissed_version": "20260829-chart-analysis-v1",
                }

            results.append(
                _run_page_case(
                    browser=browser,
                    catalog_by_id=catalog_by_id,
                    case_id="SIG-UI-005",
                    base_url=base_url,
                    timeout=timeout,
                    artifact_dir=output_dir,
                    callback=service_update_case,
                    storage_state=storage_state,
                    share_id=share_id,
                    dismiss_service_update=False,
                )
            )
        finally:
            browser.close()
    return results
