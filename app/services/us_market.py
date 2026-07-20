from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import re
from statistics import mean
from typing import Optional
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests

from app.services.stock_dashboard import _chart_analysis, _rate, _round_decimal
from app.services.ttl_cache import TTLCache

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_CHART_FALLBACK_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
YAHOO_COOKIE_URL = "https://fc.yahoo.com"
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_QUOTE_SUMMARY_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
YAHOO_TIMESERIES_URLS = (
    "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}",
    "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}",
)
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
US_CACHE = TTLCache(maxsize=2048)
US_TTL_SECONDS = 180
US_FX_TTL_SECONDS = 300
US_SECTOR_OPEN_TTL_SECONDS = 30
US_SECTOR_CLOSED_TTL_SECONDS = 300
US_HEADERS = {"User-Agent": "Mozilla/5.0"}
SEC_HEADERS = {"User-Agent": "secret-note-us-dashboard/0.1 local research app"}
NEW_YORK_TZ = ZoneInfo("America/New_York")

US_FUNDAMENTAL_TYPES: tuple[str, ...] = (
    "trailingPeRatio",
    "quarterlyDilutedEPS",
    "quarterlyTotalRevenue",
    "quarterlyOperatingIncome",
    "quarterlyNetIncome",
    "annualDilutedEPS",
    "annualTotalRevenue",
    "annualOperatingIncome",
    "annualNetIncome",
    "quarterlyStockholdersEquity",
    "annualStockholdersEquity",
    "quarterlyCommonStockEquity",
    "annualCommonStockEquity",
    "quarterlyTangibleBookValue",
    "annualTangibleBookValue",
    "quarterlyOrdinarySharesNumber",
    "annualOrdinarySharesNumber",
    "quarterlyShareIssued",
    "annualShareIssued",
    "quarterlyTotalDebt",
    "annualTotalDebt",
    "quarterlyCashAndCashEquivalents",
    "annualCashAndCashEquivalents",
    "quarterlyTotalAssets",
    "annualTotalAssets",
    "trailingAnnualDividendYield",
    "trailingAnnualDividendRate",
)

US_QUOTE_SUMMARY_MODULES: tuple[str, ...] = (
    "financialData",
    "recommendationTrend",
    "upgradeDowngradeHistory",
)

US_NEWS_POSITIVE_SIGNALS: tuple[tuple[str, int, str], ...] = (
    ("all-time high", 4, "사상 최고가 기대"),
    ("record high", 4, "신고가 기대"),
    ("buy zone", 3, "매수 구간 진입"),
    ("bullish", 3, "강세 의견"),
    ("outperform", 3, "시장 대비 우위"),
    ("upgrade", 3, "투자의견 상향"),
    ("raises price target", 3, "목표가 상향"),
    ("raised price target", 3, "목표가 상향"),
    ("price target raised", 3, "목표가 상향"),
    ("beat estimates", 3, "실적 예상 상회"),
    ("beats estimates", 3, "실적 예상 상회"),
    ("beats expectations", 3, "기대치 상회"),
    ("strong earnings", 3, "실적 호조"),
    ("strong demand", 3, "수요 호조"),
    ("ai demand", 2, "AI 수요"),
    ("growth", 2, "성장 기대"),
    ("surge", 2, "강한 상승"),
    ("jumps", 2, "주가 급등"),
    ("rallies", 2, "상승 랠리"),
    ("gains", 2, "상승"),
    ("wins", 2, "수주/성과"),
    ("joins dow", 2, "지수 편입"),
    ("seat at the dow", 2, "지수 편입"),
    ("dominance", 2, "경쟁력 우위"),
    ("shareholders", 1, "주주가치"),
    ("strategic sense", 1, "전략적 타당성"),
    ("offset higher", 1, "비용 상쇄 가능"),
)

US_NEWS_NEGATIVE_SIGNALS: tuple[tuple[str, int, str], ...] = (
    ("downgrade", 3, "투자의견 하향"),
    ("cuts price target", 3, "목표가 하향"),
    ("price target cut", 3, "목표가 하향"),
    ("misses estimates", 3, "실적 예상 하회"),
    ("misses expectations", 3, "기대치 하회"),
    ("weak earnings", 3, "실적 부진"),
    ("profit warning", 4, "실적 경고"),
    ("lawsuit", 3, "소송 리스크"),
    ("probe", 3, "조사 리스크"),
    ("investigation", 3, "조사 리스크"),
    ("antitrust", 3, "반독점 리스크"),
    ("recall", 3, "리콜 리스크"),
    ("tariff", 2, "관세 부담"),
    ("cost pressure", 2, "비용 압박"),
    ("higher costs", 2, "비용 상승"),
    ("falls", 2, "주가 하락"),
    ("falling", 2, "주가 하락"),
    ("drops", 2, "주가 하락"),
    ("trades down", 2, "주가 하락"),
    ("plunges", 3, "급락"),
    ("slumps", 3, "급락"),
    ("overvalued", 3, "고평가 부담"),
    ("bearish", 3, "약세 의견"),
    ("concerns", 2, "우려"),
    ("risk", 1, "리스크"),
    ("delay", 2, "지연"),
    ("years away", 2, "성과 지연"),
    ("without collecting personal data", 1, "개인정보 규제 이슈"),
)
US_COMPANY_SUFFIXES = (
    "incorporated",
    "corporation",
    "company",
    "holdings",
    "holding",
    "limited",
    "class",
    "inc",
    "corp",
    "co",
    "ltd",
    "plc",
    "sa",
)


NASDAQ_UNIVERSE: list[dict[str, str]] = [
    {"code": "NVDA", "name": "NVIDIA", "sector": "AI 반도체"},
    {"code": "MSFT", "name": "Microsoft", "sector": "클라우드/AI"},
    {"code": "AAPL", "name": "Apple", "sector": "소비자기기"},
    {"code": "AMZN", "name": "Amazon", "sector": "클라우드/커머스"},
    {"code": "GOOGL", "name": "Alphabet Class A", "sector": "광고/AI"},
    {"code": "GOOG", "name": "Alphabet Class C", "sector": "광고/AI"},
    {"code": "META", "name": "Meta Platforms", "sector": "소셜/AI"},
    {"code": "AVGO", "name": "Broadcom", "sector": "AI 반도체"},
    {"code": "TSLA", "name": "Tesla", "sector": "전기차/AI"},
    {"code": "COST", "name": "Costco", "sector": "유통"},
    {"code": "NFLX", "name": "Netflix", "sector": "콘텐츠"},
    {"code": "AMD", "name": "Advanced Micro Devices", "sector": "반도체"},
    {"code": "PEP", "name": "PepsiCo", "sector": "필수소비재"},
    {"code": "ADBE", "name": "Adobe", "sector": "소프트웨어"},
    {"code": "CSCO", "name": "Cisco", "sector": "네트워크"},
    {"code": "TMUS", "name": "T-Mobile US", "sector": "통신"},
    {"code": "INTU", "name": "Intuit", "sector": "소프트웨어"},
    {"code": "QCOM", "name": "Qualcomm", "sector": "반도체"},
    {"code": "TXN", "name": "Texas Instruments", "sector": "반도체"},
    {"code": "AMAT", "name": "Applied Materials", "sector": "반도체 장비"},
    {"code": "ISRG", "name": "Intuitive Surgical", "sector": "의료기기"},
    {"code": "AMGN", "name": "Amgen", "sector": "바이오"},
    {"code": "BKNG", "name": "Booking Holdings", "sector": "여행"},
    {"code": "HON", "name": "Honeywell", "sector": "산업재"},
    {"code": "VRTX", "name": "Vertex Pharmaceuticals", "sector": "바이오"},
    {"code": "SBUX", "name": "Starbucks", "sector": "소비재"},
    {"code": "PANW", "name": "Palo Alto Networks", "sector": "보안"},
    {"code": "ADP", "name": "Automatic Data Processing", "sector": "서비스"},
    {"code": "MU", "name": "Micron Technology", "sector": "메모리"},
    {"code": "LRCX", "name": "Lam Research", "sector": "반도체 장비"},
    {"code": "ADI", "name": "Analog Devices", "sector": "반도체"},
    {"code": "KLAC", "name": "KLA", "sector": "반도체 장비"},
    {"code": "MELI", "name": "MercadoLibre", "sector": "이커머스"},
    {"code": "GILD", "name": "Gilead Sciences", "sector": "바이오"},
    {"code": "REGN", "name": "Regeneron", "sector": "바이오"},
    {"code": "MDLZ", "name": "Mondelez", "sector": "필수소비재"},
    {"code": "SNPS", "name": "Synopsys", "sector": "EDA"},
    {"code": "CDNS", "name": "Cadence Design", "sector": "EDA"},
    {"code": "CRWD", "name": "CrowdStrike", "sector": "보안"},
    {"code": "PYPL", "name": "PayPal", "sector": "핀테크"},
    {"code": "MAR", "name": "Marriott", "sector": "여행"},
    {"code": "ABNB", "name": "Airbnb", "sector": "여행"},
    {"code": "MRVL", "name": "Marvell Technology", "sector": "AI 반도체"},
    {"code": "ASML", "name": "ASML Holding", "sector": "반도체 장비"},
    {"code": "ARM", "name": "Arm Holdings", "sector": "반도체 IP"},
    {"code": "INTC", "name": "Intel", "sector": "반도체"},
    {"code": "SHOP", "name": "Shopify", "sector": "이커머스"},
    {"code": "CEG", "name": "Constellation Energy", "sector": "전력/원전"},
    {"code": "PLTR", "name": "Palantir", "sector": "AI 소프트웨어"},
    {"code": "APP", "name": "AppLovin", "sector": "광고테크"},
]

SP500_UNIVERSE: list[dict[str, str]] = [
    {"code": "LLY", "name": "Eli Lilly", "sector": "헬스케어", "market": "SP500"},
    {"code": "BRK.B", "name": "Berkshire Hathaway", "sector": "금융", "market": "SP500"},
    {"code": "JPM", "name": "JPMorgan Chase", "sector": "금융", "market": "SP500"},
    {"code": "V", "name": "Visa", "sector": "결제", "market": "SP500"},
    {"code": "MA", "name": "Mastercard", "sector": "결제", "market": "SP500"},
    {"code": "UNH", "name": "UnitedHealth Group", "sector": "헬스케어", "market": "SP500"},
    {"code": "WMT", "name": "Walmart", "sector": "필수소비재", "market": "SP500"},
    {"code": "XOM", "name": "Exxon Mobil", "sector": "에너지", "market": "SP500"},
    {"code": "JNJ", "name": "Johnson & Johnson", "sector": "헬스케어", "market": "SP500"},
    {"code": "PG", "name": "Procter & Gamble", "sector": "필수소비재", "market": "SP500"},
    {"code": "HD", "name": "Home Depot", "sector": "소비재", "market": "SP500"},
    {"code": "ORCL", "name": "Oracle", "sector": "소프트웨어", "market": "SP500"},
    {"code": "BAC", "name": "Bank of America", "sector": "금융", "market": "SP500"},
    {"code": "KO", "name": "Coca-Cola", "sector": "필수소비재", "market": "SP500"},
    {"code": "CVX", "name": "Chevron", "sector": "에너지", "market": "SP500"},
    {"code": "MRK", "name": "Merck", "sector": "헬스케어", "market": "SP500"},
    {"code": "ABBV", "name": "AbbVie", "sector": "바이오", "market": "SP500"},
    {"code": "CRM", "name": "Salesforce", "sector": "소프트웨어", "market": "SP500"},
    {"code": "MCD", "name": "McDonald's", "sector": "소비재", "market": "SP500"},
    {"code": "TMO", "name": "Thermo Fisher Scientific", "sector": "헬스케어", "market": "SP500"},
    {"code": "ACN", "name": "Accenture", "sector": "IT 서비스", "market": "SP500"},
    {"code": "LIN", "name": "Linde", "sector": "소재", "market": "SP500"},
    {"code": "GE", "name": "GE Aerospace", "sector": "산업재", "market": "SP500"},
    {"code": "IBM", "name": "IBM", "sector": "IT 서비스", "market": "SP500"},
    {"code": "DIS", "name": "Walt Disney", "sector": "콘텐츠", "market": "SP500"},
    {"code": "CAT", "name": "Caterpillar", "sector": "산업재", "market": "SP500"},
]

