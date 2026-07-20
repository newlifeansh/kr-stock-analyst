from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import DailyPrice, StockMaster
from app.services.market_rankings import _base_item, _row_value
from app.services.stock_dashboard import build_stock_dashboard, _chart_analysis, _round_decimal
from app.services.ttl_cache import TTLCache


WEIGHTS = {
    "estimate_revision": Decimal("12"),
    "analyst_revision_ratio": Decimal("8"),
    "surprise": Decimal("9"),
    "guidance": Decimal("8"),
    "price_momentum": Decimal("12"),
    "trading_value": Decimal("8"),
    "valuation": Decimal("13"),
    "macro": Decimal("10"),
    "flows": Decimal("10"),
    "sentiment": Decimal("10"),
}

MARKET_CAP_UNIVERSE_LIMIT = 100
KST = timezone(timedelta(hours=9))
UNIVERSE_CACHE_TTL_SECONDS = 300
universe_cache = TTLCache(maxsize=16)


METHODOLOGY = [
    "최근 시가총액 데이터가 있으면 상위 100개, 없으면 최신 거래대금 추정 상위 종목을 추천 유니버스로 사용한다.",
    "유니버스 안에서 1개월/3개월 모멘텀, 거래대금, 거래대금 변화로 후보를 선별한다. 가격 이력이 짧으면 최신 거래대금과 단기 흐름으로 보수적으로 대체한다.",
    "선별 후보에 대해 추정치/애널리스트 변화, 실적/가이던스, 밸류에이션, 거시 민감도, 수급, 뉴스 분위기를 0~100점으로 환산한다.",
    "최종 점수는 10개 항목 가중합이며, 데이터가 부족한 항목은 중립 이하로 처리하고 이유/리스크에 표시한다.",
]

RECOMMENDATION_GROUP_PREFIXES = (
    "HD현대",
    "POSCO",
    "SK",
    "LG",
    "GS",
    "LS",
    "CJ",
    "KB",
    "BNK",
    "DGB",
    "JB",
    "NH",
    "OCI",
    "NAVER",
    "카카오",
    "삼성",
    "현대",
    "한화",
    "롯데",
    "두산",
    "신한",
    "하나",
    "우리",
    "셀트리온",
    "포스코",
    "효성",
)


def _num(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _now_kst() -> datetime:
    return datetime.now(KST)


def _clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("100")) -> Decimal:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _score(value: Decimal) -> Decimal:
    return _round_decimal(_clamp(value)) or Decimal("0")


