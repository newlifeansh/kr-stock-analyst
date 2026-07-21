from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Callable, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
FRED_SERIES_URL = "https://fred.stlouisfed.org/series/{series_id}"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{symbol}"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_TIMEOUT_SECONDS = 4
KST = ZoneInfo("Asia/Seoul")
YAHOO_FALLBACKS = {
    "DGS10": "^TNX",
    "DEXKOUS": "USDKRW=X",
    "DTWEXBGS": "DX-Y.NYB",
    "VIXCLS": "^VIX",
    "DCOILWTICO": "CL=F",
    "PCOPPUSDM": "HG=F",
    "NASDAQCOM": "^IXIC",
    "CBBTCUSD": "BTC-USD",
}


@dataclass(frozen=True)
class SeriesPoint:
    date: str
    value: float


def _round_decimal(value: float | int | None, digits: int = 2) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(round(float(value), digits)))


def _pct_change(current: Optional[float], base: Optional[float]) -> Optional[float]:
    if current is None or base in (None, 0):
        return None
    return ((current / float(base)) - 1) * 100


def _signed(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}{suffix}"


def _value_text(value: Optional[float], unit: str = "") -> str:
    if value is None:
        return "-"
    if unit == "%":
        return f"{value:.2f}%"
    if unit == "bp":
        return f"{value:.0f}bp"
    if abs(value) >= 1000:
        return f"{value:,.1f}{unit}"
    return f"{value:.2f}{unit}"


def _fetch_fred_series(series_id: str, *, limit: int = 260) -> list[SeriesPoint]:
    response = requests.get(
        FRED_CSV_URL.format(series_id=series_id),
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    reader = csv.DictReader(StringIO(response.text))
    points: list[SeriesPoint] = []
    for row in reader:
        raw_value = row.get(series_id)
        date = row.get("observation_date")
        if not raw_value or raw_value == "." or not date:
            continue
        try:
            points.append(SeriesPoint(date=date, value=float(raw_value)))
        except ValueError:
            continue
    return points[-limit:]


def _fetch_yahoo_series(symbol: str, *, limit: int = 260) -> list[SeriesPoint]:
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=quote(symbol, safe="")),
        params={"range": "2y", "interval": "1d"},
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return []
    timestamps = result.get("timestamp") or []
    quote_rows = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    closes = quote_rows.get("close") or []
    points: list[SeriesPoint] = []
    for timestamp, close in zip(timestamps, closes):
        if timestamp is None or close in (None, ""):
            continue
        try:
            points.append(
                SeriesPoint(
                    date=datetime.fromtimestamp(int(timestamp), tz=KST).date().isoformat(),
                    value=float(close),
                )
            )
        except (TypeError, ValueError, OSError):
            continue
    return points[-limit:]


def _resolve_series(series_id: str, *, limit: int = 260) -> tuple[list[SeriesPoint], str, str]:
    try:
        points = _fetch_fred_series(series_id, limit=limit)
        if points:
            return points, "FRED", FRED_SERIES_URL.format(series_id=series_id)
    except Exception:
        pass

    symbol = YAHOO_FALLBACKS.get(series_id)
    if not symbol:
        return [], "FRED", FRED_SERIES_URL.format(series_id=series_id)

    points = _fetch_yahoo_series(symbol, limit=limit)
    return points, "Yahoo Finance", YAHOO_QUOTE_URL.format(symbol=quote(symbol, safe=""))


def _series_snapshot(
    series_id: str,
    metric: str,
    *,
    unit: str = "",
    change_kind: str = "pct",
) -> tuple[Optional[dict[str, object]], Optional[list[SeriesPoint]]]:
    points, source, source_url = _resolve_series(series_id)
    if not points:
        return None, points
    latest = points[-1]
    prev = points[-2] if len(points) >= 2 else None
    prev5 = points[-6] if len(points) >= 6 else points[0]
    if change_kind == "bp":
        change_1d = (latest.value - prev.value) * 100 if prev else None
        change_5d = (latest.value - prev5.value) * 100 if prev5 else None
        change_suffix = "bp"
    else:
        change_1d = _pct_change(latest.value, prev.value if prev else None)
        change_5d = _pct_change(latest.value, prev5.value if prev5 else None)
        change_suffix = "%"
    evidence = {
        "source": source,
        "metric": metric,
        "value": _round_decimal(latest.value),
        "value_text": _value_text(latest.value, unit),
        "change_1d": _round_decimal(change_1d),
        "change_1d_text": _signed(change_1d, change_suffix),
        "change_5d": _round_decimal(change_5d),
        "change_5d_text": _signed(change_5d, change_suffix),
        "as_of": latest.date,
        "url": source_url,
    }
    return evidence, points