US_KOREAN_ALIASES: dict[str, tuple[str, ...]] = {
    "NVDA": ("엔비디아", "엔비디아주식", "젠슨황"),
    "MSFT": ("마이크로소프트", "마소", "MS", "오픈AI관련주"),
    "AAPL": ("애플", "아이폰", "맥북", "팀쿡"),
    "AMZN": ("아마존", "아마존닷컴", "AWS"),
    "GOOGL": ("구글", "알파벳", "알파벳A"),
    "GOOG": ("구글", "알파벳", "알파벳C"),
    "META": ("메타", "페이스북", "인스타그램"),
    "AVGO": ("브로드컴",),
    "TSLA": ("테슬라", "일론머스크", "전기차"),
    "COST": ("코스트코",),
    "NFLX": ("넷플릭스",),
    "AMD": ("AMD", "에이엠디", "어드밴스드마이크로디바이시스"),
    "PEP": ("펩시", "펩시코"),
    "ADBE": ("어도비",),
    "CSCO": ("시스코",),
    "TMUS": ("티모바일", "T모바일"),
    "INTU": ("인튜이트",),
    "QCOM": ("퀄컴",),
    "TXN": ("텍사스인스트루먼트",),
    "AMAT": ("어플라이드머티리얼즈", "어플라이드머티어리얼즈"),
    "ISRG": ("인튜이티브서지컬",),
    "AMGN": ("암젠",),
    "BKNG": ("부킹홀딩스", "부킹닷컴"),
    "HON": ("허니웰",),
    "VRTX": ("버텍스",),
    "SBUX": ("스타벅스",),
    "PANW": ("팔로알토", "팔로알토네트웍스"),
    "ADP": ("ADP", "오토매틱데이터프로세싱"),
    "MU": ("마이크론", "마이크론테크놀로지"),
    "LRCX": ("램리서치",),
    "ADI": ("아날로그디바이시스",),
    "KLAC": ("KLA", "케이엘에이"),
    "MELI": ("메르카도리브레",),
    "GILD": ("길리어드",),
    "REGN": ("리제네론",),
    "MDLZ": ("몬델리즈",),
    "SNPS": ("시놉시스",),
    "CDNS": ("케이던스",),
    "CRWD": ("크라우드스트라이크",),
    "PYPL": ("페이팔",),
    "MAR": ("메리어트",),
    "ABNB": ("에어비앤비",),
    "MRVL": ("마벨", "마벨테크놀로지"),
    "ASML": ("ASML", "에이에스엠엘"),
    "ARM": ("ARM", "암홀딩스"),
    "INTC": ("인텔",),
    "SHOP": ("쇼피파이",),
    "CEG": ("컨스텔레이션에너지",),
    "PLTR": ("팔란티어",),
    "APP": ("앱러빈", "앱러브인"),
    "LLY": ("일라이릴리", "릴리"),
    "BRK.B": ("버크셔", "버크셔해서웨이", "워런버핏"),
    "JPM": ("JP모건", "제이피모건", "제이피모건체이스"),
    "V": ("비자", "VISA"),
    "MA": ("마스터카드",),
    "UNH": ("유나이티드헬스", "유나이티드헬스그룹"),
    "WMT": ("월마트",),
    "XOM": ("엑슨모빌",),
    "JNJ": ("존슨앤드존슨", "존슨앤존슨"),
    "PG": ("프록터앤갬블", "P&G"),
    "HD": ("홈디포",),
    "ORCL": ("오라클",),
    "BAC": ("뱅크오브아메리카", "BoA"),
    "KO": ("코카콜라",),
    "CVX": ("쉐브론", "셰브론"),
    "MRK": ("머크",),
    "ABBV": ("애브비", "앱비"),
    "CRM": ("세일즈포스",),
    "MCD": ("맥도날드",),
    "TMO": ("써모피셔", "써모피셔사이언티픽"),
    "ACN": ("액센츄어", "액센추어"),
    "LIN": ("린데",),
    "GE": ("GE", "지이에어로스페이스"),
    "IBM": ("IBM", "아이비엠"),
    "DIS": ("디즈니", "월트디즈니"),
    "CAT": ("캐터필러", "캐터필라"),
}

US_EQUITY_UNIVERSE = [*NASDAQ_UNIVERSE, *SP500_UNIVERSE]
US_UNIVERSE_BY_CODE = {item["code"]: item for item in US_EQUITY_UNIVERSE}

US_SECTOR_ETFS: list[dict[str, str]] = [
    {"symbol": "QQQ", "label": "NASDAQ 100", "sector": "성장주"},
    {"symbol": "SOXX", "label": "미국 반도체", "sector": "반도체"},
    {"symbol": "XLK", "label": "미국 기술주", "sector": "기술주"},
    {"symbol": "LIT", "label": "글로벌 2차전지", "sector": "2차전지"},
    {"symbol": "XLY", "label": "미국 소비재", "sector": "자동차/소비"},
    {"symbol": "XLF", "label": "미국 금융", "sector": "금융"},
    {"symbol": "XLE", "label": "미국 에너지", "sector": "에너지"},
    {"symbol": "XLB", "label": "미국 소재", "sector": "소재/화학"},
    {"symbol": "XLI", "label": "미국 산업재", "sector": "산업재"},
    {"symbol": "XLV", "label": "미국 헬스케어", "sector": "헬스케어"},
    {"symbol": "XLP", "label": "미국 필수소비재", "sector": "필수소비재"},
    {"symbol": "XLU", "label": "미국 유틸리티", "sector": "유틸리티"},
    {"symbol": "JETS", "label": "미국 항공", "sector": "항공"},
    {"symbol": "IYT", "label": "미국 운송", "sector": "운송/해운"},
    {"symbol": "SPY", "label": "S&P 500", "sector": "대형주"},
    {"symbol": "IWM", "label": "Russell 2000", "sector": "중소형주"},
]


@dataclass
class USPrice:
    code: str
    trade_date: date
    open: Optional[Decimal]
    high: Optional[Decimal]
    low: Optional[Decimal]
    close: Optional[Decimal]
    volume: Optional[int]
    trading_value: Optional[Decimal]
    market_cap: Optional[int] = None
    listed_shares: Optional[int] = None


def _symbol(value: str) -> str:
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return "".join(ch for ch in value.strip().upper() if ch in allowed)[:12]


def _chart_symbol_candidates(symbol: str) -> list[str]:
    base = _symbol(symbol)
    candidates = [base]
    if "." in base:
        candidates.append(base.replace(".", "-"))
    if "-" in base:
        candidates.append(base.replace("-", "."))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _company_key(value: str) -> str:
    tokens: list[str] = []
    current = []
    for char in value.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    filtered = [token for token in tokens if token not in US_COMPANY_SUFFIXES]
    compact = "".join(filtered or tokens)
    changed = True
    while changed:
        changed = False
        for suffix in US_COMPANY_SUFFIXES:
            if len(compact) > len(suffix) + 2 and compact.endswith(suffix):
                compact = compact[: -len(suffix)]
                changed = True
                break
    return compact


def _korean_alias_match(query_key: str, code: str) -> bool:
    if len(query_key) < 2:
        return False
    for alias in US_KOREAN_ALIASES.get(code, ()):
        alias_key = _company_key(alias)
        if alias_key and (query_key in alias_key or alias_key in query_key):
            return True
    return False


def _to_decimal(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _list_get(items: list[object], index: int) -> Optional[object]:
    return items[index] if index < len(items) else None


def _fmt_market(exchange: Optional[str]) -> str:
    if exchange in {"NMS", "NGM", "NCM", "NASDAQ"}:
        return "NASDAQ"
    if exchange in {"NYQ", "NYSE"}:
        return "NYSE"
    return exchange or "US"


def _parse_date(value: object) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _parse_epoch_datetime(value: object) -> Optional[datetime]:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc)
    except Exception:
        return None


def _raw_metric_value(item: object) -> Optional[Decimal]:
    if not isinstance(item, dict):
        return None
    reported = item.get("reportedValue") or {}
    if isinstance(reported, dict):
        return _to_decimal(reported.get("raw"))
    return None


def _yahoo_raw_value(item: object, key: str) -> Optional[Decimal]:
    if not isinstance(item, dict):
        return None
    value = item.get(key)
    if isinstance(value, dict):
        return _to_decimal(value.get("raw"))
    return _to_decimal(value)


def _yahoo_text_value(item: object, key: str) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    value = item.get(key)
    if isinstance(value, dict):
        raw = value.get("raw") or value.get("fmt") or value.get("longFmt")
        return str(raw) if raw not in (None, "") else None
    return str(value) if value not in (None, "") else None


def _metric_series(fundamentals: dict[str, list[dict[str, object]]], name: str) -> list[dict[str, object]]:
    rows = [item for item in fundamentals.get(name, []) if _raw_metric_value(item) is not None]
    return sorted(rows, key=lambda item: str(item.get("asOfDate") or ""))


def _latest_metric(
    fundamentals: dict[str, list[dict[str, object]]],
    *names: str,
) -> tuple[Optional[Decimal], Optional[date]]:
    for name in names:
        series = _metric_series(fundamentals, name)
        if series:
            latest = series[-1]
            return _raw_metric_value(latest), _parse_date(latest.get("asOfDate"))
    return None, None


def _sum_latest_quarters(fundamentals: dict[str, list[dict[str, object]]], name: str, count: int = 4) -> Optional[Decimal]:
    series = _metric_series(fundamentals, name)
    values = [_raw_metric_value(item) for item in series[-count:]]
    usable = [value for value in values if value is not None]
    if len(usable) < count:
        return None
    return sum(usable)


def _metric_growth(
    fundamentals: dict[str, list[dict[str, object]]],
    name: str,
    compare_year_ago: bool = True,
) -> Optional[Decimal]:
    series = _metric_series(fundamentals, name)
    if len(series) < 2:
        return None
    latest = _raw_metric_value(series[-1])
    base_index = -5 if compare_year_ago and len(series) >= 5 else -2
    base = _raw_metric_value(series[base_index])
    return _rate(latest, base)


def _safe_ratio(numerator: Optional[Decimal], denominator: Optional[Decimal]) -> Optional[Decimal]:
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    return _round_decimal(numerator / denominator)