def _score_revisions(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    revisions = dashboard["revisions"]
    quote = dashboard["quote"]
    score = Decimal("45")
    report_count = int(revisions.get("report_count_90d") or 0)
    target_price = _num(revisions.get("latest_target_price"))
    price = _num(quote.get("price"))
    estimated_eps = _num(revisions.get("estimated_eps"))
    estimated_revenue = _num(revisions.get("estimated_revenue"))
    opinion = str(revisions.get("latest_opinion") or "")

    if report_count:
        score += min(Decimal(report_count) * Decimal("3"), Decimal("12"))
        reasons.append(f"최근 90일 리포트 {report_count}건으로 추정치 확인 가능")
    else:
        risks.append("최근 90일 리포트가 없어 EPS/매출 추정 변화 신뢰도 낮음")

    if target_price is not None and price not in (None, 0):
        upside = (target_price / price - Decimal("1")) * Decimal("100")
        score += _clamp(upside / Decimal("2"), Decimal("-15"), Decimal("20"))
        reasons.append(f"최근 목표가 기준 괴리율 {(_round_decimal(upside) or upside)}%")

    if estimated_eps is not None or estimated_revenue is not None:
        score += Decimal("8")
        reasons.append("EPS/매출 컨센서스 프록시가 존재")

    if "buy" in opinion.lower() or "매수" in opinion:
        score += Decimal("8")
    elif "sell" in opinion.lower() or "매도" in opinion:
        score -= Decimal("12")
        risks.append("최근 투자의견이 부정적")

    return _score(score)


def _score_revision_ratio(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    revisions = dashboard["revisions"]
    ratio = _num(revisions.get("target_up_ratio"))
    up_count = int(revisions.get("target_up_count") or 0)
    down_count = int(revisions.get("target_down_count") or 0)
    if ratio is None:
        if up_count == 0 and down_count == 0:
            risks.append("애널리스트 상향/하향 이력이 부족해 상향 비율은 중립 처리")
        return Decimal("45")
    if ratio >= 60:
        reasons.append(f"목표가 상향 비율 {ratio}%로 상향 쪽 우세")
    elif ratio <= 40:
        risks.append(f"목표가 상향 비율 {ratio}%로 하향 압력 확인")
    return _score(ratio)


def _score_events(label: str, payload: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    positive = int(payload.get("positive_count") or 0)
    negative = int(payload.get("negative_count") or 0)
    recent = int(payload.get("recent_count") or 0)
    revenue_growth = _num(payload.get("revenue_growth"))
    profit_growth = _num(payload.get("operating_profit_growth"))
    score = Decimal("48") + Decimal(positive - negative) * Decimal("14")

    if recent:
        reasons.append(f"{label} 관련 공시/이벤트 {recent}건 확인")
    else:
        risks.append(f"{label} 변화 이벤트가 부족")
    if revenue_growth is not None:
        score += _clamp(revenue_growth / Decimal("5"), Decimal("-10"), Decimal("10"))
    if profit_growth is not None:
        score += _clamp(profit_growth / Decimal("10"), Decimal("-12"), Decimal("12"))
        if profit_growth > 0:
            reasons.append(f"{label} 영업이익 변화율 {profit_growth}%")
        elif profit_growth < 0:
            risks.append(f"{label} 영업이익 변화율 {profit_growth}%")

    return _score(score)


def _score_momentum(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    momentum = dashboard["momentum"]
    one_month = _num(momentum.get("one_month_return"))
    three_month = _num(momentum.get("three_month_return"))
    if one_month is None and three_month is None:
        risks.append("1개월/3개월 가격 모멘텀 데이터 부족")
        return Decimal("40")
    score = Decimal("50")
    if one_month is not None:
        score += _clamp(one_month * Decimal("1.1"), Decimal("-25"), Decimal("25"))
    if three_month is not None:
        score += _clamp(three_month * Decimal("0.45"), Decimal("-25"), Decimal("25"))
    if (one_month or 0) > 0 and (three_month or 0) > 0:
        reasons.append(f"1개월 {one_month}%, 3개월 {three_month}%로 추세 양호")
    elif (one_month or 0) < 0 and (three_month or 0) < 0:
        risks.append(f"1개월 {one_month}%, 3개월 {three_month}%로 가격 추세 약함")
    if (one_month is not None and one_month > 80) or (three_month is not None and three_month > 180):
        score -= Decimal("15")
        risks.append("단기 급등 폭이 커서 추격매수 리스크 확인 필요")
    return _score(score)


def _score_trading_value(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    momentum = dashboard["momentum"]
    quote = dashboard["quote"]
    change = _num(momentum.get("trading_value_change"))
    trading_value = _num(quote.get("trading_value"))
    score = Decimal("50")
    if change is not None:
        score += _clamp(change / Decimal("2"), Decimal("-20"), Decimal("25"))
        if change > 20:
            reasons.append(f"거래대금 변화 {change}%로 관심 유입")
        elif change < -20:
            risks.append(f"거래대금 변화 {change}%로 수급 열기 둔화")
    else:
        risks.append("거래대금 변화 계산 데이터 부족")
    if trading_value is not None and trading_value >= Decimal("10000000000"):
        score += Decimal("8")
    return _score(score)


def _score_valuation(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    valuation = dashboard["valuation"]
    per = _num(valuation.get("per"))
    pbr = _num(valuation.get("pbr"))
    per_z = _num(valuation.get("per_zscore"))
    pbr_z = _num(valuation.get("pbr_zscore"))
    estimated_per = _num(valuation.get("estimated_per"))
    industry_per = _num(valuation.get("industry_per"))
    z_values = [value for value in (per_z, pbr_z) if value is not None]
    score = Decimal("50")

    if per is None and pbr is None:
        risks.append("PER/PBR 데이터 부족")
        return Decimal("40")
    if per is not None and per <= 0:
        risks.append("PER가 음수 또는 0이라 이익 안정성 확인 필요")
        score -= Decimal("15")
    if z_values:
        avg_z = sum(z_values) / Decimal(len(z_values))
        score += _clamp(-avg_z * Decimal("14"), Decimal("-25"), Decimal("25"))
        if avg_z <= -0.8:
            reasons.append(f"PER/PBR z-score 평균 {(_round_decimal(avg_z) or avg_z)}로 과거 대비 부담 낮음")
        elif avg_z >= 1.2:
            risks.append(f"PER/PBR z-score 평균 {(_round_decimal(avg_z) or avg_z)}로 과거 대비 밸류 부담")
    else:
        risks.append("PER/PBR 과거 z-score 계산 데이터 부족")

    if per is not None and industry_per not in (None, 0):
        relative = per / industry_per
        if relative <= Decimal("0.85"):
            score += Decimal("8")
            reasons.append("업종 PER 대비 할인 구간")
        elif relative >= Decimal("1.25"):
            score -= Decimal("8")
            risks.append("업종 PER 대비 프리미엄 구간")
    if estimated_per is not None and per is not None and estimated_per > 0 and estimated_per <= per * Decimal("0.85"):
        score += Decimal("8")
        reasons.append("추정 PER가 현재 PER보다 낮아 이익 개선 기대 반영")
    return _score(score)


def _score_macro(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    macro = dashboard["macro_sensitivity"]
    values = {key: _num(value) for key, value in macro.items()}
    present = [value for value in values.values() if value is not None]
    if not present:
        risks.append("금리/환율/원자재/수출 민감도 계산 데이터 부족")
        return Decimal("42")
    score = Decimal("50")
    exports = values.get("exports")
    fx = values.get("fx_usdkrw")
    rate = values.get("interest_rate")
    commodity = values.get("commodity")
    if exports is not None:
        score += _clamp(exports / Decimal("2"), Decimal("-15"), Decimal("18"))
    if fx is not None:
        score += _clamp(fx / Decimal("3"), Decimal("-12"), Decimal("12"))
    if rate is not None:
        score += _clamp(rate / Decimal("3"), Decimal("-12"), Decimal("10"))
    if commodity is not None:
        score += _clamp(commodity / Decimal("4"), Decimal("-8"), Decimal("8"))

    strongest = max(values.items(), key=lambda item: abs(item[1] or Decimal("0")))
    if strongest[1] is not None and strongest[1] > 20:
        reasons.append(f"거시 민감도 중 {strongest[0]} 신호가 우호적")
    elif strongest[1] is not None and strongest[1] < -20:
        risks.append(f"거시 민감도 중 {strongest[0]} 부담이 큼")
    return _score(score)


def _score_flows(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    flows = dashboard["flows"]
    foreign = _num(flows.get("foreign_intensity"))
    institution = _num(flows.get("institution_intensity"))
    if foreign is None and institution is None:
        risks.append("외국인/기관 수급 데이터 부족")
        return Decimal("42")
    score = Decimal("50")
    if foreign is not None:
        score += _clamp(foreign * Decimal("3"), Decimal("-18"), Decimal("18"))
    if institution is not None:
        score += _clamp(institution * Decimal("2.4"), Decimal("-16"), Decimal("16"))
    if (foreign or 0) > 0 and (institution or 0) > 0:
        reasons.append(f"외국인 {foreign}%, 기관 {institution}%로 동반 순매수 강도")
    elif (foreign or 0) < 0 and (institution or 0) < 0:
        risks.append(f"외국인 {foreign}%, 기관 {institution}%로 동반 매도 압력")
    return _score(score)


def _score_sentiment(dashboard: dict[str, object], reasons: list[str], risks: list[str]) -> Decimal:
    sentiment = dashboard["sentiment"]
    value = _num(sentiment.get("score"))
    positive = int(sentiment.get("positive_count") or 0)
    negative = int(sentiment.get("negative_count") or 0)
    neutral = int(sentiment.get("neutral_count") or 0)
    total = positive + negative + neutral
    if value is None:
        risks.append("뉴스/콜 transcript 분위기 데이터 부족")
        return Decimal("45")
    score = Decimal("50") + value / Decimal("2")
    if total:
        score += min(Decimal(total), Decimal("8"))
    if value > 20:
        reasons.append(f"뉴스 sentiment {value}%로 긍정 우위")
    elif value < -20:
        risks.append(f"뉴스 sentiment {value}%로 부정 우위")
    if total == 0:
        risks.append("콜 transcript 원문은 현재 미적재, 뉴스 제목/요약 기준으로 대체")
    return _score(score)


def _candidate_sort_key(item: dict[str, object]) -> Decimal:
    one_month = _num(item.get("one_month_return")) or Decimal("0")
    three_month = _num(item.get("three_month_return")) or Decimal("0")
    trading_change = _num(item.get("trading_value_change")) or Decimal("0")
    trading_value = _num(item.get("trading_value")) or Decimal("0")
    liquidity_bonus = min(trading_value / Decimal("1000000000"), Decimal("40"))
    return one_month * Decimal("0.9") + three_month * Decimal("0.4") + trading_change * Decimal("0.25") + liquidity_bonus


def _normalized_recommendation_name(name: object) -> str:
    value = str(name or "").strip().upper().replace(" ", "")
    for suffix in ("우B", "우C", "1우", "2우B", "우"):
        if value.endswith(suffix) and len(value) > len(suffix) + 1:
            return value[: -len(suffix)]
    return value


def _recommendation_group_key(item: dict[str, object]) -> str:
    name = _normalized_recommendation_name(item.get("name"))
    for prefix in RECOMMENDATION_GROUP_PREFIXES:
        if name.startswith(prefix):
            return prefix
    return name


def _select_diverse_recommendations(scored: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    deferred: list[dict[str, object]] = []
    seen_groups: set[str] = set()

    for item in scored:
        group_key = _recommendation_group_key(item)
        if group_key in seen_groups:
            deferred.append(item)
            continue
        selected.append(item)
        seen_groups.add(group_key)
        if len(selected) >= limit:
            return selected

    for item in deferred:
        if len(selected) >= limit:
            break
        selected.append(item)
    return selected[:limit]


def _action(score: Decimal, chart_score: object = None) -> str:
    score = _score(score)
    chart_value = _num(chart_score)
    if chart_value is not None and chart_value < Decimal("45"):
        return "관망"
    if score >= 68 and (chart_value is None or chart_value >= Decimal("60")):
        return "매수 우선검토"
    if score >= 60 and (chart_value is None or chart_value >= Decimal("50")):
        return "관심 매수후보"
    if score >= 55:
        return "관찰"
    return "관찰"


def _score_dashboard(dashboard: dict[str, object]) -> dict[str, object]:
    reasons: list[str] = []
    risks: list[str] = []
    components = {
        "estimate_revision": _score_revisions(dashboard, reasons, risks),
        "analyst_revision_ratio": _score_revision_ratio(dashboard, reasons, risks),
        "surprise": _score_events("최근 실적", dashboard["surprise"], reasons, risks),
        "guidance": _score_events("가이던스", dashboard["guidance"], reasons, risks),
        "price_momentum": _score_momentum(dashboard, reasons, risks),
        "trading_value": _score_trading_value(dashboard, reasons, risks),
        "valuation": _score_valuation(dashboard, reasons, risks),
        "macro": _score_macro(dashboard, reasons, risks),
        "flows": _score_flows(dashboard, reasons, risks),
        "sentiment": _score_sentiment(dashboard, reasons, risks),
    }
    total = sum(components[key] * weight for key, weight in WEIGHTS.items()) / Decimal("100")
    quote = dashboard["quote"]
    momentum = dashboard["momentum"]
    chart_analysis = dashboard["chart_analysis"]
    score_value = _score(total)
    return {
        "code": dashboard["code"],
        "name": dashboard["name"],
        "market": dashboard["market"],
        "score": score_value,
        "action": _action(score_value, chart_analysis.get("score")),
        "price": quote.get("price"),
        "change_rate": quote.get("change_rate"),
        "one_month_return": momentum.get("one_month_return"),
        "three_month_return": momentum.get("three_month_return"),
        "trading_value": quote.get("trading_value"),
        "component_scores": components,
        "chart_analysis": chart_analysis,
        "reasons": reasons[:8],
        "risks": risks[:6],
    }


def _score_candidate(code: str, refresh_live: bool = False) -> Optional[dict[str, object]]:
    db = SessionLocal()
    try:
        dashboard = build_stock_dashboard(db, code, refresh_live=refresh_live)
        if not dashboard:
            return None
        return _score_dashboard(dashboard)
    except Exception:
        return None
    finally:
        db.close()


def _fast_component_scores(item: dict[str, object], chart_analysis: dict[str, object]) -> dict[str, Decimal]:
    one_month = _num(item.get("one_month_return"))
    three_month = _num(item.get("three_month_return"))
    trading_change = _num(item.get("trading_value_change"))
    trading_value = _num(item.get("trading_value"))
    chart_score = _num(chart_analysis.get("score")) or Decimal("50")

    momentum = Decimal("50")
    if one_month is not None:
        momentum += _clamp(one_month * Decimal("1.1"), Decimal("-25"), Decimal("25"))
    if three_month is not None:
        momentum += _clamp(three_month * Decimal("0.45"), Decimal("-25"), Decimal("25"))
    momentum = momentum * Decimal("0.65") + chart_score * Decimal("0.35")

    liquidity = Decimal("50")
    if trading_change is not None:
        liquidity += _clamp(trading_change / Decimal("2"), Decimal("-20"), Decimal("25"))
    if trading_value is not None and trading_value >= Decimal("10000000000"):
        liquidity += Decimal("8")

    return {
        "estimate_revision": Decimal("45"),
        "analyst_revision_ratio": Decimal("45"),
        "surprise": Decimal("48"),
        "guidance": Decimal("48"),
        "price_momentum": _score(momentum),
        "trading_value": _score(liquidity),
        "valuation": Decimal("45"),
        "macro": Decimal("45"),
        "flows": Decimal("45"),
        "sentiment": Decimal("45"),
    }


def _score_fast_candidate(item: dict[str, object], prices: list[object]) -> dict[str, object]:
    chart_analysis = _chart_analysis(prices)
    components = _fast_component_scores(item, chart_analysis)
    total = sum(components[key] * weight for key, weight in WEIGHTS.items()) / Decimal("100")
    one_month = _num(item.get("one_month_return"))
    three_month = _num(item.get("three_month_return"))
    trading_change = _num(item.get("trading_value_change"))
    chart_score = _num(chart_analysis.get("score")) or Decimal("0")

    reasons = [
        f"1개월 {one_month}%·3개월 {three_month}% 가격 모멘텀 기준 선별",
        f"차트 점수 {chart_score}점, {chart_analysis.get('trend') or '추세 데이터 부족'}",
    ]
    if trading_change is not None:
        reasons.append(f"거래대금 변화 {trading_change}% 반영")
    if chart_analysis.get("support"):
        reasons.append(f"차트 지지 {chart_analysis.get('support')}, 저항 {chart_analysis.get('resistance')}")

    risks = [
        "빠른 추천은 가격·거래대금·차트 중심으로 먼저 계산",
        "추정치·수급·밸류 세부 점수는 종목 상세/카드 새로고침에서 보강",
    ]
    risks.extend(str(value) for value in chart_analysis.get("risks", [])[:3])

    score_value = _score(total)
    return {
        "code": item["code"],
        "name": item["name"],
        "market": item["market"],
        "score": score_value,
        "action": _action(score_value, chart_analysis.get("score")),
        "price": item.get("price"),
        "change_rate": item.get("change_rate"),
        "one_month_return": item.get("one_month_return"),
        "three_month_return": item.get("three_month_return"),
        "trading_value": item.get("trading_value"),
        "component_scores": components,
        "chart_analysis": chart_analysis,
        "reasons": reasons[:8],
        "risks": risks[:6],
    }


def _universe_sort_value(price: DailyPrice) -> int:
    if price.market_cap is not None:
        return int(price.market_cap)
    return int(_row_value(price) or 0)


def _top_market_cap_universe(db: Session, refresh_live: bool = False) -> dict[str, object]:
    def build() -> dict[str, object]:
        latest_date = db.scalar(select(func.max(DailyPrice.trade_date)))
        if not latest_date:
            return {"universe_count": 0, "base_items": [], "price_groups": {}}

        latest_rows = list(
            db.execute(
                select(StockMaster, DailyPrice)
                .join(DailyPrice, DailyPrice.code == StockMaster.code)
                .where(DailyPrice.trade_date == latest_date)
                .where(DailyPrice.close.is_not(None))
            )
        )
        latest_rows.sort(key=lambda row: _universe_sort_value(row[1]), reverse=True)
        latest_rows = latest_rows[: MARKET_CAP_UNIVERSE_LIMIT * 2]
        selected_codes: list[str] = []
        selected_stocks: dict[str, StockMaster] = {}
        for stock, _price in latest_rows:
            if "스팩" in stock.name.upper() or "SPAC" in stock.name.upper():
                continue
            selected_codes.append(stock.code)
            selected_stocks[stock.code] = stock
            if len(selected_codes) >= MARKET_CAP_UNIVERSE_LIMIT:
                break

        if not selected_codes:
            return {"universe_count": 0, "base_items": [], "price_groups": {}}

        from_date = latest_date - timedelta(days=150)
        price_groups: dict[str, list[DailyPrice]] = {code: [] for code in selected_codes}
        for code, price in db.execute(
            select(DailyPrice.code, DailyPrice)
            .where(DailyPrice.code.in_(selected_codes))
            .where(DailyPrice.trade_date >= from_date)
            .order_by(DailyPrice.code, DailyPrice.trade_date)
        ):
            price_groups[str(code)].append(price)

        base_items = []
        for code in selected_codes:
            stock = selected_stocks[code]
            prices = price_groups.get(code, [])
            item = _base_item(stock, prices)
            if not item or not item.get("trading_value"):
                continue
            base_items.append(item)
        return {"universe_count": len(selected_codes), "base_items": base_items, "price_groups": price_groups}

    if refresh_live:
        payload = build()
        universe_cache.set("top_market_cap_universe", payload, UNIVERSE_CACHE_TTL_SECONDS)
        return payload
    return universe_cache.get_or_set("top_market_cap_universe", UNIVERSE_CACHE_TTL_SECONDS, build)


def build_recommendations(db: Session, limit: int = 8, candidate_limit: int = 50, refresh_live: bool = False) -> dict[str, object]:
    universe = _top_market_cap_universe(db, refresh_live=refresh_live)
    base_items = list(universe["base_items"])

    base_items.sort(key=_candidate_sort_key, reverse=True)
    score_pool_limit = max(candidate_limit, limit * 4)
    if refresh_live:
        score_pool_limit = max(score_pool_limit, candidate_limit + max(limit, 8))
    else:
        score_pool_limit = max(score_pool_limit, candidate_limit + max(limit * 2, 20))
    candidates = base_items[: min(len(base_items), score_pool_limit)]
    scored = []
    if refresh_live:
        with ThreadPoolExecutor(max_workers=min(8, max(len(candidates), 1))) as executor:
            futures = [executor.submit(_score_candidate, str(item["code"]), refresh_live) for item in candidates]
            for future in as_completed(futures):
                item = future.result()
                if item:
                    scored.append(item)
    else:
        grouped_prices = universe.get("price_groups") or {}
        scored = [_score_fast_candidate(item, grouped_prices.get(str(item["code"]), [])) for item in candidates]

    scored.sort(key=lambda item: item["score"], reverse=True)
    selected = _select_diverse_recommendations(scored, limit)
    for idx, item in enumerate(selected, start=1):
        item["rank"] = idx

    return {
        "as_of": _now_kst(),
        "universe_count": universe["universe_count"],
        "candidate_count": len(candidates),
        "methodology": METHODOLOGY,
        "items": selected,
    }
