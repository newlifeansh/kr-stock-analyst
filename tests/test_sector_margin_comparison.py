from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import CompanyProfile, StockCompanySnapshot, StockFundamentalSnapshot, StockMaster
from app.services.sector_margin_comparison import build_sector_margin_comparison


def _snapshot(
    code: str,
    rows: list[tuple[int, int, float]],
    *,
    estimated: tuple[int, int, float] | None = None,
    per: float | None = 12.0,
    estimated_per: float | None = 10.0,
):
    annual = [
        {
            "period": f"{year}.12",
            "estimated": False,
            "revenue": str(revenue),
            "operating_profit": str(revenue * margin / 100),
            "operating_margin": str(margin),
        }
        for year, revenue, margin in rows
    ]
    if estimated:
        year, revenue, margin = estimated
        annual.append(
            {
                "period": f"{year}.12 (E)",
                "estimated": True,
                "revenue": str(revenue),
                "operating_profit": str(revenue * margin / 100),
                "operating_margin": str(margin),
            }
        )
    payload = {"financial_series": {"annual": annual}}
    if per is not None:
        payload["per"] = str(per)
    if estimated_per is not None:
        payload["estimated_per"] = str(estimated_per)
    return StockFundamentalSnapshot(
        stock_code=code,
        source="naver_finance",
        payload=json.dumps(payload),
        fetched_at=datetime(2026, 8, 8, 9, 0),
    )


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            StockMaster.__table__,
            CompanyProfile.__table__,
            StockFundamentalSnapshot.__table__,
            StockCompanySnapshot.__table__,
        ],
    )
    return sessionmaker(bind=engine)()


def test_sector_margin_comparison_selects_revenue_leaders_and_always_keeps_target():
    db = _session()
    try:
        rows = [
            ("100001", "선택기업", 40, 18.0),
            ("100002", "매출1위", 120, 12.0),
            ("100003", "매출2위", 100, 8.0),
            ("100004", "매출3위", 90, 5.0),
            ("100005", "매출1위우", 120, 12.0),
            ("100006", "비교홀딩스", 200, 60.0),
        ]
        for code, name, revenue, margin in rows:
            db.add(StockMaster(code=code, name=name, market="KOSPI", sector="전기전자", industry="반도체"))
            db.add(
                StockCompanySnapshot(
                    stock_code=code,
                    source="naver_wisereport",
                    sector="전기전자",
                    industry="반도체",
                    fetched_at=datetime(2026, 8, 8, 9, 0),
                )
            )
            db.add(
                _snapshot(
                    code,
                    [(2023, revenue - 20, margin - 2), (2024, revenue - 10, margin - 1), (2025, revenue, margin)],
                    estimated=(2026, revenue + 20, margin + 4),
                )
            )
        db.commit()

        payload = build_sector_margin_comparison(db, "100001", limit=3)

        assert payload is not None
        assert payload["periods"] == ["2023", "2024", "2025"]
        assert [item["name"] for item in payload["companies"]] == ["매출1위", "매출2위", "선택기업"]
        assert all(point["year"] != 2026 for item in payload["companies"] for point in item["points"])
        assert payload["target_margin_rank"] == 1
        assert payload["peer_median_margin"] == 10
        assert payload["target_margin_gap"] == 8
        assert payload["valuation_comparison"]["target"]["name"] == "선택기업"
        assert payload["valuation_comparison"]["peer"]["name"] == "매출3위"
        assert payload["valuation_comparison"]["peer"]["current_per"] == 12
        assert "매출 규모 유사성" in payload["valuation_comparison"]["basis"]
    finally:
        db.close()


def test_sector_margin_comparison_falls_back_to_sector_when_industry_has_no_peers():
    db = _session()
    try:
        for code, name, industry, revenue in [
            ("200001", "선택기업", "세부A", 80),
            ("200002", "섹터동료", "세부B", 100),
        ]:
            db.add(StockMaster(code=code, name=name, market="KOSDAQ", sector="IT", industry=industry))
            db.add(
                StockCompanySnapshot(
                    stock_code=code,
                    source="naver_wisereport",
                    sector="IT",
                    industry=industry,
                    fetched_at=datetime(2026, 8, 8, 9, 0),
                )
            )
            db.add(_snapshot(code, [(2024, revenue - 10, 7.0), (2025, revenue, 9.0)]))
        db.commit()

        payload = build_sector_margin_comparison(db, "200001", limit=5)

        assert payload is not None
        assert payload["classification_level"] == "sector"
        assert payload["classification"] == "IT"
        assert len(payload["companies"]) == 2
        assert payload["valuation_comparison"]["peer"]["name"] == "섹터동료"
    finally:
        db.close()


def test_sector_margin_comparison_prefers_peer_with_complete_per_pair_before_closest_scale():
    db = _session()
    try:
        for code, name, revenue, per, estimated_per in [
            ("300001", "선택기업", 100, 14.0, 11.0),
            ("300002", "가까운기업", 105, 9.0, None),
            ("300003", "완전한기업", 120, 16.0, 13.0),
        ]:
            db.add(StockMaster(code=code, name=name, market="KOSPI", sector="산업재", industry="기계"))
            db.add(
                StockCompanySnapshot(
                    stock_code=code,
                    source="naver_wisereport",
                    sector="산업재",
                    industry="기계",
                    fetched_at=datetime(2026, 8, 8, 9, 0),
                )
            )
            db.add(
                _snapshot(
                    code,
                    [(2024, revenue - 10, 7.0), (2025, revenue, 9.0)],
                    per=per,
                    estimated_per=estimated_per,
                )
            )
        db.commit()

        payload = build_sector_margin_comparison(db, "300001", limit=3)

        assert payload is not None
        comparison = payload["valuation_comparison"]
        assert comparison["peer"]["name"] == "완전한기업"
        assert comparison["peer"]["current_per"] == 16
        assert comparison["peer"]["forward_per"] == 13
    finally:
        db.close()