def _median_decimal(values: list[Decimal]) -> Optional[Decimal]:
    usable = sorted(value for value in values if value is not None)
    if not usable:
        return None
    middle = len(usable) // 2
    if len(usable) % 2:
        return _round_decimal(usable[middle])
    return _round_decimal((usable[middle - 1] + usable[middle]) / Decimal("2"))


def _zscore(current: Optional[Decimal], series: list[Decimal]) -> Optional[Decimal]:
    values = [Decimal(str(value)) for value in series if value is not None and Decimal(str(value)) > 0]
    if current is None or current <= 0 or len(values) < 3:
        return None
    average = sum(values) / Decimal(len(values))
    variance = sum((value - average) ** 2 for value in values) / Decimal(len(values))
    if variance <= 0:
        return None
    return _round_decimal((Decimal(str(current)) - average) / variance.sqrt())


def _peer_group_key(stock: dict[str, object]) -> str:
    sector = str(stock.get("sector") or "")
    market = str(stock.get("market") or "")
    if any(keyword in sector for keyword in ("반도체", "메모리")):
        return "semiconductors"
    if any(keyword in sector for keyword in ("클라우드", "소프트웨어", "AI", "광고", "소셜", "보안", "EDA", "네트워크", "IT 서비스", "핀테크")):
        return "technology"
    if any(keyword in sector for keyword in ("금융", "결제")):
        return "financials"
    if any(keyword in sector for keyword in ("헬스케어", "바이오", "의료")):
        return "healthcare"
    if "에너지" in sector:
        return "energy"
    if "소재" in sector:
        return "materials"
    if any(keyword in sector for keyword in ("산업재", "운송", "항공")):
        return "industrials"
    if "필수소비재" in sector:
        return "staples"
    if any(keyword in sector for keyword in ("전력", "원전", "유틸리티")):
        return "utilities"
    if any(keyword in sector for keyword in ("소비", "전기차", "유통", "여행", "이커머스", "콘텐츠", "자동차")):
        return "consumer"
    return "sp500" if market == "SP500" else "nasdaq"


def _industry_valuation_stats(peer_key: str) -> dict[str, object]:
    key = ("us_industry_valuation_stats", peer_key)

    def build() -> dict[str, object]:
        peers = US_EQUITY_UNIVERSE if peer_key == "all" else [item for item in US_EQUITY_UNIVERSE if _peer_group_key(item) == peer_key]

        def peer_snapshot(item: dict[str, str]) -> Optional[dict[str, object]]:
            try:
                fundamentals = fetch_us_fundamentals(item["code"])
                meta, prices = chart_prices(item["code"], limit=1)
                latest = prices[-1] if prices else None
                price = _to_decimal(meta.get("regularMarketPrice")) or (latest.close if latest else None)
                return _financial_snapshot(fundamentals, price)
            except Exception:
                return None

        per_values: list[Decimal] = []
        pbr_values: list[Decimal] = []
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(peers)))) as executor:
            snapshots = [future.result() for future in as_completed([executor.submit(peer_snapshot, item) for item in peers])]
        for snapshot in snapshots:
            if not snapshot:
                continue
            per = snapshot.get("per")
            pbr = snapshot.get("pbr")
            if isinstance(per, Decimal) and Decimal("0") < per < Decimal("500"):
                per_values.append(per)
            if isinstance(pbr, Decimal) and Decimal("0") < pbr < Decimal("200"):
                pbr_values.append(pbr)
        return {
            "peer_group": peer_key,
            "industry_per": _median_decimal(per_values),
            "industry_pbr": _median_decimal(pbr_values),
            "per_values": per_values,
            "pbr_values": pbr_values,
        }

    return US_CACHE.get_or_set(key, US_TTL_SECONDS * 4, build)


def _valuation_score(valuation: dict[str, object]) -> Decimal:
    z_values = [
        Decimal(str(value))
        for value in (valuation.get("per_zscore"), valuation.get("pbr_zscore"))
        if value is not None
    ]
    if z_values:
        average_z = sum(z_values) / Decimal(len(z_values))
        return max(Decimal("0"), min(Decimal("100"), Decimal("50") - average_z * Decimal("14")))
    per = _to_decimal(valuation.get("per"))
    pbr = _to_decimal(valuation.get("pbr"))
    industry_per = _to_decimal(valuation.get("industry_per"))
    if per is not None and industry_per not in (None, Decimal("0")):
        relative = per / industry_per
        score = Decimal("50") + (Decimal("1") - relative) * Decimal("35")
        if pbr is not None:
            score -= min(Decimal("25"), pbr * Decimal("1.5"))
        return max(Decimal("0"), min(Decimal("100"), score))
    if per is not None and pbr is not None:
        return max(Decimal("0"), Decimal("100") - min(Decimal("80"), per + pbr * Decimal("4")))
    return Decimal("45")


def _metric_event(
    title: str,
    published_at: Optional[date],
    score: Optional[Decimal] = None,
    source: str = "Yahoo Fundamentals",
) -> dict[str, object]:
    sentiment = "neutral"
    sentiment_label = "중립"
    if score is not None and score > 0:
        sentiment = "positive"
        sentiment_label = "긍정"
    elif score is not None and score < 0:
        sentiment = "negative"
        sentiment_label = "부정"
    return {
        "title": title,
        "source": source,
        "url": None,
        "published_at": datetime.combine(published_at, time(0), tzinfo=timezone.utc) if published_at else None,
        "sentiment": sentiment,
        "sentiment_label": sentiment_label,
        "sentiment_score": score or Decimal("0"),
        "sentiment_confidence": "보통" if score is not None else "낮음",
        "sentiment_reason": "전년/직전 대비 개선" if score and score > 0 else "전년/직전 대비 둔화" if score and score < 0 else "방향성 확인 필요",
    }


