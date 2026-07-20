from datetime import date

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import naver_flows
from app.db import Base
from app.models import IngestionRun, InvestorFlow, StockMaster


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_parse_naver_investor_flow_html():
    html = """
    <table class="type2">
      <tr><th>날짜</th><th>기관</th><th>외국인</th></tr>
      <tr>
        <td>2026.06.24</td><td>340,500</td><td>상승 30,500</td><td>+9.84%</td>
        <td>46,319,709</td><td>+2,969,153</td><td>-596,340</td><td>2,772,464,983</td><td>47.42%</td>
      </tr>
    </table>
    """

    rows = naver_flows.parse_naver_investor_flow_html("005930", html)

    assert rows == [
        {
            "code": "005930",
            "trade_date": date(2026, 6, 24),
            "investor_type": "기관합계",
            "buy_volume": None,
            "sell_volume": None,
            "net_buy_volume": 2_969_153,
            "buy_value": None,
            "sell_value": None,
            "net_buy_value": 1_010_996_596_500,
        },
        {
            "code": "005930",
            "trade_date": date(2026, 6, 24),
            "investor_type": "외국인",
            "buy_volume": None,
            "sell_volume": None,
            "net_buy_volume": -596_340,
            "buy_value": None,
            "sell_value": None,
            "net_buy_value": -203_053_770_000,
        },
    ]


def test_collect_naver_investor_flows_commits_batches_and_skips_failed_codes(monkeypatch):
    def fake_fetch(code: str, pages: int):
        if code == "000660":
            raise RuntimeError("temporary failure")
        return [
            {
                "code": code,
                "trade_date": date(2026, 6, 24),
                "investor_type": "외국인",
                "buy_volume": None,
                "sell_volume": None,
                "net_buy_volume": 10,
                "buy_value": None,
                "sell_value": None,
                "net_buy_value": 1000,
            },
            {
                "code": code,
                "trade_date": date(2026, 6, 24),
                "investor_type": "기관합계",
                "buy_volume": None,
                "sell_volume": None,
                "net_buy_volume": -5,
                "buy_value": None,
                "sell_value": None,
                "net_buy_value": -500,
            },
        ]

    monkeypatch.setattr(naver_flows, "_fetch_rows_for_code", fake_fetch)

    with _session() as db:
        db.add_all(
            [
                StockMaster(code="005930", name="삼성전자", market="KOSPI"),
                StockMaster(code="000660", name="SK하이닉스", market="KOSPI"),
                StockMaster(code="035420", name="NAVER", market="KOSPI"),
            ]
        )
        db.commit()

        count = naver_flows.collect_naver_investor_flows(db, max_workers=2, batch_size=2)

        assert count == 4
        assert db.query(func.count(InvestorFlow.id)).scalar() == 4
        assert db.query(func.count(IngestionRun.id)).scalar() == 1
        run = db.query(IngestionRun).one()
        assert run.status == "success"
        assert run.message == "failed_codes=1"
