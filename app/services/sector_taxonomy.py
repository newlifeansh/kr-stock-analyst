from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InvestmentSector:
    key: str
    label: str


INVESTMENT_SECTORS: tuple[InvestmentSector, ...] = (
    InvestmentSector("semiconductor", "반도체"),
    InvestmentSector("it-software", "IT·소프트웨어"),
    InvestmentSector("electronics", "전기전자"),
    InvestmentSector("healthcare", "바이오·헬스케어"),
    InvestmentSector("consumer", "소비재"),
    InvestmentSector("automotive", "자동차"),
    InvestmentSector("shipbuilding-defense", "조선·방산"),
    InvestmentSector("industrials", "산업재·기계"),
    InvestmentSector("materials", "소재·화학"),
    InvestmentSector("energy-utilities", "에너지·유틸리티"),
    InvestmentSector("financials", "금융"),
    InvestmentSector("construction-real-estate", "건설·부동산"),
    InvestmentSector("transportation", "운송·물류"),
    InvestmentSector("media-content", "미디어·콘텐츠"),
    InvestmentSector("telecom", "통신"),
    InvestmentSector("other", "기타"),
)

INVESTMENT_SECTOR_BY_KEY = {item.key: item for item in INVESTMENT_SECTORS}


INDUSTRIES_BY_INVESTMENT_SECTOR: dict[str, tuple[str, ...]] = {
    "semiconductor": (
        "반도체와반도체장비",
    ),
    "it-software": (
        "IT서비스",
        "소프트웨어",
        "컴퓨터와주변기기",
        "사무용전자제품",
    ),
    "electronics": (
        "전자장비와기기",
        "통신장비",
        "핸드셋",
        "전기제품",
        "전기장비",
        "디스플레이장비및부품",
        "디스플레이패널",
        "전자제품",
    ),
    "healthcare": (
        "제약",
        "건강관리장비와용품",
        "생물공학",
        "생명과학도구및서비스",
        "건강관리업체및서비스",
        "건강관리기술",
    ),
    "consumer": (
        "식품",
        "섬유,의류,신발,호화품",
        "화장품",
        "가정용기기와용품",
        "음료",
        "백화점과일반상점",
        "판매업체",
        "호텔,레스토랑,레저",
        "가구",
        "레저용장비와제품",
        "가정용품",
        "식품과기본식료품소매",
        "인터넷과카탈로그소매",
        "전문소매",
        "다각화된소비자서비스",
        "담배",
        "문구류",
    ),
    "automotive": (
        "자동차부품",
        "자동차",
    ),
    "shipbuilding-defense": (
        "우주항공과국방",
        "조선",
    ),
    "industrials": (
        "기계",
        "상업서비스와공급품",
        "무역회사와판매업체",
    ),
    "materials": (
        "화학",
        "철강",
        "건축자재",
        "비철금속",
        "포장재",
        "종이와목재",
        "건축제품",
    ),
    "energy-utilities": (
        "에너지장비및서비스",
        "석유와가스",
        "가스유틸리티",
        "전기유틸리티",
        "복합유틸리티",
    ),
    "financials": (
        "창업투자",
        "증권",
        "은행",
        "기타금융",
        "손해보험",
        "생명보험",
        "카드",
    ),
    "construction-real-estate": (
        "건설",
        "부동산",
    ),
    "transportation": (
        "항공화물운송과물류",
        "해운사",
        "항공사",
        "도로와철도운송",
        "운송인프라",
    ),
    "media-content": (
        "방송과엔터테인먼트",
        "게임엔터테인먼트",
        "광고",
        "교육서비스",
        "양방향미디어와서비스",
        "출판",
    ),
    "telecom": (
        "무선통신서비스",
        "다각화된통신서비스",
    ),
    "other": (
        "복합기업",
    ),
}


def _industry_lookup() -> dict[str, str]:
    result: dict[str, str] = {}
    for sector_key, industries in INDUSTRIES_BY_INVESTMENT_SECTOR.items():
        for industry in industries:
            if industry in result:
                raise RuntimeError(f"Duplicate industry classification: {industry}")
            result[industry] = sector_key
    return result


INDUSTRY_TO_INVESTMENT_SECTOR = _industry_lookup()

RAW_SECTOR_TO_INVESTMENT_SECTOR = {
    "전기·전자": "electronics",
    "IT 서비스": "it-software",
    "화학": "materials",
    "기계·장비": "industrials",
    "제약": "healthcare",
    "일반서비스": "industrials",
    "유통": "consumer",
    "운송장비·부품": "automotive",
    "금속": "materials",
    "의료·정밀기기": "healthcare",
    "음식료·담배": "consumer",
    "기타금융업": "financials",
    "금융": "financials",
    "건설": "construction-real-estate",
    "오락·문화": "media-content",
    "섬유·의류": "consumer",
    "비금속": "materials",
    "기타금융": "financials",
    "운송·창고": "transportation",
    "증권": "financials",
    "종이·목재": "materials",
    "부동산": "construction-real-estate",
    "미분류": "other",
    "기타제조": "consumer",
    "보험": "financials",
    "통신": "telecom",
    "전기·가스": "energy-utilities",
    "은행(단절)": "financials",
    "농업·임업 및 어업": "consumer",
    "출판·매체복제": "media-content",
}


def _clean(value: Optional[str]) -> str:
    return " ".join(str(value or "").split())


def classify_investment_sector(
    sector: Optional[str],
    industry: Optional[str],
) -> InvestmentSector:
    """Map source classifications to one stable investment-sector group.

    The detailed industry is more specific and therefore takes precedence.
    Source values remain untouched; this function only adds a derived layer.
    """

    industry_key = INDUSTRY_TO_INVESTMENT_SECTOR.get(_clean(industry))
    raw_sector_key = RAW_SECTOR_TO_INVESTMENT_SECTOR.get(_clean(sector))
    return INVESTMENT_SECTOR_BY_KEY[industry_key or raw_sector_key or "other"]


def investment_sector_fields(
    sector: Optional[str],
    industry: Optional[str],
) -> dict[str, Optional[str]]:
    classification = classify_investment_sector(sector, industry)
    return {
        "sector": sector,
        "industry": industry,
        "investment_sector": classification.key,
        "investment_sector_label": classification.label,
    }
