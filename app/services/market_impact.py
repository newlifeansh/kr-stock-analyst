from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
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
MIN_HISTORY_POINTS = 6
ONE_DAY_MAX_GAP_DAYS = 5
FIVE_DAY_MAX_GAP_DAYS = 12
PCT_SIGNAL_THRESHOLD = 0.15
BP_SIGNAL_THRESHOLD = 3.0
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


def _parse_point_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _point_gap_days(newer: SeriesPoint, older: SeriesPoint) -> Optional[int]:
    newer_date = _parse_point_date(newer.date)
    older_date = _parse_point_date(older.date)
    if newer_date is None or older_date is None:
        return None
    return (newer_date - older_date).days


def _change_from_points(
    points: Optional[list[SeriesPoint]],
    *,
    window: int,
    kind: str = "pct",
) -> Optional[float]:
    if not points:
        return None
    required = 2 if window == 1 else MIN_HISTORY_POINTS
    if len(points) < required:
        return None
    latest = points[-1]
    base = points[-2] if window == 1 else points[-MIN_HISTORY_POINTS]
    gap_days = _point_gap_days(latest, base)
    max_gap_days = ONE_DAY_MAX_GAP_DAYS if window == 1 else FIVE_DAY_MAX_GAP_DAYS
    # A monthly series must not be presented as a 1-day/5-day signal.
    if gap_days is None or gap_days > max_gap_days:
        return None
    if kind == "bp":
        return (latest.value - base.value) * 100
    return _pct_change(latest.value, base.value)


def _series_quality(
    points: Optional[list[SeriesPoint]],
    *,
    change_5d: Optional[float],
) -> tuple[str, str]:
    if not points:
        return "자료 부족", "관측값을 가져오지 못했습니다."
    if len(points) < MIN_HISTORY_POINTS:
        return "주의", f"관측값 {len(points)}개로 5일 변화율을 안정적으로 계산하기 어렵습니다."
    issues: list[str] = []
    latest_date = _parse_point_date(points[-1].date)
    if latest_date is not None:
        stale_days = (datetime.now(KST).date() - latest_date).days
        if stale_days > 7:
            issues.append(f"최근 관측일이 오늘보다 {stale_days}일 이전입니다.")
    if change_5d is None:
        issues.append("자료 주기가 1일·5일 비교와 맞지 않습니다.")
    if issues:
        return "주의", " · ".join(issues)
    return "확인", "최근 관측값과 1일·5일 변화율을 확인했습니다."


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
    if change_kind == "bp":
        change_1d = _change_from_points(points, window=1, kind="bp")
        change_5d = _change_from_points(points, window=5, kind="bp")
        change_suffix = "bp"
    else:
        change_1d = _change_from_points(points, window=1)
        change_5d = _change_from_points(points, window=5)
        change_suffix = "%"
    quality, quality_note = _series_quality(points, change_5d=change_5d)
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
        "data_quality": quality,
        "quality_note": quality_note,
        "observation_count": len(points),
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
    return _change_from_points(points, window=5, kind=kind)


def _change_1d(points: Optional[list[SeriesPoint]], *, kind: str = "pct") -> Optional[float]:
    return _change_from_points(points, window=1, kind=kind)


def _signal(value: Optional[float], threshold: float) -> int:
    if value is None or abs(value) < threshold:
        return 0
    return 1 if value > 0 else -1


def _factor_quality(
    snapshots: list[tuple[Optional[dict[str, object]], Optional[list[SeriesPoint]]]],
) -> tuple[str, str, float]:
    expected = len(snapshots)
    available = [(evidence, points) for evidence, points in snapshots if evidence and points]
    if not available:
        return "자료 부족", "필요한 공식 지표를 가져오지 못했습니다.", 20

    issues: list[str] = []
    if len(available) < expected:
        issues.append(f"필요 지표 {expected}개 중 {len(available)}개만 수집됨")
    for evidence, _ in available:
        quality = str(evidence.get("data_quality") or "확인")
        if quality != "확인":
            issues.append(str(evidence.get("quality_note") or quality))

    latest_dates = [
        _parse_point_date(str(evidence.get("as_of")))
        for evidence, _ in available
        if evidence.get("as_of")
    ]
    latest_dates = [value for value in latest_dates if value is not None]
    if latest_dates and (max(latest_dates) - min(latest_dates)).days > 2:
        issues.append("지표별 기준일이 2일 넘게 다릅니다")

    unique_issues = list(dict.fromkeys(issues))
    if len(available) < expected or unique_issues:
        confidence = 68 if len(available) == expected else 52
        return "주의", " · ".join(unique_issues), confidence
    return "확인", "모든 지표의 기준일과 변화율을 확인했습니다.", 88


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
    data_quality: str = "확인",
    quality_note: str = "",
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
        "data_quality": data_quality,
        "quality_note": quality_note,
    }


