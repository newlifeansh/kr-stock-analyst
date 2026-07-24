from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import re
from statistics import mean
from threading import RLock
from typing import Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, DisclosureItem, InvestorFlow, NewsItem, ResearchReport, StockMaster
from app.services.company_profiles import company_profile_payload
from app.services.ttl_cache import TTLCache

POSITIVE_WORDS = (
    "상향",
    "호조",
    "개선",
    "증가",
    "최대",
    "수주",
    "흑자",
    "서프라이즈",
    "강세",
    "성장",
    "돌파",
    "수혜",
    "상승",
    "반등",
    "회복",
    "호재",
    "매수",
)
NEGATIVE_WORDS = (
    "하향",
    "부진",
    "감소",
    "적자",
    "쇼크",
    "약세",
    "하락",
    "악화",
    "손실",
    "둔화",
    "우려",
    "급락",
    "악재",
    "위기",
    "충격",
    "매도",
)
SURPRISE_WORDS = ("잠정", "실적", "매출액", "영업이익", "순이익", "어닝", "서프라이즈", "쇼크")
GUIDANCE_WORDS = ("전망", "가이던스", "목표", "계획", "IR", "기업설명회", "투자설명회")
FOREIGN_TYPES = ("외국인", "외국인합계", "외국계")
INSTITUTION_TYPES = ("기관합계", "기관", "금융투자", "투신", "연기금")
NAVER_ITEM_URL = "https://finance.naver.com/item/main.naver"
NAVER_CACHE = TTLCache(maxsize=2048)
PRICE_HISTORY_BACKFILL_CACHE = TTLCache(maxsize=2048)
PRICE_HISTORY_BACKFILL_LOCK = RLock()
NAVER_SNAPSHOT_TTL_SECONDS = 120
NAVER_ITEM_NEWS_TTL_SECONDS = 180
PRICE_HISTORY_MIN_ROWS = 64
PRICE_HISTORY_LOOKBACK_DAYS = 220
PRICE_HISTORY_BACKFILL_TTL_SECONDS = 60 * 60 * 6
KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


def _round_decimal(value: Optional[Decimal | float | int], places: str = "0.01") -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _to_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    cleaned = value.replace(",", "").replace("%", "").replace("배", "").replace("원", "").strip()
    if not cleaned or cleaned in {"-", "N/A"}:
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    decimal_value = _to_decimal(value)
    if decimal_value is None:
        return None
    return int(decimal_value)


def _market_cap_from_korean(value: str) -> Optional[int]:
    cleaned = re.sub(r"\s+", " ", value.replace(",", "")).strip()
    jo_match = re.search(r"(\d+(?:\.\d+)?)\s*조", cleaned)
    eok_match = re.search(r"(\d+(?:\.\d+)?)\s*억", cleaned)
    total = Decimal("0")
    if jo_match:
        total += Decimal(jo_match.group(1)) * Decimal("1000000000000")
    if eok_match:
        total += Decimal(eok_match.group(1)) * Decimal("100000000")
    return int(total) if total else None


def _rate(current: Optional[int | Decimal], base: Optional[int | Decimal]) -> Optional[Decimal]:
    if current is None or base in (None, 0):
        return None
    return _round_decimal((Decimal(str(current)) / Decimal(str(base)) - Decimal("1")) * Decimal("100"))


def _safe_cell(row: list[Optional[Decimal]], index: int) -> Optional[Decimal]:
    if index < 0 or index >= len(row):
        return None
    return row[index]