def _fetch_yahoo_timeseries_once(symbol: str, url_template: str) -> dict[str, list[dict[str, object]]]:
    now = datetime.now(timezone.utc)
    response = requests.get(
        url_template.format(symbol=symbol),
        params={
            "type": ",".join(US_FUNDAMENTAL_TYPES),
            "period1": int((now - timedelta(days=365 * 6)).timestamp()),
            "period2": int((now + timedelta(days=30)).timestamp()),
        },
        headers=US_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    rows = (payload.get("timeseries") or {}).get("result") or []
    if not rows:
        raise ValueError("Yahoo fundamentals not found")
    result: dict[str, list[dict[str, object]]] = {}
    for block in rows:
        for key, value in block.items():
            if key in {"meta", "timestamp"}:
                continue
            if isinstance(value, list):
                result[key] = value
    if not result:
        raise ValueError("Yahoo fundamentals not found")
    return result


def fetch_us_fundamentals(symbol: str, refresh: bool = False) -> dict[str, list[dict[str, object]]]:
    code = resolve_us_stock(symbol)["code"]
    key = ("us_fundamentals", code)
    if not refresh:
        return US_CACHE.get_or_set(key, US_TTL_SECONDS * 4, lambda: fetch_us_fundamentals(code, refresh=True))
    last_error: Optional[Exception] = None
    for candidate in _chart_symbol_candidates(code):
        for url_template in YAHOO_TIMESERIES_URLS:
            try:
                payload = _fetch_yahoo_timeseries_once(candidate, url_template)
                US_CACHE.set(key, payload, US_TTL_SECONDS * 4)
                return payload
            except Exception as exc:
                last_error = exc
                continue
    raise ValueError(f"US fundamentals not found for {symbol}") from last_error


def _yahoo_auth(refresh: bool = False) -> dict[str, object]:
    key = ("yahoo_auth", "crumb")
    if not refresh:
        return US_CACHE.get_or_set(key, 60 * 60 * 6, lambda: _yahoo_auth(refresh=True))
    session = requests.Session()
    session.headers.update(US_HEADERS)
    try:
        session.get(YAHOO_COOKIE_URL, timeout=10)
    except Exception:
        pass
    response = session.get(YAHOO_CRUMB_URL, timeout=10)
    response.raise_for_status()
    crumb = response.text.strip()
    if not crumb or " " in crumb or "<" in crumb:
        raise ValueError("Yahoo crumb not available")
    payload = {"crumb": crumb, "cookies": session.cookies.get_dict()}
    US_CACHE.set(key, payload, 60 * 60 * 6)
    return payload


def _fetch_yahoo_quote_summary_once(symbol: str, refresh_auth: bool = False) -> dict[str, object]:
    auth = _yahoo_auth(refresh=refresh_auth)
    response = requests.get(
        YAHOO_QUOTE_SUMMARY_URL.format(symbol=symbol),
        params={"modules": ",".join(US_QUOTE_SUMMARY_MODULES), "crumb": auth.get("crumb")},
        headers=US_HEADERS,
        cookies=auth.get("cookies") if isinstance(auth.get("cookies"), dict) else None,
        timeout=15,
    )
    if response.status_code == 401 and not refresh_auth:
        return _fetch_yahoo_quote_summary_once(symbol, refresh_auth=True)
    response.raise_for_status()
    payload = response.json()
    quote_summary = payload.get("quoteSummary") or {}
    if quote_summary.get("error"):
        raise ValueError(str(quote_summary.get("error")))
    result = quote_summary.get("result") or []
    if not result:
        raise ValueError("Yahoo quote summary not found")
    return result[0]


def fetch_us_research_summary(symbol: str, refresh: bool = False) -> dict[str, object]:
    code = resolve_us_stock(symbol)["code"]
    key = ("us_research_summary", code)
    if not refresh:
        return US_CACHE.get_or_set(key, US_TTL_SECONDS * 4, lambda: fetch_us_research_summary(code, refresh=True))
    last_error: Optional[Exception] = None
    for candidate in _chart_symbol_candidates(code):
        try:
            payload = _fetch_yahoo_quote_summary_once(candidate)
            US_CACHE.set(key, payload, US_TTL_SECONDS * 4)
            return payload
        except Exception as exc:
            last_error = exc
            continue
    raise ValueError(f"US research summary not found for {symbol}") from last_error


def _sec_ticker_map(refresh: bool = False) -> dict[str, str]:
    key = ("sec_ticker_map", "all")
    if not refresh:
        return US_CACHE.get_or_set(key, 60 * 60 * 24, lambda: _sec_ticker_map(refresh=True))
    response = requests.get(SEC_TICKERS_URL, headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()
    payload = response.json()
    mapping = {
        str(item.get("ticker") or "").upper(): str(item.get("cik_str") or "").zfill(10)
        for item in payload.values()
        if item.get("ticker") and item.get("cik_str")
    }
    US_CACHE.set(key, mapping, 60 * 60 * 24)
    return mapping


def _sec_cik_for_symbol(symbol: str) -> Optional[str]:
    mapping = _sec_ticker_map()
    for candidate in _chart_symbol_candidates(symbol):
        cik = mapping.get(candidate) or mapping.get(candidate.replace(".", "-")) or mapping.get(candidate.replace("-", "."))
        if cik:
            return cik
    return None


def sec_filings(symbol: str, limit: int = 8, refresh: bool = False) -> list[dict[str, object]]:
    stock = resolve_us_stock(symbol)
    code = stock["code"]
    key = ("sec_filings", code)
    if not refresh:
        return US_CACHE.get_or_set(key, US_TTL_SECONDS * 4, lambda: sec_filings(code, limit=limit, refresh=True))
    cik = _sec_cik_for_symbol(code)
    if not cik:
        return []
    response = requests.get(SEC_SUBMISSIONS_URL.format(cik=cik), headers=SEC_HEADERS, timeout=20)
    response.raise_for_status()
    recent = ((response.json() or {}).get("filings") or {}).get("recent") or {}
    filings: list[dict[str, object]] = []
    for index, form in enumerate(recent.get("form") or []):
        if len(filings) >= limit:
            break
        filing_date = _parse_date(_list_get(recent.get("filingDate") or [], index))
        accession = str(_list_get(recent.get("accessionNumber") or [], index) or "")
        document = str(_list_get(recent.get("primaryDocument") or [], index) or "")
        description = str(_list_get(recent.get("primaryDocDescription") or [], index) or form or "SEC filing")
        cik_path = str(int(cik))
        accession_path = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/{document}"
            if accession and document
            else None
        )
        filings.append(
            {
                "title": f"{form} · {description}",
                "source": "SEC EDGAR",
                "url": url,
                "published_at": datetime.combine(filing_date, time(0), tzinfo=timezone.utc) if filing_date else None,
                "sentiment": "neutral",
                "sentiment_label": "중립",
                "sentiment_score": Decimal("0"),
                "sentiment_confidence": "낮음",
                "sentiment_reason": "SEC 제출 서류",
                "form": form,
                "accession_number": accession,
            }
        )
    US_CACHE.set(key, filings, US_TTL_SECONDS * 4)
    return filings


def _google_news_items(query: str, limit: int = 10) -> list[dict[str, object]]:
    response = requests.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        headers=US_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows: list[dict[str, object]] = []
    for item in root.findall("./channel/item")[:limit]:
        published_at = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                published_at = parsedate_to_datetime(pub_date).astimezone(timezone.utc)
            except Exception:
                published_at = None
        source_node = item.find("source")
        rows.append(
            {
                "title": item.findtext("title") or "",
                "source": source_node.text if source_node is not None and source_node.text else "Google News",
                "url": item.findtext("link"),
                "published_at": published_at,
            }
        )
    return rows


def _chart_has_prices(result: dict[str, object]) -> bool:
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    return any(value is not None for value in closes)


def _fetch_yahoo_chart_once(
    symbol: str,
    url_template: str,
    range_: str,
    interval: str,
    include_prepost: bool,
) -> dict[str, object]:
    response = requests.get(
        url_template.format(symbol=symbol),
        params={"range": range_, "interval": interval, "includePrePost": "true" if include_prepost else "false"},
        headers=US_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result or not _chart_has_prices(result):
        raise ValueError("Yahoo chart data not found")
    return result


def _fetch_chart(symbol: str, range_: str = "1y", interval: str = "1d", include_prepost: bool = False) -> dict[str, object]:
    if "=" in symbol:
        candidates = [_symbol(symbol) if not symbol.endswith("=X") else symbol.upper()]
    else:
        candidates = _chart_symbol_candidates(symbol)
    ranges = [(range_, interval)]
    if range_ == "1y" and interval == "1d":
        ranges.extend([("2y", "1d"), ("6mo", "1d"), ("5y", "1wk")])
    last_error: Optional[Exception] = None
    for yahoo_symbol in candidates:
        for candidate_range, candidate_interval in ranges:
            for url_template in (YAHOO_CHART_URL, YAHOO_CHART_FALLBACK_URL):
                try:
                    return _fetch_yahoo_chart_once(
                        yahoo_symbol,
                        url_template,
                        candidate_range,
                        candidate_interval,
                        include_prepost,
                    )
                except Exception as exc:
                    last_error = exc
                    continue
    raise ValueError(f"Yahoo chart data not found for {symbol}") from last_error


def _us_market_session(now: Optional[datetime] = None) -> dict[str, object]:
    current = (now or datetime.now(timezone.utc)).astimezone(NEW_YORK_TZ)
    premarket_start = time(4, 0)
    regular_start = time(9, 30)
    regular_end = time(16, 0)
    afterhours_end = time(20, 0)
    is_weekday = current.weekday() < 5
    current_time = current.time()
    if is_weekday and premarket_start <= current_time < regular_start:
        session = "premarket"
        label = "미국 프리장 진행 중"
        is_live = True
    elif is_weekday and regular_start <= current_time < regular_end:
        session = "regular"
        label = "미국 정규장 진행 중"
        is_live = True
    elif is_weekday and regular_end <= current_time < afterhours_end:
        session = "afterhours"
        label = "미국 애프터장 진행 중"
        is_live = True
    else:
        session = "closed"
        label = "미국 정규장 마감/대기"
        is_live = False
    return {
        "session": session,
        "label": label,
        "is_regular": session == "regular",
        "is_live": is_live,
        "local_time": current,
        "refresh_interval_seconds": 60 if is_live else 300,
    }


def _sector_etf_snapshot(item: dict[str, str], live: bool = False) -> dict[str, object]:
    result = _fetch_chart(
        item["symbol"],
        range_="1d" if live else "5d",
        interval="1m" if live else "1d",
        include_prepost=live,
    )
    meta = result.get("meta") or {}
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = [value for value in quote.get("close") or [] if value is not None]
    timestamps = result.get("timestamp") or []
    price = _to_decimal(closes[-1]) if live and closes else _to_decimal(meta.get("regularMarketPrice"))
    previous = _to_decimal(meta.get("chartPreviousClose")) or _to_decimal(meta.get("previousClose"))
    if price is None and closes:
        price = _to_decimal(closes[-1])
    if previous is None and len(closes) >= 2:
        previous = _to_decimal(closes[-2])
    trade_date = None
    if timestamps:
        trade_date = datetime.fromtimestamp(timestamps[-1], timezone.utc).date()
    return {
        "symbol": item["symbol"],
        "label": item["label"],
        "sector": item["sector"],
        "trade_date": trade_date,
        "price": price,
        "previous_close": previous,
        "change_rate": _rate(price, previous),
        "source": "Yahoo Finance",
    }


def us_sector_moves(refresh: bool = False) -> dict[str, object]:
    session = _us_market_session()
    ttl = US_SECTOR_OPEN_TTL_SECONDS if session["is_live"] else US_SECTOR_CLOSED_TTL_SECONDS
    key = ("us_sector_moves", session["session"])
    if not refresh:
        return US_CACHE.get_or_set(key, ttl, lambda: us_sector_moves(refresh=True))

    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_sector_etf_snapshot, item, bool(session["is_live"])) for item in US_SECTOR_ETFS]
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception:
                continue
    order = {item["symbol"]: index for index, item in enumerate(US_SECTOR_ETFS)}
    payload = {
        "as_of": datetime.now(timezone.utc),
        "market_session": session["session"],
        "market_session_label": session["label"],
        "market_local_time": session["local_time"],
        "refresh_interval_seconds": session["refresh_interval_seconds"],
        "data_mode": f"current_{session['session']}" if session["is_live"] else "latest_regular_close",
        "items": sorted(rows, key=lambda row: order.get(str(row.get("symbol")), 999)),
    }
    US_CACHE.set(key, payload, ttl)
    return payload


def fetch_chart(symbol: str, refresh: bool = False) -> dict[str, object]:
    code = _symbol(symbol)
    key = ("us_chart", code)
    if refresh:
        payload = _fetch_chart(code)
        US_CACHE.set(key, payload, US_TTL_SECONDS)
        return payload
    return US_CACHE.get_or_set(key, US_TTL_SECONDS, lambda: _fetch_chart(code))


def usdkrw_rate(refresh: bool = False) -> dict[str, object]:
    key = ("us_fx", "USDKRW")
    if refresh:
        US_CACHE.set(key, _usdkrw_rate_payload(), US_FX_TTL_SECONDS)
    return US_CACHE.get_or_set(key, US_FX_TTL_SECONDS, _usdkrw_rate_payload)


def _usdkrw_rate_payload() -> dict[str, object]:
    result = _fetch_chart("USDKRW=X", range_="1d", interval="1m")
    meta = result.get("meta") or {}
    price = _to_decimal(meta.get("regularMarketPrice")) or _to_decimal(meta.get("previousClose"))
    return {
        "base": "USD",
        "quote": "KRW",
        "rate": price,
        "as_of": datetime.now(timezone.utc),
        "source": "Yahoo Finance",
    }


def chart_prices(symbol: str, refresh: bool = False, limit: int = 250) -> tuple[dict[str, object], list[USPrice]]:
    result = fetch_chart(symbol, refresh=refresh)
    meta = result.get("meta") or {}
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    rows: list[USPrice] = []
    for index, ts in enumerate(timestamps):
        close = _to_decimal(_list_get(quote.get("close") or [], index))
        if close is None:
            continue
        volume = _list_get(quote.get("volume") or [], index)
        trading_value = close * Decimal(str(volume)) if close is not None and volume is not None else None
        rows.append(
            USPrice(
                code=_symbol(symbol),
                trade_date=datetime.fromtimestamp(ts, timezone.utc).date(),
                open=_to_decimal(_list_get(quote.get("open") or [], index)) or close,
                high=_to_decimal(_list_get(quote.get("high") or [], index)) or close,
                low=_to_decimal(_list_get(quote.get("low") or [], index)) or close,
                close=close,
                volume=int(volume) if volume is not None else None,
                trading_value=trading_value,
            )
        )
    return meta, rows[-limit:]


def _price_dict(row: USPrice) -> dict[str, object]:
    return {
        "code": row.code,
        "trade_date": row.trade_date,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "volume": row.volume,
        "trading_value": row.trading_value,
        "market_cap": row.market_cap,
        "listed_shares": row.listed_shares,
    }


def us_prices(symbol: str, limit: int = 250, refresh: bool = False) -> list[dict[str, object]]:
    stock = resolve_us_stock(symbol)
    _, rows = chart_prices(stock["code"], refresh=refresh, limit=limit)
    return [_price_dict(row) for row in rows]


def _nth_from_end(items: list[USPrice], offset: int) -> Optional[USPrice]:
    return items[-1 - offset] if len(items) > offset else None


