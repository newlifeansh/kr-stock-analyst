from __future__ import annotations

from typing import Any

from app.config import Settings

THREAD_ID = "019ed577-3961-7f30-b9da-05112758804a"

INSIGHT_PRINCIPLES = [
    "Fetch faster than you decide: query can run every 1-5 minutes, but judgment should usually aggregate at 5 minutes or slower.",
    "Separate signal horizons: short-term timing, medium-term expectation change, and long-term value should not share the same decision clock.",
    "Use real-time data for alerts and ranking, then re-score with reports, disclosures, and macro context on slower loops.",
]

INSIGHT_HORIZONS = [
    {
        "key": "short_term_relative_return",
        "label": "Short-term relative return",
        "window": "2-8 weeks",
        "focus": "price leadership, event follow-through, and relative strength against the market and sector",
        "primary_inputs": [
            "price momentum",
            "trading value",
            "foreign and institutional flow",
            "breaking news",
            "disclosures",
        ],
    },
    {
        "key": "fundamental_expectation_change",
        "label": "Fundamental expectation change",
        "window": "6-18 months",
        "focus": "consensus revisions, industry cycle turns, and margin or revenue inflection",
        "primary_inputs": [
            "research reports",
            "earnings previews",
            "company IR",
            "macro and industry KPIs",
            "financial statement deltas",
        ],
    },
    {
        "key": "long_term_value_judgment",
        "label": "Long-term value judgment",
        "window": "3-5 years",
        "focus": "business quality, capital allocation, market structure, and structural growth durability",
        "primary_inputs": [
            "annual reports",
            "capital expenditure plans",
            "return on capital",
            "shareholder return policy",
            "industry structure",
        ],
    },
]

INTRADAY_LOOPS = [
    {
        "key": "held_names",
        "label": "Held names monitor",
        "interval": "1 minute",
        "purpose": "watch portfolio risk, abnormal moves, and news or disclosure hits without waiting for a full market scan",
        "sources": ["market data", "news", "disclosures"],
        "action_rule": "alert first, summarize every 5 minutes unless the move is exceptional",
    },
    {
        "key": "watchlist_scan",
        "label": "Watchlist scan",
        "interval": "5 minutes",
        "purpose": "refresh watched names with price, flow, report, and disclosure changes",
        "sources": ["market data", "research reports", "news", "disclosures"],
        "action_rule": "re-rank names by momentum, event freshness, and conviction",
    },
    {
        "key": "market_leaders",
        "label": "Top movers and trading value",
        "interval": "1 minute",
        "purpose": "surface unexpected leadership and liquidity concentration",
        "sources": ["market data"],
        "action_rule": "flag names only when volume and event context confirm the move",
    },
    {
        "key": "event_day_monitoring",
        "label": "Event day monitoring",
        "interval": "1 minute",
        "purpose": "tighten reaction time on earnings, disclosures, and volatility spikes",
        "sources": ["research reports", "disclosures", "news", "market data"],
        "action_rule": "switch to event mode only on relevant names or broad market stress",
    },
]

REVIEW_CYCLES = [
    {
        "key": "daily_close_review",
        "label": "Daily close review",
        "interval": "Daily",
        "purpose": "check whether the day changed the thesis, risk state, or watch priority",
        "sources": ["market data", "news", "disclosures", "research reports"],
        "action_rule": "write short notes on what changed and what did not",
    },
    {
        "key": "weekly_signal_refresh",
        "label": "Weekly signal refresh",
        "interval": "Weekly",
        "purpose": "recompute short-term leaders, losers, and signal decay",
        "sources": ["market data", "flow data", "event history"],
        "action_rule": "promote or demote names in the watchlist",
    },
    {
        "key": "monthly_macro_review",
        "label": "Monthly macro and industry review",
        "interval": "Monthly",
        "purpose": "update macro regime, sector preferences, and consensus direction",
        "sources": ["macro", "industry KPIs", "research reports", "financials"],
        "action_rule": "adjust sector overweight and underweight views",
    },
    {
        "key": "quarterly_thesis_validation",
        "label": "Quarterly thesis validation",
        "interval": "Quarterly",
        "purpose": "validate or rewrite the investment thesis around earnings season",
        "sources": ["financial statements", "earnings releases", "IR decks", "research reports"],
        "action_rule": "reset valuation, catalysts, and risk cases",
    },
]

DEFAULT_WATCH_RULES = [
    "Watchlist names: refresh every 5 minutes.",
    "Held names: refresh every 1 minute.",
    "Top movers and trading value leaders: refresh every 1 minute.",
    "News and disclosures: stream immediately when possible, otherwise poll every 1 minute.",
    "Research reports and consensus changes: review 1-2 times intraday and once again after the close.",
]