def _fetch_naver_snapshot(code: str) -> dict[str, object]:
    try:
        response = requests.get(
            NAVER_ITEM_URL,
            params={"code": code},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
    except Exception:
        return {}

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    snapshot: dict[str, object] = {}

    today_values = [_to_int(item.get_text(strip=True)) for item in soup.select("p.no_today .blind")]
    exday_values = [_to_decimal(item.get_text(strip=True)) for item in soup.select("p.no_exday .blind")]
    info_values = [_to_int(item.get_text(strip=True)) for item in soup.select("table.no_info .blind")]
    market_sum = soup.select_one("em#_market_sum")
    if today_values:
        snapshot["price"] = today_values[0]
    if len(exday_values) >= 2:
        sign = Decimal("-1") if soup.select_one("p.no_exday em.no_down") else Decimal("1")
        if soup.select_one("p.no_exday em.no_unch"):
            sign = Decimal("0")
        snapshot["change_value"] = int(exday_values[0] * sign) if exday_values[0] is not None else None
        snapshot["change_rate_abs"] = _round_decimal(exday_values[1] * sign) if exday_values[1] is not None else None
    if len(info_values) >= 7:
        snapshot["volume"] = info_values[3]
        snapshot["trading_value"] = info_values[6] * 1_000_000 if info_values[6] is not None else None
    if market_sum:
        snapshot["market_cap"] = _market_cap_from_korean(market_sum.get_text(" ", strip=True))

    valuation_table = next(
        (
            table
            for table in soup.select("table")
            if "PER l EPS" in table.get_text(" ", strip=True) and "PBR l BPS" in table.get_text(" ", strip=True)
        ),
        None,
    )
    if valuation_table:
        text = valuation_table.get_text(" ", strip=True)
        base_text = text.split("추정PER", 1)[0]
        estimated_text = text.split("추정PER", 1)[1] if "추정PER" in text else ""
        per_match = re.search(r"PER l EPS.*?(-?[\d,]+(?:\.\d+)?)\s*배\s*l\s*(-?[\d,]+(?:\.\d+)?)\s*원", base_text, re.S)
        estimated_match = re.search(
            r".*?(-?[\d,]+(?:\.\d+)?)\s*배\s*l\s*(-?[\d,]+(?:\.\d+)?)\s*원",
            estimated_text,
            re.S,
        )
        pbr_match = re.search(r"PBR l BPS.*?(-?[\d,]+(?:\.\d+)?)\s*배\s*l\s*(-?[\d,]+(?:\.\d+)?)\s*원", text, re.S)
        dividend_match = re.search(r"배당수익률.*?(-?[\d,]+(?:\.\d+)?)\s*%", text, re.S)
        if per_match:
            snapshot["per"] = _to_decimal(per_match.group(1))
            snapshot["eps"] = _to_decimal(per_match.group(2))
        if estimated_match:
            snapshot["estimated_per"] = _to_decimal(estimated_match.group(1))
            snapshot["estimated_eps"] = _to_decimal(estimated_match.group(2))
        if pbr_match:
            snapshot["pbr"] = _to_decimal(pbr_match.group(1))
            snapshot["bps"] = _to_decimal(pbr_match.group(2))
        if dividend_match:
            snapshot["dividend_yield"] = _to_decimal(dividend_match.group(1))

    industry_table = next((table for table in soup.select("table") if "동일업종 PER" in table.get_text(" ", strip=True)), None)
    if industry_table:
        match = re.search(r"동일업종 PER\s+(-?[\d,]+(?:\.\d+)?)\s*배", industry_table.get_text(" ", strip=True))
        if match:
            snapshot["industry_per"] = _to_decimal(match.group(1))

    financial_table = soup.select_one("table.tb_type1.tb_num.tb_type1_ifrs")
    if financial_table:
        headers: list[str] = []
        rows: dict[str, list[Optional[Decimal]]] = {}
        for tr in financial_table.select("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            if not cells:
                continue
            if cells[0].startswith("202"):
                headers = cells
                continue
            if headers and cells[0] in {"매출액", "영업이익", "EPS(원)", "PER(배)", "PBR(배)", "BPS(원)"}:
                rows[cells[0]] = [_to_decimal(cell) for cell in cells[1:]]

        actual_indices = [idx for idx, header in enumerate(headers) if "(E)" not in header]
        estimate_indices = [idx for idx, header in enumerate(headers) if "(E)" in header]
        latest_actual_idx = actual_indices[-1] if actual_indices else None
        previous_actual_idx = actual_indices[-2] if len(actual_indices) >= 2 else None
        latest_estimate_idx = estimate_indices[-1] if estimate_indices else None

        revenue = rows.get("매출액", [])
        operating_profit = rows.get("영업이익", [])
        eps_row = rows.get("EPS(원)", [])
        per_row = rows.get("PER(배)", [])
        pbr_row = rows.get("PBR(배)", [])
        bps_row = rows.get("BPS(원)", [])
        if latest_actual_idx is not None:
            snapshot["latest_revenue"] = _safe_cell(revenue, latest_actual_idx)
            snapshot["latest_operating_profit"] = _safe_cell(operating_profit, latest_actual_idx)
            snapshot["latest_eps"] = _safe_cell(eps_row, latest_actual_idx)
            snapshot["financial_period"] = headers[latest_actual_idx]
            snapshot["per_series"] = [value for idx, value in enumerate(per_row) if idx in actual_indices and value is not None]
            snapshot["pbr_series"] = [value for idx, value in enumerate(pbr_row) if idx in actual_indices and value is not None]
            if snapshot.get("per") is None:
                snapshot["per"] = _safe_cell(per_row, latest_actual_idx)
            if snapshot.get("pbr") is None:
                snapshot["pbr"] = _safe_cell(pbr_row, latest_actual_idx)
            if snapshot.get("bps") is None:
                snapshot["bps"] = _safe_cell(bps_row, latest_actual_idx)
        if previous_actual_idx is not None:
            snapshot["revenue_growth"] = _rate(_safe_cell(revenue, latest_actual_idx), _safe_cell(revenue, previous_actual_idx))
            snapshot["operating_profit_growth"] = _rate(
                _safe_cell(operating_profit, latest_actual_idx),
                _safe_cell(operating_profit, previous_actual_idx),
            )
        if latest_estimate_idx is not None:
            snapshot["estimated_revenue"] = _safe_cell(revenue, latest_estimate_idx)
            snapshot["estimated_operating_profit"] = _safe_cell(operating_profit, latest_estimate_idx)
            if snapshot.get("estimated_eps") is None:
                snapshot["estimated_eps"] = _safe_cell(eps_row, latest_estimate_idx)
            if snapshot.get("estimated_per") is None:
                snapshot["estimated_per"] = _safe_cell(per_row, latest_estimate_idx)

    try:
        frgn_response = requests.get(
            "https://finance.naver.com/item/frgn.naver",
            params={"code": code, "page": 1},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        frgn_response.raise_for_status()
        frgn_response.encoding = "euc-kr"
        frgn_soup = BeautifulSoup(frgn_response.text, "html.parser")
        flow_table = next(
            (
                table
                for table in frgn_soup.select("table.type2")
                if "기관" in table.get_text(" ", strip=True) and "외국인" in table.get_text(" ", strip=True)
            ),
            None,
        )
        foreign_value = Decimal("0")
        institution_value = Decimal("0")
        total_value = Decimal("0")
        flow_rows = 0
        if flow_table:
            for tr in flow_table.select("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.find_all("td")]
                if len(cells) < 9 or not re.match(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
                    continue
                close = _to_decimal(cells[1])
                volume = _to_decimal(cells[4])
                institution = _to_decimal(cells[5])
                foreign = _to_decimal(cells[6])
                if close is None:
                    continue
                if institution is not None:
                    institution_value += institution * close
                if foreign is not None:
                    foreign_value += foreign * close
                if volume is not None:
                    total_value += volume * close
                flow_rows += 1
        if flow_rows:
            snapshot["foreign_net_buy_value"] = int(foreign_value)
            snapshot["institution_net_buy_value"] = int(institution_value)
            snapshot["flow_total_value"] = int(total_value) if total_value else None
            snapshot["flow_days"] = flow_rows
    except Exception:
        pass

    return snapshot


def _naver_snapshot(code: str, refresh: bool = False) -> dict[str, object]:
    if refresh:
        payload = _fetch_naver_snapshot(code)
        NAVER_CACHE.set(("naver_snapshot", code), payload, NAVER_SNAPSHOT_TTL_SECONDS)
        return payload
    return NAVER_CACHE.get_or_set(
        ("naver_snapshot", code),
        NAVER_SNAPSHOT_TTL_SECONDS,
        lambda: _fetch_naver_snapshot(code),
    )


def _keyword_score(text: str) -> int:
    score = 0
    for word in POSITIVE_WORDS:
        if word in text:
            score += 1
    for word in NEGATIVE_WORDS:
        if word in text:
            score -= 1
    return score


def _keyword_impact(score: int) -> str:
    if score > 0:
        return "호재"
    if score < 0:
        return "악재"
    return "중립"


def _event_row(
    title: str,
    source: str,
    url: Optional[str],
    published_at: Optional[datetime],
    impact: Optional[str] = None,
) -> dict[str, object]:
    return {
        "title": title,
        "source": source,
        "url": url,
        "published_at": published_at,
        "impact": impact,
    }


def _resolve_trade_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y.%m.%d %H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _fetch_naver_item_news(code: str) -> list[dict[str, object]]:
    try:
        response = requests.get(
            "https://finance.naver.com/item/news_news.naver",
            params={"code": code, "page": 1},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        response.encoding = "euc-kr"
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, object]] = []
    for tr in soup.select("table.type5 tr"):
        title_cell = tr.select_one("td.title")
        if not title_cell:
            continue
        anchor = title_cell.find("a", href=True)
        if not anchor:
            continue
        title = anchor.get_text(" ", strip=True)
        if not title:
            continue
        info_cell = tr.select_one("td.info")
        date_cell = tr.select_one("td.date")
        href = anchor["href"]
        url = href if href.startswith("http") else f"https://finance.naver.com{href}"
        rows.append(
            _event_row(
                title,
                info_cell.get_text(" ", strip=True) if info_cell else "Naver",
                url,
                _resolve_trade_date(date_cell.get_text(" ", strip=True) if date_cell else None),
            )
        )
    return rows[:10]


def _naver_item_news(code: str) -> list[dict[str, object]]:
    return NAVER_CACHE.get_or_set(
        ("naver_item_news", code),
        NAVER_ITEM_NEWS_TTL_SECONDS,
        lambda: _fetch_naver_item_news(code),
    )


def _prices(db: Session, code: str, limit: int = 180) -> list[DailyPrice]:
    statement = (
        select(DailyPrice)
        .where(DailyPrice.code == code)
        .order_by(DailyPrice.trade_date.desc())
        .limit(limit)
    )
    return list(reversed(list(db.scalars(statement))))


def ensure_stock_price_history(
    db: Session,
    code: str,
    min_rows: int = PRICE_HISTORY_MIN_ROWS,
    lookback_days: int = PRICE_HISTORY_LOOKBACK_DAYS,
) -> int:
    def count_rows() -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(DailyPrice)
                .where(DailyPrice.code == code)
            )
            or 0
        )

    current_count = count_rows()
    if current_count >= min_rows:
        return current_count

    cache_key = ("price_history_backfill", code)
    cached_count = PRICE_HISTORY_BACKFILL_CACHE.get(cache_key)
    if cached_count is not None:
        return int(cached_count)

    with PRICE_HISTORY_BACKFILL_LOCK:
        current_count = count_rows()
        if current_count >= min_rows:
            return current_count
        cached_count = PRICE_HISTORY_BACKFILL_CACHE.get(cache_key)
        if cached_count is not None:
            return int(cached_count)

        today = _now_kst().date()
        from_date = today - timedelta(days=lookback_days)
        try:
            from app.collectors.krx import collect_stock_prices

            collect_stock_prices(
                db,
                code,
                from_yyyymmdd=from_date.strftime("%Y%m%d"),
                to_yyyymmdd=today.strftime("%Y%m%d"),
            )
        except Exception:
            db.rollback()

        refreshed_count = count_rows()
        PRICE_HISTORY_BACKFILL_CACHE.set(cache_key, refreshed_count, PRICE_HISTORY_BACKFILL_TTL_SECONDS)
        return refreshed_count


def _nth_from_end(items: list[DailyPrice], offset: int) -> Optional[DailyPrice]:
    if len(items) <= offset:
        return None
    return items[-1 - offset]


def _quote(prices: list[DailyPrice], naver: dict[str, object], prefer_live: bool = False) -> dict[str, object]:
    latest = prices[-1] if prices else None
    previous = _nth_from_end(prices, 1)
    if prefer_live and naver.get("price") is not None:
        return {
            "trade_date": latest.trade_date if latest else None,
            "price": naver.get("price"),
            "change_value": naver.get("change_value"),
            "change_rate": naver.get("change_rate_abs"),
            "volume": naver.get("volume") or (latest.volume if latest else None),
            "trading_value": naver.get("trading_value") or (latest.trading_value if latest else None),
            "market_cap": naver.get("market_cap") or (latest.market_cap if latest else None),
        }
    if not latest:
        return {
            "trade_date": None,
            "price": naver.get("price"),
            "change_value": naver.get("change_value"),
            "change_rate": naver.get("change_rate_abs"),
            "volume": naver.get("volume"),
            "trading_value": naver.get("trading_value"),
            "market_cap": naver.get("market_cap"),
        }

    change_value = None
    if latest.close is not None and previous and previous.close is not None:
        change_value = latest.close - previous.close

    return {
        "trade_date": latest.trade_date,
        "price": latest.close or naver.get("price"),
        "change_value": change_value if change_value is not None else naver.get("change_value"),
        "change_rate": _rate(latest.close, previous.close if previous else None),
        "volume": latest.volume or naver.get("volume"),
        "trading_value": latest.trading_value or naver.get("trading_value"),
        "market_cap": latest.market_cap or naver.get("market_cap"),
    }


def _momentum(prices: list[DailyPrice]) -> dict[str, object]:
    latest = prices[-1] if prices else None
    one_month = _nth_from_end(prices, 21)
    three_month = _nth_from_end(prices, 63)
    def row_value(row: DailyPrice) -> Optional[int]:
        if row.trading_value is not None:
            return row.trading_value
        if row.close is not None and row.volume is not None:
            return row.close * row.volume
        return None

    recent_values = [value for row in prices[-5:] if (value := row_value(row)) is not None]
    baseline_values = [value for row in prices[-25:-5] if (value := row_value(row)) is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None

    return {
        "one_month_return": _rate(latest.close if latest else None, one_month.close if one_month else None),
        "three_month_return": _rate(latest.close if latest else None, three_month.close if three_month else None),
        "trading_value_change": _rate(recent_average, baseline_average),
        "latest_trading_value": row_value(latest) if latest else None,
        "baseline_trading_value": _round_decimal(baseline_average, "1") if baseline_average is not None else None,
    }


def _average(values: list[Decimal]) -> Optional[Decimal]:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def _moving_average(prices: list[DailyPrice], window: int, offset: int = 0) -> Optional[Decimal]:
    end = len(prices) - offset
    start = end - window
    if start < 0 or end <= 0:
        return None
    values = [Decimal(str(row.close)) for row in prices[start:end] if row.close is not None]
    if len(values) < window:
        return None
    return _round_decimal(_average(values))


def _distance(current: Optional[int | Decimal], base: Optional[int | Decimal]) -> Optional[Decimal]:
    if current is None or base in (None, 0):
        return None
    return _round_decimal((Decimal(str(current)) / Decimal(str(base)) - Decimal("1")) * Decimal("100"))


def _atr_percent(prices: list[DailyPrice], window: int = 14) -> Optional[Decimal]:
    if len(prices) <= window:
        return None
    ranges = []
    rows = prices[-window:]
    previous_rows = prices[-window - 1 : -1]
    for row, previous in zip(rows, previous_rows):
        if row.high is None or row.low is None or previous.close is None:
            continue
        high = Decimal(str(row.high))
        low = Decimal(str(row.low))
        previous_close = Decimal(str(previous.close))
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    latest_close = prices[-1].close if prices else None
    atr = _average(ranges)
    if atr is None or latest_close in (None, 0):
        return None
    return _round_decimal(atr / Decimal(str(latest_close)) * Decimal("100"))


def _chart_analysis(prices: list[DailyPrice]) -> dict[str, object]:
    latest = prices[-1] if prices else None
    latest_close = latest.close if latest else None
    latest_volume = latest.volume if latest else None
    ma5 = _moving_average(prices, 5)
    ma20 = _moving_average(prices, 20)
    ma60 = _moving_average(prices, 60)
    ma120 = _moving_average(prices, 120)
    previous_ma20 = _moving_average(prices, 20, offset=5)
    volume_values = [Decimal(str(row.volume)) for row in prices[-21:-1] if row.volume is not None]
    volume_average = _average(volume_values)
    volume_ratio = (
        _round_decimal(Decimal(str(latest_volume)) / volume_average)
        if latest_volume is not None and volume_average not in (None, 0)
        else None
    )
    recent_highs = [row.high for row in prices[-60:-1] if row.high is not None]
    recent_lows = [row.low for row in prices[-60:-1] if row.low is not None]
    resistance = max(recent_highs) if recent_highs else None
    support = min(recent_lows) if recent_lows else None
    distance_to_resistance = _distance(latest_close, resistance)
    distance_to_support = _distance(latest_close, support)
    atr = _atr_percent(prices)

    signals: list[str] = []
    risks: list[str] = []
    score = Decimal("50")

    if latest_close is None:
        return {
            "score": Decimal("0"),
            "stance": "가격 데이터 부족",
            "trend": "판단 불가",
            "setup": "대기",
            "risk_level": "높음",
            "moving_averages": {"ma5": ma5, "ma20": ma20, "ma60": ma60, "ma120": ma120},
            "volume_ratio": volume_ratio,
            "atr_percent": atr,
            "support": support,
            "resistance": resistance,
            "distance_to_support": distance_to_support,
            "distance_to_resistance": distance_to_resistance,
            "signals": ["종가 데이터가 부족합니다."],
            "risks": ["차트 판단 불가"],
        }

    if ma20 is not None and latest_close > ma20:
        score += Decimal("10")
        signals.append("현재가가 20일선 위에 있어 단기 추세가 살아있음")
    elif ma20 is not None:
        score -= Decimal("12")
        risks.append("현재가가 20일선 아래라 단기 추세 확인 필요")

    if ma20 is not None and ma60 is not None and ma20 > ma60:
        score += Decimal("12")
        signals.append("20일선이 60일선 위에 있어 중기 추세 우위")
    elif ma20 is not None and ma60 is not None:
        score -= Decimal("10")
        risks.append("20일선이 60일선 아래라 반등 지속성 확인 필요")

    if ma60 is not None and ma120 is not None and ma60 > ma120:
        score += Decimal("8")
        signals.append("60일선이 120일선 위에 있어 장기 추세 훼손 제한")
    elif ma60 is not None and ma120 is not None:
        score -= Decimal("8")
        risks.append("60일선이 120일선 아래라 장기 추세 회복 전")

    if ma20 is not None and previous_ma20 is not None and ma20 > previous_ma20:
        score += Decimal("8")
        signals.append("20일선 기울기가 상승 중")
    elif ma20 is not None and previous_ma20 is not None:
        score -= Decimal("8")
        risks.append("20일선 기울기가 둔화 또는 하락")

    if resistance is not None and latest_close > resistance:
        score += Decimal("14")
        signals.append("60일 박스권 상단 돌파")
    elif distance_to_resistance is not None and distance_to_resistance >= Decimal("-3"):
        score += Decimal("5")
        signals.append("60일 저항권에 근접")

    if support is not None and latest_close < support:
        score -= Decimal("16")
        risks.append("60일 지지선 이탈")
    elif distance_to_support is not None and distance_to_support <= Decimal("3"):
        risks.append("지지선과 거리가 가까워 이탈 여부 확인 필요")

    if volume_ratio is not None and volume_ratio >= Decimal("1.5"):
        score += Decimal("8")
        signals.append(f"거래량이 20일 평균 대비 {volume_ratio}배로 증가")
    elif volume_ratio is not None and volume_ratio <= Decimal("0.7"):
        score -= Decimal("4")
        risks.append("거래량이 평균보다 낮아 추세 신뢰도 제한")

    if atr is not None and atr >= Decimal("6"):
        score -= Decimal("8")
        risks.append(f"ATR {atr}%로 변동성 확대")
    elif atr is not None and atr <= Decimal("2.5"):
        signals.append("변동성이 안정적인 구간")

    score = _round_decimal(max(Decimal("0"), min(Decimal("100"), score))) or Decimal("0")
    if ma20 is not None and ma60 is not None and ma120 is not None and latest_close > ma20 > ma60 > ma120:
        trend = "정배열 상승 추세"
    elif ma20 is not None and ma60 is not None and latest_close > ma20 and ma20 > ma60:
        trend = "상승 추세"
    elif ma20 is not None and latest_close < ma20:
        trend = "단기 약세"
    else:
        trend = "박스권/중립"

    if resistance is not None and latest_close > resistance:
        setup = "돌파 추세"
    elif ma20 is not None and ma60 is not None and latest_close > ma60 and latest_close <= ma20:
        setup = "눌림목 관찰"
    elif support is not None and latest_close < support:
        setup = "지지 이탈"
    elif distance_to_resistance is not None and distance_to_resistance >= Decimal("-3"):
        setup = "돌파 대기"
    else:
        setup = "추세 확인"

    if atr is not None and atr >= Decimal("6"):
        risk_level = "높음"
    elif score < 45:
        risk_level = "주의"
    else:
        risk_level = "보통"

    if score >= 70:
        stance = "추세 추종 관심"
    elif score >= 55:
        stance = "관찰 가능"
    elif score >= 40:
        stance = "중립 대기"
    else:
        stance = "리스크 관리 우선"

    return {
        "score": score,
        "stance": stance,
        "trend": trend,
        "setup": setup,
        "risk_level": risk_level,
        "moving_averages": {"ma5": ma5, "ma20": ma20, "ma60": ma60, "ma120": ma120},
        "volume_ratio": volume_ratio,
        "atr_percent": atr,
        "support": support,
        "resistance": resistance,
        "distance_to_support": distance_to_support,
        "distance_to_resistance": distance_to_resistance,
        "signals": signals[:6] or ["뚜렷한 차트 신호가 아직 약합니다."],
        "risks": risks[:5] or ["주요 차트 리스크 신호는 제한적입니다."],
    }


def _research_revision(db: Session, code: str, naver: dict[str, object]) -> dict[str, object]:
    since = datetime.utcnow() - timedelta(days=180)
    reports = list(
        db.scalars(
            select(ResearchReport)
            .where(ResearchReport.stock_code == code)
            .where(ResearchReport.published_at >= since)
            .order_by(ResearchReport.published_at.asc(), ResearchReport.id.asc())
        )
    )
    by_broker: dict[str, list[ResearchReport]] = defaultdict(list)
    for report in reports:
        by_broker[report.broker_name or "unknown"].append(report)

    up_count = 0
    down_count = 0
    for broker_reports in by_broker.values():
        previous_target = None
        for report in broker_reports:
            if report.target_price is None:
                continue
            if previous_target is not None:
                if report.target_price > previous_target:
                    up_count += 1
                elif report.target_price < previous_target:
                    down_count += 1
            previous_target = report.target_price

    latest = reports[-1] if reports else None
    if latest and latest.detail_url and (latest.target_price is None or not latest.opinion):
        try:
            from app.collectors.research import fetch_company_detail_fields

            fields = fetch_company_detail_fields(latest.detail_url)
            if fields.get("target_price") is not None:
                latest.target_price = fields["target_price"]
            if fields.get("opinion"):
                latest.opinion = str(fields["opinion"])
            if fields.get("pdf_url") and not latest.pdf_url:
                latest.pdf_url = str(fields["pdf_url"])
            db.commit()
        except Exception:
            db.rollback()
    total_revision_count = up_count + down_count
    return {
        "report_count_90d": sum(
            1 for report in reports if report.published_at and report.published_at >= datetime.utcnow() - timedelta(days=90)
        ),
        "target_up_count": up_count,
        "target_down_count": down_count,
        "target_up_ratio": _round_decimal(Decimal(up_count) / Decimal(total_revision_count) * 100)
        if total_revision_count
        else None,
        "latest_target_price": latest.target_price if latest else None,
        "latest_opinion": latest.opinion if latest else None,
        "latest_report_at": latest.published_at if latest else None,
        "estimated_revenue": naver.get("estimated_revenue"),
        "estimated_operating_profit": naver.get("estimated_operating_profit"),
        "estimated_eps": naver.get("estimated_eps"),
        "estimated_per": naver.get("estimated_per"),
        "recent_reports": [
            {
                "title": report.title,
                "broker_name": report.broker_name,
                "opinion": report.opinion,
                "target_price": report.target_price,
                "url": report.detail_url or report.pdf_url,
                "published_at": report.published_at,
            }
            for report in reversed(reports[-5:])
        ],
    }


def _disclosure_events(
    db: Session,
    code: str,
    words: tuple[str, ...],
    naver: Optional[dict[str, object]] = None,
    fallback_to_recent: bool = False,
) -> dict[str, object]:
    since = datetime.utcnow() - timedelta(days=180)
    items = list(
        db.scalars(
            select(DisclosureItem)
            .where(DisclosureItem.stock_code == code)
            .where(DisclosureItem.published_at >= since)
            .order_by(DisclosureItem.published_at.desc(), DisclosureItem.id.desc())
            .limit(80)
        )
    )
    matched = [item for item in items if any(word in item.report_name for word in words)]
    if fallback_to_recent and not matched:
        matched = items[:5]
    positive_count = 0
    negative_count = 0
    for item in matched:
        score = _keyword_score(item.report_name)
        if score > 0:
            positive_count += 1
        elif score < 0:
            negative_count += 1

    payload = {
        "recent_count": len(matched),
        "all_count": len(items),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "latest_events": [
            _event_row(item.report_name, item.source, item.detail_url, item.published_at) for item in matched[:5]
        ],
        "latest_revenue": None,
        "latest_operating_profit": None,
        "latest_eps": None,
        "revenue_growth": None,
        "operating_profit_growth": None,
    }
    if naver:
        payload.update(
            {
                "latest_revenue": naver.get("latest_revenue"),
                "latest_operating_profit": naver.get("latest_operating_profit"),
                "latest_eps": naver.get("latest_eps"),
                "revenue_growth": naver.get("revenue_growth"),
                "operating_profit_growth": naver.get("operating_profit_growth"),
            }
        )
    return payload


def _zscore(current: Optional[Decimal], series: list[Decimal]) -> Optional[Decimal]:
    if current is None or len(series) < 3:
        return None
    values = [Decimal(str(value)) for value in series if value is not None and value > 0]
    if len(values) < 3:
        return None
    avg = sum(values) / Decimal(len(values))
    variance = sum((value - avg) ** 2 for value in values) / Decimal(len(values))
    std = variance.sqrt()
    if std == 0:
        return None
    return _round_decimal((Decimal(str(current)) - avg) / std)


def _valuation(naver: dict[str, object]) -> dict[str, object]:
    per = naver.get("per")
    pbr = naver.get("pbr")
    return {
        "per": per,
        "pbr": pbr,
        "eps": naver.get("eps"),
        "bps": naver.get("bps"),
        "estimated_per": naver.get("estimated_per"),
        "estimated_eps": naver.get("estimated_eps"),
        "industry_per": naver.get("industry_per"),
        "dividend_yield": naver.get("dividend_yield"),
        "per_zscore": _zscore(per if isinstance(per, Decimal) else None, naver.get("per_series", [])),
        "pbr_zscore": _zscore(pbr if isinstance(pbr, Decimal) else None, naver.get("pbr_series", [])),
        "ev_ebitda_zscore": None,
    }


def _bounded(value: Optional[Decimal | int | float], low: Decimal = Decimal("-100"), high: Decimal = Decimal("100")) -> Optional[Decimal]:
    if value is None:
        return None
    decimal_value = Decimal(str(value))
    if decimal_value < low:
        decimal_value = low
    if decimal_value > high:
        decimal_value = high
    return _round_decimal(decimal_value)


def _macro_sensitivity(momentum: dict[str, object], flows: dict[str, object], valuation: dict[str, object]) -> dict[str, Optional[Decimal]]:
    one_month = momentum.get("one_month_return")
    three_month = momentum.get("three_month_return")
    value_change = momentum.get("trading_value_change")
    foreign_intensity = flows.get("foreign_intensity")
    per_z = valuation.get("per_zscore")
    pbr_z = valuation.get("pbr_zscore")
    industry_per = valuation.get("industry_per")
    per = valuation.get("per")

    z_values = [Decimal(str(value)) for value in (per_z, pbr_z) if value is not None]
    valuation_pressure = sum(z_values) / Decimal(len(z_values)) if z_values else Decimal("0")
    relative_per = None
    if per is not None and industry_per not in (None, 0):
        relative_per = (Decimal(str(per)) / Decimal(str(industry_per)) - Decimal("1")) * Decimal("100")

    rate = _bounded(-valuation_pressure * Decimal("12") - (Decimal(str(relative_per)) / Decimal("8") if relative_per is not None else Decimal("0")))
    fx = _bounded((Decimal(str(foreign_intensity)) if foreign_intensity is not None else Decimal("0")) + (Decimal(str(three_month)) / Decimal("10") if three_month is not None else Decimal("0")))
    commodity = _bounded((Decimal(str(value_change)) / Decimal("4") if value_change is not None else Decimal("0")) - valuation_pressure)
    exports = _bounded((Decimal(str(three_month)) / Decimal("3") if three_month is not None else Decimal("0")) + (Decimal(str(one_month)) / Decimal("5") if one_month is not None else Decimal("0")))

    return {
        "interest_rate": rate,
        "fx_usdkrw": fx,
        "commodity": commodity,
        "exports": exports,
    }


def _flows(db: Session, code: str, prices: list[DailyPrice], naver: dict[str, object]) -> dict[str, object]:
    latest_prices = prices[-20:]
    if not latest_prices:
        if naver.get("flow_days"):
            foreign = naver.get("foreign_net_buy_value")
            institution = naver.get("institution_net_buy_value")
            total_value = naver.get("flow_total_value")
            return {
                "foreign_net_buy_20d": foreign,
                "institution_net_buy_20d": institution,
                "foreign_intensity": _round_decimal(Decimal(str(foreign)) / Decimal(str(total_value)) * 100)
                if foreign is not None and total_value
                else None,
                "institution_intensity": _round_decimal(Decimal(str(institution)) / Decimal(str(total_value)) * 100)
                if institution is not None and total_value
                else None,
            }
        return {
            "foreign_net_buy_20d": None,
            "institution_net_buy_20d": None,
            "foreign_intensity": None,
            "institution_intensity": None,
        }
    first_date = latest_prices[0].trade_date
    flows = list(
        db.scalars(
            select(InvestorFlow)
            .where(InvestorFlow.code == code)
            .where(InvestorFlow.trade_date >= first_date)
        )
    )
    foreign = 0
    institution = 0
    for row in flows:
        value = row.net_buy_value or 0
        if any(kind in row.investor_type for kind in FOREIGN_TYPES):
            foreign += value
        if any(kind in row.investor_type for kind in INSTITUTION_TYPES):
            institution += value

    total_value = sum(row.trading_value or 0 for row in latest_prices)
    if not flows and naver.get("flow_days"):
        foreign = naver.get("foreign_net_buy_value")
        institution = naver.get("institution_net_buy_value")
        total_value = naver.get("flow_total_value")
        return {
            "foreign_net_buy_20d": foreign,
            "institution_net_buy_20d": institution,
            "foreign_intensity": _round_decimal(Decimal(str(foreign)) / Decimal(str(total_value)) * 100)
            if foreign is not None and total_value
            else None,
            "institution_intensity": _round_decimal(Decimal(str(institution)) / Decimal(str(total_value)) * 100)
            if institution is not None and total_value
            else None,
        }

    return {
        "foreign_net_buy_20d": foreign if flows else None,
        "institution_net_buy_20d": institution if flows else None,
        "foreign_intensity": _round_decimal(Decimal(foreign) / Decimal(total_value) * 100) if total_value else None,
        "institution_intensity": _round_decimal(Decimal(institution) / Decimal(total_value) * 100) if total_value else None,
    }


def _sentiment(db: Session, stock: StockMaster, prices: list[DailyPrice], disclosures: dict[str, object]) -> dict[str, object]:
    since = datetime.utcnow() - timedelta(days=30)
    query = stock.name
    items = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= since)
            .where((NewsItem.title.contains(query)) | (NewsItem.summary.contains(query)))
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
            .limit(80)
        )
    )
    naver_news = _naver_item_news(stock.code)
    if not items and naver_news:
        positive = 0
        negative = 0
        neutral = 0
        latest_items: list[dict[str, object]] = []
        for item in naver_news:
            score = _keyword_score(str(item["title"]))
            if score > 0:
                positive += 1
            elif score < 0:
                negative += 1
            else:
                neutral += 1
            latest_items.append({**item, "impact": _keyword_impact(score)})
        total = positive + negative + neutral
        score_value = _round_decimal((Decimal(positive - negative) / Decimal(total)) * 100) if total else None
        return {
            "score": score_value,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "latest_items": latest_items[:10],
        }

    positive = 0
    negative = 0
    neutral = 0
    scored_items: list[tuple[NewsItem, int]] = []
    for item in items:
        score = _keyword_score(f"{item.title} {item.summary or ''}")
        if score > 0:
            positive += 1
        elif score < 0:
            negative += 1
        else:
            neutral += 1
        scored_items.append((item, score))

    if not scored_items:
        latest = prices[-1] if prices else None
        previous = _nth_from_end(prices, 1)
        change_rate = _rate(latest.close if latest else None, previous.close if previous else None)
        disclosure_score = (disclosures.get("positive_count") or 0) - (disclosures.get("negative_count") or 0)
        fallback_score = Decimal("0")
        if change_rate is not None:
            fallback_score += Decimal(str(change_rate))
        fallback_score += Decimal(disclosure_score) * Decimal("10")
        if fallback_score > 0:
            positive = 1
        elif fallback_score < 0:
            negative = 1
        else:
            neutral = 1
        return {
            "score": _bounded(fallback_score),
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "latest_items": [
                _event_row(
                    "최근 종목 뉴스 없음",
                    "price/disclosure",
                    None,
                    datetime.combine(latest.trade_date, datetime.min.time()) if latest else None,
                )
            ],
        }

    total = positive + negative + neutral
    score_value = _round_decimal((Decimal(positive - negative) / Decimal(total)) * 100) if total else None
    return {
        "score": score_value,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
        "latest_items": [
            _event_row(
                item.title,
                item.press_name or item.source,
                item.detail_url,
                item.published_at,
                _keyword_impact(score),
            )
            for item, score in scored_items[:10]
        ],
    }


