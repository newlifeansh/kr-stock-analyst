from datetime import date

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.collectors import research
from app.collectors.research import (
    collect_canonical_research_reports,
    fetch_naver_company_reports_for_stock,
    fetch_stockhub_reports_for_stock,
    naver_mobile_research_url,
    parse_naver_listing_html,
    preferred_research_url,
)
from app.db import Base
from app.models import DailyPrice, IngestionRun, ResearchReport, StockMaster


COMPANY_HTML = """
<html>
  <body>
    <table class="type_1">
      <tr><th>header</th></tr>
      <tr><th>header</th></tr>
      <tr>
        <td><a href="/item/main.naver?code=005930">삼성전자</a></td>
        <td><a href="company_read.naver?nid=12345&page=1">반도체 업황 점검</a></td>
        <td>하나증권</td>
        <td><a href="https://stock.pstatic.net/stock-research/company/01/test.pdf">pdf</a></td>
        <td>26.06.17</td>
        <td>1,234</td>
      </tr>
    </table>
  </body>
</html>
"""


INDUSTRY_HTML = """
<html>
  <body>
    <table class="type_1">
      <tr><th>header</th></tr>
      <tr><th>header</th></tr>
      <tr>
        <td>반도체</td>
        <td><a href="industry_read.naver?nid=54321&page=1">Higher, Better, More!</a></td>
        <td>DS투자증권</td>
        <td><a href="https://stock.pstatic.net/stock-research/industry/01/test.pdf">pdf</a></td>
        <td>26.06.17</td>
        <td>2,345</td>
      </tr>
    </table>
  </body>
</html>
"""


COMPANY_DETAIL_HTML = """
<html>
  <body>
    <table class="type_1">
      <tr><th>투자의견</th><td>매수</td></tr>
      <tr><th>목표가</th><td>4,200,000</td></tr>
      <tr><td><a href="https://stock.pstatic.net/stock-research/company/01/detail.pdf">PDF</a></td></tr>
    </table>
  </body>
</html>
"""


STOCKHUB_HTML = r'''
<script>\"analystReports\":[{\"id\":13793,\"ticker\":\"078930\",\"broker\":\"DB증권\",\"report_title\":\"GS 목표가 120,000원 상향\",\"target_price\":120000,\"opinion_raw\":\"매수-유지\",\"report_date\":\"2026-07-20\",\"source_url\":\"https://www.db-fi.com/bbs/board.php?bo_table=research\",\"pdf_url\":null}],\"usConsensus\":null</script>
'''


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_collect_canonical_research_reports_validates_and_upserts(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "source": "stockhub",
                    "source_category": "company",
                    "external_id": "stockhub-16480",
                    "title": "한미약품 목표가 상향",
                    "stock_code": "128940",
                    "broker_name": "KB증권",
                    "target_price": "650000.00",
                    "published_at": "2026-09-10T00:00:00",
                },
                {
                    "source": "untrusted",
                    "source_category": "company",
                    "external_id": "bad",
                    "title": "거부",
                },
            ]

    monkeypatch.setattr(research.requests, "get", lambda *args, **kwargs: Response())

    with _session() as db:
        db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        db.add(
            DailyPrice(
                code="005930",
                trade_date=date(2026, 9, 10),
                open=100,
                high=110,
                low=90,
                close=105,
                market_cap=1_000_000,
            )
        )
        db.commit()
        count = collect_canonical_research_reports(
            db,
            base_url="https://canonical.example/",
            limit=900,
            timeout=7,
        )

        assert count == 1
        assert db.query(func.count(ResearchReport.id)).scalar() == 1
        report = db.query(ResearchReport).one()
        assert report.stock_code == "128940"
        assert report.target_price == 650000
        run = db.query(IngestionRun).one()
        assert run.source == "research"
        assert run.dataset == "canonical"
        assert run.message == (
            "canonical_limit=500 targeted_codes=1 targeted_failures=0"
        )


def test_parse_company_listing_html():
    items = parse_naver_listing_html(COMPANY_HTML, "company")
    assert len(items) == 1
    item = items[0]
    assert item.company_name == "삼성전자"
    assert item.stock_code == "005930"
    assert item.title == "반도체 업황 점검"
    assert item.broker_name == "하나증권"
    assert item.external_id == "12345"
    assert item.pdf_url and item.pdf_url.endswith("test.pdf")


def test_parse_industry_listing_html():
    items = parse_naver_listing_html(INDUSTRY_HTML, "industry")
    assert len(items) == 1
    item = items[0]
    assert item.subject_name == "반도체"
    assert item.company_name is None
    assert item.title == "Higher, Better, More!"
    assert item.external_id == "54321"


def test_fetch_company_detail_fields(monkeypatch):
    monkeypatch.setattr(research, "_naver_get_html", lambda url: COMPANY_DETAIL_HTML)

    fields = research.fetch_company_detail_fields("https://example.com/report")

    assert fields["opinion"] == "매수"
    assert fields["target_price"] == 4200000
    assert fields["pdf_url"].endswith("detail.pdf")


def test_fetch_company_reports_for_stock_uses_item_code_filter(monkeypatch):
    calls = []

    def fake_get_html(url):
        calls.append(url)
        return COMPANY_HTML

    monkeypatch.setattr(research, "_naver_get_html", fake_get_html)
    reports = fetch_naver_company_reports_for_stock("005930", days_back=180, max_pages=1, include_detail=False)

    assert len(reports) == 1
    assert reports[0].stock_code == "005930"
    assert calls and "searchType=itemCode" in calls[0] and "itemCode=005930" in calls[0]


def test_fetch_stockhub_reports_for_stock_parses_broker_metadata():
    reports = fetch_stockhub_reports_for_stock(
        STOCKHUB_HTML,
        "078930",
        days_back=180,
        now=research.datetime(2026, 8, 8),
    )

    assert len(reports) == 1
    assert reports[0].source == "stockhub"
    assert reports[0].external_id == "stockhub-13793"
    assert reports[0].broker_name == "DB증권"
    assert reports[0].target_price == 120000
    assert reports[0].detail_url.startswith("https://www.db-fi.com/")


def test_naver_mobile_research_url_points_to_the_report_detail():
    assert naver_mobile_research_url("000660", "94963") == (
        "https://m.stock.naver.com/domestic/stock/000660/research/94963"
    )
    assert naver_mobile_research_url("SK하이닉스", "94963") is None
    assert preferred_research_url(
        "000660",
        "94963",
        "https://stock.pstatic.net/stock-research/company/report.pdf",
        "https://finance.naver.com/research/company_read.naver?nid=94963",
    ) == "https://m.stock.naver.com/domestic/stock/000660/research/94963"
    assert preferred_research_url(
        None,
        None,
        "https://stock.pstatic.net/stock-research/company/report.pdf",
        "https://finance.naver.com/research/company_read.naver?nid=94963",
    ) == "https://stock.pstatic.net/stock-research/company/report.pdf"