def _momentum(prices: list[USPrice]) -> dict[str, object]:
    latest = prices[-1] if prices else None
    one_month = _nth_from_end(prices, 21)
    three_month = _nth_from_end(prices, 63)
    recent_values = [row.trading_value for row in prices[-5:] if row.trading_value is not None]
    baseline_values = [row.trading_value for row in prices[-25:-5] if row.trading_value is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None
    return {
        "one_month_return": _rate(latest.close if latest else None, one_month.close if one_month else None),
        "three_month_return": _rate(latest.close if latest else None, three_month.close if three_month else None),
        "trading_value_change": _rate(recent_average, baseline_average),
        "latest_trading_value": latest.trading_value if latest else None,
        "baseline_trading_value": _round_decimal(baseline_average, "1") if baseline_average is not None else None,
    }


def _preferred_liquidity_etf(stock: dict[str, object]) -> str:
    sector = str(stock.get("sector") or "")
    market = str(stock.get("market") or "")
    if any(keyword in sector for keyword in ("반도체", "메모리")):
        return "SOXX"
    if any(keyword in sector for keyword in ("클라우드", "소프트웨어", "AI", "광고", "소셜", "보안", "EDA", "네트워크", "IT 서비스", "핀테크")):
        return "XLK"
    if any(keyword in sector for keyword in ("금융", "결제")):
        return "XLF"
    if "에너지" in sector:
        return "XLE"
    if "소재" in sector:
        return "XLB"
    if any(keyword in sector for keyword in ("산업재", "운송", "항공")):
        return "XLI"
    if any(keyword in sector for keyword in ("헬스케어", "바이오", "의료")):
        return "XLV"
    if "필수소비재" in sector:
        return "XLP"
    if any(keyword in sector for keyword in ("전력", "원전", "유틸리티")):
        return "XLU"
    if any(keyword in sector for keyword in ("소비", "전기차", "유통", "여행", "이커머스", "콘텐츠", "자동차")):
        return "XLY"
    if market == "SP500":
        return "SPY"
    return "QQQ"


def _trading_value_flow(momentum: dict[str, object]) -> Optional[Decimal]:
    latest = _to_decimal(momentum.get("latest_trading_value"))
    baseline = _to_decimal(momentum.get("baseline_trading_value"))
    if latest is None or baseline is None:
        return None
    return _round_decimal(latest - baseline, "1")


def _us_liquidity_proxy(
    stock: dict[str, object],
    stock_momentum: dict[str, object],
) -> dict[str, object]:
    etf_symbol = _preferred_liquidity_etf(stock)
    etf_momentum: dict[str, object] = {}
    try:
        _, etf_prices = chart_prices(etf_symbol, limit=60)
        etf_momentum = _momentum(etf_prices)
    except Exception:
        etf_momentum = {}
    stock_flow = _trading_value_flow(stock_momentum)
    etf_flow = _trading_value_flow(etf_momentum)
    return {
        "foreign_net_buy_20d": stock_flow,
        "institution_net_buy_20d": etf_flow,
        "foreign_intensity": stock_momentum.get("trading_value_change"),
        "institution_intensity": etf_momentum.get("trading_value_change"),
        "source": "Yahoo Finance volume proxy",
        "stock_liquidity_label": "개별 종목 거래대금 변화",
        "etf_symbol": etf_symbol,
        "etf_liquidity_label": f"{etf_symbol} 거래대금 변화",
    }


def _search_yahoo(query: str, limit: int = 20, news_count: int = 0) -> dict[str, object]:
    response = requests.get(
        YAHOO_SEARCH_URL,
        params={"q": query, "quotesCount": limit, "newsCount": news_count},
        headers=US_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def search_us_stocks(query: str, limit: int = 20) -> list[dict[str, object]]:
    cleaned = query.strip()
    normalized = cleaned.upper()
    query_key = _company_key(cleaned)
    items: dict[str, dict[str, object]] = {}
    for item in US_EQUITY_UNIVERSE:
        item_key = _company_key(item["name"])
        if (
            normalized in item["code"]
            or cleaned.lower() in item["name"].lower()
            or (len(query_key) >= 4 and (query_key in item_key or item_key in query_key))
            or _korean_alias_match(query_key, item["code"])
        ):
            items[item["code"]] = {
                "code": item["code"],
                "name": item["name"],
                "market": item.get("market", "NASDAQ"),
                "sector": item["sector"],
            }
    try:
        search_query = cleaned
        if len(query_key) >= 4 and query_key != _company_key(cleaned.replace(".", " ")):
            search_query = query_key
        payload = _search_yahoo(search_query, limit=limit)
        for quote in payload.get("quotes") or []:
            symbol = _symbol(quote.get("symbol") or "")
            if not symbol or quote.get("quoteType") not in {None, "EQUITY"}:
                continue
            market = _fmt_market(quote.get("exchange"))
            if market not in {"NASDAQ", "NYSE", "US"}:
                continue
            items[symbol] = {
                "code": symbol,
                "name": quote.get("longname") or quote.get("shortname") or symbol,
                "market": market,
                "sector": (US_UNIVERSE_BY_CODE.get(symbol) or {}).get("sector"),
            }
    except Exception:
        pass
    return list(items.values())[:limit]


def resolve_us_stock(query: str) -> dict[str, object]:
    code = _symbol(query)
    if code in US_UNIVERSE_BY_CODE:
        item = US_UNIVERSE_BY_CODE[code]
        return {"code": code, "name": item["name"], "market": item.get("market", "NASDAQ"), "sector": item["sector"]}
    matches = search_us_stocks(query, limit=1)
    if matches:
        return matches[0]
    if not code:
        raise ValueError(f"US stock not found for {query}")
    meta, _ = chart_prices(code, limit=1)
    return {
        "code": code,
        "name": meta.get("longName") or meta.get("shortName") or code,
        "market": _fmt_market(meta.get("exchangeName")),
        "sector": (US_UNIVERSE_BY_CODE.get(code) or {}).get("sector"),
    }


def _news(symbol: str) -> list[dict[str, object]]:
    queries = [symbol]
    google_queries = []
    try:
        stock = resolve_us_stock(symbol)
        queries.append(stock["code"])
        if stock.get("name"):
            google_queries.append(f'"{stock["name"]}" OR {stock["code"]} stock')
    except Exception:
        pass
    queries.extend(_chart_symbol_candidates(symbol))
    rows = []
    seen: set[str] = set()
    for query in dict.fromkeys(google_queries):
        try:
            items = _google_news_items(query, limit=10)
        except Exception:
            continue
        for item in items:
            url = item.get("url") or item.get("title")
            if not url or str(url) in seen:
                continue
            seen.add(str(url))
            rows.append(item)
            if len(rows) >= 10:
                return rows
    for query in dict.fromkeys(item for item in queries if str(item or "").strip()):
        try:
            payload = _search_yahoo(str(query), limit=1, news_count=10)
        except Exception:
            continue
        for item in payload.get("news") or []:
            url = item.get("link") or item.get("uuid") or item.get("title")
            if not url or str(url) in seen:
                continue
            seen.add(str(url))
            published_at = None
            if item.get("providerPublishTime"):
                published_at = datetime.fromtimestamp(item["providerPublishTime"], timezone.utc)
            rows.append(
                {
                    "title": item.get("title") or "",
                    "source": item.get("publisher") or "Yahoo Finance",
                    "url": item.get("link"),
                    "published_at": published_at,
                }
            )
            if len(rows) >= 10:
                return rows
    return rows[:10]


def _classify_us_news_item(item: dict[str, object]) -> dict[str, object]:
    title = str(item.get("title") or "")
    lowered = title.lower()
    raw_score = 0
    reasons: list[str] = []
    for phrase, weight, reason in US_NEWS_POSITIVE_SIGNALS:
        if phrase in lowered:
            raw_score += weight
            reasons.append(reason)
    for phrase, weight, reason in US_NEWS_NEGATIVE_SIGNALS:
        if phrase in lowered:
            raw_score -= weight
            reasons.append(reason)
    normalized_score = max(-100, min(100, raw_score * 20))
    if normalized_score > 0:
        sentiment = "positive"
        sentiment_label = "긍정"
    elif normalized_score < 0:
        sentiment = "negative"
        sentiment_label = "부정"
    else:
        sentiment = "neutral"
        sentiment_label = "중립"
    confidence = "높음" if abs(raw_score) >= 4 else "보통" if abs(raw_score) >= 2 else "낮음"
    return {
        **item,
        "sentiment": sentiment,
        "sentiment_label": sentiment_label,
        "sentiment_score": Decimal(str(normalized_score)),
        "sentiment_confidence": confidence,
        "sentiment_reason": ", ".join(dict.fromkeys(reasons)) if reasons else "명확한 방향성 단어 없음",
    }


def _classify_us_news(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [_classify_us_news_item(item) for item in items]


def _extract_target_price(title: str) -> Optional[Decimal]:
    patterns = [
        r"price target (?:to|at|of) \$?([0-9]+(?:\.[0-9]+)?)",
        r"(?:raises|raised|cuts|cut|lowers|lowered).{0,40}target.{0,20}\$?([0-9]+(?:\.[0-9]+)?)",
        r"\$([0-9]+(?:\.[0-9]+)?) price target",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            return _to_decimal(match.group(1))
    return None


def _research_proxy(news_items: list[dict[str, object]]) -> dict[str, object]:
    signal_items = []
    up_count = 0
    down_count = 0
    latest_target_price = None
    latest_opinion = None
    latest_report_at = None
    for item in news_items:
        title = str(item.get("title") or "")
        lowered = title.lower()
        is_up = any(
            phrase in lowered
            for phrase in (
                "upgrade",
                "raises price target",
                "raised price target",
                "price target raised",
                "bullish",
                "outperform",
                "buy rating",
                "stays bullish",
            )
        )
        is_down = any(
            phrase in lowered
            for phrase in (
                "downgrade",
                "cuts price target",
                "cut price target",
                "price target cut",
                "lowers price target",
                "bearish",
                "underperform",
                "sell rating",
            )
        )
        if not is_up and not is_down:
            continue
        signal_items.append(item)
        if is_up:
            up_count += 1
        if is_down:
            down_count += 1
        if latest_target_price is None:
            latest_target_price = _extract_target_price(title)
        if latest_opinion is None:
            latest_opinion = "상향/긍정" if is_up and not is_down else "하향/부정" if is_down and not is_up else "혼재"
        if latest_report_at is None:
            latest_report_at = item.get("published_at")
    total = len(signal_items)
    return {
        "report_count_90d": total,
        "target_up_count": up_count,
        "target_down_count": down_count,
        "target_up_ratio": _round_decimal(Decimal(up_count) / Decimal(total) * Decimal("100")) if total else None,
        "latest_target_price": latest_target_price,
        "latest_opinion": latest_opinion,
        "latest_report_at": latest_report_at,
    }


def _grade_tone(grade: object) -> int:
    normalized = str(grade or "").lower()
    if any(word in normalized for word in ("strong buy", "buy", "outperform", "overweight", "positive")):
        return 1
    if any(word in normalized for word in ("sell", "underperform", "underweight", "negative")):
        return -1
    return 0


def _grade_label(grade: object) -> Optional[str]:
    normalized = str(grade or "").strip().lower()
    if not normalized:
        return None
    if "strong buy" in normalized:
        return "강력매수"
    if "buy" in normalized:
        return "매수"
    if any(word in normalized for word in ("outperform", "overweight")):
        return "시장상회"
    if any(word in normalized for word in ("hold", "neutral", "equal weight", "market perform")):
        return "중립"
    if any(word in normalized for word in ("underperform", "underweight")):
        return "시장하회"
    if "sell" in normalized:
        return "매도"
    return str(grade)


def _recommendation_key_label(key: object, mean: Optional[Decimal] = None) -> Optional[str]:
    normalized = str(key or "").replace("_", " ").strip().lower()
    labels = {
        "strong buy": "강력매수",
        "buy": "매수",
        "hold": "중립",
        "underperform": "시장하회",
        "sell": "매도",
    }
    if normalized in labels:
        return labels[normalized]
    if mean is not None:
        if mean <= Decimal("1.8"):
            return "강력매수"
        if mean <= Decimal("2.5"):
            return "매수"
        if mean <= Decimal("3.5"):
            return "중립"
        if mean <= Decimal("4.2"):
            return "시장하회"
        return "매도"
    return None


def _research_from_quote_summary(summary: dict[str, object]) -> dict[str, object]:
    financial = summary.get("financialData") if isinstance(summary.get("financialData"), dict) else {}
    trend = summary.get("recommendationTrend") if isinstance(summary.get("recommendationTrend"), dict) else {}
    history = summary.get("upgradeDowngradeHistory") if isinstance(summary.get("upgradeDowngradeHistory"), dict) else {}
    trend_rows = trend.get("trend") if isinstance(trend, dict) else []
    current_trend = next((row for row in trend_rows if isinstance(row, dict) and row.get("period") == "0m"), None)
    if current_trend is None and isinstance(trend_rows, list) and trend_rows:
        current_trend = trend_rows[0] if isinstance(trend_rows[0], dict) else None

    trend_counts = {
        key: int(current_trend.get(key) or 0) if isinstance(current_trend, dict) else 0
        for key in ("strongBuy", "buy", "hold", "sell", "strongSell")
    }
    trend_total = sum(trend_counts.values())
    positive_trend = trend_counts["strongBuy"] + trend_counts["buy"]
    negative_trend = trend_counts["sell"] + trend_counts["strongSell"]

    now = datetime.now(timezone.utc)
    history_rows = []
    if isinstance(history, dict):
        for row in history.get("history") or []:
            if not isinstance(row, dict):
                continue
            report_at = _parse_epoch_datetime(row.get("epochGradeDate"))
            if report_at and report_at < now - timedelta(days=90):
                continue
            history_rows.append({**row, "report_at": report_at})

    up_count = 0
    down_count = 0
    latest_target_price = _yahoo_raw_value(financial, "targetMeanPrice")
    latest_opinion = _recommendation_key_label(
        _yahoo_text_value(financial, "recommendationKey"),
        _yahoo_raw_value(financial, "recommendationMean"),
    )
    latest_report_at = None
    for row in history_rows:
        action = str(row.get("action") or "").lower()
        price_action = str(row.get("priceTargetAction") or "").lower()
        to_tone = _grade_tone(row.get("toGrade"))
        from_tone = _grade_tone(row.get("fromGrade"))
        if action == "up" or "raise" in price_action or to_tone > from_tone:
            up_count += 1
        elif action == "down" or any(word in price_action for word in ("lower", "cut", "reduce")) or to_tone < from_tone:
            down_count += 1
        if latest_report_at is None and row.get("report_at"):
            latest_report_at = row.get("report_at")
        if latest_target_price is None:
            latest_target_price = _to_decimal(row.get("currentPriceTarget"))
        if latest_opinion is None and row.get("toGrade"):
            latest_opinion = _grade_label(row.get("toGrade"))

    if up_count == 0 and down_count == 0 and trend_total:
        up_count = positive_trend
        down_count = negative_trend

    analyst_count = int(_yahoo_raw_value(financial, "numberOfAnalystOpinions") or 0)
    report_count = len(history_rows) or analyst_count or trend_total
    ratio_denominator = trend_total or (up_count + down_count)
    target_up_ratio = (
        _round_decimal(Decimal(positive_trend or up_count) / Decimal(ratio_denominator) * Decimal("100"))
        if ratio_denominator
        else None
    )
    return {
        "report_count_90d": report_count,
        "target_up_count": up_count,
        "target_down_count": down_count,
        "target_up_ratio": target_up_ratio,
        "latest_target_price": latest_target_price,
        "latest_opinion": latest_opinion,
        "latest_report_at": latest_report_at,
        "analyst_opinion_count": analyst_count or trend_total,
        "recommendation_mean": _yahoo_raw_value(financial, "recommendationMean"),
        "target_high_price": _yahoo_raw_value(financial, "targetHighPrice"),
        "target_low_price": _yahoo_raw_value(financial, "targetLowPrice"),
        "source": "Yahoo Finance quoteSummary",
    }


def _merge_research_signals(news_research: dict[str, object], analyst_research: dict[str, object]) -> dict[str, object]:
    if not analyst_research.get("report_count_90d"):
        return news_research
    merged = {**news_research}
    analyst_count = int(analyst_research.get("report_count_90d") or 0)
    news_count = int(merged.get("report_count_90d") or 0)
    if analyst_count >= news_count:
        for key in (
            "report_count_90d",
            "target_up_count",
            "target_down_count",
            "target_up_ratio",
            "latest_opinion",
            "latest_report_at",
        ):
            if analyst_research.get(key) is not None:
                merged[key] = analyst_research[key]
    for key in (
        "latest_target_price",
        "analyst_opinion_count",
        "recommendation_mean",
        "target_high_price",
        "target_low_price",
        "source",
    ):
        if analyst_research.get(key) is not None:
            merged[key] = analyst_research[key]
    return merged


def _financial_snapshot(
    fundamentals: dict[str, list[dict[str, object]]],
    price: Optional[Decimal],
) -> dict[str, object]:
    quarterly_revenue, revenue_date = _latest_metric(fundamentals, "quarterlyTotalRevenue")
    quarterly_operating_income, profit_date = _latest_metric(fundamentals, "quarterlyOperatingIncome")
    quarterly_eps, eps_date = _latest_metric(fundamentals, "quarterlyDilutedEPS")
    ttm_revenue = _sum_latest_quarters(fundamentals, "quarterlyTotalRevenue") or _latest_metric(fundamentals, "annualTotalRevenue")[0]
    ttm_operating_income = _sum_latest_quarters(fundamentals, "quarterlyOperatingIncome") or _latest_metric(fundamentals, "annualOperatingIncome")[0]
    ttm_eps = _sum_latest_quarters(fundamentals, "quarterlyDilutedEPS") or _latest_metric(fundamentals, "annualDilutedEPS")[0]
    shares, _ = _latest_metric(
        fundamentals,
        "quarterlyOrdinarySharesNumber",
        "quarterlyShareIssued",
        "annualOrdinarySharesNumber",
        "annualShareIssued",
    )
    equity, _ = _latest_metric(
        fundamentals,
        "quarterlyStockholdersEquity",
        "quarterlyCommonStockEquity",
        "quarterlyTangibleBookValue",
        "annualStockholdersEquity",
        "annualCommonStockEquity",
        "annualTangibleBookValue",
    )
    trailing_pe, _ = _latest_metric(fundamentals, "trailingPeRatio")
    per_series = [
        value
        for value in (_raw_metric_value(item) for item in _metric_series(fundamentals, "trailingPeRatio"))
        if value is not None and value > 0
    ]
    dividend_yield, _ = _latest_metric(fundamentals, "trailingAnnualDividendYield")
    if dividend_yield is not None and dividend_yield < Decimal("1"):
        dividend_yield = dividend_yield * Decimal("100")
    market_cap = price * shares if price is not None and shares is not None else None
    bps = _safe_ratio(equity, shares)
    per = trailing_pe or _safe_ratio(price, ttm_eps)
    pbr = _safe_ratio(price, bps) or _safe_ratio(market_cap, equity)
    if pbr is not None and pbr < Decimal("0.05"):
        pbr = None
        market_cap = None
    revenue_growth = _metric_growth(fundamentals, "quarterlyTotalRevenue")
    operating_profit_growth = _metric_growth(fundamentals, "quarterlyOperatingIncome")
    latest_date = revenue_date or profit_date or eps_date
    event_title = []
    if quarterly_revenue is not None:
        event_title.append(f"매출 ${_round_decimal(quarterly_revenue / Decimal('1000000000'), '0.1')}B")
    if quarterly_operating_income is not None:
        event_title.append(f"영업이익 ${_round_decimal(quarterly_operating_income / Decimal('1000000000'), '0.1')}B")
    if quarterly_eps is not None:
        event_title.append(f"EPS ${_round_decimal(quarterly_eps, '0.01')}")
    latest_events = []
    if event_title:
        latest_events.append(
            _metric_event(
                "최근 분기 " + " · ".join(event_title),
                latest_date,
                operating_profit_growth if operating_profit_growth is not None else revenue_growth,
            )
        )
    return {
        "ttm_revenue": ttm_revenue,
        "ttm_operating_income": ttm_operating_income,
        "ttm_eps": ttm_eps,
        "quarterly_revenue": quarterly_revenue,
        "quarterly_operating_income": quarterly_operating_income,
        "quarterly_eps": quarterly_eps,
        "revenue_growth": revenue_growth,
        "operating_profit_growth": operating_profit_growth,
        "shares": shares,
        "market_cap": market_cap,
        "equity": equity,
        "bps": bps,
        "per": _round_decimal(per) if per is not None else None,
        "pbr": _round_decimal(pbr) if pbr is not None else None,
        "per_series": per_series,
        "dividend_yield": _round_decimal(dividend_yield) if dividend_yield is not None else None,
        "latest_events": latest_events,
    }


def build_us_dashboard(symbol: str, refresh: bool = False) -> dict[str, object]:
    stock = resolve_us_stock(symbol)
    meta, prices = chart_prices(stock["code"], refresh=refresh, limit=250)
    latest = prices[-1] if prices else None
    previous = _nth_from_end(prices, 1)
    price = _to_decimal(meta.get("regularMarketPrice")) or (latest.close if latest else None)
    volume = meta.get("regularMarketVolume") or (latest.volume if latest else None)
    trading_value = price * Decimal(str(volume)) if price is not None and volume is not None else None
    news_items = _classify_us_news(_news(stock["code"]))
    sentiment_points = [Decimal(str(item.get("sentiment_score") or 0)) for item in news_items]
    positive = sum(1 for item in news_items if item.get("sentiment") == "positive")
    negative = sum(1 for item in news_items if item.get("sentiment") == "negative")
    neutral = max(0, len(news_items) - positive - negative)
    sentiment_score = _round_decimal(sum(sentiment_points) / Decimal(len(sentiment_points))) if sentiment_points else None
    chart = _chart_analysis(prices)
    momentum = _momentum(prices)
    flows = _us_liquidity_proxy(stock, momentum)
    try:
        fundamentals = fetch_us_fundamentals(stock["code"], refresh=refresh)
    except Exception:
        fundamentals = {}
    financials = _financial_snapshot(fundamentals, price) if fundamentals else {}
    peer_stats = _industry_valuation_stats(_peer_group_key(stock)) if financials else {}
    per_zscore = _zscore(financials.get("per"), financials.get("per_series") or []) or _zscore(
        financials.get("per"), peer_stats.get("per_values") or []
    )
    pbr_zscore = _zscore(financials.get("pbr"), peer_stats.get("pbr_values") or [])
    if financials and (per_zscore is None or (pbr_zscore is None and financials.get("pbr") is not None)):
        market_stats = _industry_valuation_stats("all")
        per_zscore = per_zscore or _zscore(financials.get("per"), market_stats.get("per_values") or [])
        pbr_zscore = pbr_zscore or _zscore(financials.get("pbr"), market_stats.get("pbr_values") or [])
    research = _research_proxy(news_items)
    try:
        analyst_research = _research_from_quote_summary(fetch_us_research_summary(stock["code"], refresh=refresh))
        research = _merge_research_signals(research, analyst_research)
    except Exception:
        pass
    try:
        filings = sec_filings(stock["code"], limit=8, refresh=refresh)
    except Exception:
        filings = []

    return {
        "code": stock["code"],
        "name": stock["name"],
        "market": stock["market"],
        "as_of": datetime.now(timezone.utc),
        "quote": {
            "trade_date": latest.trade_date if latest else None,
            "price": price,
            "change_value": price - previous.close if price is not None and previous and previous.close is not None else None,
            "change_rate": _rate(price, previous.close if previous else None),
            "volume": int(volume) if volume is not None else None,
            "trading_value": trading_value,
            "market_cap": financials.get("market_cap"),
        },
        "revisions": {
            **research,
            "estimated_revenue": financials.get("ttm_revenue"),
            "estimated_operating_profit": financials.get("ttm_operating_income"),
            "estimated_eps": financials.get("ttm_eps"),
            "estimated_per": financials.get("per"),
        },
        "surprise": {
            "recent_count": len(financials.get("latest_events") or []),
            "positive_count": sum(1 for item in financials.get("latest_events") or [] if item.get("sentiment") == "positive"),
            "negative_count": sum(1 for item in financials.get("latest_events") or [] if item.get("sentiment") == "negative"),
            "latest_events": financials.get("latest_events") or [],
            "latest_revenue": financials.get("quarterly_revenue"),
            "latest_operating_profit": financials.get("quarterly_operating_income"),
            "latest_eps": financials.get("quarterly_eps"),
            "revenue_growth": financials.get("revenue_growth"),
            "operating_profit_growth": financials.get("operating_profit_growth"),
        },
        "guidance": {
            "recent_count": len(filings),
            "positive_count": 0,
            "negative_count": 0,
            "latest_events": filings,
        },
        "momentum": momentum,
        "chart_analysis": chart,
        "flows": flows,
        "valuation": {
            "per": financials.get("per"),
            "pbr": financials.get("pbr"),
            "eps": financials.get("ttm_eps"),
            "bps": financials.get("bps"),
            "estimated_per": financials.get("per"),
            "estimated_eps": financials.get("ttm_eps"),
            "industry_per": peer_stats.get("industry_per"),
            "dividend_yield": financials.get("dividend_yield"),
            "per_zscore": per_zscore,
            "pbr_zscore": pbr_zscore,
            "ev_ebitda_zscore": None,
        },
        "macro_sensitivity": {
            "interest_rate": Decimal("-0.20") if stock.get("sector") in {"클라우드/AI", "소프트웨어", "AI 소프트웨어"} else Decimal("-0.10"),
            "fx": Decimal("0.20"),
            "commodity": Decimal("-0.10"),
            "export": Decimal("0.30"),
        },
        "sentiment": {
            "score": sentiment_score,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "latest_items": news_items,
        },
        "coverage": {
            "price": bool(prices),
            "investor_flow": bool(
                flows.get("foreign_net_buy_20d") is not None
                or flows.get("institution_net_buy_20d") is not None
                or flows.get("foreign_intensity") is not None
                or flows.get("institution_intensity") is not None
            ),
            "research_proxy": bool(research.get("report_count_90d")),
            "disclosure": bool(filings),
            "news": bool(news_items),
            "valuation": bool(financials.get("per") or financials.get("pbr") or financials.get("ttm_eps")),
            "macro_sensitivity": True,
        },
    }


def _dashboard_cached(symbol: str) -> Optional[dict[str, object]]:
    try:
        return US_CACHE.get_or_set(("us_dashboard", _symbol(symbol)), US_TTL_SECONDS, lambda: build_us_dashboard(symbol))
    except Exception:
        return None


def _us_universe_for_market(market: str = "ALL") -> list[dict[str, str]]:
    normalized = (market or "ALL").upper()
    if normalized == "NASDAQ":
        return NASDAQ_UNIVERSE
    if normalized in {"SP500", "S&P500", "S&P_500"}:
        return SP500_UNIVERSE
    return US_EQUITY_UNIVERSE


def _us_market_label(market: str = "ALL") -> str:
    normalized = (market or "ALL").upper()
    if normalized == "NASDAQ":
        return "NASDAQ"
    if normalized in {"SP500", "S&P500", "S&P_500"}:
        return "S&P 500"
    return "전체 미장"


def build_us_rankings(category: str = "surge", limit: int = 20, market: str = "ALL") -> dict[str, object]:
    category = category if category in {"surge", "trading_value", "valuation", "momentum", "sentiment"} else "surge"
    universe = _us_universe_for_market(market)
    dashboards = []
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(universe)))) as executor:
        futures = [executor.submit(_dashboard_cached, item["code"]) for item in universe]
        for future in as_completed(futures):
            payload = future.result()
            if payload:
                dashboards.append(payload)

    def metric(payload: dict[str, object]) -> Decimal:
        quote = payload["quote"]
        momentum = payload["momentum"]
        sentiment = payload["sentiment"]
        chart = payload["chart_analysis"]
        if category == "trading_value":
            return Decimal(str(quote.get("trading_value") or 0))
        if category == "momentum":
            return Decimal(str(momentum.get("three_month_return") or momentum.get("one_month_return") or 0))
        if category == "sentiment":
            return Decimal(str(sentiment.get("score") or 0))
        if category == "valuation":
            valuation = payload.get("valuation") or {}
            return _valuation_score(valuation)
        return Decimal(str(quote.get("change_rate") or 0))

    rows = []
    for rank, payload in enumerate(sorted(dashboards, key=metric, reverse=True)[:limit], start=1):
        quote = payload["quote"]
        momentum = payload["momentum"]
        sentiment = payload["sentiment"]
        valuation = payload.get("valuation") or {}
        rows.append(
            {
                "rank": rank,
                "category": category,
                "code": payload["code"],
                "name": payload["name"],
                "market": payload["market"],
                "trade_date": quote.get("trade_date"),
                "price": quote.get("price"),
                "change_rate": quote.get("change_rate"),
                "one_month_return": momentum.get("one_month_return"),
                "three_month_return": momentum.get("three_month_return"),
                "trading_value": quote.get("trading_value"),
                "trading_value_change": momentum.get("trading_value_change"),
                "per": valuation.get("per"),
                "pbr": valuation.get("pbr"),
                "sentiment_score": sentiment.get("score"),
                "news_count": sum(sentiment.get(key, 0) for key in ("positive_count", "negative_count", "neutral_count")),
                "metric_value": metric(payload),
            }
        )
    return {"category": category, "market": _us_market_label(market), "as_of": datetime.now(timezone.utc), "items": rows}


def build_us_recommendations(limit: int = 8, candidate_limit: int = 30) -> dict[str, object]:
    rankings = build_us_rankings("momentum", limit=max(candidate_limit, limit), market="ALL")
    items = []
    for payload in rankings["items"][:candidate_limit]:
        dashboard = _dashboard_cached(payload["code"])
        if not dashboard:
            continue
        chart = dashboard["chart_analysis"]
        momentum = dashboard["momentum"]
        quote = dashboard["quote"]
        sentiment = dashboard["sentiment"]
        valuation = dashboard.get("valuation") or {}
        score = Decimal("0")
        score += Decimal(str(chart.get("score") or 0)) * Decimal("0.45")
        score += max(Decimal("0"), Decimal(str(momentum.get("one_month_return") or 0))) * Decimal("0.35")
        score += max(Decimal("0"), Decimal(str(sentiment.get("score") or 0))) * Decimal("0.12")
        if any(valuation.get(key) is not None for key in ("per", "pbr", "industry_per", "per_zscore", "pbr_zscore")):
            value_score = _valuation_score(valuation)
            score += value_score * Decimal("0.08")
        score = _round_decimal(min(Decimal("100"), score)) or Decimal("0")
        reasons = [
            f"차트 점수 {chart.get('score')}점, {chart.get('trend')} 흐름",
            f"1개월 {momentum.get('one_month_return') or 0}%, 3개월 {momentum.get('three_month_return') or 0}% 모멘텀",
            "NASDAQ·S&P 500 대표 종목 후보군 안에서 계산",
        ]
        if sentiment.get("positive_count"):
            reasons.append(f"최근 긍정 뉴스 {sentiment.get('positive_count')}건")
        risks = list(chart.get("risks") or [])[:3] or ["무료 데이터 기반이라 실적 추정·ETF/펀드 플로우는 제한적으로 반영"]
        items.append(
            {
                "rank": 0,
                "code": dashboard["code"],
                "name": dashboard["name"],
                "market": dashboard["market"],
                "score": score,
                "action": "관심 매수후보" if score >= 60 else "관망",
                "price": quote.get("price"),
                "change_rate": quote.get("change_rate"),
                "one_month_return": momentum.get("one_month_return"),
                "three_month_return": momentum.get("three_month_return"),
                "trading_value": quote.get("trading_value"),
                "component_scores": {
                    "estimate_revision": Decimal("45"),
                    "analyst_revision_ratio": Decimal("45"),
                    "surprise": Decimal("45"),
                    "guidance": Decimal("45"),
                    "price_momentum": min(Decimal("100"), max(Decimal("0"), Decimal("50") + Decimal(str(momentum.get("one_month_return") or 0)))),
                    "trading_value": Decimal("60") if quote.get("trading_value") else Decimal("45"),
                    "valuation": _valuation_score(valuation),
                    "macro": Decimal("55"),
                    "flows": Decimal("45"),
                    "sentiment": min(Decimal("100"), max(Decimal("0"), Decimal("55") + Decimal(str(sentiment.get("score") or 0)) * Decimal("0.45"))),
                },
                "chart_analysis": chart,
                "reasons": reasons,
                "risks": risks,
            }
        )
    selected = sorted(items, key=lambda item: item["score"], reverse=True)[:limit]
    for index, item in enumerate(selected, start=1):
        item["rank"] = index
    return {
        "as_of": datetime.now(timezone.utc),
        "universe_count": len(US_EQUITY_UNIVERSE),
        "candidate_count": min(candidate_limit, len(items)),
        "methodology": [
            "무료 Yahoo Finance 차트·뉴스 기반",
            "차트 점수, 1개월/3개월 모멘텀, 거래대금, 뉴스 분위기 중심",
            "미국 개별주 13F·애널리스트 세부 데이터는 현재 무료 대체값으로 처리",
        ],
        "items": selected,
    }


def build_us_trends(days: int = 7) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    timeline = [
        {
            "id": "us-ai-capex",
            "published_at": now,
            "title": "AI 인프라 투자와 반도체 수요를 계속 점검",
            "source": "NASDAQ Brief",
            "url": None,
            "category": "AI",
            "impact": "호재",
            "leader_stocks": ["NVDA", "AVGO", "AMD"],
            "related_event": "ai-capex",
        },
        {
            "id": "us-rate-watch",
            "published_at": now,
            "title": "미국 금리와 달러 방향은 성장주 밸류에이션에 직접 영향",
            "source": "Macro Brief",
            "url": None,
            "category": "금리",
            "impact": "악재",
            "leader_stocks": ["MSFT", "AAPL", "AMZN"],
            "related_event": "fed-watch",
        },
    ]
    events = [
        {
            "id": "fed-watch",
            "starts_at": now,
            "category": "금리",
            "title": "미국 금리·달러 방향 점검",
            "importance": "중요",
            "expected_impact": "금리 하락 기대는 성장주 멀티플에 우호적, 금리 상승은 부담",
            "affected_variables": ["10Y Yield", "USD", "Growth Multiple"],
            "affected_sectors": ["AI", "소프트웨어", "반도체"],
            "watch_points": ["금리 하락 시 성장주 선호 회복", "금리 상승 시 고PER 종목 변동성 확대"],
            "source_name": "Macro Calendar",
            "source_url": "https://finance.yahoo.com/calendar/economic",
            "timeline": [timeline[1]],
        },
        {
            "id": "ai-capex",
            "starts_at": now,
            "category": "AI",
            "title": "AI 설비투자와 반도체 수요",
            "importance": "중요",
            "expected_impact": "AI 서버 투자 확대는 GPU·네트워크·메모리 밸류체인에 우호적",
            "affected_variables": ["AI Capex", "GPU", "HBM", "Data Center"],
            "affected_sectors": ["AI 반도체", "반도체 장비", "클라우드"],
            "watch_points": ["빅테크 CAPEX 상향", "데이터센터 전력 수요", "메모리 가격"],
            "source_name": "NASDAQ Brief",
            "source_url": "https://finance.yahoo.com/",
            "timeline": [timeline[0]],
        },
    ]
    return {
        "as_of": now,
        "window_start": now,
        "window_end": now,
        "headline": "미장은 금리·AI 설비투자·달러 흐름이 대형 성장주와 S&P 500 주도주의 방향을 좌우합니다.",
        "events": events,
        "past_events": [],
        "timeline": timeline,
    }


def _us_market_impact_factor_defaults() -> list[dict[str, object]]:
    return [
        {
            "key": "rate",
            "label": "금리",
            "interpretation_good": "금리 부담이 낮아지면 대형 성장주와 장기 스토리 종목의 밸류에이션이 회복되기 쉽습니다.",
            "interpretation_bad": "금리 부담이 커지면 고PER 성장주와 장기 스토리 종목 밸류에이션에 압박이 생깁니다.",
            "affected_sectors": ["대형 성장주", "소프트웨어", "반도체"],
            "leader_stocks": ["MSFT", "AAPL", "AMZN", "META"],
        },
        {
            "key": "dollar",
            "label": "달러",
            "interpretation_good": "달러 부담이 낮아지면 글로벌 유동성과 위험자산 선호 회복에 우호적입니다.",
            "interpretation_bad": "달러가 강하면 글로벌 유동성 부담이 커지고 위험자산 선호가 약해질 수 있습니다.",
            "affected_sectors": ["대형 기술주", "소비재", "클라우드"],
            "leader_stocks": ["AAPL", "NVDA", "TSLA", "AMZN"],
        },
        {
            "key": "bond",
            "label": "채권",
            "interpretation_good": "채권금리 안정은 성장주의 할인율 부담을 덜어주는 신호입니다.",
            "interpretation_bad": "채권수익률 상승은 주식보다 채권 매력을 키워 성장주에 부담을 줍니다.",
            "affected_sectors": ["클라우드", "SaaS", "플랫폼"],
            "leader_stocks": ["MSFT", "GOOGL", "CRM", "NVDA"],
        },
        {
            "key": "commodity",
            "label": "원자재",
            "interpretation_good": "원자재 부담이 낮아지면 소비주와 일부 제조업 마진 기대에 우호적입니다.",
            "interpretation_bad": "원자재 가격 상승은 물류와 제조 원가 부담을 키워 마진 압박으로 이어질 수 있습니다.",
            "affected_sectors": ["소비재", "전기차", "에너지"],
            "leader_stocks": ["TSLA", "AMZN", "CEG", "XOM"],
        },
        {
            "key": "risk",
            "label": "위험자산",
            "interpretation_good": "AI와 위험자산 선호가 강하면 나스닥과 반도체 주도주의 유동성이 강화되기 쉽습니다.",
            "interpretation_bad": "위험자산 선호가 약해지면 고변동 성장주 중심으로 차익실현 압력이 커질 수 있습니다.",
            "affected_sectors": ["AI", "반도체", "고성장 소프트웨어"],
            "leader_stocks": ["NVDA", "AVGO", "AMD", "PLTR"],
        },
    ]


def _us_market_impact_keywords() -> dict[str, tuple[str, ...]]:
    return {
        "rate": ("금리", "fed", "rate", "yield", "10y", "fomc"),
        "dollar": ("달러", "usd", "dollar", "dxy", "환율"),
        "bond": ("채권", "bond", "yield", "10y", "treasury"),
        "commodity": ("원유", "oil", "commodity", "energy", "원자재"),
        "risk": ("ai", "capex", "gpu", "반도체", "위험자산", "growth", "data center"),
    }


def _us_market_impact_direction(text: str, fallback: str = "") -> int:
    normalized = (text or "").lower()
    score = 0
    positive_words = ("우호", "확대", "회복", "완화", "강화", "수요", "호조", "랠리", "improves", "recovery", "supportive")
    negative_words = ("부담", "압박", "둔화", "약화", "위험", "긴축", "악재", "강세", "상승", "risk-off", "pressure")
    for word in positive_words:
        if word in normalized:
            score += 1
    for word in negative_words:
        if word in normalized:
            score -= 1
    if fallback == "호재":
        score += 1
    elif fallback == "악재":
        score -= 1
    return score


def build_us_market_impact() -> dict[str, object]:
    payload = build_us_trends(days=7)
    now = payload.get("as_of") or datetime.now(timezone.utc)
    factors = []
    keyword_map = _us_market_impact_keywords()
    for base in _us_market_impact_factor_defaults():
        factors.append(
            {
                **base,
                "raw": Decimal("4"),
                "direction_score": Decimal("0"),
                "evidence": [],
                "stocks": list(base["leader_stocks"]),
                "sectors": list(base["affected_sectors"]),
            }
        )

    def push_evidence(target: dict[str, object], source: str, metric: str, value_text: str, url: str = "") -> None:
        evidence = target["evidence"]
        if len(evidence) >= 3:
            return
        evidence.append(
            {
                "source": source,
                "metric": metric,
                "value_text": value_text,
                "as_of": now.isoformat(),
                "url": url or "https://finance.yahoo.com/",
            }
        )

    def apply_signal(text: str, fallback: str, source_name: str, title: str, summary: str, url: str, weight: Decimal, stocks: list[str], sectors: list[str]) -> None:
        lower_text = (text or "").lower()
        for factor in factors:
            keys = keyword_map[factor["key"]]
            if not any(keyword in lower_text for keyword in keys):
                continue
            factor["raw"] += weight
            factor["direction_score"] += Decimal(str(_us_market_impact_direction(text, fallback)))
            factor["stocks"].extend(stocks or [])
            factor["sectors"].extend(sectors or [])
            push_evidence(factor, source_name, title, summary, url)

    for event in payload.get("events", []):
        text = " ".join(
            [
                str(event.get("title") or ""),
                str(event.get("category") or ""),
                str(event.get("expected_impact") or ""),
                " ".join(str(value) for value in event.get("affected_variables", [])),
                " ".join(str(value) for value in event.get("affected_sectors", [])),
                " ".join(str(value) for value in event.get("watch_points", [])),
            ]
        )
        apply_signal(
            text,
            "호재" if "우호" in str(event.get("expected_impact") or "") or "확대" in str(event.get("expected_impact") or "") else "악재",
            str(event.get("source_name") or "US Macro"),
            str(event.get("title") or "미국 이벤트"),
            str(event.get("expected_impact") or ""),
            str(event.get("source_url") or "https://finance.yahoo.com/"),
            Decimal("12") if event.get("importance") == "중요" else Decimal("8"),
            list(event.get("leader_stocks") or []),
            list(event.get("affected_sectors") or []),
        )

    for item in payload.get("timeline", []):
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("category") or ""),
                str(item.get("impact") or ""),
                str(item.get("related_event") or ""),
            ]
        )
        apply_signal(
            text,
            str(item.get("impact") or ""),
            str(item.get("source") or "US Timeline"),
            str(item.get("title") or "미국 타임라인"),
            str(item.get("impact") or ""),
            "https://finance.yahoo.com/",
            Decimal("10"),
            list(item.get("leader_stocks") or []),
            [],
        )

    raw_total = sum(Decimal(str(factor["raw"])) for factor in factors) or Decimal("1")
    result_factors = []
    running_percent = Decimal("0")
    for index, factor in enumerate(factors):
        raw_percent = (Decimal(str(factor["raw"])) / raw_total) * Decimal("100")
        percent = Decimal("100") - running_percent if index == len(factors) - 1 else _round_decimal(raw_percent, "0.1") or Decimal("0")
        running_percent += percent
        direction = "호재" if Decimal(str(factor["direction_score"])) >= 0 else "악재"
        result_factors.append(
            {
                "key": factor["key"],
                "label": factor["label"],
                "percent": max(Decimal("0"), percent),
                "direction": direction,
                "confidence": Decimal("76") if factor["evidence"] else Decimal("62"),
                "interpretation": factor["interpretation_good"] if direction == "호재" else factor["interpretation_bad"],
                "evidence": factor["evidence"],
                "affected_sectors": list(dict.fromkeys(factor["sectors"]))[:4],
                "leader_stocks": list(dict.fromkeys(factor["stocks"]))[:5],
            }
        )

    result_factors.sort(key=lambda item: float(item["percent"]), reverse=True)
    good_weight = sum(float(item["percent"]) for item in result_factors if item["direction"] == "호재")
    bad_weight = sum(float(item["percent"]) for item in result_factors if item["direction"] != "호재")
    market_status = "호재 우위" if good_weight >= bad_weight else "리스크 우위"
    lead = result_factors[0]
    summary = (
        f"{lead['label']} 영향이 가장 크고, 현재는 호재 축이 더 우세합니다."
        if market_status == "호재 우위"
        else f"{lead['label']} 영향이 가장 크고, 현재는 리스크 관리가 더 우선입니다."
    )
    return {
        "as_of": now,
        "market_status": market_status,
        "summary": summary,
        "good_weight": _round_decimal(good_weight, "0.1") or Decimal("0"),
        "bad_weight": _round_decimal(bad_weight, "0.1") or Decimal("0"),
        "factors": result_factors,
    }