def _fallback_factor(key: str, label: str, affected_sectors: list[str], leader_stocks: list[str]) -> dict[str, object]:
    return _factor(
        key=key,
        label=label,
        direction="자료 부족",
        raw=3,
        confidence=20,
        interpretation="공식 지표를 가져오지 못해 방향 판단을 보류합니다.",
        evidence=[
            {
                "source": "시스템",
                "metric": "데이터 수집 상태",
                "value_text": "수집 실패",
                "change_1d_text": "-",
                "change_5d_text": "-",
                "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                "url": "https://fred.stlouisfed.org/",
                "data_quality": "자료 부족",
                "quality_note": "지표 수집 실패",
            }
        ],
        affected_sectors=affected_sectors,
        leader_stocks=leader_stocks,
        data_quality="자료 부족",
        quality_note="공식 지표 수집 실패",
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
            _fallback_factor("bond", "채권금리", ["금융", "건설", "리츠"], ["KB금융", "삼성생명"]),
        ),
        (
            _build_commodity_factor,
            _fallback_factor("commodity", "원자재", ["정유", "화학", "항공"], ["S-Oil", "LG화학"]),
        ),
        (
            _build_risk_factor,
            _fallback_factor(
                "risk",
                "투자심리",
                ["반도체", "인터넷", "AI", "게임", "2차전지"],
                ["SK하이닉스", "삼성전자", "NAVER", "한미반도체"],
            ),
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
    snapshots_for_quality = [(dgs10, dgs10_points), (real10, real10_points)]
    data_quality, quality_note, quality_confidence = _factor_quality(snapshots_for_quality)
    dgs10_5d = _change_5d(dgs10_points, kind="bp")
    real10_5d = _change_5d(real10_points, kind="bp")
    available_changes = [value for value in (dgs10_5d, real10_5d) if value is not None]
    pressure = (
        (dgs10_5d * 0.6 if dgs10_5d is not None else 0)
        + (real10_5d * 0.4 if real10_5d is not None else 0)
    )
    rate_signals = [_signal(value, BP_SIGNAL_THRESHOLD) for value in (dgs10_5d, real10_5d) if value is not None]
    mixed = len(rate_signals) == 2 and rate_signals[0] != rate_signals[1]
    if not available_changes:
        direction = "자료 부족"
    elif mixed or abs(pressure) < BP_SIGNAL_THRESHOLD:
        direction = "혼조"
    else:
        direction = "악재" if pressure > 0 else "호재"
    raw = abs(pressure) / 2.4 + 8 if available_changes else 3
    if direction == "악재":
        interpretation = "미국 명목·실질금리가 올라 예금·채권의 상대 매력이 커지고 성장주 할인율 부담이 늘어나는 흐름입니다."
    elif direction == "호재":
        interpretation = "미국 명목·실질금리가 내려 성장주와 고PER 종목의 할인율 부담이 완화되는 흐름입니다."
    elif direction == "혼조":
        interpretation = "명목금리와 실질금리 방향이 엇갈리거나 변화가 작아 금리 신호만으로 방향을 단정하기 어렵습니다."
    else:
        interpretation = "금리 자료가 부족해 성장주 영향 방향을 판단하지 않습니다."
    return _factor(
        key="rate",
        label="금리",
        direction=direction,
        raw=raw,
        confidence=quality_confidence,
        interpretation=interpretation,
        evidence=[item for item in [dgs10, real10] if item],
        affected_sectors=["인터넷", "바이오", "2차전지", "은행/보험"],
        leader_stocks=["NAVER", "카카오", "삼성바이오로직스", "KB금융"],
        data_quality=data_quality,
        quality_note=quality_note,
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
    snapshots_for_quality = [(usdk, usdk_points), (broad, broad_points)]
    data_quality, quality_note, quality_confidence = _factor_quality(snapshots_for_quality)
    usdk_5d = _change_5d(usdk_points)
    broad_5d = _change_5d(broad_points)
    available_changes = [value for value in (usdk_5d, broad_5d) if value is not None]
    pressure = (
        (usdk_5d * 0.6 if usdk_5d is not None else 0)
        + (broad_5d * 0.4 if broad_5d is not None else 0)
    )
    dollar_signals = [_signal(value, PCT_SIGNAL_THRESHOLD) for value in (usdk_5d, broad_5d) if value is not None]
    mixed = len(dollar_signals) == 2 and dollar_signals[0] != dollar_signals[1]
    if not available_changes:
        direction = "자료 부족"
    elif mixed or abs(pressure) < PCT_SIGNAL_THRESHOLD:
        direction = "혼조"
    else:
        direction = "악재" if pressure > 0 else "호재"
    raw = abs(pressure) * 4.8 + 8 if available_changes else 3
    if direction == "악재":
        interpretation = "원/달러와 광의 달러지수가 함께 올라 달러 강세·원화 약세와 외국인 수급 부담이 커지는 흐름입니다."
    elif direction == "호재":
        interpretation = "원/달러와 광의 달러지수가 함께 내려 달러 부담이 낮아지는 흐름입니다. 외국인 수급에는 우호적일 수 있습니다."
    elif direction == "혼조":
        interpretation = "원/달러와 광의 달러지수 방향이 엇갈리거나 변화가 작아 환율 신호가 혼조입니다."
    else:
        interpretation = "환율 자료가 부족해 달러 방향을 판단하지 않습니다."
    return _factor(
        key="dollar",
        label="달러",
        direction=direction,
        raw=raw,
        confidence=quality_confidence,
        interpretation=interpretation,
        evidence=[item for item in [usdk, broad] if item],
        affected_sectors=["반도체", "자동차", "항공", "수입소비재"],
        leader_stocks=["삼성전자", "SK하이닉스", "현대차", "대한항공"],
        data_quality=data_quality,
        quality_note=quality_note,
    )


def _build_bond_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("curve", "T10Y2Y", "미국 10년-2년 금리차", "%p", "bp"),
        ]
    )
    curve, curve_points = snapshots["curve"]
    snapshots_for_quality = [(curve, curve_points)]
    data_quality, quality_note, quality_confidence = _factor_quality(snapshots_for_quality)
    curve_5d = _change_5d(curve_points, kind="bp")
    available_changes = [value for value in (curve_5d,) if value is not None]
    # A rising 10-year/2-year spread means the curve is less inverted or
    # steeper; that is a modestly better signal for cyclical risk appetite.
    pressure = -curve_5d if curve_5d is not None else 0
    if not available_changes:
        direction = "자료 부족"
    elif abs(pressure) < BP_SIGNAL_THRESHOLD:
        direction = "혼조"
    else:
        direction = "악재" if pressure > 0 else "호재"
    raw = abs(pressure) / 2.4 + 7 if available_changes else 3
    if direction == "악재":
        interpretation = "미국 수익률곡선이 더 역전되어 경기·위험선호 신호가 약해지고 성장주·리츠에 부담이 되는 흐름입니다."
    elif direction == "호재":
        interpretation = "미국 수익률곡선이 덜 역전되거나 가팔라져 경기·위험선호 신호가 개선되는 흐름입니다."
    elif direction == "혼조":
        interpretation = "미국 수익률곡선 변화가 작아 채권금리 신호만으로 방향을 단정하기 어렵습니다."
    else:
        interpretation = "채권금리 자료가 부족해 방향을 판단하지 않습니다."
    return _factor(
        key="bond",
        label="채권금리",
        direction=direction,
        raw=raw,
        confidence=quality_confidence,
        interpretation=interpretation,
        evidence=[item for item in [curve] if item],
        affected_sectors=["금융", "건설", "리츠", "성장주"],
        leader_stocks=["KB금융", "삼성생명", "현대건설", "NAVER"],
        data_quality=data_quality,
        quality_note=quality_note,
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
    snapshots_for_quality = [(wti, wti_points), (copper, copper_points)]
    data_quality, quality_note, quality_confidence = _factor_quality(snapshots_for_quality)
    wti_5d = _change_5d(wti_points)
    copper_5d = _change_5d(copper_points)
    available_changes = [value for value in (wti_5d, copper_5d) if value is not None]
    pressure = (
        (wti_5d * 0.75 if wti_5d is not None else 0)
        + (copper_5d * 0.25 if copper_5d is not None else 0)
    )
    commodity_signals = [_signal(value, PCT_SIGNAL_THRESHOLD) for value in (wti_5d, copper_5d) if value is not None]
    mixed = len(commodity_signals) == 2 and commodity_signals[0] != commodity_signals[1]
    if not available_changes:
        direction = "자료 부족"
    elif mixed or abs(pressure) < PCT_SIGNAL_THRESHOLD:
        direction = "혼조"
    else:
        direction = "악재" if pressure > 0 else "호재"
    raw = abs(pressure) * 4.2 + 10 if available_changes else 3
    if direction == "악재":
        interpretation = "유가 중심 원자재 가격이 올라 물가·운송비와 항공·화학·운송 원가 부담이 커지는 흐름입니다. 정유·소재는 업종별 수혜를 따로 봐야 합니다."
    elif direction == "호재":
        interpretation = "유가 중심 원자재 가격이 내려 비용 민감 업종의 부담이 완화되는 흐름입니다. 정유·소재에는 반드시 같은 방향의 호재는 아닙니다."
    elif direction == "혼조":
        interpretation = "유가와 구리 방향이 엇갈려 비용 민감 업종과 소재·철강 업종에 미치는 영향이 서로 다릅니다."
    else:
        interpretation = "원자재 자료가 부족해 비용·수요 방향을 판단하지 않습니다."
    eia_note = {
        "source": "EIA",
        "metric": "주간 원유재고 발표",
        "value_text": "재고 이벤트 확인",
        "change_1d_text": "-",
        "change_5d_text": "-",
        "as_of": datetime.now(KST).strftime("%Y-%m-%d"),
        "url": "https://www.eia.gov/petroleum/supply/weekly/",
        "data_quality": "참고",
        "quality_note": "가격 방향 판정에는 사용하지 않은 이벤트 참고 링크",
    }
    return _factor(
        key="commodity",
        label="원자재",
        direction=direction,
        raw=raw,
        confidence=quality_confidence,
        interpretation=interpretation,
        evidence=[item for item in [wti, copper, eia_note] if item],
        affected_sectors=["정유", "화학", "항공", "해운", "철강"],
        leader_stocks=["S-Oil", "LG화학", "대한항공", "POSCO홀딩스"],
        data_quality=data_quality,
        quality_note=quality_note,
    )


def _build_risk_factor() -> dict[str, object]:
    snapshots = _series_snapshots(
        [
            ("nasdaq", "NASDAQCOM", "나스닥 종합", "", "pct"),
            ("btc", "CBBTCUSD", "비트코인", "", "pct"),
            ("vix", "VIXCLS", "미국 증시 불안지수(VIX)", "", "pct"),
        ]
    )
    nasdaq, nasdaq_points = snapshots["nasdaq"]
    btc, btc_points = snapshots["btc"]
    vix, vix_points = snapshots["vix"]
    snapshots_for_quality = [(nasdaq, nasdaq_points), (btc, btc_points), (vix, vix_points)]
    data_quality, quality_note, quality_confidence = _factor_quality(snapshots_for_quality)
    nasdaq_5d = _change_5d(nasdaq_points)
    btc_5d = _change_5d(btc_points)
    vix_5d = _change_5d(vix_points)
    appetite = (
        (nasdaq_5d * 0.45 if nasdaq_5d is not None else 0)
        + (btc_5d * 0.35 if btc_5d is not None else 0)
        - (vix_5d * 0.20 if vix_5d is not None else 0)
    )
    signal_values = [
        _signal(nasdaq_5d, PCT_SIGNAL_THRESHOLD),
        _signal(btc_5d, PCT_SIGNAL_THRESHOLD),
        -_signal(vix_5d, PCT_SIGNAL_THRESHOLD),
    ]
    positive_signals = sum(value > 0 for value in signal_values)
    negative_signals = sum(value < 0 for value in signal_values)
    if not any(value != 0 for value in signal_values):
        direction = "자료 부족"
    elif positive_signals == 3:
        direction = "호재"
    elif negative_signals == 3:
        direction = "악재"
    else:
        direction = "혼조"
    raw = abs(appetite) * 3.4 + 8 if any(value is not None for value in (nasdaq_5d, btc_5d, vix_5d)) else 3
    if direction == "호재":
        interpretation = "미국 기술주와 가상자산은 강세이고, 시장 불안 지표는 낮아 투자심리가 비교적 안정적입니다."
    elif direction == "악재":
        interpretation = "미국 기술주와 가상자산은 약세이고, 시장 불안 지표는 높아 투자심리가 위축된 상태입니다."
    elif direction == "혼조":
        if nasdaq_5d is not None and btc_5d is not None and nasdaq_5d > PCT_SIGNAL_THRESHOLD and btc_5d < -PCT_SIGNAL_THRESHOLD:
            interpretation = "나스닥은 강세지만 비트코인은 약세라 주식과 코인의 위험선호가 갈립니다. 국내 성장주에는 혼조 신호입니다."
        elif nasdaq_5d is not None and btc_5d is not None and nasdaq_5d < -PCT_SIGNAL_THRESHOLD and btc_5d > PCT_SIGNAL_THRESHOLD:
            interpretation = "비트코인은 강세지만 나스닥은 약세라 위험자산 내부의 방향이 갈립니다."
        else:
            interpretation = "미국 기술주·가상자산·시장 불안 지표의 방향이 엇갈려 투자심리를 한쪽으로 판단하기 어렵습니다."
    else:
        interpretation = "미국 기술주·가상자산·시장 불안 지표 자료가 부족해 투자심리를 판단하지 않습니다."
    return _factor(
        key="risk",
        label="투자심리",
        direction=direction,
        raw=raw,
        confidence=quality_confidence,
        interpretation=interpretation,
        evidence=[item for item in [nasdaq, btc, vix] if item],
        affected_sectors=["반도체", "인터넷", "AI", "게임", "2차전지"],
        leader_stocks=["SK하이닉스", "삼성전자", "NAVER", "한미반도체"],
        data_quality=data_quality,
        quality_note=quality_note,
    )


def build_market_impact() -> dict[str, object]:
    factors = _build_factors()
    raw_values: list[float] = []
    for factor in factors:
        raw = float(factor.pop("raw", 0) or 0)
        confidence = float(factor.get("confidence") or 20)
        # Low-quality data may still be shown, but it must not receive the
        # same influence weight as a fully validated factor.
        adjusted_raw = raw * (0.5 + (max(0.0, min(100.0, confidence)) / 200.0))
        raw_values.append(max(adjusted_raw, 0.1))
    raw_total = sum(raw_values) or 1.0
    percentages = [round(raw / raw_total * 100, 1) for raw in raw_values]
    rounding_delta = round(100.0 - sum(percentages), 1)
    if percentages:
        percentages[-1] = round(percentages[-1] + rounding_delta, 1)
    for factor, percent in zip(factors, percentages):
        factor["percent"] = _round_decimal(percent, 1) or Decimal("0")

    factors.sort(key=lambda item: float(item.get("percent") or 0), reverse=True)
    good_weight = sum(float(item["percent"]) for item in factors if item.get("direction") == "호재")
    neutral_weight = sum(
        float(item["percent"])
        for item in factors
        if item.get("direction") not in {"호재", "악재"}
    )
    bad_weight = sum(float(item["percent"]) for item in factors if item.get("direction") == "악재")
    available_factor_count = sum(item.get("direction") in {"호재", "악재", "혼조"} for item in factors)
    if available_factor_count < 2:
        market_status = "자료 부족"
    elif abs(good_weight - bad_weight) <= max(8.0, neutral_weight * 0.35):
        market_status = "혼조"
    elif good_weight > bad_weight:
        market_status = "호재 우위"
    else:
        market_status = "리스크 우위"
    lead = factors[0]
    if market_status == "자료 부족":
        summary = "공식 지표가 충분하지 않아 시장 방향 판단을 보류합니다."
    elif market_status == "혼조":
        summary = f"{lead['label']} 영향이 가장 크지만 요인이 엇갈려 한 방향의 시장심리로 보기 어렵습니다."
    elif market_status == "호재 우위":
        summary = f"{lead['label']} 영향이 가장 크고, 현재는 호재 쪽이 더 우세합니다."
    else:
        summary = f"{lead['label']} 영향이 가장 크고, 현재는 리스크 관리가 더 우선입니다."
    quality_values = [str(item.get("data_quality") or "주의") for item in factors]
    if all(value == "자료 부족" for value in quality_values):
        data_quality = "자료 부족"
        data_quality_note = "5개 축 모두 공식 지표를 수집하지 못했습니다."
    elif any(value != "확인" for value in quality_values):
        data_quality = "주의"
        data_quality_note = "일부 축의 기준일·관측주기·결측 상태를 확인해야 합니다."
    else:
        data_quality = "확인"
        data_quality_note = "5개 축의 기준일과 변화율을 확인했습니다."
    evidence_dates = [
        _parse_point_date(str(evidence.get("as_of")))
        for factor in factors
        for evidence in factor.get("evidence", [])
        if evidence.get("source") != "시스템" and evidence.get("value") is not None and evidence.get("as_of")
    ]
    evidence_dates = [value for value in evidence_dates if value is not None]
    return {
        "as_of": datetime.now(KST),
        "data_as_of": max(evidence_dates).isoformat() if evidence_dates else None,
        "data_quality": data_quality,
        "data_quality_note": data_quality_note,
        "market_status": market_status,
        "summary": summary,
        "good_weight": _round_decimal(good_weight, 1) or Decimal("0"),
        "bad_weight": _round_decimal(bad_weight, 1) or Decimal("0"),
        "neutral_weight": _round_decimal(neutral_weight, 1) or Decimal("0"),
        "factors": factors,
    }
