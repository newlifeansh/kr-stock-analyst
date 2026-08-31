from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.collectors.briefing import (
    BriefingBundle,
    BriefingEventPayload,
    BriefingMetricPayload,
    BriefingMoverPayload,
    BriefingQuotePayload,
    KisRestBriefingProvider,
    persist_briefing_bundle,
)
from app.config import Settings
from app.db import Base
from app.models import BriefingEvent, BriefingMetric, BriefingMover, BriefingQuote, BriefingSnapshot


def test_kis_daily_price_rows_use_final_session_ohlc(monkeypatch):
    provider = KisRestBriefingProvider(
        Settings(kis_app_key="key", kis_app_secret="secret")
    )
    payloads = {
        "010060": {
            "stck_oprc": "280500",
            "stck_hgpr": "283500",
            "stck_lwpr": "259500",
            "stck_prpr": "265000",
            "acml_vol": "276693",
            "acml_tr_pbmn": "74863818500",
        },
        "000000": {
            "stck_oprc": "100",
            "stck_hgpr": "90",
            "stck_lwpr": "80",
            "stck_prpr": "95",
        },
    }
    monkeypatch.setattr(
        provider,
        "_request_current_price",
        lambda code: payloads[code],
    )

    rows = provider.fetch_daily_price_rows(
        ["010060", "010060", "000000"],
        date(2026, 8, 21),
    )

    assert rows == [
        {
            "code": "010060",
            "trade_date": date(2026, 8, 21),
            "open": 280500,
            "high": 283500,
            "low": 259500,
            "close": 265000,
            "volume": 276693,
            "trading_value": 74863818500,
            "market_cap": None,
            "listed_shares": None,
        }
    ]


def test_kis_fluctuation_ranking_uses_case_sensitive_official_query_contract(monkeypatch):
    provider = KisRestBriefingProvider(
        Settings(kis_app_key="key", kis_app_secret="secret")
    )
    captured = {}

    def fake_get(path, tr_id, params):
        captured.update({"path": path, "tr_id": tr_id, "params": params})
        return {
            "output": [
                {
                    "mksc_shrn_iscd": "005930",
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "257000",
                    "prdy_vrss": "-9000",
                    "prdy_ctrt": "-3.38",
                    "acml_vol": "20300000",
                    "acml_tr_pbmn": "5200000000000",
                }
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    rows = provider._fetch_fluctuation(
        list_type="losers",
        limit=10,
        min_rate="-300",
        max_rate="0",
    )

    assert captured["path"] == "/uapi/domestic-stock/v1/ranking/fluctuation"
    assert captured["tr_id"] == "FHPST01700000"
    assert captured["params"] == {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "20170",
        "FID_INPUT_ISCD": "0000",
        "FID_RANK_SORT_CLS_CODE": "0",
        "FID_INPUT_CNT_1": "0",
        "FID_PRC_CLS_CODE": "0",
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_TRGT_CLS_CODE": "0",
        "FID_TRGT_EXLS_CLS_CODE": "0",
        "FID_DIV_CLS_CODE": "0",
        "FID_RSFL_RATE1": "-300",
        "FID_RSFL_RATE2": "0",
    }
    assert len(rows) == 1
    assert rows[0].code == "005930"
    assert rows[0].change_rate == Decimal("-3.38")


def test_kis_fluctuation_ranking_sorts_directionally_and_drops_flat_rows(monkeypatch):
    provider = KisRestBriefingProvider(
        Settings(kis_app_key="key", kis_app_secret="secret")
    )
    monkeypatch.setattr(
        provider,
        "_get",
        lambda *_args, **_kwargs: {
            "output": [
                {"mksc_shrn_iscd": "000001", "hts_kor_isnm": "A", "prdy_ctrt": "-1.0"},
                {"mksc_shrn_iscd": "000002", "hts_kor_isnm": "B", "prdy_ctrt": "0"},
                {"mksc_shrn_iscd": "000003", "hts_kor_isnm": "C", "prdy_ctrt": "-8.0"},
                {"mksc_shrn_iscd": "000004", "hts_kor_isnm": "D", "prdy_ctrt": "-3.0"},
            ]
        },
    )

    rows = provider._fetch_fluctuation("losers", 3, "-300", "0")

    assert [(row.code, row.rank, row.change_rate) for row in rows] == [
        ("000003", 1, Decimal("-8.0")),
        ("000004", 2, Decimal("-3.0")),
        ("000001", 3, Decimal("-1.0")),
    ]


def test_persist_briefing_bundle_in_memory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    bundle = BriefingBundle(
        briefing_kind="home",
        source="test",
        transport="polling",
        market_status="open",
        is_live=True,
        as_of=datetime(2026, 6, 17, 9, 1, 0),
        summary="watchlist=1 movers=1 disclosures=1",
        metrics=[
            BriefingMetricPayload(
                metric_key="market_status",
                label="장 상태",
                value_text="open",
                sort_order=0,
            )
        ],
        quotes=[
            BriefingQuotePayload(
                code="005930",
                name="삼성전자",
                market="KOSPI",
                role="watchlist",
                price=Decimal("81200"),
                change_rate=Decimal("1.23"),
            )
        ],
        movers=[
            BriefingMoverPayload(
                list_type="gainers",
                rank=1,
                code="000660",
                name="SK하이닉스",
                market="KOSPI",
                price=Decimal("250000"),
                change_rate=Decimal("3.45"),
            )
        ],
        events=[
            BriefingEventPayload(
                event_type="disclosure",
                source="dart",
                title="주요사항보고서",
                company_name="삼성전자",
            )
        ],
    )

    with SessionLocal() as db:
        snapshot = persist_briefing_bundle(db, bundle)

        assert snapshot.id == 1
        assert db.scalar(select(func.count()).select_from(BriefingSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingQuote)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingMover)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingEvent)) == 1


def test_persist_briefing_bundle_prunes_old_snapshots_and_children():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        for minute in range(4):
            bundle = BriefingBundle(
                briefing_kind="home",
                source="test",
                transport="polling",
                market_status="open",
                is_live=True,
                as_of=datetime(2026, 6, 17, 9, minute, 0),
                summary=f"snapshot={minute}",
                metrics=[
                    BriefingMetricPayload(
                        metric_key="market_status",
                        label="장 상태",
                        value_text="open",
                    )
                ],
                quotes=[
                    BriefingQuotePayload(
                        code="005930",
                        name="삼성전자",
                        market="KOSPI",
                        role="watchlist",
                    )
                ],
                movers=[
                    BriefingMoverPayload(
                        list_type="gainers",
                        rank=1,
                        code="000660",
                        name="SK하이닉스",
                        market="KOSPI",
                    )
                ],
                events=[
                    BriefingEventPayload(
                        event_type="news",
                        source="test",
                        title=f"뉴스 {minute}",
                    )
                ],
            )
            persist_briefing_bundle(db, bundle, retention_limit=2)

        assert db.scalar(select(func.count()).select_from(BriefingSnapshot)) == 2
        assert db.scalar(select(func.count()).select_from(BriefingMetric)) == 2
        assert db.scalar(select(func.count()).select_from(BriefingQuote)) == 2
        assert db.scalar(select(func.count()).select_from(BriefingMover)) == 2
        assert db.scalar(select(func.count()).select_from(BriefingEvent)) == 2
