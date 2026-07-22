from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KR Stock Analyst Backend"
    database_url: str = "sqlite:///./data/analyst.db"
    dart_api_key: Optional[str] = None
    ecos_api_key: Optional[str] = None
    kis_app_key: Optional[str] = None
    kis_app_secret: Optional[str] = None
    kis_env: str = "real"
    kis_realtime_enabled: bool = True
    briefing_realtime_enabled: bool = True
    briefing_poll_seconds: int = 30
    briefing_watch_codes: str = "005930,000660,035420,005380,105560"
    briefing_disclosure_limit: int = 20
    briefing_report_limit: int = 10
    briefing_news_limit: int = 12
    research_enabled: bool = True
    research_poll_seconds: int = 600
    research_categories: str = "company,industry,market,economy,invest,debenture"
    research_max_pages: int = 2
    research_days_back: int = 3
    research_include_detail: bool = True
    research_backfill_poll_seconds: int = 86400
    research_backfill_max_pages: int = 20
    research_backfill_days_back: int = 180
    disclosure_enabled: bool = True
    disclosure_poll_seconds: int = 300
    disclosure_days_back: int = 7
    disclosure_page_count: int = 100
    news_enabled: bool = True
    news_poll_seconds: int = 300
    news_categories: str = "breaking,market,company,global,bond,disclosure_memo,fx"
    news_max_pages: int = 2
    news_days_back: int = 3
    price_enabled: bool = True
    price_poll_seconds: int = 1800
    price_days_back: int = 7
    price_code_limit: int = 80
    price_max_workers: int = 8
    investor_flow_enabled: bool = True
    investor_flow_poll_seconds: int = 1800
    investor_flow_pages: int = 1
    investor_flow_code_limit: Optional[int] = None
    investor_flow_max_workers: int = 8
    financials_enabled: bool = True
    financials_poll_seconds: int = 21600
    financials_year: Optional[str] = None
    financials_report: Optional[str] = None
    financials_fs_div: str = "CFS"
    financials_company_limit: Optional[int] = None
    macro_enabled: bool = True
    macro_poll_seconds: int = 21600
    macro_range: str = "1y"
    web_push_enabled: bool = True
    web_push_poll_seconds: int = 60
    web_push_price_threshold: float = 5.0
    web_push_event_lead_hours: int = 24
    web_push_vapid_private_key: Optional[str] = None
    web_push_vapid_public_key: Optional[str] = None
    web_push_vapid_subject: str = "mailto:admin@secret-note.app"
    toss_enabled: bool = False
    toss_base_url: str = "https://openapi.tossinvest.com"
    toss_client_id: Optional[str] = None
    toss_client_secret: Optional[str] = None
    toss_account_no: Optional[str] = None
    toss_account_seq: Optional[int] = None
    toss_poll_seconds: int = 60
    toss_order_poll_seconds: int = 300
    toss_sync_holdings_enabled: bool = False
    bootstrap_on_start: bool = True
    bootstrap_force_refresh: bool = False
    mcp_enabled: bool = True
    mcp_server_name: str = "한국증시 비밀노트"
    mcp_public_base_url: Optional[str] = None
    mcp_allowed_hosts: str = "127.0.0.1:*,localhost:*"
    mcp_allowed_origins: str = (
        "https://playmcp.kakao.com,"
        "http://127.0.0.1:8000,http://localhost:8000,"
        "http://127.0.0.1:8001,http://localhost:8001"
    )
    mcp_log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def briefing_watch_code_list(self) -> list[str]:
        return [code.strip() for code in self.briefing_watch_codes.split(",") if code.strip()]

    def research_category_list(self) -> list[str]:
        return [category.strip() for category in self.research_categories.split(",") if category.strip()]

    def news_category_list(self) -> list[str]:
        return [category.strip() for category in self.news_categories.split(",") if category.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
