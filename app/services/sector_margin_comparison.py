from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from statistics import median
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CompanyProfile, StockCompanySnapshot, StockFundamentalSnapshot, StockMaster


PREFERRED_SHARE_SUFFIX = re.compile(r"(?:\d*우(?:B)?|우선주)$", re.IGNORECASE)
FINANCIAL_INDUSTRY_PREFIXES = ("64", "65", "66")
NON_OPERATING_NAME_TOKENS = ("홀딩스", "스퀘어", "지주")


def _decimal(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def _year(value: object) -> Optional[int]:
    match = re.search(r"(20\d{2})", str(value or ""))
    return int(match.group(1)) if match else None


def _actual_annual_points(payload: str) -> dict[int, dict[str, object]]:
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return {}
    annual = ((parsed.get("financial_series") or {}).get("annual") or [])
    result: dict[int, dict[str, object]] = {}
    for raw in annual:
        if not isinstance(raw, dict) or raw.get("estimated"):
            continue
        year = _year(raw.get("period"))
        revenue = _decimal(raw.get("revenue"))
        operating_profit = _decimal(raw.get("operating_profit"))
        operating_margin = _decimal(raw.get("operating_margin"))
        if operating_margin is None and revenue not in (None, 0) and operating_profit is not None:
            operating_margin = (
                operating_profit * Decimal("100") / revenue
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if year is None or operating_margin is None:
            continue
        result[year] = {
            "period": str(raw.get("period") or year),
            "year": year,
            "revenue": revenue,
            "operating_margin": operating_margin,
        }
    return result


def _valuation_values(payload: str) -> dict[str, Optional[Decimal]]:
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        parsed = {}
    return {
        "current_per": _decimal(parsed.get("per")),
        "forward_per": _decimal(parsed.get("estimated_per")),
    }


def _positive_multiple(value: object) -> Optional[Decimal]:
    number = _decimal(value)
    return number if number is not None and number > 0 else None


def _share_name_key(name: str) -> str:
    return PREFERRED_SHARE_SUFFIX.sub("", name.strip())


def _is_financial_profile(profile: Optional[CompanyProfile]) -> bool:
    industry_code = str(profile.industry_code or "") if profile else ""
    return industry_code.startswith(FINANCIAL_INDUSTRY_PREFIXES)


def _classification_value(
    stock: StockMaster,
    company: Optional[StockCompanySnapshot],
    level: str,
) -> str:
    company_value = getattr(company, level, None) if company else None
    stock_value = getattr(stock, level, None)
    return str(company_value or stock_value or "").strip()


def _empty_payload(
    stock: StockMaster,
    *,
    industry: str,
    sector: str,
    classification_level: str = "industry",
) -> dict[str, object]:
    classification = industry if classification_level == "industry" else sector
    return {
        "code": stock.code,
        "name": stock.name,
        "industry": industry or None,
        "sector": sector or None,
        "classification": classification or None,
        "classification_level": classification_level,
        "basis": "동일 업종 · 최근 실제 연간 매출 상위 · 선택 종목 포함",
        "latest_period": None,
        "periods": [],
        "companies": [],
        "target_margin_rank": None,
        "peer_median_margin": None,
        "target_margin_gap": None,
        "valuation_comparison": None,
        "source": "네이버 금융",
        "as_of": None,
    }


def build_sector_margin_comparison(
    db: Session,
    code: str,
    *,
    limit: int = 5,
) -> Optional[dict[str, object]]:
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        return None

    target_company = db.get(StockCompanySnapshot, code)
    target_profile = db.get(CompanyProfile, code)
    target_fundamental = db.get(StockFundamentalSnapshot, code)
    industry = _classification_value(stock, target_company, "industry")
    sector = _classification_value(stock, target_company, "sector")
    target_points = _actual_annual_points(target_fundamental.payload) if target_fundamental else {}
    target_years = [year for year, point in target_points.items() if point.get("revenue") not in (None, 0)]
    if not target_years:
        return _empty_payload(stock, industry=industry, sector=sector)
    latest_year = max(target_years)

    rows = db.execute(
        select(StockMaster, StockFundamentalSnapshot, StockCompanySnapshot, CompanyProfile)
        .join(StockFundamentalSnapshot, StockFundamentalSnapshot.stock_code == StockMaster.code)
        .outerjoin(StockCompanySnapshot, StockCompanySnapshot.stock_code == StockMaster.code)
        .outerjoin(CompanyProfile, CompanyProfile.stock_code == StockMaster.code)
        .where(StockMaster.is_active.is_(True))
    ).all()

    target_is_financial = _is_financial_profile(target_profile) or "금융" in sector
    target_is_holding = any(token in stock.name for token in NON_OPERATING_NAME_TOKENS)

    def candidates_for(level: str, value: str) -> list[dict[str, object]]:
        if not value:
            return []
        candidates: list[dict[str, object]] = []
        for candidate_stock, fundamental, company, profile in rows:
            if _classification_value(candidate_stock, company, level) != value:
                continue
            if candidate_stock.code != code and PREFERRED_SHARE_SUFFIX.search(candidate_stock.name):
                continue
            if not target_is_financial and candidate_stock.code != code and _is_financial_profile(profile):
                continue
            if (
                not target_is_holding
                and candidate_stock.code != code
                and any(token in candidate_stock.name for token in NON_OPERATING_NAME_TOKENS)
            ):
                continue
            points = _actual_annual_points(fundamental.payload)
            valuation = _valuation_values(fundamental.payload)
            latest = points.get(latest_year)
            if not latest or latest.get("revenue") in (None, 0):
                continue
            candidates.append(
                {
                    "code": candidate_stock.code,
                    "name": candidate_stock.name,
                    "is_target": candidate_stock.code == code,
                    "latest_revenue": latest["revenue"],
                    "points_by_year": points,
                    "current_per": _positive_multiple(valuation["current_per"]),
                    "forward_per": _positive_multiple(valuation["forward_per"]),
                    "fetched_at": fundamental.fetched_at,
                }
            )

        deduplicated: dict[str, dict[str, object]] = {}
        for candidate in candidates:
            key = _share_name_key(str(candidate["name"]))
            existing = deduplicated.get(key)
            if existing is None or candidate["is_target"] or PREFERRED_SHARE_SUFFIX.search(str(existing["name"])):
                deduplicated[key] = candidate
        return list(deduplicated.values())

    classification_level = "industry"
    comparable = candidates_for("industry", industry)
    if len(comparable) < 2:
        classification_level = "sector"
        comparable = candidates_for("sector", sector)
    classification = industry if classification_level == "industry" else sector
    if len(comparable) < 2:
        return _empty_payload(
            stock,
            industry=industry,
            sector=sector,
            classification_level=classification_level,
        )

    comparable.sort(key=lambda item: (Decimal(str(item["latest_revenue"])), item["code"]), reverse=True)
    for rank, candidate in enumerate(comparable, start=1):
        candidate["revenue_rank"] = rank

    selected = comparable[:limit]
    target = next((item for item in comparable if item["is_target"]), None)
    if target and not any(item["is_target"] for item in selected):
        selected = [*selected[: max(0, limit - 1)], target]
    selected.sort(key=lambda item: (Decimal(str(item["latest_revenue"])), item["code"]), reverse=True)

    years = sorted(
        {
            year
            for candidate in selected
            for year in candidate["points_by_year"]
            if year <= latest_year
        }
    )[-4:]
    companies: list[dict[str, object]] = []
    for candidate in selected:
        points = [
            {
                "period": candidate["points_by_year"][year]["period"],
                "year": year,
                "operating_margin": candidate["points_by_year"][year]["operating_margin"],
            }
            for year in years
            if year in candidate["points_by_year"]
        ]
        latest_margin = candidate["points_by_year"][latest_year]["operating_margin"]
        companies.append(
            {
                "code": candidate["code"],
                "name": candidate["name"],
                "is_target": candidate["is_target"],
                "revenue_rank": candidate["revenue_rank"],
                "latest_revenue": candidate["latest_revenue"],
                "latest_operating_margin": latest_margin,
                "points": points,
            }
        )

    latest_margins = sorted(
        companies,
        key=lambda item: (Decimal(str(item["latest_operating_margin"])), item["code"]),
        reverse=True,
    )
    target_company = next((item for item in companies if item["is_target"]), None)
    target_margin_rank = (
        next(index for index, item in enumerate(latest_margins, start=1) if item["is_target"])
        if target_company
        else None
    )
    peer_margins = [
        Decimal(str(item["latest_operating_margin"]))
        for item in companies
        if not item["is_target"]
    ]
    peer_median_margin = (
        Decimal(str(median(peer_margins))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if peer_margins
        else None
    )
    target_margin = Decimal(str(target_company["latest_operating_margin"])) if target_company else None
    target_margin_gap = (
        (target_margin - peer_median_margin).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if target_margin is not None and peer_median_margin is not None
        else None
    )
    valuation_comparison = None
    if target:
        target_revenue = Decimal(str(target["latest_revenue"]))
        peers = [item for item in comparable if not item["is_target"]]

        def valuation_peer_sort(item: dict[str, object]) -> tuple[object, ...]:
            completeness = sum(
                value is not None
                for value in (item.get("current_per"), item.get("forward_per"))
            )
            revenue = Decimal(str(item["latest_revenue"]))
            scale_ratio = (
                max(target_revenue, revenue) / min(target_revenue, revenue)
                if target_revenue > 0 and revenue > 0
                else Decimal("999999")
            )
            return (-completeness, scale_ratio, -revenue, str(item["code"]))

        peer = min(peers, key=valuation_peer_sort) if peers else None
        if peer:
            completeness = sum(
                value is not None
                for value in (peer.get("current_per"), peer.get("forward_per"))
            )
            completeness_reason = (
                "현재·예상 PER 자료가 모두 있고"
                if completeness == 2
                else "확인 가능한 PER 자료가 있으며"
                if completeness == 1
                else "PER 자료 확인이 필요하지만"
            )
            valuation_as_of = [
                item["fetched_at"]
                for item in (target, peer)
                if isinstance(item.get("fetched_at"), datetime)
            ]

            def valuation_company(item: dict[str, object]) -> dict[str, object]:
                return {
                    "code": item["code"],
                    "name": item["name"],
                    "is_target": item["is_target"],
                    "latest_revenue": item["latest_revenue"],
                    "current_per": item.get("current_per"),
                    "forward_per": item.get("forward_per"),
                }

            valuation_comparison = {
                "classification": classification or None,
                "classification_level": classification_level,
                "basis": f"동일 {'업종' if classification_level == 'industry' else '섹터'} · PER 자료 완성도 · {latest_year}년 매출 규모 유사성",
                "selection_reason": f"비교 기업은 {peer['name']}입니다. {completeness_reason} 최근 실제 연간 매출 규모가 선택 종목과 가장 가깝습니다.",
                "target": valuation_company(target),
                "peer": valuation_company(peer),
                "source": "네이버 금융",
                "as_of": max(valuation_as_of) if valuation_as_of else None,
            }
    fetched_values = [item["fetched_at"] for item in selected if isinstance(item.get("fetched_at"), datetime)]

    return {
        "code": stock.code,
        "name": stock.name,
        "industry": industry or None,
        "sector": sector or None,
        "classification": classification or None,
        "classification_level": classification_level,
        "basis": f"동일 {'업종' if classification_level == 'industry' else '섹터'} · {latest_year}년 매출 상위 · 선택 종목 포함",
        "latest_period": str(latest_year),
        "periods": [str(year) for year in years],
        "companies": companies,
        "target_margin_rank": target_margin_rank,
        "peer_median_margin": peer_median_margin,
        "target_margin_gap": target_margin_gap,
        "valuation_comparison": valuation_comparison,
        "source": "네이버 금융",
        "as_of": max(fetched_values) if fetched_values else None,
    }