def build_stock_dashboard(db: Session, code: str, refresh_live: bool = False) -> Optional[dict[str, object]]:
    stock = db.get(StockMaster, code)
    if not stock:
        return None

    price_rows = _prices(db, code)
    naver = _naver_snapshot(code, refresh=refresh_live)
    revisions = _research_revision(db, code, naver)
    surprise = _disclosure_events(db, code, SURPRISE_WORDS, naver)
    guidance = _disclosure_events(db, code, GUIDANCE_WORDS, fallback_to_recent=True)
    momentum = _momentum(price_rows)
    chart_analysis = _chart_analysis(price_rows)
    flows = _flows(db, code, price_rows, naver)
    valuation = _valuation(naver)
    sentiment = _sentiment(db, stock, price_rows, surprise)
    macro_sensitivity = _macro_sensitivity(momentum, flows, valuation)

    return {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "as_of": _now_kst(),
        "company_profile": company_profile_payload(db, stock),
        "quote": _quote(price_rows, naver, prefer_live=refresh_live),
        "revisions": revisions,
        "surprise": surprise,
        "guidance": guidance,
        "momentum": momentum,
        "chart_analysis": chart_analysis,
        "flows": flows,
        "valuation": valuation,
        "macro_sensitivity": macro_sensitivity,
        "sentiment": sentiment,
        "coverage": {
            "price": bool(price_rows),
            "investor_flow": flows["foreign_net_buy_20d"] is not None or flows["institution_net_buy_20d"] is not None,
            "research_proxy": revisions["report_count_90d"] > 0,
            "disclosure": surprise.get("all_count", 0) > 0 or guidance.get("all_count", 0) > 0,
            "news": bool(sentiment["latest_items"]),
            "valuation": valuation["per"] is not None or valuation["pbr"] is not None,
            "macro_sensitivity": any(value is not None for value in macro_sensitivity.values()),
        },
    }