def build_us_event_graph(event_id: str) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    if event_id == "ai-capex":
        negative_label = "투자 둔화"
        positive_label = "투자 확대"
        stocks = ["NVDA", "AVGO", "AMD", "MRVL"]
    else:
        negative_label = "금리 상승"
        positive_label = "금리 하락"
        stocks = ["MSFT", "AAPL", "AMZN", "META"]
    impacted = []
    for code in stocks:
        base = US_UNIVERSE_BY_CODE.get(code, {"name": code})
        impacted.append(
            {
                "code": code,
                "name": base["name"],
                "market": "NASDAQ",
                "market_cap": None,
                "impact_score": Decimal("70"),
                "impact_direction": "호재",
                "reasons": [f"{positive_label} 시 수혜 가능", "미국 대형 성장주 영향권"],
            }
        )
    return {
        "event_id": event_id,
        "title": "AI 설비투자" if event_id == "ai-capex" else "미국 금리 방향",
        "as_of": now,
        "summary": f"{positive_label}과 {negative_label}에 따라 미국 성장주와 S&P 500 주도주의 밸류에이션, 수요 기대가 달라집니다.",
        "scenario": "base",
        "negative_label": negative_label,
        "positive_label": positive_label,
        "layers": [
            {"title": "이벤트", "nodes": [{"id": event_id, "label": "미국 핵심 이벤트", "kind": "event", "detail": "중요", "polarity": "neutral"}]},
            {"title": "1차 변수", "nodes": [{"id": "rate", "label": "금리/AI 투자", "kind": "factor", "detail": "1차 변수", "polarity": "neutral"}]},
            {"title": "2차 영향", "nodes": [{"id": "multiple", "label": "성장주 멀티플", "kind": "sector", "detail": "밸류에이션 영향", "polarity": "neutral"}]},
        ],
        "negative_stocks": impacted[:2],
        "positive_stocks": impacted,
    }