RESEARCH_SOURCES = [
    {
        "key": "naver_finance",
        "display_name": "Naver Finance Research",
        "source_type": "aggregator",
        "access_model": "free_public",
        "listing_url": "https://finance.naver.com/research/company_list.naver",
        "is_active_collector": True,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Current backend collector source for public research metadata and broker report links.",
    },
    {
        "key": "hankyung_consensus",
        "display_name": "Hankyung Korea Market Consensus",
        "source_type": "aggregator",
        "access_model": "free_public_partial",
        "listing_url": "https://www.hankyung.com/koreamarket/",
        "is_active_collector": False,
        "supports_pdf": False,
        "supports_target_price": True,
        "notes": "Useful as a public consensus discovery surface, but the backend collector is not attached yet.",
    },
    {
        "key": "hanaw",
        "display_name": "Hana Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.hanaw.com/main/research/research/list.cmd",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "koreainvestment",
        "display_name": "Korea Investment Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://securities.koreainvestment.com/main/research/research/Strategy.jsp?jkGubun=10",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "samsungpop",
        "display_name": "Samsung Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.samsungpop.com/sscommon/jsp/search/research/research_pop.jsp",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "miraeasset",
        "display_name": "Mirae Asset Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1800",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "kiwoom",
        "display_name": "Kiwoom Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.kiwoom.com/h/invest/research/VAnalCRView",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "daishin",
        "display_name": "Daishin Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://money2.daishin.com/e5/research/research/list.asp?m=3795",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "eugene",
        "display_name": "Eugene Investment Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.eugenefn.com/comm/msgList.do?board_yn=Y&menu_id=02010401&menu_lever=4&menu_url=%2Fingo%2Figii%2Figii400",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "hanwha",
        "display_name": "Hanwha Investment Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.hanwhawm.com/main/research/main/list.cmd?depth3_id=anls1&mode=R&p=&templet=default",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "ibk",
        "display_name": "IBK Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.ibks.com/customer/research/list/CompanyResearch",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "hyundai_motor",
        "display_name": "Hyundai Motor Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.hmsec.com/research/invest_list.do",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
    {
        "key": "im_securities",
        "display_name": "iM Securities Research",
        "source_type": "broker",
        "access_model": "free_public",
        "listing_url": "https://www.imfnsec.com/research/report/list",
        "is_active_collector": False,
        "supports_pdf": True,
        "supports_target_price": True,
        "notes": "Candidate public broker source from prior source review.",
    },
]


def insight_cadence_payload() -> dict[str, Any]:
    return {
        "thread_id": THREAD_ID,
        "principles": INSIGHT_PRINCIPLES,
        "horizons": INSIGHT_HORIZONS,
        "intraday_loops": INTRADAY_LOOPS,
        "review_cycles": REVIEW_CYCLES,
        "default_watch_rules": DEFAULT_WATCH_RULES,
    }


def research_source_payload(active_only: bool = False) -> list[dict[str, Any]]:
    if not active_only:
        return RESEARCH_SOURCES
    return [item for item in RESEARCH_SOURCES if item["is_active_collector"]]


def integration_payload(settings: Settings) -> list[dict[str, Any]]:
    toss_configured = bool(settings.toss_client_id and settings.toss_client_secret)
    toss_enabled = settings.toss_enabled
    items = [
        {
            "key": "kis_market_data",
            "display_name": "Korea Investment Open API",
            "integration_type": "market_data",
            "status": "active",
            "configured": bool(settings.kis_app_key and settings.kis_app_secret),
            "enabled": settings.briefing_realtime_enabled,
            "default_poll_seconds": settings.briefing_poll_seconds,
            "base_url": None,
            "purpose": "real-time home briefing snapshots, quotes, movers, and trading value scans",
            "capabilities": ["quotes", "movers", "watchlist polling"],
            "not_for": ["research reports", "news", "public disclosures"],
            "required_settings": ["KIS_APP_KEY", "KIS_APP_SECRET", "BRIEFING_REALTIME_ENABLED"],
            "note": "This is the live market data backbone for the current home briefing runtime.",
        },
        {
            "key": "open_dart",
            "display_name": "Open DART",
            "integration_type": "disclosure_api",
            "status": "active",
            "configured": bool(settings.dart_api_key),
            "enabled": settings.disclosure_enabled,
            "default_poll_seconds": settings.disclosure_poll_seconds,
            "base_url": "https://opendart.fss.or.kr/api",
            "purpose": "public disclosure, IR, and financial statement ingestion",
            "capabilities": ["disclosures", "financial statements", "IR events"],
            "not_for": ["live quotes", "broker research", "portfolio sync"],
            "required_settings": ["DART_API_KEY"],
            "note": "Current disclosure collector source.",
        },
        {
            "key": "naver_finance",
            "display_name": "Naver Finance",
            "integration_type": "public_web_source",
            "status": "active",
            "configured": True,
            "enabled": settings.research_enabled or settings.news_enabled,
            "default_poll_seconds": min(settings.research_poll_seconds, settings.news_poll_seconds),
            "base_url": "https://finance.naver.com",
            "purpose": "public research report metadata and public market news collection",
            "capabilities": ["research metadata", "news", "report links"],
            "not_for": ["broker account sync", "order execution", "official consensus API"],
            "required_settings": [],
            "note": "Current backend collector for public report and news surfaces.",
        },
        {
            "key": "toss_securities",
            "display_name": "Toss Securities Open API",
            "integration_type": "broker_api",
            "status": "scaffolded",
            "configured": toss_configured,
            "enabled": toss_enabled,
            "default_poll_seconds": settings.toss_poll_seconds,
            "base_url": settings.toss_base_url,
            "purpose": "connect account context, holdings, orderability, and execution-aware portfolio workflows",
            "capabilities": [
                "domestic and US quotes",
                "stock master data",
                "exchange rate",
                "market calendar",
                "accounts and holdings",
                "orders and order status",
            ],
            "not_for": ["broker research reports", "public news ingestion", "consensus history"],
            "required_settings": ["TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET", "TOSS_ACCOUNT_SEQ or TOSS_ACCOUNT_NO"],
            "note": "Official OAuth client, account, holdings, order, buying-power, and stock lookup integration is wired in. Live execution still requires valid credentials and account permissions.",
        },
    ]
    return items