def _series_snapshots(
    specs: list[tuple[str, str, str, str, str]],
) -> dict[str, tuple[Optional[dict[str, object]], Optional[list[SeriesPoint]]]]:
    def load(spec: tuple[str, str, str, str, str]) -> tuple[str, tuple[Optional[dict[str, object]], Optional[list[SeriesPoint]]]]:
        key, series_id, metric, unit, change_kind = spec
        return key, _series_snapshot(series_id, metric, unit=unit, change_kind=change_kind)

    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        results = list(executor.map(load, specs))
    return dict(results)


def _latest(points: Optional[list[SeriesPoint]]) -> Optional[float]:
    return points[-1].value if points else None


def _change_5d(points: Optional[list[SeriesPoint]], *, kind: str = "pct") -> Optional[float]:
    if not points:
        return None
    latest = points[-1].value
    prev5 = points[-6].value if len(points) >= 6 else points[0].value
    if kind == "bp":
        return (latest - prev5) * 100
    return _pct_change(latest, prev5)


def _change_1d(points: Optional[list[SeriesPoint]], *, kind: str = "pct") -> Optional[float]:
    if not points or len(points) < 2:
        return None
    latest = points[-1].value
    prev = points[-2].value
    if kind == "bp":
        return (latest - prev) * 100
    return _pct_change(latest, prev)


def _factor(
    *,
    key: str,
    label: str,
    direction: str,
    raw: float,
    confidence: float,
    interpretation: str,
    evidence: list[dict[str, object]],
    affected_sectors: list[str],
    leader_stocks: list[str],
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "percent": Decimal("0"),
        "direction": direction,
        "raw": max(raw, 3),
        "confidence": _round_decimal(max(20, min(95, confidence)), 1) or Decimal("20"),
        "interpretation": interpretation,
        "evidence": evidence,
        "affected_sectors": affected_sectors,
        "leader_stocks": leader_stocks,
    }


def _fallback_factor(key: str, label: str, affected_sectors: list[str], leader_stocks: list[str]) -> dict[str, object]:
    return _factor(
        key=key,
        label=label,
        direction="악재",
        raw=3,
        confidence=20,
        interpretation="공식 지표를 일부 가져오지 못해 보수적으로 리스크 기준으로 표시합니다.",
        evidence=[
            {
                "source": "시스템",
                "metric": "데이터 수집 상태",
                "value_text": "수집 실패",
                "change_1d_text": "-",
                "change_5d_text": "-",
                "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "url": "https://fred.stlouisfed.org/",
            }
        ],
        affected_sectors=affected_sectors,
        leader_stocks=leader_stocks,
    )


def _safe_build(builder: Callable[[], dict[str, object]], fallback: dict[str, object]) -> dict[str, object]:
    try:
        return builder()
    except Exception:
        return fallback


def _build_factors() -> list[dict[str, object]]:
    jobs = [
        (
            _build_rate_factor,
            _fallback_factor("rate", "금리", ["인터넷", "바이오", "은행/보험"], ["NAVER", "KB금융"]),
        ),
        (
            _build_dollar_factor,
            _fallback_factor("dollar", "달러", ["반도체", "자동차", "항공"], ["삼성전자", "현대차"]),
        ),
        (
            _build_bond_factor,
            _fallback_factor("bond", "채권", ["금융", "건설", "리츠"], ["KB금융", "삼성생명"]),
        ),
        (
            _build_commodity_factor,
            _fallback_factor("commodity", "원자재", ["정유", "화학", "항공"], ["S-Oil", "LG화학"]),
        ),
        (
            _build_risk_factor,
            _fallback_factor("risk", "위험자산", ["반도체", "인터넷", "AI"], ["SK하이닉스", "NAVER"]),
        ),
    ]
    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
        futures = [executor.submit(_safe_build, builder, fallback) for builder, fallback in jobs]
        return [future.result() for future in futures]


