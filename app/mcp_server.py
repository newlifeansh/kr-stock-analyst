from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterator, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import SessionLocal
from app.meta import integration_payload, insight_cadence_payload, research_source_payload
from app.models import StockMaster
from app.repository import (
    briefing_events,
    briefing_metrics,
    briefing_movers,
    briefing_quotes,
    latest_briefing_snapshot,
    latest_disclosures,
    latest_news_items,
    latest_prices_by_codes,
    latest_research_reports,
)
from app.services.briefing import briefing_runtime
from app.services.company_briefs import build_company_briefs
from app.services.market_impact import build_market_impact
from app.services.market_rankings import build_market_rankings
from app.services.recommendations import build_recommendations
from app.services.stock_ai_analysis import build_stock_ai_analysis
from app.services.stock_dashboard import build_stock_dashboard

MCP_IMPORT_ERROR: Optional[Exception] = None
FastMCP = None
TransportSecuritySettings = None
if sys.version_info >= (3, 10):
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.server.transport_security import TransportSecuritySettings
    except Exception as exc:  # pragma: no cover - import path differs by runtime
        MCP_IMPORT_ERROR = exc
else:  # pragma: no cover - Python 3.9 local compatibility path
    MCP_IMPORT_ERROR = RuntimeError("MCP SDK requires Python 3.10 or newer.")

SEARCH_QUERY_RE = re.compile(r"[^0-9A-Z가-힣]")


def mcp_sdk_available() -> bool:
    return FastMCP is not None and TransportSecuritySettings is not None


def _split_csv(value: Optional[str]) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _json_text(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, indent=2)


