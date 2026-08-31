from app.models import StockMaster
from app.schemas import StockOut
from app.services.sector_taxonomy import (
    INDUSTRIES_BY_INVESTMENT_SECTOR,
    INDUSTRY_TO_INVESTMENT_SECTOR,
    INVESTMENT_SECTORS,
    classify_investment_sector,
    investment_sector_fields,
)


def test_investment_sector_taxonomy_is_complete_and_unique():
    assert len(INVESTMENT_SECTORS) == 16
    assert len({item.key for item in INVESTMENT_SECTORS}) == len(INVESTMENT_SECTORS)
    assert len({item.label for item in INVESTMENT_SECTORS}) == len(INVESTMENT_SECTORS)
    assert len(INDUSTRY_TO_INVESTMENT_SECTOR) == 78
    for sector_key, industries in INDUSTRIES_BY_INVESTMENT_SECTOR.items():
        assert all(INDUSTRY_TO_INVESTMENT_SECTOR[industry] == sector_key for industry in industries)


def test_investment_sector_uses_detailed_industry_before_raw_sector():
    assert classify_investment_sector("전기·전자", "반도체와반도체장비").label == "반도체"
    assert classify_investment_sector("화학", "화장품").label == "소비재"
    assert classify_investment_sector("일반서비스", "제약").label == "바이오·헬스케어"
    assert classify_investment_sector("운송장비·부품", "조선").label == "조선·방산"


def test_investment_sector_falls_back_without_losing_source_classification():
    fields = investment_sector_fields("음식료·담배", None)

    assert fields == {
        "sector": "음식료·담배",
        "industry": None,
        "investment_sector": "consumer",
        "investment_sector_label": "소비재",
    }
    assert classify_investment_sector(None, None).key == "other"


def test_stock_api_schema_exposes_derived_investment_sector():
    stock = StockMaster(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        is_active=True,
        sector="전기·전자",
        industry="반도체와반도체장비",
    )

    payload = StockOut.model_validate(stock).model_dump()

    assert payload["sector"] == "전기·전자"
    assert payload["industry"] == "반도체와반도체장비"
    assert payload["investment_sector"] == "semiconductor"
    assert payload["investment_sector_label"] == "반도체"
