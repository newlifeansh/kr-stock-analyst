"""Versioned KRX regular-only prices, independent of mutable display candles.

An exchange selector is not a session selector after the KRX after-market
launch. Evidence is append-only; ambiguous or incomplete inputs cannot silently
fall back to an all-session daily candle. Legacy prices are never overwritten.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo
import zlib

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, SignalSessionPrice
from app.services.market_calendar import is_scheduled_korea_market_session_date

KST = ZoneInfo("Asia/Seoul")
# v1 local prototype assumed a counter reset at the date boundary. Source
# comparison disproved that assumption for opening cumulative turnover.
# Retain its evidence but never select it for the corrected candidate.
REGULAR_PRICE_BASIS = "krx-regular-session-v4-candidate"
REGULAR_PRICE_EFFECTIVE_DATE = date(2026, 9, 14)
REGULAR_PRICE_SOURCE = "kis_dated_minutes:FHKST03010230:J"
_VALIDATED_EVIDENCE_CACHE_MAX_BYTES = 64 * 1024 * 1024
_validated_evidence_cache: OrderedDict[tuple[Any, ...], bytes] = OrderedDict()
_validated_evidence_cache_bytes = 0
_validated_evidence_cache_lock = Lock()
PRICE_FIELDS = ("open", "high", "low", "close", "volume", "trading_value")
NAVER_REGULAR_COVERAGE_BASIS = (
    "naver_38_buckets_with_complete_opening_volume_anchor"
)
NAVER_MINUTE_OPENING_COVERAGE_BASIS = (
    "naver_38_buckets_and_1m_delayed_open_volume_reconciliation"
)
THIRD_SOURCE_BUCKET_OPEN_COVERAGE_BASIS = (
    "naver_1m_volume_and_yahoo_1m_halt_bucket_open_corroboration"
)
NAVER_COMPLETE_MINUTE_PATH_BASIS = "naver_full_day_1m_path_corroboration"
THIRD_SOURCE_MINUTE_OPEN_BASIS = "yahoo_1m_disputed_minute_open_corroboration"
TOSS_DATED_MINUTE_PATH_BASIS = "toss_krx_dated_1m_full_path_corroboration"
TOSS_AUCTION_RECONCILIATION_BASIS = (
    TOSS_DATED_MINUTE_PATH_BASIS + "+kis_j_daily_verified_auction_separation"
)
TOSS_DELAYED_AUCTION_BASIS = (
    TOSS_DATED_MINUTE_PATH_BASIS + "+kis_1532_delayed_closing_auction"
)
NAVER_REGULAR_COVERAGE_BASIS_ALIASES = frozenset(
    {
        NAVER_REGULAR_COVERAGE_BASIS,
        (
            "naver_regular_buckets_with_complete_opening_volume_anchor_"
            "and_confirmed_empty_intervals"
        ),
    }
)
NAVER_SPARSE_PATH_COVERAGE_BASES = NAVER_REGULAR_COVERAGE_BASIS_ALIASES | frozenset({
    NAVER_MINUTE_OPENING_COVERAGE_BASIS,
    NAVER_MINUTE_OPENING_COVERAGE_BASIS + "+" + THIRD_SOURCE_BUCKET_OPEN_COVERAGE_BASIS,
    NAVER_COMPLETE_MINUTE_PATH_BASIS,
    NAVER_COMPLETE_MINUTE_PATH_BASIS + "+" + THIRD_SOURCE_MINUTE_OPEN_BASIS,
    TOSS_DATED_MINUTE_PATH_BASIS,
    TOSS_AUCTION_RECONCILIATION_BASIS,
    TOSS_DELAYED_AUCTION_BASIS,
})


class UnverifiedRegularSessionPrice(RuntimeError):
    pass


def verified_revised_dated_kis_rows(
    trade_date: date,
    original_rows: list[dict[str, Any]],
    complete_rows: list[dict[str, Any]],
    alternate_rows: list[dict[str, Any]],
    *,
    original_baseline: dict[str, Any] | None,
    complete_baseline: dict[str, Any] | None,
    code: str | None = None,
    toss_dated_minute_proof: dict[str, Any] | None = None,
    yahoo_minute_proof: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Accept a historical KIS correction with cursor or independent consensus.

    KIS can return different minute OHLCV for the same date when the first
    query cursor is 15:30 versus 15:31. The regular collector starts at 15:31;
    the historical chart starts at 15:30. Cursor disagreement is publishable
    only for one OHLC-only minute independently confirmed by both Toss and
    Yahoo; the original monetary boundary must remain unchanged.
    """
    target = trade_date.strftime("%Y%m%d")
    if complete_baseline != original_baseline or original_baseline is None:
        raise ValueError("dated KIS opening boundary changed")

    def regular(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(rows, list) or not rows:
            raise ValueError("dated KIS path missing")
        stamps = []
        for row in rows:
            if not isinstance(row, dict) or row.get("trade_date") != target:
                raise ValueError("dated KIS row identity mismatch")
            stamp = str(row.get("trade_time") or "")
            if len(stamp) != 6 or not stamp.isdigit():
                raise ValueError("dated KIS minute timestamp invalid")
            stamps.append(stamp)
        if any(left >= right for left, right in zip(stamps, stamps[1:])):
            raise ValueError("dated KIS path ordering invalid")
        return [row for row in rows if "090000" <= row["trade_time"] <= "153000"]

    original = regular(original_rows)
    complete = regular(complete_rows)
    alternate = regular(alternate_rows)
    if complete != alternate:
        if (
            not code or original != alternate
            or not isinstance(toss_dated_minute_proof, dict)
            or not isinstance(yahoo_minute_proof, dict)
            or len(complete) != len(alternate)
            or [row["trade_time"] for row in complete]
               != [row["trade_time"] for row in alternate]
        ):
            raise ValueError("dated KIS cursor paths disagree")
        changed = [(old, new) for old, new in zip(alternate, complete) if old != new]
        if len(changed) != 1:
            raise ValueError("dated KIS cursor paths disagree")
        old, new = changed[0]
        if (
            {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
            != {"open", "low"}
            or any(old.get(key) != new.get(key) for key in
                   ("trade_date", "trade_time", "high", "price", "volume", "trading_value"))
        ):
            raise ValueError("dated KIS cursor revision is not OHLC-only")
        independent = _verified_yahoo_minute_rows(
            code, trade_date, yahoo_minute_proof, (new["trade_time"],)
        )[new["trade_time"]]
        if any(_integer(independent[yahoo_key], positive=True) != _integer(new[kis_key], positive=True)
               for yahoo_key, kis_key in (("open", "open"), ("high", "high"),
                                          ("low", "low"), ("close", "price"))):
            raise ValueError("Yahoo minute disagrees with revised KIS OHLC")
        candles = toss_dated_minute_proof.get("candles")
        expected_stamp = (
            datetime.combine(trade_date, datetime.strptime(new["trade_time"], "%H%M%S").time(), KST)
            + timedelta(minutes=1)
        ).isoformat()
        matching = [candle for candle in candles if isinstance(candle, dict)
                    and candle.get("dt") == expected_stamp] if isinstance(candles, list) else []
        if (
            toss_dated_minute_proof.get("code") != code
            or toss_dated_minute_proof.get("date") != trade_date.isoformat()
            or toss_dated_minute_proof.get("exchange") != "krx"
            or toss_dated_minute_proof.get("interval") != "1m"
            or toss_dated_minute_proof.get("use_adjusted_rate") is not False
            or len(matching) != 1
            or any(_integer(matching[0][toss_key], positive=True) != _integer(new[kis_key], positive=True)
                   for toss_key, kis_key in (("open", "open"), ("high", "high"),
                                             ("low", "low"), ("close", "price"),
                                             ("volume", "volume")))
        ):
            raise ValueError("Toss minute disagrees with revised KIS OHLCV")
    if complete == original:
        raise ValueError("dated KIS requery did not revise a regular minute")
    if [row for row in complete_rows if row["trade_time"] < "090000"] != [
        row for row in original_rows if row["trade_time"] < "090000"
    ]:
        raise ValueError("dated KIS preopen rows changed")
    return complete_rows


def _verified_yahoo_minute_rows(
    code: str, trade_date: date, proof: dict[str, Any], times: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    """Check the dated third-source identity and exact requested 1m bars."""
    if not isinstance(proof, dict):
        raise ValueError("dated Yahoo minute source missing")
    parsed_url = urlparse(str(proof.get("url") or ""))
    params = parse_qs(parsed_url.query)
    expected_start = int(datetime.combine(trade_date, time(8, 50), KST).timestamp())
    expected_end = int(datetime.combine(trade_date, time(16, 50), KST).timestamp())
    raw_hash = proof.get("raw_sha256")
    if (
        set(proof) != {"code", "date", "ticker", "url", "status", "raw_sha256", "meta", "rows"}
        or proof.get("code") != code or proof.get("date") != trade_date.isoformat()
        or proof.get("ticker") != f"{code}.KS" or proof.get("status") != 200
        or parsed_url.scheme != "https" or parsed_url.netloc != "query1.finance.yahoo.com"
        or parsed_url.path != f"/v8/finance/chart/{code}.KS"
        or params != {"period1": [str(expected_start)], "period2": [str(expected_end)], "interval": ["1m"]}
        or not isinstance(raw_hash, str) or len(raw_hash) != 64
        or any(character not in "0123456789abcdef" for character in raw_hash)
        or not isinstance(proof.get("meta"), dict)
        or proof["meta"].get("symbol") != f"{code}.KS"
        or proof["meta"].get("exchangeTimezoneName") != "Asia/Seoul"
        or proof["meta"].get("dataGranularity") != "1m"
        or not isinstance(proof.get("rows"), list)
    ):
        raise ValueError("dated Yahoo minute source identity mismatch")
    rows = proof["rows"]
    if len(rows) != len(times) or {row.get("trade_time") for row in rows if isinstance(row, dict)} != set(times):
        raise ValueError("dated Yahoo minute proof incomplete")
    return {row["trade_time"]: row for row in rows}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _matches_recomputed_evidence(
    stored: dict[str, Any], recomputed: dict[str, Any]
) -> bool:
    """Compare evidence while retaining append-only coverage-label aliases.

    The coverage wording changed without a price-basis version change during
    the halt-interval rollout. Both labels describe the same independently
    verified KIS/Naver contract; hashes and every other evidence field remain
    exact. Treating only this label as an alias keeps records written before
    and during that rollout readable without weakening integrity checks.
    """
    if stored == recomputed:
        return True
    if (
        stored.get("coverage_basis") not in NAVER_REGULAR_COVERAGE_BASIS_ALIASES
        or recomputed.get("coverage_basis")
        not in NAVER_REGULAR_COVERAGE_BASIS_ALIASES
    ):
        return False
    return {
        **stored,
        "coverage_basis": NAVER_REGULAR_COVERAGE_BASIS,
    } == {
        **recomputed,
        "coverage_basis": NAVER_REGULAR_COVERAGE_BASIS,
    }


def _integer(value: Any, *, positive: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a price")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid non-negative integer") from exc
    if not number.is_finite() or number != number.to_integral_value() or number < (1 if positive else 0):
        raise ValueError("invalid non-negative integer")
    return int(number)


def _verified_toss_auction_reconciliation(
    code: str, trade_date: date, regular: list[dict[str, Any]],
    auction: dict[str, Any], chart_auction: dict[str, Any], proof: dict[str, Any],
) -> dict[str, Any]:
    """Repair a KIS 15:30 undercount when dated feeds separate later trades.

    KIS's J daily total includes KRX after-market trading. Therefore its excess
    volume is a closing-auction correction only when both dated paths and the
    daily counters reconcile the auction separately from all later trades.
    """
    if isinstance(proof, dict) and proof.get("kis_late_pages") is not None:
        return _verified_toss_auction_with_postmarket(
            code, trade_date, regular, auction, chart_auction, proof,
        )
    target = trade_date.strftime("%Y%m%d")
    day = trade_date.isoformat()
    if not isinstance(proof, dict) or proof.get("code") != code or proof.get("trade_date") != day:
        raise ValueError("closing auction reconciliation identity mismatch")
    daily = proof.get("kis_daily")
    late = proof.get("kis_late")
    toss_late = proof.get("toss_late")
    if not all(isinstance(item, dict) for item in (daily, late, toss_late)):
        raise ValueError("closing auction reconciliation sources missing")
    if (
        daily.get("market") != "J" or daily.get("tr_id") != "FHKST03010100"
        or daily.get("code") != code or daily.get("requested_date") != target
        or not isinstance(daily.get("row"), dict)
        or daily["row"].get("stck_bsop_date") != target
    ):
        raise ValueError("dated KRX daily source identity mismatch")
    kis_request = late.get("request")
    kis_rows = late.get("output2")
    if (
        late.get("code") != code or late.get("date") != target or late.get("rt_cd") != "0"
        or not isinstance(kis_request, dict)
        or kis_request.get("FID_COND_MRKT_DIV_CODE") != "J"
        or kis_request.get("FID_INPUT_ISCD") != code
        or kis_request.get("FID_INPUT_DATE_1") != target
        or kis_request.get("FID_INPUT_HOUR_1") != "200000"
        or not isinstance(kis_rows, list) or len(kis_rows) != 120
    ):
        raise ValueError("dated KRX after-market source identity mismatch")
    stamps = []
    for row in kis_rows:
        if not isinstance(row, dict) or row.get("stck_bsop_date") != target:
            raise ValueError("dated KRX after-market row date mismatch")
        stamp = str(row.get("stck_cntg_hour") or "")
        if len(stamp) != 6 or not stamp.isdigit():
            raise ValueError("dated KRX after-market row time invalid")
        stamps.append(stamp)
    if stamps[0] != "153000" or any(a <= b for a, b in zip(stamps, stamps[1:])):
        raise ValueError("dated KRX after-market trades are not excluded")
    first = kis_rows[0]
    if any(
        _integer(first.get(kis_key), positive=True) != _integer(auction.get(row_key), positive=True)
        for kis_key, row_key in (("stck_oprc", "open"), ("stck_hgpr", "high"),
                                 ("stck_lwpr", "low"), ("stck_prpr", "price"),
                                 ("cntg_vol", "volume"), ("acml_tr_pbmn", "trading_value"))
    ):
        raise ValueError("later KIS source conflicts with stored closing trade")
    candles = toss_late.get("candles")
    if (
        toss_late.get("code") != code or toss_late.get("date") != day
        or toss_late.get("http_status") != 200 or toss_late.get("response_code") != "A" + code
        or toss_late.get("exchange") != "krx" or toss_late.get("interval") != "1m"
        or toss_late.get("invest_mode") != "krx" or toss_late.get("use_adjusted_rate") is not False
        or toss_late.get("requested_from") != day + "T20:01:00+09:00"
        or not isinstance(candles, list) or len(candles) != 200
    ):
        raise ValueError("independent after-market source identity mismatch")
    chart_stamps = []
    for candle in candles:
        if not isinstance(candle, dict):
            raise ValueError("invalid independent after-market candle")
        stamp = datetime.fromisoformat(str(candle.get("dt") or ""))
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(hours=9) or stamp.date() != trade_date:
            raise ValueError("independent after-market candle date mismatch")
        chart_stamps.append(stamp)
    if (
        chart_stamps[0] != datetime.combine(trade_date, time(15, 30), KST)
        or any(a <= b for a, b in zip(chart_stamps, chart_stamps[1:]))
        or toss_late.get("next") != (chart_stamps[-1] - timedelta(minutes=1)).isoformat()
    ):
        raise ValueError("independent after-market trades are not excluded")
    if any(_integer(auction.get(key), positive=True) != _integer(auction.get("price"), positive=True)
           for key in ("open", "high", "low")):
        raise ValueError("closing auction is not a single-price trade")
    revised_volume = _integer(chart_auction.get("volume"), positive=True)
    old_volume = _integer(auction.get("volume"), positive=True)
    delta = revised_volume - old_volume
    if delta <= 0:
        raise ValueError("closing auction has no verified missing volume")
    daily_row = daily["row"]
    actual = [row for row in regular if _integer(row.get("volume")) > 0]
    expected_ohlc = (
        _integer(actual[0]["open"], positive=True),
        max(_integer(row["high"], positive=True) for row in actual),
        min(_integer(row["low"], positive=True) for row in actual),
        _integer(auction["price"], positive=True),
    )
    if (
        tuple(_integer(daily_row.get(key), positive=True) for key in
              ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr")) != expected_ohlc
        or _integer(daily_row.get("acml_vol"), positive=True)
           != sum(_integer(row["volume"], positive=True) for row in actual) + delta
        or _integer(daily_row.get("acml_tr_pbmn"), positive=True)
           != _integer(auction["trading_value"], positive=True) + delta * expected_ohlc[3]
    ):
        raise ValueError("KRX daily total does not reconcile with the auction correction")
    return {**auction, "volume": revised_volume, "trading_value": _integer(daily_row["acml_tr_pbmn"], positive=True)}


def _verified_toss_auction_with_postmarket(
    code: str, trade_date: date, regular: list[dict[str, Any]],
    auction: dict[str, Any] | None, chart_auction: dict[str, Any], proof: dict[str, Any],
) -> dict[str, Any]:
    """Separate a missing closing execution from fully observed later KRX trades."""
    day = trade_date.isoformat()
    target = trade_date.strftime("%Y%m%d")
    delayed = auction is None
    required_keys = {"code", "trade_date", "kis_daily", "kis_late_pages", "toss_postmarket"}
    if delayed:
        required_keys.add("delayed_kis_auction_time")
    if (
        set(proof) != required_keys or proof["code"] != code or proof["trade_date"] != day
        or (delayed and proof.get("delayed_kis_auction_time") != "153200")
    ):
        raise ValueError("after-market reconciliation identity mismatch")
    daily = proof["kis_daily"]
    pages = proof["kis_late_pages"]
    toss = proof["toss_postmarket"]
    if not isinstance(daily, dict) or not isinstance(pages, list) or not isinstance(toss, dict):
        raise ValueError("after-market reconciliation source missing")
    if (
        daily.get("market") != "J" or daily.get("tr_id") != "FHKST03010100"
        or daily.get("code") != code or daily.get("requested_date") != target
        or not isinstance(daily.get("row"), dict)
        or daily["row"].get("stck_bsop_date") != target
        or not 1 <= len(pages) <= 6
    ):
        raise ValueError("dated KRX daily source identity mismatch")
    kis_rows: list[dict[str, Any]] = []
    cursor = "200000"
    for page in pages:
        request = page.get("request") if isinstance(page, dict) else None
        rows = page.get("output2") if isinstance(page, dict) else None
        if (
            not isinstance(request, dict) or page.get("rt_cd") != "0"
            or request.get("FID_COND_MRKT_DIV_CODE") != "J"
            or request.get("FID_INPUT_ISCD") != code
            or request.get("FID_INPUT_DATE_1") != target
            or request.get("FID_INPUT_HOUR_1") != cursor
            or request.get("FID_PW_DATA_INCU_YN") != "Y"
            or request.get("FID_FAKE_TICK_INCU_YN") != ""
            or not isinstance(rows, list) or len(rows) != 120
        ):
            raise ValueError("dated KRX late-session page identity mismatch")
        stamps = []
        for row in rows:
            if not isinstance(row, dict) or row.get("stck_bsop_date") != target:
                raise ValueError("dated KRX late-session row identity mismatch")
            stamp = str(row.get("stck_cntg_hour") or "")
            if len(stamp) != 6 or not stamp.isdigit() or stamp > cursor:
                raise ValueError("dated KRX late-session row time invalid")
            stamps.append(stamp)
        if any(left <= right for left, right in zip(stamps, stamps[1:])):
            raise ValueError("dated KRX late-session page ordering invalid")
        kis_rows.extend(rows)
        cursor = (datetime.strptime(stamps[-1], "%H%M%S") - timedelta(minutes=1)).strftime("%H%M%S")
    stamps = [str(row["stck_cntg_hour"]) for row in kis_rows]
    close_time = "153200" if delayed else "153000"
    if (
        any(left <= right for left, right in zip(stamps, stamps[1:]))
        or close_time not in stamps or stamps[-1] >= close_time
        or stamps[0] > "195900"
        or (delayed and any("153000" <= stamp < close_time for stamp in stamps))
    ):
        raise ValueError("dated KRX late-session path does not reach closing trade")
    close_row = kis_rows[stamps.index(close_time)]
    if delayed:
        if any(
            _integer(close_row.get(kis_key), positive=True)
            != _integer(chart_auction.get(chart_key), positive=True)
            for kis_key, chart_key in (("stck_oprc", "open"), ("stck_hgpr", "high"),
                                       ("stck_lwpr", "low"), ("stck_prpr", "close"),
                                       ("cntg_vol", "volume"))
        ):
            raise ValueError("delayed KIS closing print conflicts with dated chart")
    elif any(
        _integer(close_row.get(kis_key), positive=True) != _integer(auction.get(row_key), positive=True)
        for kis_key, row_key in (("stck_oprc", "open"), ("stck_hgpr", "high"),
                                 ("stck_lwpr", "low"), ("stck_prpr", "price"),
                                 ("cntg_vol", "volume"), ("acml_tr_pbmn", "trading_value"))
    ):
        raise ValueError("later KIS source conflicts with stored closing trade")
    after = [row for row in kis_rows if row["stck_cntg_hour"] > close_time]
    if not after or any(not "160000" <= row["stck_cntg_hour"] <= "195900" for row in after):
        raise ValueError("late-session trades outside supported window")
    if (
        toss.get("code") != code or toss.get("date") != day
        or toss.get("exchange") != "krx" or toss.get("interval") != "1m"
        or toss.get("invest_mode") != "krx" or toss.get("use_adjusted_rate") is not False
        or toss.get("error") is not None
    ):
        raise ValueError("independent late-session source identity mismatch")
    toss_pages = toss.get("pages")
    candles = toss.get("candles")
    if (
        not isinstance(toss_pages, list) or len(toss_pages) != 2
        or any(not isinstance(page, dict) or page.get("http_status") != 200
               or page.get("response_code") != "A" + code
               or page.get("exchange") != "krx" or page.get("returned_count") != 200
               for page in toss_pages)
        or toss_pages[0].get("requested_from") != day + "T20:01:00+09:00"
        or toss_pages[1].get("requested_from") != toss_pages[0].get("next")
        or toss_pages[0].get("next") != day + "T16:40:00+09:00"
        or toss_pages[1].get("next") != day + "T13:20:00+09:00"
        or not isinstance(candles, list) or len(candles) != 271
    ):
        raise ValueError("independent late-session pagination incomplete")
    chart: dict[str, dict[str, Any]] = {}
    for i, candle in enumerate(candles):
        if not isinstance(candle, dict):
            raise ValueError("invalid independent late-session candle")
        stamp = datetime.fromisoformat(str(candle.get("dt") or ""))
        expected = datetime.combine(trade_date, time(20), KST) - timedelta(minutes=i)
        if stamp != expected:
            raise ValueError("independent late-session minute path incomplete")
        chart[stamp.strftime("%H%M%S")] = candle
    if any(
        _integer(chart["153000"].get(key), positive=True)
        != _integer(chart_auction.get(key), positive=True)
        for key in ("open", "high", "low", "close", "volume")
    ):
        raise ValueError("independent late-session auction conflicts with dated chart")
    after_by_time = {row["stck_cntg_hour"]: row for row in after}
    for i in range(270):
        stamp = datetime.combine(trade_date, time(15, 30), KST) + timedelta(minutes=i)
        kis_stamp = stamp.strftime("%H%M%S")
        chart_stamp = (stamp + timedelta(minutes=1)).strftime("%H%M%S")
        row = after_by_time.get(kis_stamp)
        candle = chart[chart_stamp]
        volume = _integer(candle.get("volume"))
        if volume != (_integer(row.get("cntg_vol"), positive=True) if row else 0):
            raise ValueError("independent late-session minute volume conflicts with KIS")
        if row and any(
            _integer(row.get(kis_key), positive=True) != _integer(candle.get(chart_key), positive=True)
            for kis_key, chart_key in (("stck_oprc", "open"), ("stck_hgpr", "high"),
                                       ("stck_lwpr", "low"), ("stck_prpr", "close"))
        ):
            raise ValueError("independent late-session minute OHLC conflicts with KIS")
    auction_price = _integer(close_row["stck_prpr"], positive=True) if delayed else _integer(auction["price"], positive=True)
    if any(
        _integer(close_row.get(key), positive=True) != auction_price
        for key in ("stck_oprc", "stck_hgpr", "stck_lwpr")
    ):
        raise ValueError("closing auction is not single-price")
    actual = [row for row in regular if _integer(row.get("volume")) > 0]
    if not actual:
        raise ValueError("regular session has no earlier trade")
    if delayed:
        delayed_volume = _integer(close_row["cntg_vol"], positive=True)
        delta = delayed_volume
        corrected_cash = _integer(close_row["acml_tr_pbmn"], positive=True)
        if corrected_cash != _integer(actual[-1]["trading_value"], positive=True) + delayed_volume * auction_price:
            raise ValueError("delayed KIS closing print cash does not reconcile")
    else:
        delta = _integer(chart_auction.get("volume"), positive=True) - _integer(auction.get("volume"), positive=True)
        if delta <= 0:
            raise ValueError("closing auction has no verified missing volume")
        corrected_cash = _integer(auction["trading_value"], positive=True) + delta * auction_price
    prior_cash = corrected_cash
    for row in reversed(after):
        volume = _integer(row["cntg_vol"], positive=True)
        cash = _integer(row["acml_tr_pbmn"], positive=True)
        if not volume * _integer(row["stck_lwpr"], positive=True) <= cash - prior_cash <= volume * _integer(row["stck_hgpr"], positive=True):
            raise ValueError("KIS late-session cumulative money discontinuity")
        prior_cash = cash
    daily_row = daily["row"]
    expected_ohlc = (
        _integer(actual[0]["open"], positive=True),
        max([_integer(row["high"], positive=True) for row in actual] + [auction_price]),
        min([_integer(row["low"], positive=True) for row in actual] + [auction_price]),
        auction_price,
    )
    if (
        tuple(_integer(daily_row.get(key), positive=True) for key in
              ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr")) != expected_ohlc
        or _integer(daily_row.get("acml_vol"), positive=True)
           != sum(_integer(row["volume"], positive=True) for row in actual) + delta
              + sum(_integer(row["cntg_vol"], positive=True) for row in after)
        or _integer(daily_row.get("acml_tr_pbmn"), positive=True) != prior_cash
    ):
        raise ValueError("KRX daily counters do not reconcile with both sessions")
    if delayed:
        return {
            "trade_date": target, "trade_time": "153000", "open": auction_price,
            "high": auction_price, "low": auction_price, "price": auction_price,
            "volume": _integer(close_row["cntg_vol"], positive=True),
            "trading_value": corrected_cash,
        }
    return {**auction, "volume": _integer(chart_auction["volume"], positive=True), "trading_value": corrected_cash}


def _verified_adjacent_minute_volume_shift(
    code: str, trade_date: date, regular: list[dict[str, Any]],
    chart: dict[str, dict[str, Any]], proof: dict[str, Any],
) -> set[str]:
    """Allow a bounded two-minute trade allocation dispute with three-source totals."""
    if (
        set(proof) != {"code", "trade_date", "first_time", "yahoo_minute_proof"}
        or proof.get("code") != code or proof.get("trade_date") != trade_date.isoformat()
        or not isinstance(proof.get("first_time"), str)
        or len(proof["first_time"]) != 6 or not proof["first_time"].isdigit()
        or not "090000" <= proof["first_time"] < "151900"
    ):
        raise ValueError("adjacent minute volume proof identity mismatch")
    first_time = proof["first_time"]
    first = datetime.combine(trade_date, datetime.strptime(first_time, "%H%M%S").time(), KST)
    times = (first_time, (first + timedelta(minutes=1)).strftime("%H%M%S"))
    independent = _verified_yahoo_minute_rows(
        code, trade_date, proof["yahoo_minute_proof"], times
    )
    kis = {row["trade_time"]: row for row in regular}
    prior = next((row for row in reversed(regular) if row["trade_time"] < first_time), None)
    if prior is None or any(stamp not in kis for stamp in times):
        raise ValueError("adjacent minute KIS path incomplete")
    source_volumes = []
    chart_volumes = []
    yahoo_volumes = []
    previous_cash = _integer(prior["trading_value"], positive=True)
    for stamp in times:
        row = kis[stamp]
        chart_stamp = (
            datetime.combine(trade_date, datetime.strptime(stamp, "%H%M%S").time(), KST)
            + timedelta(minutes=1)
        ).strftime("%H%M%S")
        candle = chart.get(chart_stamp)
        yahoo = independent[stamp]
        if candle is None:
            raise ValueError("adjacent minute Toss path incomplete")
        volume = _integer(row["volume"], positive=True)
        source_volumes.append(volume)
        chart_volumes.append(_integer(candle.get("volume"), positive=True))
        yahoo_volumes.append(_integer(yahoo.get("volume"), positive=True))
        if any(
            _integer(yahoo.get(yahoo_key), positive=True) != _integer(row.get(kis_key), positive=True)
            for yahoo_key, kis_key in (("open", "open"), ("high", "high"),
                                       ("low", "low"), ("close", "price"))
        ):
            raise ValueError("adjacent minute Yahoo OHLC conflicts with KIS")
        cash = _integer(row["trading_value"], positive=True)
        if not volume * _integer(row["low"], positive=True) <= cash - previous_cash <= volume * _integer(row["high"], positive=True):
            raise ValueError("adjacent minute KIS monetary path conflicts with volume")
        previous_cash = cash
    shift = chart_volumes[0] - source_volumes[0]
    if (
        not shift or abs(shift) > 10
        or chart_volumes[1] - source_volumes[1] != -shift
        or sum(yahoo_volumes) != sum(source_volumes)
    ):
        raise ValueError("adjacent minute volumes do not reconcile")
    return set(times)


def _verified_toss_dated_minute_path(
    code: str, trade_date: date, regular: list[dict[str, Any]], proof: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None]:
    """Corroborate every KIS minute against a complete dated KRX chart.

    Toss stamps continuous trades at the minute end, one minute after the KIS
    stamp. The 15:30 auction uses the same stamp in both feeds. The public
    chart can include later trading in its 15:30 volume. A volume mismatch
    requires separate dated proof that all later KRX trades are accounted for
    and that the KRX daily counters reconcile to the corrected auction.
    """
    day = trade_date.isoformat()
    if (
        not isinstance(proof, dict) or proof.get("code") != code
        or proof.get("date") != day or proof.get("exchange") != "krx"
        or proof.get("interval") != "1m" or proof.get("invest_mode") != "krx"
        or proof.get("use_adjusted_rate") is not False or proof.get("error") is not None
    ):
        raise ValueError("dated minute source identity mismatch")
    pages = proof.get("pages")
    if (
        not isinstance(pages, list) or len(pages) != 2
        or any(not isinstance(page, dict) or page.get("http_status") != 200
               or page.get("returned_count") != 200 for page in pages)
        or pages[0].get("requested_from") != day + "T15:31:00+09:00"
        or pages[1].get("requested_from") != pages[0].get("next")
    ):
        raise ValueError("dated minute pagination is incomplete")
    candles = proof.get("candles")
    if not isinstance(candles, list) or len(candles) not in (390, 391):
        raise ValueError("dated minute path is incomplete")
    stamps = []
    for candle in candles:
        if not isinstance(candle, dict):
            raise ValueError("invalid dated minute candle")
        stamp = datetime.fromisoformat(str(candle.get("dt") or ""))
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(hours=9) or stamp.date() != trade_date or stamp.second or stamp.microsecond:
            raise ValueError("dated minute timestamp mismatch")
        stamps.append(stamp)
    if any(left <= right for left, right in zip(stamps, stamps[1:])):
        raise ValueError("dated minute path is not strictly descending")
    by_time = {stamp.strftime("%H%M%S"): candle for stamp, candle in zip(stamps, candles)}
    expected = [
        (datetime.combine(trade_date, time(9, 1), KST) + timedelta(minutes=i)).strftime("%H%M%S")
        for i in range(390)
    ]
    if set(by_time) != set(expected) | ({"153100"} if len(candles) == 391 else set()):
        raise ValueError("dated minute path has missing or extra bars")
    for stamp in ["152100", "152200", "152300", "152400", "152500", "152600", "152700", "152800", "152900", "153100"]:
        if stamp in by_time and _integer(by_time[stamp].get("volume")) != 0:
            raise ValueError("dated minute auction window has unverified trades")
    kis = {row["trade_time"]: row for row in regular}
    shifted = (
        _verified_adjacent_minute_volume_shift(
            code, trade_date, regular, by_time, proof["minute_volume_reallocation"]
        )
        if proof.get("minute_volume_reallocation") is not None else set()
    )
    observed_shift: set[str] = set()
    if any("152000" <= stamp < "153000" and _integer(row.get("volume")) > 0 for stamp, row in kis.items()):
        raise ValueError("dated minute proof cannot classify 15:20 trade")
    for i in range(380):
        stamp = (datetime.combine(trade_date, time(9), KST) + timedelta(minutes=i)).strftime("%H%M%S")
        chart_stamp = expected[i]
        candle = by_time[chart_stamp]
        source = kis.get(stamp)
        source_volume = _integer(source.get("volume")) if source is not None else 0
        chart_volume = _integer(candle.get("volume"))
        if chart_volume != source_volume and stamp not in shifted:
            raise ValueError("dated minute volume conflicts with KIS")
        if chart_volume != source_volume:
            observed_shift.add(stamp)
        if chart_volume:
            if source is None or any(
                _integer(source.get(left), positive=True) != _integer(candle.get(right), positive=True)
                for left, right in (("open", "open"), ("high", "high"), ("low", "low"), ("price", "close"))
            ):
                raise ValueError("dated minute OHLC conflicts with KIS")
    if observed_shift != shifted:
        raise ValueError("unneeded adjacent minute volume proof")
    auction = kis.get("153000")
    chart_auction = by_time["153000"]
    if auction is None or _integer(auction.get("volume")) == 0:
        if proof.get("auction_reconciliation") is not None:
            raise ValueError("auction correction cannot replace an absent KIS closing trade")
        if _integer(chart_auction.get("volume")) != 0:
            delayed_proof = proof.get("delayed_auction_reconciliation")
            if delayed_proof is not None:
                if auction is not None:
                    prior = next((row for row in reversed(regular) if row["trade_time"] < "153000" and _integer(row.get("volume")) > 0), None)
                    if prior is None or _integer(auction.get("trading_value")) != _integer(prior.get("trading_value")):
                        raise ValueError("zero-volume KIS auction changes cumulative turnover")
                return False, _verified_toss_auction_with_postmarket(
                    code, trade_date, regular, None, chart_auction, delayed_proof,
                )
            raise ValueError("dated minute closing auction conflicts with KIS")
        if proof.get("delayed_auction_reconciliation") is not None:
            raise ValueError("unneeded delayed closing print proof")
        if auction is not None:
            prior = next((row for row in reversed(regular) if row["trade_time"] < "153000" and _integer(row.get("volume")) > 0), None)
            if prior is None or _integer(auction.get("trading_value")) != _integer(prior.get("trading_value")):
                raise ValueError("zero-volume auction changes cumulative turnover")
        return True, None  # Both dated sources omit a closing execution.
    if any(
        _integer(auction.get(left), positive=True) != _integer(chart_auction.get(right), positive=True)
        for left, right in (("open", "open"), ("high", "high"), ("low", "low"), ("price", "close"))
    ):
        raise ValueError("dated minute closing auction conflicts with KIS")
    if proof.get("delayed_auction_reconciliation") is not None:
        raise ValueError("delayed closing print conflicts with stored KIS auction")
    if _integer(auction.get("volume"), positive=True) != _integer(chart_auction.get("volume"), positive=True):
        reconciliation = proof.get("auction_reconciliation")
        if reconciliation is None:
            raise ValueError("dated minute closing auction conflicts with KIS")
        return False, _verified_toss_auction_reconciliation(
            code, trade_date, regular, auction, chart_auction, reconciliation,
        )
    if proof.get("auction_reconciliation") is not None:
        raise ValueError("unneeded auction correction proof")
    return False, None


def _corroborated_full_minute_path(
    code: str, trade_date: date, rows: list[dict[str, Any]], proof: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    """Check every executed minute before accepting one independently observed open."""
    naver = proof.get("naver") or {}
    prior = proof.get("prior_path")
    if (
        not isinstance(naver, dict) or naver.get("code") != code
        or naver.get("trade_date") != trade_date.strftime("%Y%m%d")
        or naver.get("periodType") != "day"
        or naver.get("stockExchangeType") != "KRX"
        or not isinstance(prior, list) or not prior
        or proof.get("prior_path_hash") != sha256(_json(prior).encode()).hexdigest()
    ):
        raise ValueError("full minute path source or prior snapshot identity mismatch")
    minute_rows = naver.get("rows")
    if not isinstance(minute_rows, list) or len(minute_rows) != len(rows):
        raise ValueError("independent full minute path coverage is incomplete")
    corrected = [dict(row) for row in rows]
    discrepancy = None
    cumulative_offset = None
    running = 0
    previous_time = None
    for row, observed in zip(corrected, minute_rows):
        stamp = str(observed.get("localDateTime") or "")
        if (
            len(stamp) != 14 or not stamp.isdigit()
            or stamp != trade_date.strftime("%Y%m%d") + row["trade_time"]
            or (previous_time is not None and stamp <= previous_time)
        ):
            raise ValueError("independent minute timestamp conflicts with KIS")
        previous_time = stamp
        observed_values = {
            "open": _integer(observed.get("openPrice"), positive=True),
            "high": _integer(observed.get("highPrice"), positive=True),
            "low": _integer(observed.get("lowPrice"), positive=True),
            "price": _integer(observed.get("currentPrice"), positive=True),
        }
        if any(_integer(row.get(key), positive=True) != observed_values[key]
               for key in ("high", "low", "price")):
            raise ValueError("independent minute OHLC conflicts with KIS")
        if _integer(row.get("open"), positive=True) != observed_values["open"]:
            if discrepancy is not None or not (
                observed_values["low"] <= observed_values["open"] <= observed_values["high"]
            ):
                raise ValueError("more than one disputed minute open")
            discrepancy = row["trade_time"]
            row["open"] = observed_values["open"]
        running += _integer(row.get("volume"), positive=True)
        observed_cumulative = _integer(observed.get("accumulatedTradingVolume"), positive=True)
        if cumulative_offset is None:
            cumulative_offset = observed_cumulative - running
            if not 0 <= cumulative_offset <= max(1, _integer(row["volume"]) // 1000):
                raise ValueError("independent minute opening volume offset is unsafe")
        if observed_cumulative != running + cumulative_offset:
            raise ValueError("independent minute volume path conflicts with KIS")
    yahoo = proof.get("yahoo")
    if discrepancy is None:
        if yahoo is not None:
            raise ValueError("unneeded third-source minute proof")
    else:
        if not isinstance(yahoo, dict):
            raise ValueError("disputed minute open lacks a third source")
        bucket_start = str(yahoo.get("bucket_start") or "")
        bucket_end = (
            datetime.strptime(bucket_start, "%H%M%S") + timedelta(minutes=10)
        ).strftime("%H%M%S")
        if (
            yahoo.get("ticker") not in {f"{code}.KS", f"{code}.KQ"}
            or yahoo.get("trade_date") != trade_date.strftime("%Y%m%d")
            or yahoo.get("exchange_timezone") != "Asia/Seoul"
            or yahoo.get("interval") != "1m"
            or not bucket_start <= discrepancy < bucket_end
            or not isinstance(yahoo.get("rows"), list)
        ):
            raise ValueError("third-source minute identity mismatch")
        matches = [item for item in yahoo["rows"] if item.get("trade_time") == discrepancy]
        corrected_row = next(row for row in corrected if row["trade_time"] == discrepancy)
        if (
            len(matches) != 1
            or _integer(matches[0].get("open"), positive=True) != corrected_row["open"]
            or _integer(matches[0].get("close"), positive=True) != corrected_row["price"]
        ):
            raise ValueError("third-source minute open does not corroborate Naver")
    return corrected, discrepancy


def _verified_naver_minute_opening_offset(
    code: str, day: date, regular: list[dict[str, Any]], payload: dict[str, Any],
) -> int:
    """Cross-check the opening ten minutes before accepting an offset.

    The weekly ten-minute chart independently checks later buckets. Restrict
    this extra minute proof to the opening bucket so later transient one-minute
    cumulative-volume display glitches cannot change a matched bucket result.
    """
    opening = [row for row in regular if row["trade_time"] < "091000"]
    if (
        payload.get("code") != code
        or payload.get("trade_date") != day.strftime("%Y%m%d")
        or payload.get("timeframe") != "minute"
        or not isinstance(payload.get("rows"), list)
        or not opening
        or opening[0]["trade_time"] == "090000"
    ):
        raise ValueError("wrong delayed-opening minute source identity")
    minutes = payload["rows"]
    times = [str(row.get("trade_time") or "") for row in minutes]
    expected = [row["trade_time"] for row in opening]
    if times != expected or len(set(times)) != len(times):
        raise ValueError("Naver minute trade timestamps conflict with KIS")
    cumulative = 0
    offset = None
    for kis, naver in zip(opening, minutes):
        if _integer(naver.get("close"), positive=True) != _integer(kis["price"], positive=True):
            raise ValueError("Naver minute close conflicts with KIS")
        cumulative += _integer(kis["volume"], positive=True)
        observed = _integer(naver.get("accumulated_volume")) - cumulative
        if offset is None:
            offset = observed
        if observed < 0 or observed != offset:
            raise ValueError("Naver minute volume delta conflicts with KIS")
    return int(offset)


def _verify_halt_bucket_open(
    code: str, day: date, start_time: str, minutes: list[dict[str, Any]],
    *, cumulative_before: int, offset: int | None, proof: dict[str, Any] | None,
) -> None:
    """Resolve one ten-minute opening-price conflict with two dated minute feeds."""
    if (
        proof is None or offset is None
        or proof.get("code") != code
        or proof.get("trade_date") != day.strftime("%Y%m%d")
        or proof.get("bucket_start") != start_time
        or not isinstance(proof.get("naver_minutes"), list)
        or not isinstance(proof.get("yahoo"), dict)
        or minutes[0]["trade_time"] <= start_time
    ):
        raise ValueError("missing independent halt-bucket opening proof")
    naver = proof["naver_minutes"]
    if [row.get("trade_time") for row in naver] != [row["trade_time"] for row in minutes]:
        raise ValueError("halt-bucket minute timestamps conflict")
    cumulative = cumulative_before
    for kis, other in zip(minutes, naver):
        cumulative += _integer(kis["volume"], positive=True)
        if (
            _integer(other.get("close"), positive=True) != _integer(kis["price"], positive=True)
            or _integer(other.get("accumulated_volume")) - cumulative != offset
        ):
            raise ValueError("halt-bucket minute prices or volume conflict")
    yahoo = proof["yahoo"]
    ticker = str(yahoo.get("ticker") or "")
    bars = yahoo.get("rows")
    if (
        ticker not in (code + ".KS", code + ".KQ")
        or yahoo.get("exchange_timezone") != "Asia/Seoul"
        or yahoo.get("interval") != "1m"
        or yahoo.get("trade_date") != day.strftime("%Y%m%d")
        or yahoo.get("bucket_start") != start_time
        or not isinstance(bars, list) or not bars
        or bars[0].get("trade_time") != minutes[0]["trade_time"]
        or len({bar.get("trade_time") for bar in bars}) != len(bars)
        or [bar.get("trade_time") for bar in bars] != sorted(bar.get("trade_time") for bar in bars)
        or _integer(bars[0].get("open"), positive=True) != _integer(minutes[0]["open"], positive=True)
        or _integer(bars[0].get("close"), positive=True) != _integer(minutes[0]["price"], positive=True)
    ):
        raise ValueError("Yahoo first minute does not corroborate KIS open")


def _verified_naver_closing_auction(
    code: str, day: date, regular: list[dict[str, Any]], payload: dict[str, Any],
    *, verified_opening_offset: int | None = None,
    bucket_open_proof: dict[str, Any] | None = None,
    closing_window_trade: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Verify sparse regular coverage and the presence or absence of an auction.

    Naver's KRX weekly chart has ten-minute buckets. Every observed regular
    bucket before the auction must match KIS OHLC and cumulative volume up to
    a constant pre-open offset. A jointly absent middle bucket is accepted
    only when a later bucket preserves that offset. A positive 15:20 last
    continuous trade needs matching price, volume and turnover from both feeds.
    The 15:30 bucket ends
    before 15:40 after-hours; when present its O/H/L/C must be one price and
    its volume delta strictly positive. Joint KIS/Naver absence preserves the
    last actual regular trade and never fabricates a 15:30 execution.
    """
    if payload.get("code") != code or payload.get("stockExchangeType") != "KRX" or payload.get("periodType") != "week":
        raise ValueError("wrong closing-auction source identity")
    if not regular or not "090000" <= regular[0]["trade_time"] <= "090900":
        raise ValueError("cross-source coverage requires a first-bucket trade anchor")
    delayed_opening_trade = regular[0]["trade_time"] != "090000"
    day_key = day.strftime("%Y%m%d")
    candles = (payload.get("priceInfos") or {}).get(day_key)
    if not isinstance(candles, list):
        raise ValueError("missing dated closing-auction evidence")
    buckets = {}
    for row in candles:
        stamp = str(row.get("localDateTime") or "")
        if not stamp.startswith(day_key) or stamp in buckets:
            raise ValueError("wrong date or duplicate closing-auction bucket")
        buckets[stamp] = row
    cumulative = 0
    offset = None
    last_cumulative = None
    pending_empty_buckets = 0
    proven_open_conflicts = 0
    for index in range(0, 380, 10):
        expected_start = datetime.combine(day, time(9)) + timedelta(minutes=index)
        expected_end = expected_start + timedelta(minutes=10)
        # These bounds are identical for every minute in the bucket. Formatting
        # them inside the predicate multiplies strftime work by ~380 per stock
        # and session during recommendation evidence replay.
        start_time = expected_start.strftime("%H%M%S")
        end_time = expected_end.strftime("%H%M%S")
        minutes = [row for row in regular if start_time <= row["trade_time"] < end_time]
        bucket_key = expected_start.strftime("%Y%m%d%H%M%S")
        bucket = buckets.get(bucket_key)
        if not minutes:
            # A volatility interruption or exchange halt can legitimately
            # leave an entire ten-minute interval without a print. Accept it
            # only when the independent Naver KRX series omits the same
            # bucket and a later observed bucket proves the cumulative-volume
            # offset stayed unchanged. A trailing whole bucket cannot be
            # proven because there is no later pre-auction observation.
            if bucket is not None:
                raise ValueError("KIS empty bucket conflicts with Naver trades")
            if offset is None:
                raise ValueError("closing recovery requires an opening volume anchor")
            pending_empty_buckets += 1
            continue
        if bucket is None:
            raise ValueError("Naver missing a KIS pre-auction bucket")
        actual = [_integer(bucket.get(key), positive=True) for key in ("openPrice", "highPrice", "lowPrice", "currentPrice")]
        expected = [_integer(minutes[0]["open"], positive=True), max(_integer(row["high"], positive=True) for row in minutes), min(_integer(row["low"], positive=True) for row in minutes), _integer(minutes[-1]["price"], positive=True)]
        if actual != expected:
            if (
                actual[1:] != expected[1:]
                or actual[0] == expected[0]
                or not _integer(minutes[0]["low"], positive=True) <= actual[0] <= _integer(minutes[0]["high"], positive=True)
                or proven_open_conflicts
            ):
                raise ValueError("closing source conflicts with KIS pre-auction OHLC")
            _verify_halt_bucket_open(
                code, day, start_time, minutes, cumulative_before=cumulative,
                offset=offset, proof=bucket_open_proof,
            )
            proven_open_conflicts += 1
        cumulative += sum(_integer(row["volume"], positive=True) for row in minutes)
        last_cumulative = _integer(bucket.get("accumulatedTradingVolume"))
        observed_offset = last_cumulative - cumulative
        if offset is None:
            offset = observed_offset
            if delayed_opening_trade and offset != 0 and offset != verified_opening_offset:
                # A later first KIS trade is safe only when Naver's first
                # bucket contains exactly the same total actual volume. Any
                # offset could hide an omitted opening print or pre-open volume.
                raise ValueError(
                    "delayed opening anchor requires zero cross-source volume offset"
                )
        if observed_offset < 0 or observed_offset != offset:
            raise ValueError("closing source conflicts with KIS pre-auction volume")
        pending_empty_buckets = 0
    if pending_empty_buckets:
        raise ValueError("unverified trailing empty pre-auction bucket")
    if bucket_open_proof is not None and proven_open_conflicts != 1:
        raise ValueError("unused halt-bucket opening proof")
    closing_window = buckets.get(day_key + "152000")
    if closing_window_trade is None:
        if closing_window is not None and _integer(closing_window.get("accumulatedTradingVolume")) != last_cumulative:
            raise ValueError("unverified positive-volume closing auction interval")
    else:
        # A minute ending at 15:20 can contain the final continuous-session
        # executions. Require the independent KRX bucket and KIS monetary
        # counter to prove the exact same single-price trade before retaining it.
        price = _integer(closing_window_trade.get("price"), positive=True)
        volume = _integer(closing_window_trade.get("volume"), positive=True)
        if (
            closing_window_trade.get("trade_time") != "152000"
            or closing_window is None
            or any(_integer(closing_window_trade.get(key), positive=True) != price for key in ("open", "high", "low"))
            or any(_integer(closing_window.get(key), positive=True) != price for key in ("openPrice", "highPrice", "lowPrice", "currentPrice"))
            or _integer(closing_window.get("accumulatedTradingVolume")) - int(last_cumulative) != volume
            or _integer(closing_window_trade.get("trading_value")) - _integer(regular[-1].get("trading_value")) != price * volume
        ):
            raise ValueError("closing-window trade conflicts with independent KRX evidence")
    close = buckets.get(day_key + "153000")
    if close is None:
        # Both dated sources omit a positive closing-auction execution. The
        # regular close is therefore the last independently matched trade;
        # do not invent a 15:30 print merely to make the path continuous.
        return None
    prices = [_integer(close.get(key), positive=True) for key in ("openPrice", "highPrice", "lowPrice", "currentPrice")]
    if len(set(prices)) != 1:
        raise ValueError("closing auction is not a single-price print")
    volume = _integer(close.get("accumulatedTradingVolume")) - int(last_cumulative)
    if closing_window_trade is not None:
        volume -= _integer(closing_window_trade.get("volume"), positive=True)
    if volume <= 0:
        raise ValueError("closing auction has no actual volume")
    prior_turnover = closing_window_trade if closing_window_trade is not None else regular[-1]
    return {"trade_date": day_key, "trade_time": "153000",
            "open": prices[0], "high": prices[0], "low": prices[0], "price": prices[0],
            "volume": volume, "trading_value": _integer(prior_turnover["trading_value"]) + prices[0] * volume}


def regular_session_evidence(
    code: str, trade_date: date, rows: list[dict[str, Any]], *, observed_at: datetime,
    preopen_baseline: dict[str, Any] | None = None,
    closing_auction_evidence: dict[str, Any] | None = None,
    minute_coverage_evidence: dict[str, Any] | None = None,
    bucket_open_proof: dict[str, Any] | None = None,
    full_minute_path_proof: dict[str, Any] | None = None,
    toss_dated_minute_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate actual regular trades and preserve the complete source envelope.

    ``trading_value`` in the KIS minute response is cumulative, not minute
    turnover. Its pre-open baseline must be observed; never sum cumulative
    values or use the after-market daily total for an entry liquidity filter.
    """
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    if observed_at.astimezone(KST) < datetime.combine(trade_date, time(15, 31), KST):
        raise ValueError("regular session is not complete")
    if not code or not isinstance(rows, list):
        raise ValueError("code and minute rows are required")
    raw = json.loads(_json(rows))
    result: dict[str, Any] = {
        "code": code, "trade_date": trade_date.isoformat(),
        "basis_version": REGULAR_PRICE_BASIS, "source": REGULAR_PRICE_SOURCE,
        "exchange": "KRX", "session": "regular", "start": "09:00", "end": "15:30",
        "state": "unverified", "reason": None, "prices": None, "turnover_bounds": None,
        "raw_rows": raw, "regular_rows": [], "preopen_baseline": preopen_baseline,
        "closing_auction_evidence": closing_auction_evidence,
        "volume_basis": "sum_actual_regular_minute_volume",
        "trading_value_basis": "closing_cumulative_minus_preopen_cumulative",
        "coverage_basis": "continuous_actual_minutes",
    }
    if minute_coverage_evidence is not None:
        result["minute_coverage_evidence"] = minute_coverage_evidence
    if bucket_open_proof is not None:
        result["bucket_open_proof"] = bucket_open_proof
    if full_minute_path_proof is not None:
        result["full_minute_path_proof"] = full_minute_path_proof
    if toss_dated_minute_proof is not None:
        result["toss_dated_minute_proof"] = toss_dated_minute_proof
    try:
        if toss_dated_minute_proof is not None and any(
            item is not None for item in (
                closing_auction_evidence, minute_coverage_evidence,
                bucket_open_proof, full_minute_path_proof,
            )
        ):
            raise ValueError("dated minute proof conflicts with another path proof")
        parsed = []
        seen = set()
        for row in raw:
            stamp = str(row.get("trade_date") or "").replace("-", "")
            hhmmss = str(row.get("trade_time") or "").zfill(6)
            instant = datetime.strptime(stamp + hhmmss, "%Y%m%d%H%M%S")
            if instant.date() != trade_date or instant.second or hhmmss in seen:
                raise ValueError("wrong date, duplicate or non-minute source row")
            seen.add(hhmmss)
            parsed.append((instant, row))
        parsed.sort(key=lambda pair: pair[0])
        regular = [row for instant, row in parsed if time(9) <= instant.time() <= time(15, 30)]
        if any("152000" < row["trade_time"] < "153000" and _integer(row.get("volume")) > 0 for row in regular):
            raise ValueError("unverified auction-window trade")
        prefix_rows = [row for row in regular if "090000" <= row["trade_time"] <= "151900"]
        actual_prefix = [row for row in prefix_rows if _integer(row.get("volume")) > 0]
        closing_window_trade = next((row for row in regular if row["trade_time"] == "152000" and _integer(row.get("volume")) > 0), None)
        sparse_prefix_verified = False
        verified_no_closing_trade = False
        verified_closing = None
        verified_opening_offset = None
        if toss_dated_minute_proof is not None:
            verified_no_closing_trade, revised_auction = _verified_toss_dated_minute_path(
                code, trade_date, regular, toss_dated_minute_proof,
            )
            sparse_prefix_verified = True
            result["coverage_basis"] = TOSS_DATED_MINUTE_PATH_BASIS
            result["source"] += "+toss_krx_dated_1m"
            if revised_auction is not None:
                if toss_dated_minute_proof.get("delayed_auction_reconciliation") is not None:
                    result["coverage_basis"] = TOSS_DELAYED_AUCTION_BASIS
                    result["source"] += "+kis_1532_delayed_closing_auction"
                else:
                    result["coverage_basis"] = TOSS_AUCTION_RECONCILIATION_BASIS
                    result["source"] += "+kis_j_daily_no_postmarket_auction_correction"
            regular = [
                revised_auction if row["trade_time"] == "153000" and revised_auction is not None else row
                for row in regular
                if not (
                    ("090000" <= row["trade_time"] <= "151900" or row["trade_time"] == "153000")
                    and _integer(row.get("volume")) == 0
                )
            ]
            if revised_auction is not None and not any(row["trade_time"] == "153000" for row in regular):
                regular.append(revised_auction)
        if len(actual_prefix) < 380 and closing_auction_evidence is not None:
            if actual_prefix and actual_prefix[0]["trade_time"] != "090000" and minute_coverage_evidence is not None:
                verified_opening_offset = _verified_naver_minute_opening_offset(
                    code, trade_date, actual_prefix, minute_coverage_evidence
                )
            verified_closing = _verified_naver_closing_auction(
                code, trade_date, actual_prefix, closing_auction_evidence,
                verified_opening_offset=verified_opening_offset,
                bucket_open_proof=bucket_open_proof,
                closing_window_trade=closing_window_trade,
            )
            observed_close = next((row for row in regular if row["trade_time"] == "153000"), None)
            if observed_close is not None and _integer(observed_close.get("volume")) > 0:
                if verified_closing is None or any(
                    _integer(observed_close.get(key)) != _integer(verified_closing[key])
                    for key in ("open", "high", "low", "price", "volume", "trading_value")
                ):
                    raise ValueError("closing source conflicts with actual KIS closing trade")
            elif verified_closing is None:
                verified_no_closing_trade = True
            sparse_prefix_verified = True
            # Keep the persisted identifier stable. The QA contract defines
            # how jointly absent halt intervals are proven; changing this
            # append-only label without a basis-version bump would make older
            # evidence fail deterministic recomputation.
            result["coverage_basis"] = NAVER_REGULAR_COVERAGE_BASIS
            result["source"] += "+naver_krx_regular_coverage"
            if verified_opening_offset:
                result["coverage_basis"] = NAVER_MINUTE_OPENING_COVERAGE_BASIS
                result["source"] += "+naver_1m_delayed_open"
            if bucket_open_proof is not None:
                result["coverage_basis"] += "+" + THIRD_SOURCE_BUCKET_OPEN_COVERAGE_BASIS
                result["source"] += "+yahoo_1m_halt_bucket_open"
            regular = [
                row
                for row in regular
                if not (
                    "090000" <= row["trade_time"] <= "151900"
                    and _integer(row.get("volume")) == 0
                )
            ]
        closing_trade_missing = bool(
            regular
            and (
                regular[-1]["trade_time"] != "153000"
                or _integer(regular[-1].get("volume")) <= 0
            )
        )
        if closing_trade_missing and closing_auction_evidence is not None:
            preauction = [
                row
                for row in regular
                if row["trade_time"] <= "151900"
                and _integer(row.get("volume")) > 0
            ]
            recovered_closing = (
                verified_closing
                if sparse_prefix_verified
                else _verified_naver_closing_auction(
                    code, trade_date, preauction, closing_auction_evidence,
                    closing_window_trade=closing_window_trade,
                )
            )
            regular = preauction + ([closing_window_trade] if closing_window_trade is not None else []) + (
                [recovered_closing] if recovered_closing is not None else []
            )
            if recovered_closing is None:
                verified_no_closing_trade = True
                sparse_prefix_verified = True
                result["coverage_basis"] = NAVER_REGULAR_COVERAGE_BASIS
                result["source"] += "+naver_krx_no_closing_trade"
            else:
                result["source"] += "+naver_krx_closing_auction"
        if (
            not regular
            or (
                regular[0]["trade_time"] != "090000"
                and not sparse_prefix_verified
            )
            or (
                not verified_no_closing_trade
                and regular[-1]["trade_time"] != "153000"
            )
        ):
            raise ValueError("missing regular opening or closing trade")
        executable = []
        for row in regular:
            volume = _integer(row.get("volume"))
            if "152000" <= row["trade_time"] < "153000" and volume == 0:
                continue  # indicative auction prices are not executed trades
            if volume == 0:
                raise ValueError("unverified zero-volume regular minute")
            o, h, l, c = [_integer(row.get(key), positive=True) for key in ("open", "high", "low", "price")]
            if not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError("invalid minute OHLC")
            executable.append(row)
        for prior, following in zip(executable, executable[1:]):
            before = datetime.strptime(prior["trade_time"], "%H%M%S")
            after = datetime.strptime(following["trade_time"], "%H%M%S")
            if after - before != timedelta(minutes=1) and not (
                prior["trade_time"] in {"151900", "152000"} and following["trade_time"] == "153000"
            ) and not sparse_prefix_verified:
                raise ValueError("missing regular minute")
        if full_minute_path_proof is not None:
            executable, disputed_open = _corroborated_full_minute_path(
                code, trade_date, executable, full_minute_path_proof,
            )
            result["coverage_basis"] = NAVER_COMPLETE_MINUTE_PATH_BASIS
            result["source"] += "+naver_full_day_1m"
            if disputed_open is not None:
                result["coverage_basis"] += "+" + THIRD_SOURCE_MINUTE_OPEN_BASIS
                result["source"] += "+yahoo_1m_disputed_open"
        prices = {
            "open": _integer(executable[0]["open"], positive=True),
            "high": max(_integer(row["high"], positive=True) for row in executable),
            "low": min(_integer(row["low"], positive=True) for row in executable),
            "close": _integer(executable[-1]["price"], positive=True),
            "volume": sum(_integer(row["volume"], positive=True) for row in executable),
            "trading_value": None,
        }
        result.update(prices=prices, regular_rows=executable)
        baseline_rows = [row for instant, row in parsed if instant.time() < time(9)]
        if baseline_rows and baseline_rows[-1]["trade_time"] == "085900":
            baseline = _integer(baseline_rows[-1].get("trading_value"))
        elif (
            isinstance(preopen_baseline, dict)
            and preopen_baseline.get("kind") == "observed_day_boundary"
            and preopen_baseline.get("requested_date") == trade_date.strftime("%Y%m%d")
            and preopen_baseline.get("requested_time") == "085900"
            and datetime.strptime(str(preopen_baseline.get("previous_trade_date")), "%Y%m%d").date() < trade_date
            and datetime.strptime(str(preopen_baseline.get("previous_trade_time")), "%H%M%S")
            and preopen_baseline.get("value") in (None, 0)
        ):
            # The endpoint omits pre-open prints even when its cumulative
            # money counter includes them. Date rollover is NOT proof of a
            # zero pre-open monetary baseline. Preserve a rigorous interval
            # using actual first-minute OHLC/volume and later counter deltas.
            first = executable[0]
            first_value = _integer(first.get("trading_value"))
            later_value = _integer(executable[-1].get("trading_value")) - first_value
            first_volume = _integer(first.get("volume"), positive=True)
            lower = _integer(first["low"], positive=True) * first_volume + later_value
            # Pre-open turnover cannot be negative, so the cumulative first
            # value is an additional upper bound on that minute's turnover.
            upper = min(_integer(first["high"], positive=True) * first_volume, first_value) + later_value
            if lower <= 0 or upper < lower:
                raise ValueError("opening cumulative turnover cannot cover actual trades")
            result["turnover_bounds"] = {"lower": lower, "upper": upper, "basis": "actual_first_minute_ohlcv_plus_later_cumulative_deltas"}
            # First validate every subsequent minute independently of the
            # unknown opening counter baseline.
            previous = first_value
            for row in regular[1:]:
                cumulative = _integer(row.get("trading_value"))
                volume = _integer(row.get("volume"))
                if not _integer(row.get("low")) * volume <= cumulative - previous <= _integer(row.get("high")) * volume:
                    raise ValueError("cumulative turnover does not reconcile with actual trades")
                previous = cumulative
            if lower != upper:
                result.update(
                    state="bounded",
                    reason="exact opening turnover unavailable; validated monetary interval only",
                    trading_value_basis="bounded_actual_regular_turnover",
                )
                return result
            baseline = first_value - _integer(first["low"], positive=True) * first_volume
            if baseline < 0:
                raise ValueError("negative preopen cumulative turnover baseline")
        else:
            raise ValueError("missing preopen cumulative turnover baseline")
        previous = baseline
        for row in regular:
            cumulative = _integer(row.get("trading_value"))
            delta = cumulative - previous
            volume = _integer(row.get("volume"))
            # Real monetary turnover must lie within the traded minute range.
            low = _integer(row.get("low"), positive=True) if volume else 0
            high = _integer(row.get("high"), positive=True) if volume else 0
            if not volume * low <= delta <= volume * high:
                raise ValueError("cumulative turnover does not reconcile with actual trades")
            previous = cumulative
        prices["trading_value"] = previous - baseline
        if prices["trading_value"] <= 0:
            raise ValueError("empty regular turnover")
        result["state"] = "ready"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        result["reason"] = str(exc)
    return result


def store_regular_session_evidence(
    db: Session, evidence: dict[str, Any], *, observed_at: datetime,
) -> SignalSessionPrice:
    """Append evidence and an untouched legacy-price snapshot; do not commit."""
    verified = regular_session_evidence(
        evidence["code"], date.fromisoformat(evidence["trade_date"]),
        evidence["raw_rows"], observed_at=observed_at,
        preopen_baseline=evidence.get("preopen_baseline"),
        closing_auction_evidence=evidence.get("closing_auction_evidence"),
        minute_coverage_evidence=evidence.get("minute_coverage_evidence"),
        bucket_open_proof=evidence.get("bucket_open_proof"),
        full_minute_path_proof=evidence.get("full_minute_path_proof"),
        toss_dated_minute_proof=evidence.get("toss_dated_minute_proof"),
    )
    if not _matches_recomputed_evidence(evidence, verified):
        raise ValueError("evidence failed deterministic recomputation")
    digest = sha256(_json(evidence).encode()).hexdigest()
    existing = db.scalar(select(SignalSessionPrice).where(
        SignalSessionPrice.code == evidence["code"],
        SignalSessionPrice.trade_date == date.fromisoformat(evidence["trade_date"]),
        SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS,
        SignalSessionPrice.evidence_hash == digest,
    ))
    if existing is not None:
        return existing
    legacy = db.scalar(select(DailyPrice).where(
        DailyPrice.code == evidence["code"], DailyPrice.trade_date == date.fromisoformat(evidence["trade_date"]),
    ))
    envelope = {
        "evidence": evidence,
        "legacy_display_price_at_capture": {key: getattr(legacy, key) for key in PRICE_FIELDS} if legacy is not None else None,
    }
    record = SignalSessionPrice(
        code=evidence["code"], trade_date=date.fromisoformat(evidence["trade_date"]),
        basis_version=REGULAR_PRICE_BASIS, evidence_hash=digest, state=evidence["state"],
        payload=_json(envelope), observed_at=observed_at.astimezone(timezone.utc).replace(tzinfo=None),
    )
    db.add(record)
    db.flush()
    return record


def load_regular_session_evidence(
    db: Session, code: str, trade_date: date, *, allow_bounded: bool = False,
) -> dict[str, Any]:
    global _validated_evidence_cache_bytes
    # A default dry-run must also work before the additive table is installed.
    # Do not create schema or write anything as a side effect of a read.
    if not inspect(db.connection()).has_table(SignalSessionPrice.__tablename__):
        raise UnverifiedRegularSessionPrice("정규장 가격 근거 테이블이 없습니다")
    states = ("ready", "bounded") if allow_bounded else ("ready",)
    records = list(db.scalars(select(SignalSessionPrice).where(
        SignalSessionPrice.code == code, SignalSessionPrice.trade_date == trade_date,
        SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS, SignalSessionPrice.state.in_(states),
    )))
    if not records:
        raise UnverifiedRegularSessionPrice(f"{code} {trade_date}: 검증된 정규장 가격이 없습니다")
    accepted = []
    for record in records:
        try:
            # The market feed reads each immutable dated record repeatedly for
            # peer context and position replay. Recompute once per exact stored
            # content, while a changed payload/hash/state always gets checked
            # again (including mutations in the same SQLAlchemy session).
            cache_key = (
                REGULAR_PRICE_BASIS, record.id, code, trade_date.isoformat(),
                record.observed_at.isoformat(), record.state, record.evidence_hash,
                sha256(record.payload.encode("utf-8")).digest(),
            )
            with _validated_evidence_cache_lock:
                cached = _validated_evidence_cache.get(cache_key)
                if cached is not None:
                    _validated_evidence_cache.move_to_end(cache_key)
            if cached is None:
                evidence = json.loads(record.payload)["evidence"]
                regenerated = regular_session_evidence(
                    code, trade_date, evidence["raw_rows"],
                    observed_at=record.observed_at.replace(tzinfo=timezone.utc),
                    preopen_baseline=evidence.get("preopen_baseline"),
                    closing_auction_evidence=evidence.get("closing_auction_evidence"),
                    minute_coverage_evidence=evidence.get("minute_coverage_evidence"),
                    bucket_open_proof=evidence.get("bucket_open_proof"),
                    full_minute_path_proof=evidence.get("full_minute_path_proof"),
                    toss_dated_minute_proof=evidence.get("toss_dated_minute_proof"),
                )
                if (
                    not _matches_recomputed_evidence(evidence, regenerated)
                    or sha256(_json(evidence).encode()).hexdigest() != record.evidence_hash
                    or evidence["state"] != record.state
                    or evidence["state"] not in states
                ):
                    raise ValueError("integrity mismatch")
                packed = zlib.compress(_json(evidence).encode("utf-8"), level=1)
                if len(packed) <= _VALIDATED_EVIDENCE_CACHE_MAX_BYTES:
                    with _validated_evidence_cache_lock:
                        previous = _validated_evidence_cache.pop(cache_key, None)
                        if previous is not None:
                            _validated_evidence_cache_bytes -= len(previous)
                        _validated_evidence_cache[cache_key] = packed
                        _validated_evidence_cache_bytes += len(packed)
                        while _validated_evidence_cache_bytes > _VALIDATED_EVIDENCE_CACHE_MAX_BYTES:
                            _, evicted = _validated_evidence_cache.popitem(last=False)
                            _validated_evidence_cache_bytes -= len(evicted)
            else:
                evidence = json.loads(zlib.decompress(cached))
                if evidence["state"] != record.state or evidence["state"] not in states:
                    raise ValueError("integrity mismatch")
        except (ValueError, KeyError, TypeError) as exc:
            raise UnverifiedRegularSessionPrice("정규장 가격 근거의 무결성이 깨졌습니다") from exc
        accepted.append(evidence)
    if len({_json(item["prices"]) for item in accepted}) != 1 or len({_json(item["turnover_bounds"]) for item in accepted}) != 1:
        raise UnverifiedRegularSessionPrice("동일 정규장의 원천 가격 근거가 충돌합니다")
    independently_corroborated = [
        item for item in accepted if item.get("full_minute_path_proof") is not None
        or item.get("toss_dated_minute_proof") is not None
    ]
    if independently_corroborated:
        if len({_json(item["regular_rows"]) for item in independently_corroborated}) != 1:
            raise UnverifiedRegularSessionPrice("독립 분봉 보정 근거가 서로 충돌합니다")
        return independently_corroborated[0]
    return accepted[0]


def regular_signal_price_rows(db: Session, rows: list[DailyPrice], *, completed_through: date) -> list[DailyPrice]:
    """Return detached signal inputs; leave display and historical rows intact."""
    result = []
    by_code: dict[str, list[DailyPrice]] = {}
    for row in rows:
        by_code.setdefault(row.code, []).append(row)
        if row.trade_date < REGULAR_PRICE_EFFECTIVE_DATE and row.trade_date <= completed_through:
            result.append(row)
    for code, original in by_code.items():
        first = max(REGULAR_PRICE_EFFECTIVE_DATE, min(row.trade_date for row in original))
        originals = {row.trade_date: row for row in original}
        for day in _session_dates(first, completed_through):
            evidence = load_regular_session_evidence(db, code, day)
            display = originals.get(day)
            result.append(DailyPrice(code=code, trade_date=day, **evidence["prices"],
                                     market_cap=display.market_cap if display else None,
                                     listed_shares=display.listed_shares if display else None))
    # In-progress daily OHLC may include other sessions. Live regular
    # execution must obtain its independently verified current quote.
    result.sort(key=lambda row: (row.code, row.trade_date))
    return result


def _session_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(max(0, (end - start).days + 1))
            if is_scheduled_korea_market_session_date(start + timedelta(days=offset))]


def collect_regular_session_prices(
    db: Session, provider: Any, *, codes: list[str], start: date, end: date,
    observed_at: datetime, persist: bool = False, max_pairs: int = 250,
    retry_cooldown: timedelta = timedelta(minutes=30),
) -> dict[str, Any]:
    """Bounded, resumable sidecar backfill; never publishes signals or pushes.

    Only supplied symbols and scheduled completed session dates are inspected.
    Each persisted evidence item commits independently so a provider outage
    cannot discard earlier completed work. Unverified evidence remains visible.
    """
    if (
        start < REGULAR_PRICE_EFFECTIVE_DATE
        or end < start
        or max_pairs < 1
        or retry_cooldown < timedelta(0)
    ):
        raise ValueError("invalid regular-session backfill range")
    local = observed_at.astimezone(KST) if observed_at.tzinfo is not None else None
    if local is None or end > local.date() or (end == local.date() and local.time() < time(15, 31)):
        raise ValueError("backfill end must be a completed session date")
    has_table = inspect(db.connection()).has_table(SignalSessionPrice.__tablename__)
    if persist and not has_table:
        raise ValueError("create the additive evidence table before persisting")
    active_codes = sorted(set(codes))
    pairs = [(code, day) for day in reversed(_session_dates(start, end)) for code in active_codes]
    # A fixed newest-first cap can indefinitely starve an older failed day
    # when the current cohort grows. Retry recorded failures first, while
    # spacing provider attempts so an unchanged bad session cannot monopolize
    # the next pass or exhaust the dated-chart API.
    retry_cutoff = (
        observed_at.astimezone(timezone.utc).replace(tzinfo=None) - retry_cooldown
    )
    last_unverified = {
        (code, day): latest
        for code, day, latest in db.execute(
            select(
                SignalSessionPrice.code,
                SignalSessionPrice.trade_date,
                func.max(SignalSessionPrice.observed_at),
            ).where(
                SignalSessionPrice.code.in_(active_codes),
                SignalSessionPrice.trade_date >= start,
                SignalSessionPrice.trade_date <= end,
                SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS,
                SignalSessionPrice.state == "unverified",
            ).group_by(SignalSessionPrice.code, SignalSessionPrice.trade_date)
        )
    } if active_codes and has_table else {}
    retryable = sorted(
        (pair for pair in pairs if pair in last_unverified and last_unverified[pair] < retry_cutoff),
        key=lambda pair: (last_unverified[pair], -pair[1].toordinal(), pair[0]),
    )
    retryable_set = set(retryable)
    retry_quota = max(1, max_pairs // 4)
    pairs = retryable[:retry_quota] + [pair for pair in pairs if pair not in retryable_set] + retryable[retry_quota:]
    report: dict[str, Any] = {
        "basis_version": REGULAR_PRICE_BASIS, "start": start.isoformat(), "end": end.isoformat(),
        "persist": persist, "total_pairs": len(pairs), "attempted": 0,
        "ready": 0, "already_ready": 0, "bounded": 0, "already_bounded": 0, "unverified": [], "deferred": 0,
        "signal_publication": False, "history_overwrite": False, "notifications_sent": 0,
    }
    for code, day in pairs:
        try:
            prior = load_regular_session_evidence(db, code, day, allow_bounded=True)
        except UnverifiedRegularSessionPrice:
            existing_ready = db.scalar(select(SignalSessionPrice.id).where(
                SignalSessionPrice.code == code, SignalSessionPrice.trade_date == day,
                SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS, SignalSessionPrice.state.in_(("ready", "bounded")),
            ).limit(1)) if has_table else None
            if existing_ready is not None:
                report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": "stored_evidence_conflict_or_corruption"})
                continue
        else:
            report["already_ready" if prior["state"] == "ready" else "already_bounded"] += 1
            continue
        last_attempt = last_unverified.get((code, day))
        if last_attempt is not None and last_attempt >= retry_cutoff:
            report["unverified"].append({
                "code": code, "trade_date": day.isoformat(), "reason": "retry_cooldown",
            })
            continue
        if report["attempted"] >= max_pairs:
            report["deferred"] += 1
            continue
        report["attempted"] += 1
        try:
            source = provider.fetch_regular_session_data(code, day)
            result = regular_session_evidence(code, day, source["rows"], observed_at=observed_at, preopen_baseline=source.get("preopen_baseline"), closing_auction_evidence=source.get("closing_auction_evidence"), minute_coverage_evidence=source.get("minute_coverage_evidence"), bucket_open_proof=source.get("bucket_open_proof"), full_minute_path_proof=source.get("full_minute_path_proof"))
        except Exception as exc:
            # Provider errors can contain credential-bearing URLs; never export
            # their text to a CLI report or public diagnostic.
            report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": "source_unavailable", "error_type": type(exc).__name__})
            continue
        if result["state"] == "unverified" and result.get("reason") in {
            "closing source conflicts with KIS pre-auction OHLC",
            "closing source conflicts with KIS pre-auction volume",
            "cumulative turnover does not reconcile with actual trades",
        }:
            # Dated KIS pages can intermittently omit one actual minute. A
            # later page read may be complete, but one lucky response is not
            # enough to clear an isolated session. Accept only two identical,
            # independently revalidated complete reads; otherwise preserve
            # the original failure and the normal retry cooldown.
            stable: list[dict[str, Any]] = []
            for _ in range(2):
                try:
                    retry_source = provider.fetch_regular_session_data(code, day)
                    retry = regular_session_evidence(
                        code, day, retry_source["rows"], observed_at=observed_at,
                        preopen_baseline=retry_source.get("preopen_baseline"),
                        closing_auction_evidence=retry_source.get("closing_auction_evidence"),
                        minute_coverage_evidence=retry_source.get("minute_coverage_evidence"),
                        bucket_open_proof=retry_source.get("bucket_open_proof"),
                        full_minute_path_proof=retry_source.get("full_minute_path_proof"),
                    )
                except Exception:
                    break
                if retry["state"] not in {"ready", "bounded"}:
                    break
                stable.append(retry)
            if len(stable) == 2 and _json(stable[0]) == _json(stable[1]):
                result = stable[1]
        if persist:
            store_regular_session_evidence(db, result, observed_at=observed_at)
            db.commit()
        if result["state"] == "ready":
            report["ready"] += 1
        elif result["state"] == "bounded":
            report["bounded"] += 1
        else:
            report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": result["reason"]})
    report["state"] = "ready" if pairs and not report["unverified"] and not report["deferred"] else "incomplete"
    report["exact_turnover_complete"] = report["state"] == "ready" and not (report["bounded"] or report["already_bounded"])
    report["production_ready"] = False  # collection is not a strategy approval
    return report