def _end_of_day(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.combine(value, time(23, 59, 59))


@contextmanager
def _db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_query(value: str) -> str:
    return SEARCH_QUERY_RE.sub("", value.strip().upper())


def _normalize_stock_code(value: str) -> str:
    cleaned = _normalize_query(value)
    if len(cleaned) == 7 and cleaned.startswith("A") and cleaned[1:].isdigit():
        return cleaned[1:]
    return cleaned


def _search_stock_rows(db: Session, query: str, limit: int) -> list[StockMaster]:
    cleaned = query.strip()
    normalized = _normalize_query(cleaned)
    code = _normalize_stock_code(cleaned)
    statement = (
        select(StockMaster)
        .where(or_(StockMaster.name.contains(cleaned), StockMaster.code.startswith(code)))
        .order_by(StockMaster.market, StockMaster.code)
        .limit(500)
    )
    candidates = list(db.scalars(statement))
    if not candidates and normalized:
        candidates = [
            item
            for item in db.scalars(select(StockMaster).order_by(StockMaster.market, StockMaster.code).limit(5000))
            if normalized in _normalize_query(item.name) or code in item.code
        ]
    unique = {item.code: item for item in candidates}
    if code and code not in unique:
        exact = db.get(StockMaster, code)
        if exact:
            unique[exact.code] = exact

    price_map = latest_prices_by_codes(db, list(unique))

    def sort_key(item: StockMaster) -> tuple[int, int, int, int, str]:
        name_key = _normalize_query(item.name)
        exact_rank = 0 if item.code == code or item.name == cleaned or name_key == normalized else 1
        prefix_rank = 0 if item.name.startswith(cleaned) or name_key.startswith(normalized) else 1
        market_rank = 0 if item.market == "KOSPI" else 1 if item.market == "KOSDAQ" else 2
        market_cap = -(price_map.get(item.code).market_cap or 0) if item.code in price_map else 0
        return (exact_rank, prefix_rank, market_rank, market_cap, item.code)

    return sorted(unique.values(), key=sort_key)[:limit]


def _serialize_stock_rows(db: Session, rows: list[StockMaster]) -> list[dict[str, object]]:
    price_map = latest_prices_by_codes(db, [item.code for item in rows])
    payload: list[dict[str, object]] = []
    for item in rows:
        latest_price = price_map.get(item.code)
        payload.append(
            {
                "code": item.code,
                "name": item.name,
                "market": item.market,
                "latest_close": latest_price.close if latest_price else None,
                "latest_trade_date": latest_price.trade_date if latest_price else None,
                "market_cap": latest_price.market_cap if latest_price else None,
            }
        )
    return _json_safe(payload)


def _format_reports(items: list[Any]) -> list[dict[str, object]]:
    return _json_safe(
        [
            {
                "title": item.title,
                "company_name": item.company_name,
                "stock_code": item.stock_code,
                "broker_name": item.broker_name,
                "opinion": item.opinion,
                "target_price": item.target_price,
                "published_at": item.published_at,
                "detail_url": item.detail_url,
                "pdf_url": item.pdf_url,
                "source_category": item.source_category,
            }
            for item in items
        ]
    )


def _format_disclosures(items: list[Any]) -> list[dict[str, object]]:
    return _json_safe(
        [
            {
                "company_name": item.company_name,
                "stock_code": item.stock_code,
                "category": item.disclosure_category,
                "report_name": item.report_name,
                "filer_name": item.filer_name,
                "published_at": item.published_at,
                "detail_url": item.detail_url,
                "remark": item.remark,
            }
            for item in items
        ]
    )


def _format_news(items: list[Any]) -> list[dict[str, object]]:
    return _json_safe(
        [
            {
                "category": item.source_category,
                "title": item.title,
                "summary": item.summary,
                "press_name": item.press_name,
                "published_at": item.published_at,
                "detail_url": item.detail_url,
            }
            for item in items
        ]
    )


def _format_company_briefs(items: list[dict[str, object]]) -> list[dict[str, object]]:
    slimmed: list[dict[str, object]] = []
    for item in items:
        slimmed.append(
            {
                "company_name": item.get("company_name"),
                "stock_code": item.get("stock_code"),
                "market": item.get("market"),
                "latest_close": item.get("latest_close"),
                "latest_trade_date": item.get("latest_trade_date"),
                "report_count": item.get("report_count"),
                "disclosure_count": item.get("disclosure_count"),
                "news_count": item.get("news_count"),
                "total_count": item.get("total_count"),
                "latest_published_at": item.get("latest_published_at"),
                "latest_report_title": item.get("latest_report_title"),
                "latest_disclosure_title": item.get("latest_disclosure_title"),
                "latest_news_title": item.get("latest_news_title"),
            }
        )
    return _json_safe(slimmed)


def _transport_security(settings: Settings):
    if TransportSecuritySettings is None:
        return None
    allowed_hosts = _split_csv(getattr(settings, "mcp_allowed_hosts", ""))
    allowed_origins = _split_csv(getattr(settings, "mcp_allowed_origins", ""))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(allowed_hosts or allowed_origins),
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def build_insight_mcp_server(settings: Settings):
    if not mcp_sdk_available():
        return None

    server = FastMCP(
        name=settings.mcp_server_name,
        instructions=(
            "이 서버는 한국 주식 인사이트 데이터를 읽기 전용으로 제공합니다. "
            "증권사 리포트, 공시, 뉴스, 종목 브리핑, 시장 영향도를 조회할 수 있으며 "
            "투자 실행이나 계좌 조작은 허용하지 않습니다. "
            "응답은 데이터 설명과 근거를 함께 제공하되 투자 자문처럼 단정하지 말고, "
            "가능하면 최신 시각과 데이터 공백 여부를 함께 언급하세요."
        ),
        website_url=settings.mcp_public_base_url,
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_transport_security(settings),
        log_level=settings.mcp_log_level,
    )

    @server.resource(
        "insight://cadence",
        name="insight_cadence",
        title="인사이트 주기 기준",
        description="한국증시 인사이트를 읽는 주기와 판단 주기 기준입니다.",
        mime_type="application/json",
    )
    def insight_cadence_resource() -> str:
        return _json_text(insight_cadence_payload())

    @server.resource(
        "insight://sources",
        name="insight_sources",
        title="데이터 소스 현황",
        description="리포트, 공시, 뉴스, 브로커 연동 소스 현황입니다.",
        mime_type="application/json",
    )
    def insight_sources_resource() -> str:
        payload = {
            "research_sources": research_source_payload(active_only=False),
            "integrations": integration_payload(settings),
        }
        return _json_text(payload)

    @server.prompt(
        name="korea_stock_daily_brief",
        title="한국증시 일간 브리핑",
        description="시장 브리핑과 종목 근거를 함께 정리하는 프롬프트 템플릿입니다.",
    )
    def korea_stock_daily_brief(
        focus: str = "오늘 한국증시에서 중요한 종목과 이벤트를 요약해줘.",
    ) -> str:
        return (
            "당신은 한국증시 비밀노트의 리서치 어시스턴트다. "
            "먼저 get_market_briefing, get_market_impact, get_market_recommendations를 확인하고, "
            "필요하면 search_korea_stocks와 get_korea_stock_dashboard를 추가로 사용한다. "
            "리포트, 공시, 뉴스 근거를 분리해서 요약하고 데이터가 없는 부분은 빈칸으로 추정하지 않는다. "
            f"사용자 요청: {focus}"
        )

    @server.tool(
        name="get_data_pipeline_status",
        title="데이터 파이프라인 상태",
        description="현재 수집 파이프라인의 활성화 상태와 마지막 갱신 시각을 조회합니다.",
        structured_output=True,
    )
    def get_data_pipeline_status() -> dict[str, object]:
        return _json_safe(briefing_runtime.status())

    @server.tool(
        name="get_market_briefing",
        title="국내증시 현재 브리핑",
        description="최신 브리핑 스냅샷과 리포트·공시·뉴스 묶음을 함께 조회합니다.",
        structured_output=True,
    )
    def get_market_briefing(
        include_reports: int = 5,
        include_disclosures: int = 5,
        include_news: int = 5,
    ) -> dict[str, object]:
        with _db_session() as db:
            snapshot = latest_briefing_snapshot(db, kind="home")
            reports = latest_research_reports(db, limit=max(1, min(include_reports, 20)))
            disclosures = latest_disclosures(db, limit=max(1, min(include_disclosures, 20)))
            news_items = latest_news_items(db, limit=max(1, min(include_news, 20)))
            if snapshot is None:
                return {
                    "ok": False,
                    "message": "아직 브리핑 스냅샷이 없습니다.",
                    "reports": _format_reports(reports),
                    "disclosures": _format_disclosures(disclosures),
                    "news": _format_news(news_items),
                }
            movers_by_type: dict[str, list[dict[str, object]]] = {}
            for item in briefing_movers(db, snapshot.id):
                movers_by_type.setdefault(item.list_type, []).append(
                    {
                        "rank": item.rank,
                        "code": item.code,
                        "name": item.name,
                        "price": item.price,
                        "change_rate": item.change_rate,
                        "trading_value": item.trading_value,
                    }
                )
            payload = {
                "ok": True,
                "snapshot": {
                    "id": snapshot.id,
                    "title": f"{snapshot.briefing_kind} briefing",
                    "briefing_kind": snapshot.briefing_kind,
                    "market_status": snapshot.market_status,
                    "source": snapshot.source,
                    "transport": snapshot.transport,
                    "is_live": snapshot.is_live,
                    "summary": snapshot.summary,
                    "as_of": snapshot.as_of,
                    "metrics": [
                        {
                            "metric_key": item.metric_key,
                            "label": item.label,
                            "value_numeric": item.value_numeric,
                            "value_text": item.value_text,
                            "change_value": item.change_value,
                            "change_rate": item.change_rate,
                            "unit": item.unit,
                            "sort_order": item.sort_order,
                        }
                        for item in briefing_metrics(db, snapshot.id)
                    ],
                    "quotes": [
                        {
                            "role": item.role,
                            "code": item.code,
                            "name": item.name,
                            "price": item.price,
                            "change_rate": item.change_rate,
                            "trading_value": item.trading_value,
                        }
                        for item in briefing_quotes(db, snapshot.id)
                    ],
                    "movers": movers_by_type,
                    "events": [
                        {
                            "event_type": item.event_type,
                            "source": item.source,
                            "title": item.title,
                            "company_name": item.company_name,
                            "stock_code": item.stock_code,
                            "raw": item.raw,
                            "published_at": item.published_at,
                            "url": item.url,
                        }
                        for item in briefing_events(db, snapshot.id)
                    ],
                },
                "reports": _format_reports(reports),
                "disclosures": _format_disclosures(disclosures),
                "news": _format_news(news_items),
            }
            return _json_safe(payload)

    @server.tool(
        name="search_korea_stocks",
        title="국내 종목 검색",
        description="종목명 또는 코드로 한국 주식을 검색합니다.",
        structured_output=True,
    )
    def search_korea_stocks(query: str, limit: int = 10) -> dict[str, object]:
        with _db_session() as db:
            rows = _search_stock_rows(db, query, max(1, min(limit, 50)))
            return {
                "query": query,
                "count": len(rows),
                "stocks": _serialize_stock_rows(db, rows),
            }

    @server.tool(
        name="get_korea_stock_dashboard",
        title="국내 종목 상세 브리핑",
        description="특정 국내 종목의 시세, 리포트, 공시, 뉴스, 밸류에이션을 묶어서 조회합니다.",
        structured_output=True,
    )
    def get_korea_stock_dashboard(
        code: str,
        refresh: bool = False,
        include_ai_analysis: bool = True,
    ) -> dict[str, object]:
        normalized = _normalize_stock_code(code)
        with _db_session() as db:
            payload = build_stock_dashboard(db, normalized, refresh_live=refresh)
            if not payload:
                return {"ok": False, "code": normalized, "message": "종목을 찾지 못했습니다."}
            result = {"ok": True, "dashboard": payload}
            if include_ai_analysis:
                result["ai_analysis"] = build_stock_ai_analysis(payload)
            return _json_safe(result)

    @server.tool(
        name="list_research_reports",
        title="증권사 리포트 조회",
        description="최신 증권사 리포트 메타데이터를 조건별로 조회합니다.",
        structured_output=True,
    )
    def list_research_reports(
        limit: int = 10,
        stock_code: Optional[str] = None,
        company_name: Optional[str] = None,
        broker_name: Optional[str] = None,
        opinion: Optional[str] = None,
        source_category: Optional[str] = None,
        query: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict[str, object]:
        with _db_session() as db:
            items = latest_research_reports(
                db,
                limit=max(1, min(limit, 50)),
                stock_code=_normalize_stock_code(stock_code or "") or None,
                company_name=company_name,
                broker_name=broker_name,
                opinion=opinion,
                source_category=source_category,
                query=query,
                from_at=from_date,
                to_at=_end_of_day(to_date),
            )
            return {
                "count": len(items),
                "reports": _format_reports(items),
            }

    @server.tool(
        name="list_disclosures",
        title="공시·IR 조회",
        description="최신 공시·IR 데이터를 조건별로 조회합니다.",
        structured_output=True,
    )
    def list_disclosures(
        limit: int = 20,
        stock_code: Optional[str] = None,
        company_name: Optional[str] = None,
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict[str, object]:
        with _db_session() as db:
            items = latest_disclosures(
                db,
                limit=max(1, min(limit, 100)),
                stock_code=_normalize_stock_code(stock_code or "") or None,
                company_name=company_name,
                category=category,
                from_at=from_date,
                to_at=_end_of_day(to_date),
            )
            return {
                "count": len(items),
                "disclosures": _format_disclosures(items),
            }

    @server.tool(
        name="list_news_items",
        title="뉴스 조회",
        description="최신 한국증시 뉴스 메타데이터를 조건별로 조회합니다.",
        structured_output=True,
    )
    def list_news_items(
        limit: int = 20,
        category: Optional[str] = None,
        press_name: Optional[str] = None,
        query: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict[str, object]:
        with _db_session() as db:
            items = latest_news_items(
                db,
                limit=max(1, min(limit, 100)),
                category=category,
                press_name=press_name,
                query=query,
                from_at=from_date,
                to_at=_end_of_day(to_date),
            )
            return {
                "count": len(items),
                "news": _format_news(items),
            }

    @server.tool(
        name="get_company_briefs",
        title="종목 브리핑 묶음",
        description="리포트·공시·뉴스를 종목별로 묶은 브리핑 카드 목록을 조회합니다.",
        structured_output=True,
    )
    def get_company_briefs(limit: int = 20, query: Optional[str] = None) -> dict[str, object]:
        with _db_session() as db:
            research_items = latest_research_reports(db, limit=max(limit * 4, 80))
            disclosure_items = latest_disclosures(db, limit=max(limit * 4, 80))
            news_items = latest_news_items(db, limit=max(limit * 4, 80))
            briefs = build_company_briefs(
                db,
                research_items=research_items,
                disclosure_items=disclosure_items,
                news_items=news_items,
                limit=max(1, min(limit, 100)),
            )
            if query:
                normalized = _normalize_query(query)
                briefs = [
                    item
                    for item in briefs
                    if normalized in _normalize_query(str(item.get("company_name") or ""))
                    or normalized in _normalize_query(str(item.get("stock_code") or ""))
                ]
            return {
                "count": len(briefs),
                "items": _format_company_briefs(briefs[:limit]),
            }

    @server.tool(
        name="get_market_rankings",
        title="시장 랭킹 조회",
        description="급등, 거래대금, 밸류에이션 등 국내증시 랭킹을 조회합니다.",
        structured_output=True,
    )
    def get_market_rankings(
        category: str = "surge",
        market: str = "ALL",
        limit: int = 20,
    ) -> dict[str, object]:
        return _json_safe(build_market_rankings(category=category, limit=max(1, min(limit, 100)), market=market))

    @server.tool(
        name="get_market_recommendations",
        title="관심 종목 추천",
        description="현재 데이터 기준으로 우선 모니터링할 국내 종목 추천 목록을 조회합니다.",
        structured_output=True,
    )
    def get_market_recommendations(limit: int = 8, candidate_limit: int = 30) -> dict[str, object]:
        return _json_safe(
            build_recommendations(
                limit=max(1, min(limit, 20)),
                candidate_limit=max(5, min(candidate_limit, 100)),
            )
        )

    @server.tool(
        name="get_market_impact",
        title="시장 영향도 분석",
        description="금리, 달러, 채권, 원자재, 위험선호가 한국증시에 주는 영향도를 조회합니다.",
        structured_output=True,
    )
    def get_market_impact() -> dict[str, object]:
        return _json_safe(build_market_impact())

    return server
