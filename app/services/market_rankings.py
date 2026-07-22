from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.models import DailyPrice, NewsItem, StockMaster
from app.services.stock_dashboard import NAVER_CACHE, _keyword_score, _naver_snapshot, _rate, _round_decimal

KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    return datetime.now(KST)


def _is_regular_session(now: Optional[datetime] = None) -> bool:
    current = now or _now_kst()
    if current.weekday() >= 5:
        return False
    return (current.hour, current.minute) >= (9, 0) and (current.hour, current.minute) <= (15, 30)


def _row_value(row: DailyPrice) -> Optional[int]:
    if row.trading_value is not None:
        return row.trading_value
    if row.close is not None and row.volume is not None:
        return row.close * row.volume
    return None


def _mapping_row_value(row: dict[str, object]) -> Optional[int]:
    if row.get("trading_value") is not None:
        return int(row["trading_value"])
    if row.get("close") is not None and row.get("volume") is not None:
        return int(row["close"]) * int(row["volume"])
    return None


def _price_groups(db: Session, market: Optional[str]) -> dict[str, tuple[StockMaster, list[DailyPrice]]]:
    latest_date = db.scalar(select(func.max(DailyPrice.trade_date)))
    if not latest_date:
        return {}

    from_date = latest_date - timedelta(days=150)
    statement = (
        select(StockMaster, DailyPrice)
        .join(DailyPrice, DailyPrice.code == StockMaster.code)
        .where(DailyPrice.trade_date >= from_date)
        .order_by(StockMaster.code, DailyPrice.trade_date)
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    groups: dict[str, tuple[StockMaster, list[DailyPrice]]] = {}
    for stock, price in db.execute(statement):
        if stock.code not in groups:
            groups[stock.code] = (stock, [])
        groups[stock.code][1].append(price)
    return groups


def _base_item_from_rows(stock: dict[str, object], prices: list[dict[str, object]]) -> Optional[dict[str, object]]:
    if not prices:
        return None
    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else None
    one_month = prices[-22] if len(prices) >= 22 else None
    three_month = prices[-64] if len(prices) >= 64 else None
    recent_values = [value for row in prices[-5:] if (value := _mapping_row_value(row)) is not None]
    baseline_values = [value for row in prices[-25:-5] if (value := _mapping_row_value(row)) is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None

    return {
        "code": stock["code"],
        "name": stock["name"],
        "market": stock["market"],
        "trade_date": latest.get("trade_date"),
        "price": latest.get("close"),
        "market_cap": latest.get("market_cap"),
        "change_rate": _rate(latest.get("close"), previous.get("close") if previous else None),
        "_previous_price": previous.get("close") if previous else None,
        "_one_month_price": one_month.get("close") if one_month else None,
        "_three_month_price": three_month.get("close") if three_month else None,
        "one_month_return": _rate(latest.get("close"), one_month.get("close") if one_month else None),
        "three_month_return": _rate(latest.get("close"), three_month.get("close") if three_month else None),
        "trading_value": _mapping_row_value(latest),
        "trading_value_change": _rate(recent_average, baseline_average),
        "per": None,
        "pbr": None,
        "sentiment_score": None,
    }


def _fast_price_items(db: Session, market: Optional[str], lookback: int = 64) -> list[dict[str, object]]:
    row_number = func.row_number().over(partition_by=DailyPrice.code, order_by=DailyPrice.trade_date.desc()).label("row_number")
    statement = (
        select(
            StockMaster.code.label("code"),
            StockMaster.name.label("name"),
            StockMaster.market.label("market"),
            DailyPrice.trade_date.label("trade_date"),
            DailyPrice.close.label("close"),
            DailyPrice.volume.label("volume"),
            DailyPrice.trading_value.label("trading_value"),
            DailyPrice.market_cap.label("market_cap"),
            row_number,
        )
        .join(DailyPrice, DailyPrice.code == StockMaster.code)
        .where(DailyPrice.close.is_not(None))
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    ranked = statement.subquery()
    rows = db.execute(
        select(ranked)
        .where(ranked.c.row_number <= lookback)
        .order_by(ranked.c.code, ranked.c.trade_date)
    ).mappings()

    groups: dict[str, tuple[dict[str, object], list[dict[str, object]]]] = {}
    for row in rows:
        code = str(row["code"])
        if code not in groups:
            groups[code] = (
                {"code": code, "name": row["name"], "market": row["market"]},
                [],
            )
        groups[code][1].append(dict(row))
    return [item for stock, prices in groups.values() if (item := _base_item_from_rows(stock, prices))]


def _latest_session_surge_items(db: Session, market: Optional[str]) -> list[dict[str, object]]:
    latest_date_statement = select(func.max(DailyPrice.trade_date)).join(StockMaster, StockMaster.code == DailyPrice.code)
    if market:
        latest_date_statement = latest_date_statement.where(StockMaster.market == market.upper())
    latest_date = db.scalar(latest_date_statement)
    if not latest_date:
        return []

    now = _now_kst()
    if latest_date >= now.date() and (now.hour, now.minute) <= (15, 30):
        completed_date_statement = (
            select(func.max(DailyPrice.trade_date))
            .join(StockMaster, StockMaster.code == DailyPrice.code)
            .where(DailyPrice.trade_date < now.date())
        )
        if market:
            completed_date_statement = completed_date_statement.where(StockMaster.market == market.upper())
        latest_date = db.scalar(completed_date_statement)
        if not latest_date:
            return []

    previous_date_statement = (
        select(func.max(DailyPrice.trade_date))
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(DailyPrice.trade_date < latest_date)
    )
    if market:
        previous_date_statement = previous_date_statement.where(StockMaster.market == market.upper())
    previous_date = db.scalar(previous_date_statement)

    LatestPrice = aliased(DailyPrice)
    PreviousPrice = aliased(DailyPrice)
    statement = (
        select(StockMaster, LatestPrice, PreviousPrice.close.label("previous_close"))
        .join(LatestPrice, and_(LatestPrice.code == StockMaster.code, LatestPrice.trade_date == latest_date))
        .outerjoin(PreviousPrice, and_(PreviousPrice.code == StockMaster.code, PreviousPrice.trade_date == previous_date))
        .where(LatestPrice.close.is_not(None))
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    items: list[dict[str, object]] = []
    for stock, latest, previous_close in db.execute(statement):
        items.append(
            {
                "code": stock.code,
                "name": stock.name,
                "market": stock.market,
                "trade_date": latest.trade_date,
                "price": latest.close,
                "market_cap": latest.market_cap,
                "change_rate": _rate(latest.close, previous_close),
                "_previous_price": previous_close,
                "_one_month_price": None,
                "_three_month_price": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value": _row_value(latest),
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "sentiment_score": None,
            }
        )
    return items


def _base_item(stock: StockMaster, prices: list[DailyPrice]) -> Optional[dict[str, object]]:
    if not prices:
        return None
    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else None
    one_month = prices[-22] if len(prices) >= 22 else None
    three_month = prices[-64] if len(prices) >= 64 else None
    recent_values = [value for row in prices[-5:] if (value := _row_value(row)) is not None]
    baseline_values = [value for row in prices[-25:-5] if (value := _row_value(row)) is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None

    return {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "trade_date": latest.trade_date,
        "price": latest.close,
        "market_cap": latest.market_cap,
        "change_rate": _rate(latest.close, previous.close if previous else None),
        "_previous_price": previous.close if previous else None,
        "_one_month_price": one_month.close if one_month else None,
        "_three_month_price": three_month.close if three_month else None,
        "one_month_return": _rate(latest.close, one_month.close if one_month else None),
        "three_month_return": _rate(latest.close, three_month.close if three_month else None),
        "trading_value": _row_value(latest),
        "trading_value_change": _rate(recent_average, baseline_average),
        "per": None,
        "pbr": None,
        "sentiment_score": None,
    }


def _ranked(items: list[dict[str, object]], category: str, metric_key: str, reverse: bool = True, limit: int = 50) -> list[dict[str, object]]:
    filtered = [item for item in items if item.get(metric_key) is not None]
    filtered.sort(key=lambda item: Decimal(str(item[metric_key])), reverse=reverse)
    output = filtered[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = category
        item["metric_value"] = item.get(metric_key)
    return output


def _valuation_rank(
    items: list[dict[str, object]],
    limit: int,
    candidate_count: int = 160,
    refresh_live: bool = False,
) -> list[dict[str, object]]:
    candidates = sorted(
        [item for item in items if item.get("trading_value")],
        key=lambda item: int(item["trading_value"]),
        reverse=True,
    )[:candidate_count]

    def enrich(item: dict[str, object]) -> Optional[dict[str, object]]:
        if refresh_live:
            snapshot = _naver_snapshot(str(item["code"]), refresh=True)
        else:
            snapshot = NAVER_CACHE.get(("naver_snapshot", str(item["code"]))) or {}
        per = snapshot.get("per")
        pbr = snapshot.get("pbr")
        if per is None or pbr is None or Decimal(str(per)) <= 0 or Decimal(str(pbr)) <= 0:
            return None
        enriched = dict(item)
        enriched["per"] = per
        enriched["pbr"] = pbr
        industry_per = snapshot.get("industry_per")
        if industry_per and Decimal(str(industry_per)) > 0:
            enriched["metric_value"] = _round_decimal(Decimal(str(per)) / Decimal(str(industry_per)) * Decimal("100"))
        else:
            enriched["metric_value"] = per
        return enriched

    enriched_items: list[dict[str, object]] = []
    if refresh_live:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(enrich, item): item for item in candidates}
            for future in as_completed(futures):
                item = future.result()
                if item:
                    enriched_items.append(item)
    else:
        for candidate in candidates:
            item = enrich(candidate)
            if item:
                enriched_items.append(item)

    if len(enriched_items) < limit:
        fallback_items: list[dict[str, object]] = []
        for item in candidates:
            if any(existing["code"] == item["code"] for existing in enriched_items):
                continue
            market_cap = item.get("market_cap")
            trading_value = item.get("trading_value")
            if not market_cap or not trading_value:
                continue
            fallback = dict(item)
            fallback["metric_value"] = _round_decimal(Decimal(str(trading_value)) / Decimal(str(market_cap)) * Decimal("100"))
            fallback_items.append(fallback)
        fallback_items.sort(key=lambda item: Decimal(str(item["metric_value"])), reverse=True)
        enriched_items.extend(fallback_items[: max(0, limit - len(enriched_items))])

    def valuation_sort_key(item: dict[str, object]) -> tuple[int, Decimal, Decimal]:
        if item.get("per") is not None and item.get("pbr") is not None:
            return (0, Decimal(str(item["metric_value"])), Decimal(str(item["pbr"])))
        return (1, -Decimal(str(item["metric_value"] or 0)), Decimal("0"))

    enriched_items.sort(key=valuation_sort_key)
    output = enriched_items[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = "valuation"
    return output


def _enrich_live_rankings(items: list[dict[str, object]], category: str, limit: int) -> list[dict[str, object]]:
    def enrich(item: dict[str, object]) -> dict[str, object]:
        snapshot = _naver_snapshot(str(item["code"]), refresh=True)
        enriched = dict(item)
        price = snapshot.get("price")
        if price is not None:
            enriched["price"] = price
            enriched["one_month_return"] = _rate(price, item.get("_one_month_price"))
            enriched["three_month_return"] = _rate(price, item.get("_three_month_price"))
        change_rate = snapshot.get("change_rate_abs")
        if change_rate is not None:
            enriched["change_rate"] = change_rate
        if snapshot.get("trading_value") is not None:
            enriched["trading_value"] = snapshot.get("trading_value")
        if snapshot.get("market_cap") is not None:
            enriched["market_cap"] = snapshot.get("market_cap")
        if category == "surge":
            enriched["metric_value"] = enriched.get("change_rate")
        elif category == "trading_value":
            enriched["metric_value"] = enriched.get("trading_value")
        elif category == "momentum":
            one_month = enriched.get("one_month_return")
            three_month = enriched.get("three_month_return")
            if one_month is not None and three_month is not None:
                enriched["momentum_score"] = _round_decimal(
                    Decimal(str(one_month)) * Decimal("0.55") + Decimal(str(three_month)) * Decimal("0.45")
                )
                enriched["metric_value"] = enriched["momentum_score"]
        return enriched

    enriched_items: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(enrich, item) for item in items]
        for future in as_completed(futures):
            enriched_items.append(future.result())

    metric_key = {
        "surge": "change_rate",
        "trading_value": "trading_value",
        "momentum": "momentum_score",
        "sentiment": "sentiment_score",
        "valuation": "metric_value",
    }.get(category, "metric_value")
    reverse = category != "valuation"
    enriched_items = [item for item in enriched_items if item.get(metric_key) is not None]
    enriched_items.sort(key=lambda item: Decimal(str(item[metric_key])), reverse=reverse)
    output = enriched_items[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = category
        item["metric_value"] = item.get(metric_key)
    return output


def _news_sentiment_rank(db: Session, items: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    since = datetime.utcnow() - timedelta(days=14)
    news = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= since)
            .order_by(NewsItem.published_at.desc())
            .limit(2000)
        )
    )
    if not news:
        return []

    scored: list[dict[str, object]] = []
    stock_items = sorted(items, key=lambda item: int(item.get("trading_value") or 0), reverse=True)[:600]
    for item in stock_items:
        name = str(item["name"])
        matches = [row for row in news if name in row.title or (row.summary and name in row.summary)]
        if not matches:
            continue
        score = sum(_keyword_score(f"{row.title} {row.summary or ''}") for row in matches)
        normalized = _round_decimal(Decimal(score) / Decimal(len(matches)) * Decimal("100"))
        ranked = dict(item)
        ranked["sentiment_score"] = normalized
        ranked["metric_value"] = normalized
        ranked["news_count"] = len(matches)
        scored.append(ranked)

    scored.sort(key=lambda item: Decimal(str(item["sentiment_score"])), reverse=True)
    output = scored[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = "sentiment"
    return output


def build_market_rankings(
    db: Session,
    category: str,
    market: Optional[str] = None,
    limit: int = 50,
    refresh_live: bool = False,
) -> dict[str, object]:
    should_refresh_live = refresh_live and _is_regular_session()
    rank_limit = min(max(limit * 5, limit), 200) if should_refresh_live and category in {"surge", "trading_value", "momentum"} else limit
    if category == "surge" and not should_refresh_live:
        items = _latest_session_surge_items(db, market)
    elif category == "surge":
        items = _fast_price_items(db, market, lookback=64)
    else:
        groups = _price_groups(db, market)
        items = [item for stock, prices in groups.values() if (item := _base_item(stock, prices))]

    universe_count = len(items)
    matching_count = 0
    if category == "surge":
        rising_items = [item for item in items if Decimal(str(item.get("change_rate") or 0)) > 0]
        matching_count = len(rising_items)
        rankings = _ranked(rising_items, "surge", "change_rate", True, rank_limit)
    elif category == "trading_value":
        rankings = _ranked(items, "trading_value", "trading_value", True, rank_limit)
    elif category == "momentum":
        for item in items:
            one_month = item.get("one_month_return")
            three_month = item.get("three_month_return")
            if one_month is not None and three_month is not None:
                item["momentum_score"] = _round_decimal(Decimal(str(one_month)) * Decimal("0.55") + Decimal(str(three_month)) * Decimal("0.45"))
        rankings = _ranked(items, "momentum", "momentum_score", True, rank_limit)
    elif category == "valuation":
        rankings = _valuation_rank(items, limit, refresh_live=refresh_live)
    elif category == "sentiment":
        rankings = _news_sentiment_rank(db, items, limit)
    else:
        rankings = _ranked(items, "surge", "change_rate", True, rank_limit)
    if category != "surge":
        matching_count = len(rankings)

    if should_refresh_live and rankings:
        fallback_rankings = rankings[:limit]
        try:
            live_rankings = _enrich_live_rankings(rankings, category, limit)
        except Exception:
            live_rankings = []
        if live_rankings:
            existing_codes = {str(item["code"]) for item in live_rankings}
            for item in fallback_rankings:
                if str(item["code"]) not in existing_codes:
                    live_rankings.append(item)
                if len(live_rankings) >= limit:
                    break
            rankings = live_rankings[:limit]
        else:
            rankings = fallback_rankings

    return {
        "category": category,
        "market": market,
        "as_of": _now_kst(),
        "universe_count": universe_count,
        "matching_count": matching_count,
        "items": rankings,
    }
