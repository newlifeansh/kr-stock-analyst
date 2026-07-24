from datetime import datetime

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import dart
from app.db import Base
from app.models import DisclosureItem, FinancialStatementLine, IngestionRun, StockMaster


class _Settings:
    dart_api_key = "test-key"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _payload(stock_code: str, account_name: str = "자산총계"):
    return {
        "status": "000",
        "message": "정상",
        "list": [
            {
                "stock_code": stock_code,
                "fs_div": "CFS",
                "sj_div": "BS",
                "account_id": "ifrs-full_Assets",
                "account_nm": account_name,
                "ord": "1",
                "thstrm_amount": "1,000",
                "frmtrm_amount": "900",
            }
        ],
    }


def test_collect_financial_statement_maps_amounts_and_stock_code(monkeypatch):
    monkeypatch.setattr(dart, "get_settings", lambda: _Settings())
    monkeypatch.setattr(dart, "fetch_opendart_json", lambda *args, **kwargs: _payload("005930"))

    with _session() as db:
        count = dart.collect_financial_statement(db, "00126380", "2025", "annual", "CFS")

        assert count == 1
        line = db.query(FinancialStatementLine).one()
        assert line.stock_code == "005930"
        assert line.reprt_code == "11011"
        assert line.current_amount == 1000


def test_collect_financial_statement_deduplicates_identical_dart_keys(monkeypatch):
    monkeypatch.setattr(dart, "get_settings", lambda: _Settings())
    payload = _payload("005930")
    duplicate = dict(payload["list"][0])
    duplicate["thstrm_amount"] = "1,100"
    payload["list"].append(duplicate)
    monkeypatch.setattr(dart, "fetch_opendart_json", lambda *args, **kwargs: payload)

    with _session() as db:
        count = dart.collect_financial_statement(db, "00126380", "2025", "annual", "CFS")

        assert count == 1
        line = db.query(FinancialStatementLine).one()
        assert line.current_amount == 1100


def test_collect_financial_statements_for_disclosure_companies_falls_back_to_annual(monkeypatch):
    monkeypatch.setattr(dart, "get_settings", lambda: _Settings())

    def fake_fetch(url, params, timeout=30):
        corp_code = params["corp_code"]
        report = params["reprt_code"]
        if corp_code == "corp-q1" and report == "11013":
            return _payload("000660", "매출액")
        if corp_code == "corp-fallback" and report == "11013":
            return {"status": "013", "message": "조회된 데이타가 없습니다."}
        if corp_code == "corp-fallback" and report == "11011":
            return _payload("005930", "자본총계")
        return {"status": "013", "message": "조회된 데이타가 없습니다."}

    monkeypatch.setattr(dart, "fetch_opendart_json", fake_fetch)

    with _session() as db:
        db.add_all(
            [
                DisclosureItem(
                    source="dart_api",
                    external_id="1",
                    disclosure_category="filings",
                    company_name="SK하이닉스",
                    stock_code="000660",
                    corp_code="corp-q1",
                    report_name="분기보고서",
                    published_at=datetime(2026, 6, 1),
                ),
                DisclosureItem(
                    source="dart_api",
                    external_id="2",
                    disclosure_category="filings",
                    company_name="삼성전자",
                    stock_code="005930",
                    corp_code="corp-fallback",
                    report_name="사업보고서",
                    published_at=datetime(2026, 5, 1),
                ),
            ]
        )
        db.commit()

        result = dart.collect_financial_statements_for_disclosure_companies(
            db,
            bsns_year="2026",
            report="q1",
            fs_div="CFS",
            fallback_previous_annual=True,
        )

        assert result["rows_loaded"] == 2
        assert result["companies_loaded"] == 2
        assert result["fallback_loaded"] == 1
        assert result["failed"] == 0
        assert db.query(func.count(FinancialStatementLine.id)).scalar() == 2
        assert db.query(func.count(IngestionRun.id)).scalar() == 1
        reports = {(line.stock_code, line.bsns_year, line.reprt_code) for line in db.query(FinancialStatementLine)}
        assert reports == {("000660", "2026", "11013"), ("005930", "2025", "11011")}


def test_financial_account_id_accepts_long_dart_identifiers():
    assert FinancialStatementLine.__table__.c.account_id.type.length == 255


def test_bulk_financials_uses_full_active_stock_master_without_disclosure(monkeypatch):
    monkeypatch.setattr(dart, "get_settings", lambda: _Settings())
    monkeypatch.setattr(dart, "dart_corp_code_map", lambda _settings=None: {"215600": "corp-sillajen"})
    monkeypatch.setattr(dart, "fetch_opendart_json", lambda *args, **kwargs: _payload("215600", "매출액"))

    with _session() as db:
        db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
        db.commit()

        result = dart.collect_financial_statements_for_disclosure_companies(
            db,
            bsns_year="2026",
            report="q1",
            fs_div="CFS",
        )

        assert result["companies"] == 1
        assert result["companies_loaded"] == 1
        assert db.query(FinancialStatementLine).one().stock_code == "215600"