def _build_rate_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("dgs10", "DGS10", "미국 10년물 국채금리", "%", "bp"),
            ("real10", "DFII10", "미국 10년 실질금리", "%", "bp"),
        ]
    )
    dgs10, dgs10_points = snapshots["dgs10"]
    real10, real10_points = snapshots["real10"]
    dgs10_5d = _change_5d(dgs10_points, kind="bp") or 0
    real10_5d = _change_5d(real10_points, kind="bp") or 0
    latest_rate = _latest(dgs10_points) or 0
    pressure = dgs10_5d + (real10_5d * 0.8) + (12 if latest_rate >= 4.5 else 0)
    direction = "악재" if pressure >= 0 else "호재"
    raw = abs(pressure) / 2.4 + 8
    interpretation = (
        "금리와 실질금리가 올라 주식 밸류에이션 부담이 커지는 구간입니다."
        if direction == "악재"
        else "금리 부담이 낮아져 성장주와 고PER 종목의 할인율 부담이 완화되는 구간입니다."
    )
    return _factor(
        key="rate",
        label="금리",
        direction=direction,
        raw=raw,
        confidence=82 if dgs10 and real10 else 58,
        interpretation=interpretation,
        evidence=[item for item in [dgs10, real10] if item],
        affected_sectors=["인터넷", "바이오", "2차전지", "은행/보험"],
        leader_stocks=["NAVER", "카카오", "삼성바이오로직스", "KB금융"],
    )


def _build_dollar_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("usdk", "DEXKOUS", "원/달러 환율", "원", "pct"),
            ("broad", "DTWEXBGS", "광의 달러지수", "", "pct"),
        ]
    )
    usdk, usdk_points = snapshots["usdk"]
    broad, broad_points = snapshots["broad"]
    usdk_5d = _change_5d(usdk_points) or 0
    broad_5d = _change_5d(broad_points) or 0
    pressure = usdk_5d + (broad_5d * 0.7)
    direction = "악재" if pressure >= 0 else "호재"
    raw = abs(pressure) * 4.8 + 8
    interpretation = (
        "달러 강세와 원화 약세는 외국인 수급과 수입물가에 부담입니다."
        if direction == "악재"
        else "달러 약세와 원화 안정은 외국인 수급과 대형주 심리에 우호적입니다."
    )
    return _factor(
        key="dollar",
        label="달러",
        direction=direction,
        raw=raw,
        confidence=82 if usdk and broad else 58,
        interpretation=interpretation,
        evidence=[item for item in [usdk, broad] if item],
        affected_sectors=["반도체", "자동차", "항공", "수입소비재"],
        leader_stocks=["삼성전자", "SK하이닉스", "현대차", "대한항공"],
    )


def _build_bond_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("curve", "T10Y2Y", "미국 10년-2년 금리차", "%p", "bp"),
            ("dgs10", "DGS10", "미국 10년물 국채금리", "%", "bp"),
            ("vix", "VIXCLS", "VIX 변동성 지수", "", "pct"),
        ]
    )
    curve, curve_points = snapshots["curve"]
    dgs10, dgs10_points = snapshots["dgs10"]
    vix, vix_points = snapshots["vix"]
    curve_latest = _latest(curve_points) or 0
    dgs10_5d = _change_5d(dgs10_points, kind="bp") or 0
    vix_5d = _change_5d(vix_points) or 0
    risk_pressure = (8 if curve_latest < 0 else -3) + (dgs10_5d / 6) + max(vix_5d, 0) * 0.35
    direction = "악재" if risk_pressure >= 0 else "호재"
    raw = abs(risk_pressure) * 2.2 + 6
    interpretation = (
        "금리차와 변동성 흐름이 경기·안전자산 선호 부담을 키우는 쪽입니다."
        if direction == "악재"
        else "채권금리와 변동성이 안정되어 주식의 상대 매력이 회복되는 쪽입니다."
    )
    return _factor(
        key="bond",
        label="채권",
        direction=direction,
        raw=raw,
        confidence=86 if curve and dgs10 and vix else 62,
        interpretation=interpretation,
        evidence=[item for item in [curve, dgs10, vix] if item],
        affected_sectors=["금융", "건설", "리츠", "성장주"],
        leader_stocks=["KB금융", "삼성생명", "현대건설", "NAVER"],
    )


