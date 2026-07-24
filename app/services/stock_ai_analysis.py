from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _num(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_number(value: object) -> str:
    number = _num(value)
    if number is None:
        return "-"
    return f"{number:,.0f}"


def _fmt_percent(value: object) -> str:
    number = _num(value)
    if number is None:
        return "-"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def _fmt_money(value: object) -> str:
    number = _num(value)
    if number is None:
        return "-"
    if abs(number) >= 1_0000_0000_0000:
        return f"{number / 1_0000_0000_0000:,.1f}조"
    if abs(number) >= 1_0000_0000:
        return f"{number / 1_0000_0000:,.1f}억"
    return f"{number:,.0f}"


def _fmt_multiple(value: object) -> str:
    number = _num(value)
    if number is None:
        return "-"
    return f"{number:.2f}x"


def _round_trade_price(value: float | None) -> int | None:
    if value is None:
        return None
    absolute = abs(value)
    if absolute >= 500_000:
        tick = 1000
    elif absolute >= 200_000:
        tick = 500
    elif absolute >= 50_000:
        tick = 100
    elif absolute >= 20_000:
        tick = 50
    elif absolute >= 5_000:
        tick = 10
    elif absolute >= 2_000:
        tick = 5
    else:
        tick = 1
    return int(round(value / tick) * tick)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _near_price_level(raw: object, price: float | None, *, side: str, max_distance_pct: float = 12.0) -> int | None:
    raw_number = _num(raw)
    if raw_number is None or price is None or price <= 0:
        return None
    distance_pct = abs(raw_number - price) / price * 100
    if distance_pct > max_distance_pct:
        return None
    if side == "support" and raw_number >= price:
        return None
    if side == "resistance" and raw_number <= price:
        return None
    return _round_trade_price(raw_number)


def _trade_levels(price: object, chart: dict[str, Any]) -> dict[str, int | str | bool | None]:
    price_number = _num(price)
    if price_number is None or price_number <= 0:
        return {
            "buy_low": None,
            "buy_high": None,
            "breakout": None,
            "stop": None,
            "first_sell": None,
            "support_reference": _round_trade_price(_num(chart.get("support"))),
            "resistance_reference": _round_trade_price(_num(chart.get("resistance"))),
            "actionable": False,
            "entry_label": "관찰 가격대",
            "entry_note": "데이터 부족",
        }

    atr = _num(chart.get("atr_percent"))
    moving_averages = chart.get("moving_averages") if isinstance(chart.get("moving_averages"), dict) else {}
    support_reference = _round_trade_price(_num(chart.get("support")))
    resistance_reference = _round_trade_price(_num(chart.get("resistance")))
    raw_support = _near_price_level(
        chart.get("support"),
        price_number,
        side="support",
        max_distance_pct=3.0,
    )
    raw_resistance = _near_price_level(
        chart.get("resistance"),
        price_number,
        side="resistance",
        max_distance_pct=3.0,
    )
    ma_supports = [
        _near_price_level(moving_averages.get(key), price_number, side="support", max_distance_pct=3.0)
        for key in ("ma5", "ma20", "ma60")
    ]
    ma_supports = [value for value in ma_supports if value is not None]

    # The execution guide is intentionally tighter than the full technical box.
    # Distant support/resistance remains visible as evidence, but should not create
    # an impractically wide first-order range.
    atr_basis = _clamp(atr or 3.0, 1.0, 8.0)
    pullback_pct = _clamp(atr_basis * 0.45, 1.0, 2.2)
    upper_discount_pct = _clamp(atr_basis * 0.10, 0.2, 0.6)
    buy_high_raw = price_number * (1 - upper_discount_pct / 100)
    fallback_buy_low = price_number * (1 - pullback_pct / 100)
    nearby_supports = [value for value in [raw_support, *ma_supports] if value is not None]
    nearby_supports = [value for value in nearby_supports if fallback_buy_low <= value <= buy_high_raw]
    preferred_buy_low = max(nearby_supports) if nearby_supports else fallback_buy_low
    minimum_zone_low = buy_high_raw * 0.992
    buy_low = _round_trade_price(max(fallback_buy_low, min(preferred_buy_low, minimum_zone_low)))
    buy_high = _round_trade_price(buy_high_raw)

    stop_pct = _clamp(atr_basis * 0.55, 2.0, 3.5)
    stop = _round_trade_price(
        min(
            price_number * (1 - stop_pct / 100),
            (buy_low or price_number) * 0.992,
        )
    )
    breakout_pct = _clamp(atr_basis * 0.35, 1.2, 2.5)
    breakout_floor = price_number * 1.012
    breakout_ceiling = price_number * 1.025
    breakout_raw = price_number * (1 + breakout_pct / 100)
    if raw_resistance is not None:
        breakout_raw = _clamp(raw_resistance, breakout_floor, breakout_ceiling)
    breakout = _round_trade_price(breakout_raw)
    sell_pct = _clamp(atr_basis * 0.8, 3.0, 5.5)
    first_sell = _round_trade_price(
        max(
            (breakout or 0) * 1.008,
            price_number * (1 + sell_pct / 100),
        )
    )

    return {
        "buy_low": buy_low,
        "buy_high": buy_high,
        "breakout": breakout,
        "stop": stop,
        "first_sell": first_sell,
        "support_reference": support_reference,
        "resistance_reference": resistance_reference,
        "actionable": False,
        "entry_label": "관찰 가격대",
        "entry_note": "신규 매수 보류 기준",
    }


def _fmt_range(low: object, high: object) -> str:
    low_number = _num(low)
    high_number = _num(high)
    if low_number is None or high_number is None:
        return "-"
    return f"{_fmt_number(min(low_number, high_number))}~{_fmt_number(max(low_number, high_number))}"


def _tone(value: float | None, positive: float, negative: float) -> int:
    if value is None:
        return 0
    if value >= positive:
        return 1
    if value <= negative:
        return -1
    return 0


def _first(items: list[str], fallback: str) -> str:
    return items[0] if items else fallback


def _topic_name(name: object) -> str:
    text = str(name or "해당 종목")
    if not text:
        return "해당 종목은"
    last = text[-1]
    if "가" <= last <= "힣":
        return f"{text}{'은' if (ord(last) - ord('가')) % 28 else '는'}"
    return f"{text}은"


def _as_state(value: str) -> str:
    if not value:
        return "-"
    last = value[-1]
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 == 0:
        return f"{value}로"
    return f"{value}으로"


def _is_us_market(market: object) -> bool:
    normalized = str(market or "").strip().upper()
    return normalized not in {"", "KOSPI", "KOSDAQ", "KONEX"}


def _flow_plain(
    primary_intensity: float | None,
    secondary_intensity: float | None,
    *,
    is_us: bool = False,
    secondary_label: str = "기관",
) -> str:
    if primary_intensity is None and secondary_intensity is None:
        return "아직 흐름이 한쪽으로 강하게 기울지는 않았습니다."
    primary_positive = primary_intensity is not None and primary_intensity > 0
    secondary_positive = secondary_intensity is not None and secondary_intensity > 0
    primary_negative = primary_intensity is not None and primary_intensity < 0
    secondary_negative = secondary_intensity is not None and secondary_intensity < 0
    if is_us:
        if primary_positive and secondary_positive:
            return f"개별 종목과 {secondary_label}가 함께 살아 있어 추세가 버티기 좋은 편입니다."
        if primary_negative and secondary_negative:
            return f"개별 종목과 {secondary_label}가 같이 식어 있어 상승 탄력이 약해질 수 있습니다."
        if primary_positive and secondary_negative:
            return f"개별 종목 거래는 강하지만 {secondary_label}가 따라오지 않아 힘이 갈립니다."
        if primary_negative and secondary_positive:
            return f"{secondary_label}는 받치지만 개별 종목 쪽 거래가 약해 방향 확인이 더 필요합니다."
        return "개별 종목과 ETF 흐름이 아직 한쪽으로 강하게 정리되지는 않았습니다."
    if primary_positive and secondary_positive:
        return "외국인과 기관이 함께 사는 쪽이라 수급은 우호적입니다."
    if primary_negative and secondary_negative:
        return "외국인과 기관이 함께 파는 쪽이라 가격이 눌릴 수 있습니다."
    if primary_positive and secondary_negative:
        return "외국인은 사고 있지만 기관 매도가 있어 힘이 갈립니다."
    if primary_negative and secondary_positive:
        return "기관은 사고 있지만 외국인 매도가 있어 힘이 갈립니다."
    return "수급은 한쪽으로 강하게 기울지 않았습니다."


def _valuation_plain(per_z: float | None, pbr_z: float | None) -> str:
    rich_count = sum(1 for value in (per_z, pbr_z) if value is not None and value > 1.5)
    cheap_count = sum(1 for value in (per_z, pbr_z) if value is not None and value < -1.0)
    if rich_count >= 2:
        return "과거와 비교하면 가격 부담이 큰 편입니다."
    if rich_count == 1:
        return "일부 지표에서 가격 부담이 보입니다."
    if cheap_count:
        return "과거와 비교하면 가격 부담은 크지 않습니다."
    return "가격 부담은 과도하지도, 아주 싸지도 않은 구간입니다."


def _plain_chart_risk(chart_risks: list[str]) -> str:
    joined = " ".join(chart_risks)
    if not joined:
        return "큰 위험 신호는 많지 않지만, 기준 가격 이탈 여부는 봐야 합니다."
    if "ATR" in joined or "변동성" in joined:
        return "하루 변동폭이 큰 편이라 매수 직후 흔들림이 커질 수 있습니다."
    if "거래량" in joined or "거래대금" in joined:
        return "거래가 충분히 늘지 않으면 상승이 오래 이어지기 어렵습니다."
    if "20일선" in joined or "60일선" in joined:
        return "최근 평균 가격 아래로 내려가면 단기 흐름이 약해질 수 있습니다."
    if "지지" in joined or "이탈" in joined:
        return "가까운 지지 가격이 깨지면 하락 속도가 빨라질 수 있습니다."
    return "차트상 부담 신호가 있어 가격 변동이 커질 수 있습니다."


def _intraday_context(day_change: float | None, one_month: float | None) -> str:
    if day_change is None:
        return "오늘 등락 데이터는 확인 중입니다."
    if day_change >= 2 and one_month is not None and one_month <= -5:
        return (
            f"오늘 {_fmt_percent(day_change)} 강세지만 1개월 {_fmt_percent(one_month)}여서, "
            "급락 뒤 반등인지 추세 전환인지 구분해야 합니다."
        )
    if day_change >= 2:
        return f"오늘 {_fmt_percent(day_change)} 강세로 단기 매수세가 유입되고 있습니다."
    if day_change <= -2 and one_month is not None and one_month >= 5:
        return (
            f"오늘 {_fmt_percent(day_change)} 조정 중이지만 1개월 {_fmt_percent(one_month)} 흐름은 아직 유지되고 있습니다."
        )
    if day_change <= -2:
        return f"오늘 {_fmt_percent(day_change)} 약세로 단기 매도 압력이 커졌습니다."
    return f"오늘 등락률은 {_fmt_percent(day_change)}로 방향성이 크지 않습니다."


def build_stock_ai_analysis(dashboard: dict[str, Any]) -> dict[str, object]:
    quote = dashboard.get("quote", {})
    momentum = dashboard.get("momentum", {})
    chart = dashboard.get("chart_analysis", {})
    revisions = dashboard.get("revisions", {})
    surprise = dashboard.get("surprise", {})
    guidance = dashboard.get("guidance", {})
    flows = dashboard.get("flows", {})
    valuation = dashboard.get("valuation", {})
    sentiment = dashboard.get("sentiment", {})
    macro = dashboard.get("macro_sensitivity", {})
    coverage = dashboard.get("coverage", {})
    is_us = _is_us_market(dashboard.get("market"))

    score = 0
    day_change = _num(quote.get("change_rate"))
    chart_score = _num(chart.get("score"))
    one_month = _num(momentum.get("one_month_return"))
    three_month = _num(momentum.get("three_month_return"))
    value_change = _num(momentum.get("trading_value_change"))
    sentiment_score = _num(sentiment.get("score"))
    foreign_intensity = _num(flows.get("foreign_intensity"))
    institution_intensity = _num(flows.get("institution_intensity"))
    per_z = _num(valuation.get("per_zscore"))
    pbr_z = _num(valuation.get("pbr_zscore"))
    profit_growth = _num(surprise.get("operating_profit_growth"))
    target_up_ratio = _num(revisions.get("target_up_ratio"))

    score += 2 * _tone(chart_score, 70, 45)
    score += _tone(one_month, 8, -8)
    score += _tone(three_month, 15, -15)
    score += _tone(value_change, 30, -30)
    score += _tone(sentiment_score, 20, -20)
    score += _tone(foreign_intensity, 0.5, -0.5)
    score += _tone(institution_intensity, 0.5, -0.5)
    score += _tone(profit_growth, 10, -10)
    score += _tone(target_up_ratio, 55, 35)
    if per_z is not None and per_z > 1.5:
        score -= 1
    if pbr_z is not None and pbr_z > 1.5:
        score -= 1

    if score >= 5:
        stance = "관심 매수 후보"
    elif score >= 2:
        stance = "추세 확인 후 분할 접근"
    elif score <= -3:
        stance = "관망 우선"
    else:
        stance = "중립 관찰"

    data_total = len(coverage) if isinstance(coverage, dict) else 0
    data_covered = sum(1 for value in coverage.values() if value) if isinstance(coverage, dict) else 0
    confidence = Decimal(str(round(data_covered / data_total * 100, 1))) if data_total else Decimal("0")

    price = quote.get("price")
    actionable_trade = stance in {"관심 매수 후보", "추세 확인 후 분할 접근"}
    trade_levels = _trade_levels(price, chart)
    trade_levels["actionable"] = actionable_trade
    trade_levels["entry_label"] = "1차 매수권" if actionable_trade else "관찰 가격대"
    trade_levels["entry_note"] = "분할 접근 구간" if actionable_trade else "신규 매수 보류 기준"
    buy_zone = _fmt_range(trade_levels["buy_low"], trade_levels["buy_high"])
    stop_line = trade_levels["stop"]
    breakout_line = trade_levels["breakout"]
    first_sell_line = trade_levels["first_sell"]
    support_reference = trade_levels["support_reference"]
    resistance_reference = trade_levels["resistance_reference"]
    intraday_context = _intraday_context(day_change, one_month)
    latest_news = sentiment.get("latest_items") or []
    latest_news_title = latest_news[0].get("title") if latest_news else "최근 뉴스 신호가 제한적입니다."
    etf_symbol = str(flows.get("etf_symbol") or "섹터 ETF")
    macro_fx = macro.get("fx")
    if macro_fx is None:
        macro_fx = macro.get("fx_usdkrw")
    macro_growth = macro.get("export")
    if macro_growth is None:
        macro_growth = macro.get("exports")

    if actionable_trade:
        summary = (
            f"{intraday_context} {_topic_name(dashboard.get('name'))} 현재 {_as_state(stance)} 분류됩니다. "
            f"차트는 {chart.get('stance') or '-'}이고, 1개월 {_fmt_percent(one_month)}, "
            f"3개월 {_fmt_percent(three_month)} 흐름입니다. "
            f"현재가 {_fmt_number(price)} 기준 1차 매수권은 {buy_zone}, 돌파 기준은 {_fmt_number(breakout_line)}입니다."
        )
    else:
        summary = (
            f"{intraday_context} {_topic_name(dashboard.get('name'))} 현재 {_as_state(stance)} 분류됩니다. "
            f"차트는 {chart.get('stance') or '-'}이고, 1개월 {_fmt_percent(one_month)}, "
            f"3개월 {_fmt_percent(three_month)} 흐름입니다. "
            f"현재가 {_fmt_number(price)} 기준 {buy_zone}은 실행 구간이 아니라 관찰 가격대이며, "
            f"신규 매수는 {_fmt_number(breakout_line)} 돌파와 거래대금 증가가 나온 뒤로 미룹니다."
        )

    if is_us:
        flow_plain = _flow_plain(
            foreign_intensity,
            institution_intensity,
            is_us=True,
            secondary_label=etf_symbol,
        )
        flow_point = (
            f"개별 거래대금 변화 {_fmt_percent(foreign_intensity)}, {etf_symbol} 흐름 {_fmt_percent(institution_intensity)}입니다. {flow_plain}"
        )
        macro_point = (
            f"뉴스 점수 {_fmt_percent(sentiment_score)}이며, 금리 {_fmt_percent(macro.get('interest_rate'))}, "
            f"달러 {_fmt_percent(macro_fx)}, 원자재 {_fmt_percent(macro.get('commodity'))}, "
            f"리스크 선호 {_fmt_percent(macro_growth)}를 함께 봅니다."
        )
        flow_section = {
            "title": "유동성과 ETF 흐름",
            "items": [
                f"개별 종목 거래대금 변화는 {_fmt_percent(foreign_intensity)}이고, {etf_symbol} 거래대금 변화는 {_fmt_percent(institution_intensity)}입니다.",
                f"최근 거래대금 변화 {_fmt_percent(value_change)}로 시장 관심이 다시 붙는지 확인합니다.",
            ],
        }
        news_macro_section = {
            "title": "뉴스와 매크로",
            "items": [
                f"뉴스 점수 {_fmt_percent(sentiment_score)}: {latest_news_title}",
                f"금리 {_fmt_percent(macro.get('interest_rate'))}, 달러 {_fmt_percent(macro_fx)}, 원자재 {_fmt_percent(macro.get('commodity'))}, 리스크 선호 {_fmt_percent(macro_growth)}를 같이 봅니다.",
            ],
        }
    else:
        flow_plain = _flow_plain(foreign_intensity, institution_intensity)
        flow_point = (
            f"{flow_plain} 외국인 {_fmt_percent(foreign_intensity)}, 기관 {_fmt_percent(institution_intensity)}입니다."
        )
        macro_point = (
            f"최근 뉴스 흐름은 {_fmt_percent(sentiment_score)}입니다. 가장 눈에 띄는 뉴스는 '{latest_news_title}'입니다."
        )
        flow_section = {
            "title": "수급과 거래대금",
            "items": [
                f"외국인 20일 순매수 {_fmt_money(flows.get('foreign_net_buy_20d'))}, 기관 20일 순매수 {_fmt_money(flows.get('institution_net_buy_20d'))}입니다.",
                f"거래대금 변화 {_fmt_percent(value_change)}로 시장 관심 변화를 확인합니다.",
            ],
        }
        news_macro_section = {
            "title": "뉴스와 거시",
            "items": [
                f"뉴스 점수 {_fmt_percent(sentiment_score)}: {latest_news_title}",
                f"금리 {_fmt_percent(macro.get('interest_rate'))}, 환율 {_fmt_percent(macro_fx)}, 원자재 {_fmt_percent(macro.get('commodity'))}, 수출 {_fmt_percent(macro_growth)} 민감도를 함께 봅니다.",
            ],
        }

    chart_risks = [str(item) for item in chart.get("risks") or []]
    key_points = [
        intraday_context,
        f"가격 흐름은 {chart.get('stance') or chart.get('trend') or '-'}입니다. 1개월 {_fmt_percent(one_month)}, 3개월 {_fmt_percent(three_month)}라 단기와 중기 흐름을 같이 봅니다.",
        f"거래대금은 최근 {_fmt_money(quote.get('trading_value'))}이고 변화율은 {_fmt_percent(value_change)}입니다. 돈이 계속 들어오는지가 핵심입니다.",
        flow_point,
        f"이익 대비 가격(PER)은 {_fmt_multiple(valuation.get('per'))}, 자산 대비 가격(PBR)은 {_fmt_multiple(valuation.get('pbr'))}입니다. {_valuation_plain(per_z, pbr_z)}",
        macro_point,
    ]

    if actionable_trade:
        strategy = [
            f"1차 매수: {buy_zone}에서 가격이 밀리지 않고 거래대금이 유지될 때만 분할 접근합니다.",
            f"추가 매수: {_fmt_number(breakout_line)} 위로 올라서고 거래대금이 늘면 돌파 매수 구간으로 봅니다.",
            f"매도/축소: {_fmt_number(stop_line)} 아래로 내려가면 시나리오가 틀린 것으로 보고 비중을 줄입니다.",
            f"1차 매도: {_fmt_number(first_sell_line)} 부근에서는 일부 이익실현을 먼저 고려합니다.",
        ]
    else:
        strategy = [
            f"신규 매수: 보류합니다. {buy_zone}은 가격이 안정되는지 보는 관찰 가격대입니다.",
            f"전환 가격: {_fmt_number(breakout_line)} 위로 올라서고 거래대금이 늘 때만 분할 접근 후보로 다시 봅니다.",
            f"보유 대응: {_fmt_number(stop_line)} 아래로 내려가면 약세 지속으로 보고 비중을 줄입니다.",
            f"이익 관리: 이미 보유 중이라면 {_fmt_number(first_sell_line)} 부근에서 일부 이익실현만 참고합니다.",
        ]

    risks = [
        _plain_chart_risk(chart_risks),
        "가격이 올라가도 거래대금이 같이 늘지 않으면 따라 사기보다 한 번 쉬어가는 편이 좋습니다.",
    ]
    if per_z is not None and per_z > 1.5:
        risks.append("이익 기준으로는 과거보다 비싸게 거래되고 있어 실적 기대가 꺾이면 조정이 커질 수 있습니다.")
    if pbr_z is not None and pbr_z > 1.5:
        risks.append("자산가치 기준으로도 가격 부담이 있어 급등 뒤에는 되돌림을 조심해야 합니다.")
    if sentiment_score is not None and sentiment_score < 0:
        risks.append("최근 뉴스 흐름이 좋지 않아 단기 투자심리가 약해질 수 있습니다.")

    sections = [
        {
            "title": "차트와 타이밍",
            "items": [
                f"{chart.get('stance') or '-'} 판단입니다. 핵심 신호는 {_first(chart.get('signals') or [], '아직 뚜렷하지 않습니다.')}",
                (
                    f"매매 기준은 1차 매수 {buy_zone}, 돌파 {_fmt_number(breakout_line)}, 손절/축소 {_fmt_number(stop_line)}입니다."
                    if actionable_trade
                    else f"가격 기준은 관찰 가격대 {buy_zone}, 전환 가격 {_fmt_number(breakout_line)}, 축소 기준 {_fmt_number(stop_line)}입니다. 현재 판단에서는 신규 매수 실행선이 아닙니다."
                ),
                f"참고 박스권은 지지 {_fmt_number(support_reference)}, 저항 {_fmt_number(resistance_reference)}입니다. 현재가와 멀면 매매 실행선으로 쓰지 않습니다.",
            ],
        },
        {
            "title": "실적과 밸류",
            "items": [
                f"최근 영업이익 변화는 {_fmt_percent(profit_growth)}이고 리포트 수는 {_fmt_number(revisions.get('report_count_90d'))}건입니다.",
                f"추정 EPS {_fmt_number(revisions.get('estimated_eps'))}, 추정 PER {_fmt_multiple(valuation.get('estimated_per'))} 기준으로 봅니다.",
            ],
        },
        flow_section,
        news_macro_section,
        {
            "title": "조건부 시나리오",
            "items": [
                (
                    f"상승 시나리오: {_fmt_number(breakout_line)} 돌파와 거래대금 증가가 동시에 나오면 추가 상승 흐름으로 봅니다."
                    if actionable_trade
                    else f"매수 전환 시나리오: {_fmt_number(breakout_line)} 돌파와 거래대금 증가가 동시에 나와야 신규 매수 후보로 격상합니다."
                ),
                f"하락 시나리오: {_fmt_number(stop_line)} 이탈 시 단기 추세 훼손으로 보고 신규 매수는 보류합니다.",
            ],
        },
    ]

    return {
        "code": dashboard.get("code"),
        "name": dashboard.get("name"),
        "market": dashboard.get("market"),
        "as_of": dashboard.get("as_of"),
        "generated_at": datetime.now(timezone.utc),
        "stance": stance,
        "confidence": confidence,
        "data_covered": data_covered,
        "data_total": data_total,
        "summary": summary,
        "key_points": key_points,
        "strategy": strategy,
        "risks": risks[:5],
        "sections": sections,
        "trade_levels": trade_levels,
        "generation_mode": "rules",
        "model_name": None,
        "generation_note": "데이터 기반 규칙 분석",
    }