def _build_commodity_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("wti", "DCOILWTICO", "WTI 원유", "$", "pct"),
            ("copper", "PCOPPUSDM", "구리 월간 가격", "$", "pct"),
        ]
    )
    wti, wti_points = snapshots["wti"]
    copper, copper_points = snapshots["copper"]
    wti_5d = _change_5d(wti_points) or 0
    copper_1d = _change_1d(copper_points) or 0
    pressure = wti_5d - (copper_1d * 0.25)
    direction = "악재" if pressure >= 0 else "호재"
    raw = abs(pressure) * 4.2 + 10
    interpretation = (
        "원유 가격 상승은 물가와 비용 부담을 키워 항공·화학·운송 마진에 부담입니다."
        if direction == "악재"
        else "원유 가격 안정은 물가와 비용 부담을 낮춰 비용 민감 업종에 우호적입니다."
    )
    eia_note = {
        "source": "EIA",
        "metric": "주간 원유재고 발표",
        "value_text": "재고 이벤트 확인",
        "change_1d_text": "-",
        "change_5d_text": "-",
        "as_of": datetime.now(KST).strftime("%Y-%m-%d"),
        "url": "https://www.eia.gov/petroleum/supply/weekly/",
    }
    return _factor(
        key="commodity",
        label="원자재",
        direction=direction,
        raw=raw,
        confidence=78 if wti else 52,
        interpretation=interpretation,
        evidence=[item for item in [wti, copper, eia_note] if item],
        affected_sectors=["정유", "화학", "항공", "해운", "철강"],
        leader_stocks=["S-Oil", "LG화학", "대한항공", "POSCO홀딩스"],
    )


def _build_risk_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("nasdaq", "NASDAQCOM", "나스닥 종합", "", "pct"),
            ("btc", "CBBTCUSD", "비트코인", "", "pct"),
            ("vix", "VIXCLS", "VIX 변동성 지수", "", "pct"),
        ]
    )
    nasdaq, nasdaq_points = snapshots["nasdaq"]
    btc, btc_points = snapshots["btc"]
    vix, vix_points = snapshots["vix"]
    nasdaq_5d = _change_5d(nasdaq_points) or 0
    btc_5d = _change_5d(btc_points) or 0
    vix_5d = _change_5d(vix_points) or 0
    appetite = (nasdaq_5d * 1.2) + (btc_5d * 0.35) - (vix_5d * 0.45)
    direction = "호재" if appetite >= 0 else "악재"
    raw = abs(appetite) * 3.4 + 8
    interpretation = (
        "나스닥·비트코인 흐름과 변동성이 위험자산 선호를 지지하는 구간입니다."
        if direction == "호재"
        else "나스닥·비트코인 약세 또는 VIX 상승으로 성장주 심리가 약한 구간입니다."
    )
    return _factor(
        key="risk",
        label="위험자산",
        direction=direction,
        raw=raw,
        confidence=88 if nasdaq and btc and vix else 64,
        interpretation=interpretation,
        evidence=[item for item in [nasdaq, btc, vix] if item],
        affected_sectors=["반도체", "인터넷", "AI", "게임", "2차전지"],
        leader_stocks=["SK하이닉스", "삼성전자", "NAVER", "한미반도체"],
    )


def build_market_impact() -> dict[str, object]:
    factors = _build_factors()
    raw_values: list[float] = []
    raw_total = 0.0
    for factor in factors:
        raw = float(factor.pop("raw", 0) or 0)
        raw_values.append(raw)
        raw_total += raw
    raw_total = raw_total or 1
    for factor, raw in zip(factors, raw_values):
        percent = (raw / raw_total) * 100
        factor["percent"] = _round_decimal(max(3, percent), 1) or Decimal("3")

    factors.sort(key=lambda item: float(item.get("percent") or 0), reverse=True)
    good_weight = sum(float(item["percent"]) for item in factors if item.get("direction") == "호재")
    bad_weight = sum(float(item["percent"]) for item in factors if item.get("direction") != "호재")
    market_status = "호재 우위" if good_weight >= bad_weight else "리스크 우위"
    lead = factors[0]
    if market_status == "호재 우위":
        summary = f"{lead['label']} 영향이 가장 크고, 현재는 호재 쪽이 더 우세합니다."
    else:
        summary = f"{lead['label']} 영향이 가장 크고, 현재는 리스크 관리가 더 우선입니다."
    return {
        "as_of": datetime.now(KST),
        "market_status": market_status,
        "summary": summary,
        "good_weight": _round_decimal(good_weight, 1) or Decimal("0"),
        "bad_weight": _round_decimal(bad_weight, 1) or Decimal("0"),
        "factors": factors,
    }
