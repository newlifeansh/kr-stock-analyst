from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.collectors.news import preferred_news_url
from app.models import NewsItem
from app.repository import latest_news_items
from app.services.investor_calendar import InvestorScheduleEvent, upcoming_investor_events


KST = ZoneInfo("Asia/Seoul")
MORNING_BRIEFING_START = time(16, 0)
MORNING_BRIEFING_END = time(6, 0)
MIDDAY_BRIEFING_START = time(9, 0)
MIDDAY_BRIEFING_END = time(12, 0)
AFTERNOON_BRIEFING_START = time(12, 0)
AFTERNOON_BRIEFING_END = time(16, 0)
MORNING_BRIEFING_QUERY_LIMIT = 320
MORNING_BRIEFING_HISTORY_CANDIDATE_LIMIT = 64
MORNING_BRIEFING_ITEMS_PER_CATEGORY = 2
MORNING_BRIEFING_TOTAL_ITEM_LIMIT = 12
MORNING_BRIEFING_HIGHLIGHT_LIMIT = 3
MORNING_BRIEFING_CONTEXT_LIMIT = 105
MORNING_BRIEFING_SUMMARY_LIMIT = 180


@dataclass(frozen=True)
class MorningBriefingCategory:
    key: str
    label: str
    icon: str
    description: str
    why_it_matters: str


@dataclass(frozen=True)
class MoneyBriefingEdition:
    edition: str
    edition_key: str
    edition_label: str
    publication_date: date
    window_start: datetime
    window_end: datetime
    published_at: datetime
    next_publication_at: datetime


CATEGORIES = (
    MorningBriefingCategory(
        key="schedule",
        label="오늘 체크할 일정",
        icon="📅",
        description="IPO 청약·실적 발표·경제지표처럼 오늘 놓치지 말아야 할 일정",
        why_it_matters="발표 전후 가격 변동이 커질 수 있어 확인할 시간대를 먼저 잡아두세요.",
    ),
    MorningBriefingCategory(
        key="market",
        label="증시 UP&DOWN",
        icon="📈",
        description="국내·해외 지수, 외국인·기관 수급과 주도 흐름",
        why_it_matters="지수 방향과 장 초반 거래가 몰릴 업종을 가늠하는 단서예요.",
    ),
    MorningBriefingCategory(
        key="money",
        label="금융시장 동향",
        icon="🪙",
        description="채권금리, 원·달러, 유가와 주요 자산 가격 변화",
        why_it_matters="할인율·원가·외국인 수급을 함께 움직일 수 있는 가격 변수예요.",
    ),
    MorningBriefingCategory(
        key="invest",
        label="투자·재테크",
        icon="💰",
        description="ETF·펀드·연금·세제와 실전 자산관리 정보",
        why_it_matters="수익률뿐 아니라 비용·세금·만기까지 비교해 내 자산관리에 맞는지 봐야 해요.",
    ),
    MorningBriefingCategory(
        key="industry",
        label="산업 뉴스",
        icon="⚙️",
        description="반도체·배터리·자동차 등 주요 산업과 공급망 변화",
        why_it_matters="관련 밸류체인의 실적 기대와 테마 강도에 영향을 줄 수 있어요.",
    ),
    MorningBriefingCategory(
        key="company",
        label="기업 소식",
        icon="💼",
        description="실적, 투자, 인수합병과 개별 기업 주요 변화",
        why_it_matters="개별 종목의 실적 추정치와 단기 변동성을 바꿀 수 있는 재료예요.",
    ),
    MorningBriefingCategory(
        key="tech",
        label="테크(Tech)",
        icon="⚙️",
        description="AI·소프트웨어·클라우드·디지털 플랫폼 변화",
        why_it_matters="새 기술의 상용화 속도가 관련 기업의 매출과 비용 구조를 바꾸는지 봐야 해요.",
    ),
    MorningBriefingCategory(
        key="policy",
        label="정책·경제지표",
        icon="📌",
        description="정부·중앙은행 정책과 물가·고용·수출 지표",
        why_it_matters="금리 기대와 정책 수혜 업종의 실적·가치평가를 바꿀 수 있어요.",
    ),
    MorningBriefingCategory(
        key="real_estate",
        label="부동산",
        icon="🏠",
        description="주택 공급·대출·세제와 매매·전세 시장 변화",
        why_it_matters="공급·대출 조건과 거래 흐름이 건설·은행·리츠와 주거 비용에 어떤 영향을 주는지 봐야 해요.",
    ),
)

# Keep helper-level compatibility for callers that still reference the former
# broad categories. These aliases are never rendered as briefing sections.
LEGACY_CATEGORY_ALIASES = (
    MorningBriefingCategory(
        key="global",
        label="증시 UP&DOWN",
        icon="🌍",
        description="미국·유럽·중국 등 해외시장 핵심 변수",
        why_it_matters="해외시장 흐름이 국내 성장주와 수출주에 어떤 영향을 주는지 봐야 해요.",
    ),
    MorningBriefingCategory(
        key="other",
        label="핫이슈",
        icon="🫘",
        description="지금 시장에서 영향력이 큰 이슈",
        why_it_matters="여러 자산에 번질 수 있는 영향 경로를 확인해보세요.",
    ),
)
CATEGORY_LOOKUP = {
    category.key: category for category in (*CATEGORIES, *LEGACY_CATEGORY_ALIASES)
}

SCHEDULE_EVENT_KEYWORDS = (
    "발표", "실적", "상장", "청약", "공모주", "ipo", "회의", "fomc", "cpi", "고용",
    "공개", "개최", "출시", "설명회",
)
SCHEDULE_FUTURE_KEYWORDS = (
    "예정", "앞두고", "오늘", "내일", "이번 주", "이번주", "다음 주", "다음주",
    "오늘 밤", "내일 밤", "청약", "공모주", "ipo", "개최", "출시한다", "공개한다",
)
IPO_SCHEDULE_KEYWORDS = ("ipo", "공모주", "공모 청약", "청약", "수요예측")
EARNINGS_SCHEDULE_KEYWORDS = (
    "실적 발표", "실적발표", "경영실적", "실적 공개", "earnings",
)
DOMESTIC_MARKET_KEYWORDS = (
    "코스피", "코스닥", "삼전닉스", "외국인", "기관", "개인투자자", "수급", "공매도",
    "거래대금", "사이드카", "상한가", "하한가", "동전주", "시총 미달", "상폐",
    "상장폐지", "관리종목", "주식시장", "증시 급등", "증시 급락", "주가 급등",
    "주가 급락", "株", "휘청",
)
GLOBAL_MARKET_KEYWORDS = (
    "뉴욕증시", "나스닥", "다우", "s&p", "스탠더드앤드푸어스", "유럽증시",
    "중국증시", "중국 증시", "中 증시", "美증시", "美 증시", "일본증시", "일본 증시",
    "홍콩증시", "홍콩 증시", "해외증시", "월스트리트", "월가", "주가지수",
)
GLOBAL_MARKET_KEYWORDS += (
    "\ub300\ub9cc\uc99d\uc2dc",
    "\ub300\ub9cc \uc99d\uc2dc",
)
MONEY_KEYWORDS = (
    "금리", "국채", "채권", "환율", "원·달러", "원/달러", "달러", "엔화", "위안",
    "유가", "원유", "금값", "금 가격", "원자재", "비트코인", "가상자산", "코인",
)
MONEY_KEYWORDS += (
    "금 선물", "은 선물", "브렌트유", "wti", "달러인덱스",
)
INVESTMENT_KEYWORDS = (
    "etf", "tdf", "펀드", "재테크", "예금", "적금", "연금", "isa", "절세",
    "수수료", "배당주", "자산배분", "포트폴리오", "레버리지", "인버스",
    "종합자산관리", "투자전략", "노후준비", "퇴직연금", "개인연금",
)
POLICY_KEYWORDS = (
    "정부", "정책", "규제", "지원책", "세제", "관세", "보조금", "한국은행", "연준",
    "fed", "fomc", "cpi", "pce", "소비자물가", "생산자물가", "물가", "고용", "실업",
    "수출액", "수출 증가", "수출 감소", "수출입", "무역수지", "gdp", "성장률",
    "재정", "법안", "위헌",
)
POLICY_KEYWORDS += (
    "\uc77c\uc790\ub9ac",
    "\ub300\ucc45",
    "\ubaa8\uc758\uac70\ub798",
    "\uae08\uc735\uac10\ub3c5\uc6d0",
    "\uae08\uac10\uc6d0",
)
REAL_ESTATE_POLICY_TOPICS = (
    "부동산", "주택", "아파트", "비아파트", "신도시", "재건축", "재개발",
    "정비사업", "공공택지", "전세", "주거", "집값", "분양",
)
REAL_ESTATE_POLICY_ACTIONS = (
    "정책", "대책", "공급", "규제", "지원", "완화", "인센티브", "대출",
    "국토부", "국토교통부", "정부", "대통령", "보금자리론", "착공", "세제",
)
REAL_ESTATE_POLICY_PHRASES = (
    "부동산 대책", "부동산대책", "주택 공급", "주택공급", "공급 대책", "공급대책",
    "정책 대출", "정책대출", "전세 대출", "전세대출", "주택담보대출", "주담대",
    "보금자리론", "이주비 대출", "이주비대출", "파격 금리", "초저금리",
)
REAL_ESTATE_TRANSACTION_ASSETS = (
    "빌딩", "타워", "오피스", "상가", "호텔", "물류센터", "업무시설",
)
REAL_ESTATE_TRANSACTION_ACTIONS = ("인수", "매입", "매각", "거래", "개발")
INDUSTRY_KEYWORDS = (
    "반도체", "ai반도체", "배터리", "이차전지", "2차전지", "로봇",
    "바이오", "헬스케어", "자동차", "전기차", "조선", "방산", "원전", "태양광",
    "디스플레이", "데이터센터", "게임", "콘텐츠", "항공", "해운", "철강", "석유화학",
    "화장품", "k뷰티", "k-뷰티", "뷰티", "제약", "의료기기",
)
TECH_KEYWORDS = (
    "인공지능", "ai 모델", "ai 서비스", "생성형 ai", "오픈ai", "openai",
    "챗gpt", "chatgpt", "클라우드", "소프트웨어", "플랫폼", "앱마켓",
    "사이버보안", "퀴텀", "양자컴퓨팅", "워터마크", "알고리즘", "디지털",
)
GLOBAL_REGION_KEYWORDS = (
    "미국", "미 대통령", "트럼프", "백악관", "유럽", "중국", "일본", "홍콩", "대만",
    "글로벌", "해외",
)
MARKET_KEYWORDS = (
    "증시", "주가", "주도주", "신고가", "급등주", "급락주", "시가총액",
)
COMPANY_KEYWORDS = (
    "실적", "영업이익", "매출", "순이익", "인수", "합병", "유상증자", "무상증자", "수주",
    "계약", "기술이전", "증설", "자사주", "배당", "주주환원", "공시", "목표가", "목표주가",
    "최대주주", "지분", "유령주식",
)
COMPANY_KEYWORDS += (
    "\uc601\uc5c5\uc775",
    "\uc601\uc5c5\uc190\uc2e4",
    "\uc21c\uc775",
    "\uc0c1\uc7a5",
    "\uc720\uc99d",
    "\ub9e4\uac01",
)
NON_INVESTMENT_KEYWORDS = (
    "\ucf58서트", "\ud32c미팅", "\uc2e0곡", "\uc74c원", "\uc568범", "\uc608능", "\ub4dc라마", "\ubba4지컬",
    "\ubcf4컬리스트", "\uac00수", "\ubc30우", "\uc544이돌", "\uacf5연 \uac1c최",
)
LOW_INFORMATION_TITLE_KEYWORDS = (
    "\uc8fc요경제지표",
    "\uc624늘의 \uc6b4세",
)
OTHER_INVESTMENT_KEYWORDS = (
    "\ud22c\uc790", "\uc8fc\uc2dd", "\uc99d\uad8c", "\ud380\ub4dc", "etf", "tdf", "\uc218\uc218\ub8cc", "\ub300\ucd9c", "\uae08\uc735",
    "\ubd80\ub3d9\uc0b0", "\ub9e4\uac01", "\uc784\ub300", "\uc218\uc775", "\uae30\uc5c5", "\uc2e4\uc801", "\uc601\uc5c5", "\ub9e4\ucd9c", "\uc218\ucd9c",
    "\uae08\ub9ac", "\ud658\uc728", "\uacbd\uc81c", "\uace0\uc6a9", "\ubb3c\uac00", "\uc138\uae08", "\uc138\uc81c", "\uc5f0\uae08", "\ubcf4\ud5d8", "\uc740\ud589",
)
POSITIVE_KEYWORDS = (
    "상승", "급등", "호조", "증가", "개선", "흑자", "수주", "최대", "돌파", "확대",
    "인하", "완화", "회복", "강세", "상향", "승인", "지원", "매수",
)
CAUTION_KEYWORDS = (
    "하락", "급락", "부진", "감소", "악화", "적자", "우려", "리스크", "중단", "취소",
    "인상", "긴축", "약세", "하향", "제재", "조사", "충돌", "전쟁", "매도",
)
IMPACT_KEYWORDS = (
    "금리", "환율", "cpi", "fomc", "연준", "실적", "반도체", "수출", "유가", "관세",
    "인수", "합병", "상장", "공모", "급등", "급락", "최대", "최저", "정책", "규제",
)

CATEGORY_TAKEAWAY_RULES = {
    "market": (
        (
            ("국민연금", "연기금"),
            "연기금의 매매 변화가 대형주 수급과 지수 변동성에 미칠 영향을 봐야 해요.",
        ),
        (
            ("코스닥",),
            "코스닥 강세가 외국인·기관 수급으로 이어지는지 장 초반 거래대금을 함께 확인해보세요.",
        ),
        (
            ("반도체", "삼성전자", "하이닉스", "삼전닉스"),
            "반도체 대형주의 방향이 지수와 외국인 수급으로 이어지는지 함께 봐야 해요.",
        ),
        (
            ("나스닥", "뉴욕증시", "s&p", "다우"),
            "미국 지수와 기술주 방향이 국내 반도체·성장주의 장 초반 수급으로 이어지는지 봐야 해요.",
        ),
    ),
    "global": (
        (
            ("나스닥", "기술주", "ai"),
            "미국 기술주 흐름은 국내 반도체·성장주의 장 초반 투자심리에도 영향을 줄 수 있어요.",
        ),
        (
            ("중국", "홍콩", "대만"),
            "중화권 증시 흐름은 국내 소비주와 소재·산업재의 수요 기대에 영향을 줄 수 있어요.",
        ),
    ),
    "money": (
        (
            ("환율", "원·달러", "원/달러", "달러·원"),
            "원화 흐름은 외국인 수급과 수입 기업의 원가 부담을 가늠하는 단서예요.",
        ),
        (
            ("유가", "원유"),
            "유가 변화는 정유·항공·화학 업종의 비용과 이익 기대를 바꿀 수 있어요.",
        ),
        (
            ("cpi", "fomc", "금리", "국채", "채권"),
            "금리 기대 변화는 성장주 가치평가와 달러 흐름을 함께 움직일 수 있어요.",
        ),
    ),
    "invest": (
        (
            ("etf", "tdf", "펀드", "레버리지", "인버스"),
            "편입 자산과 비용·변동성이 내 보유 기간과 맞는지 함께 비교해보세요.",
        ),
        (
            ("isa", "연금", "절세", "퇴직연금"),
            "가입 조건과 세제 혜택, 중도 인출 제약까지 내 자산관리 목표와 맞는지 봐야 해요.",
        ),
    ),
    "policy": (
        (
            ("cpi", "fomc", "연준", "물가", "고용"),
            "지표 결과가 중앙은행의 금리 경로를 바꾸는지에 따라 증시 변동성도 커질 수 있어요.",
        ),
        (
            ("관세", "보조금", "세제", "지원책", "수출"),
            "정책 범위와 시행 시점에 따라 수혜·부담 업종이 갈릴 수 있어요.",
        ),
    ),
    "industry": (
        (
            ("화장품", "k뷰티", "k-뷰티", "뷰티"),
            "수출 증가가 실제 매출과 이익률 개선으로 이어지는지 관련 기업 실적을 함께 볼 필요가 있어요.",
        ),
        (
            ("반도체", "인공지능", " ai ", "데이터센터"),
            "국내 반도체·장비·소재 기업의 수주와 실적 기대를 움직일 수 있어요.",
        ),
        (
            ("배터리", "이차전지", "2차전지", "전기차"),
            "배터리 소재·셀 업체의 가동률과 수익성 기대에 영향을 줄 수 있어요.",
        ),
    ),
    "tech": (
        (
            ("오픈ai", "openai", "챗gpt", "chatgpt", "ai 모델", "생성형 ai"),
            "새 모델의 성능과 비용이 클라우드·소프트웨어 기업의 사용량과 수익성을 바꾸는지 봐야 해요.",
        ),
        (
            ("워터마크", "사이버보안", "규제", "ai법"),
            "규제 적용 시점과 도입 비용이 관련 기술 수요에 어떤 변화를 주는지 봐야 해요.",
        ),
    ),
    "real_estate": (
        (
            REAL_ESTATE_TRANSACTION_ASSETS,
            "거래가격과 임대수익이 리츠·부동산 운용사 가치에 어떻게 반영되는지 확인해보세요.",
        ),
        (
            REAL_ESTATE_POLICY_TOPICS + ("대출", "보금자리론"),
            "주택 공급·대출 조건 변화가 건설·은행·리츠와 실수요자 부담에 어떤 영향을 주는지 봐야 해요.",
        ),
    ),
    "company": (
        (
            ("자사주", "주주환원", "배당"),
            "자사주 소각과 배당 확대가 주당가치와 수급 개선으로 이어지는지 확인해보세요.",
        ),
        (
            ("회사채", "자금조달", "채권 발행"),
            "조달 규모와 금리 부담이 현금흐름과 향후 투자 여력에 미칠 영향을 살펴볼 필요가 있어요.",
        ),
        (
            ("배상", "판결", "조사", "제재", "소송", "유령주식"),
            "배상·규제 비용과 신뢰도 변화가 실적과 주가에 얼마나 반영될지 살펴볼 필요가 있어요.",
        ),
        (
            ("인수", "합병", "투자", "증설", "유상증자"),
            "성장 효과와 자금 부담이 기업가치에 어떻게 반영될지가 관전 포인트예요.",
        ),
        (
            ("실적", "영업이익", "매출", "순이익"),
            "발표된 숫자가 시장 기대와 얼마나 다른지, 향후 전망이 바뀌는지 확인해보세요.",
        ),
    ),
}


def _kst_datetime(now: Optional[datetime] = None) -> datetime:
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        return current.replace(tzinfo=KST)
    return current.astimezone(KST)


def money_briefing_edition(now: Optional[datetime] = None) -> MoneyBriefingEdition:
    """Return the latest published KST briefing edition, including weekends."""

    current = _kst_datetime(now)
    current_time = current.timetz().replace(tzinfo=None)
    publication_date = current.date()

    if current_time < MORNING_BRIEFING_END:
        publication_date -= timedelta(days=1)
        edition = "afternoon"
        edition_label = "오후판"
        edition_hour = AFTERNOON_BRIEFING_END.hour
        window_start = datetime.combine(
            publication_date,
            AFTERNOON_BRIEFING_START,
            tzinfo=KST,
        )
        window_end = datetime.combine(
            publication_date,
            AFTERNOON_BRIEFING_END,
            tzinfo=KST,
        )
        next_publication_at = datetime.combine(
            publication_date + timedelta(days=1),
            MORNING_BRIEFING_END,
            tzinfo=KST,
        )
    elif current_time < MIDDAY_BRIEFING_END:
        edition = "morning"
        edition_label = "오전판"
        edition_hour = MORNING_BRIEFING_END.hour
        window_start = datetime.combine(
            publication_date - timedelta(days=1),
            MORNING_BRIEFING_START,
            tzinfo=KST,
        )
        window_end = datetime.combine(
            publication_date,
            MORNING_BRIEFING_END,
            tzinfo=KST,
        )
        next_publication_at = datetime.combine(
            publication_date,
            MIDDAY_BRIEFING_END,
            tzinfo=KST,
        )
    elif current_time < AFTERNOON_BRIEFING_END:
        edition = "midday"
        edition_label = "점심판"
        edition_hour = MIDDAY_BRIEFING_END.hour
        window_start = datetime.combine(
            publication_date,
            MIDDAY_BRIEFING_START,
            tzinfo=KST,
        )
        window_end = datetime.combine(
            publication_date,
            MIDDAY_BRIEFING_END,
            tzinfo=KST,
        )
        next_publication_at = datetime.combine(
            publication_date,
            AFTERNOON_BRIEFING_END,
            tzinfo=KST,
        )
    else:
        edition = "afternoon"
        edition_label = "오후판"
        edition_hour = AFTERNOON_BRIEFING_END.hour
        window_start = datetime.combine(
            publication_date,
            AFTERNOON_BRIEFING_START,
            tzinfo=KST,
        )
        window_end = datetime.combine(
            publication_date,
            AFTERNOON_BRIEFING_END,
            tzinfo=KST,
        )
        next_publication_at = datetime.combine(
            publication_date + timedelta(days=1),
            MORNING_BRIEFING_END,
            tzinfo=KST,
        )

    published_at = window_end
    return MoneyBriefingEdition(
        edition=edition,
        edition_key=f"{publication_date.isoformat()}:{edition_hour:02d}",
        edition_label=edition_label,
        publication_date=publication_date,
        window_start=window_start,
        window_end=window_end,
        published_at=published_at,
        next_publication_at=next_publication_at,
    )


def morning_briefing_window(now: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Return the latest published briefing window as the legacy triple."""

    edition = money_briefing_edition(now)
    return edition.window_start, edition.window_end, edition.publication_date


def _contains(text: str, keywords: Iterable[str]) -> bool:
    padded = f" {text.casefold()} "
    return any(keyword.casefold() in padded for keyword in keywords)


def _is_real_estate_policy_text(value: object) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).casefold().strip()
    if not text:
        return False
    if _contains(text, REAL_ESTATE_POLICY_PHRASES):
        return True
    return _contains(text, REAL_ESTATE_POLICY_TOPICS) and _contains(
        text,
        REAL_ESTATE_POLICY_ACTIONS,
    )


def _is_schedule_title(title: str) -> bool:
    has_event = _contains(title, SCHEDULE_EVENT_KEYWORDS)
    has_future_marker = _contains(title, SCHEDULE_FUTURE_KEYWORDS)
    return has_event and has_future_marker


def _category_from_text(value: object) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "")).casefold().strip()
    if not text:
        return None
    if _is_schedule_title(text):
        return "schedule"

    scores = _category_scores(text)
    return _dominant_category(scores)


def _keyword_hits(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for keyword in set(keywords) if keyword.casefold() in text)


def _category_scores(text: str, *, weight: int = 1) -> dict[str, int]:
    # Category scoring must keep company names intact. Story normalization turns
    # Samsung Electronics/SK hynix into "반도체", which is useful for
    # deduplication but would misclassify a bond-demand story as industry news.
    normalized = re.sub(r"\s+", " ", str(text or "")).casefold().strip()
    scores = {
        "market": _keyword_hits(
            normalized,
            DOMESTIC_MARKET_KEYWORDS + GLOBAL_MARKET_KEYWORDS + MARKET_KEYWORDS,
        ),
        "money": _keyword_hits(normalized, MONEY_KEYWORDS),
        "invest": _keyword_hits(normalized, INVESTMENT_KEYWORDS),
        "policy": _keyword_hits(normalized, POLICY_KEYWORDS),
        "industry": _keyword_hits(normalized, INDUSTRY_KEYWORDS),
        "company": _keyword_hits(normalized, COMPANY_KEYWORDS),
        "tech": _keyword_hits(normalized, TECH_KEYWORDS),
        "real_estate": _keyword_hits(normalized, REAL_ESTATE_POLICY_TOPICS),
    }
    if re.search(r"\d{4,5}피(?:\s|$)", normalized):
        scores["market"] += 5
    if _contains(
        normalized,
        (
            "코스피", "코스닥", "뉴욕증시", "나스닥", "다우", "s&p", "중국증시",
            "일본증시", "홍콩증시", "대만증시", "대만 증시",
        ),
    ):
        scores["market"] += 4
    if _contains(normalized, ("株", "휘청", "주가 급등", "주가 급락", "사이드카")):
        scores["market"] += 2
    if _contains(normalized, ("국민연금", "연기금")) and _contains(
        normalized,
        ("국내주식", "매수", "매도", "비중", "수급", "리밸런싱", "유예"),
    ):
        scores["market"] += 7
        scores["invest"] = 0
    if _is_real_estate_policy_text(normalized):
        scores["real_estate"] += 3
    if _contains(normalized, REAL_ESTATE_TRANSACTION_ASSETS) and _contains(
        normalized,
        REAL_ESTATE_TRANSACTION_ACTIONS,
    ):
        scores["real_estate"] += 5
    if scores["invest"]:
        # Product names such as ETF, ISA and TDF should not be swallowed by a
        # passing mention of rates or the broader market.
        scores["invest"] += 2
    if _contains(
        normalized,
        ("규제", "금감원", "금융감독원", "금융당국", "법안", "정부 발표"),
    ):
        scores["policy"] += 3
    if _contains(normalized, INDUSTRY_KEYWORDS):
        scores["industry"] += 2
    broad_sector_hits = sum(
        keyword in normalized
        for keyword in ("반도체", "자동차", "조선", "화학", "철강", "바이오", "화장품")
    )
    if re.search(r"(?:^|[\s·,/])차(?:$|[\s·,/])", normalized):
        broad_sector_hits += 1
    if broad_sector_hits >= 2 and _contains(
        normalized,
        ("실적", "전망", "쾌청", "호황", "회복"),
    ):
        scores["industry"] += 6
    if _contains(
        normalized,
        (
            "실적", "영업이익", "영업손실", "순이익", "순익", "매출", "수주", "계약",
            "기술이전", "인수", "합병", "유상증자", "무상증자", "자사주", "배당",
        ),
    ):
        scores["company"] += 3
    return {key: value * weight for key, value in scores.items()}


def _dominant_category(scores: dict[str, int]) -> Optional[str]:
    # Ties intentionally prefer a concrete reader-facing section over broad
    # industry/company buckets.
    priority = (
        "real_estate",
        "invest",
        "market",
        "policy",
        "money",
        "company",
        "tech",
        "industry",
    )
    best = max((scores.get(key, 0), -priority.index(key), key) for key in priority)
    return best[2] if best[0] > 0 else None


def classify_morning_news(item: NewsItem) -> str:
    title = re.sub(r"\s+", " ", str(item.title or "")).casefold().strip()
    if _is_schedule_title(title):
        return "schedule"

    scores = _category_scores(title, weight=3)
    if _summary_matches_title(item.title, item.summary):
        for key, score in _category_scores(str(item.summary or "")).items():
            scores[key] = scores.get(key, 0) + score

    source_category = str(item.source_category or "").casefold()
    source_fallback = {
        "bond": "money",
        "fx": "money",
        "company": "company",
        "disclosure_memo": "company",
        "market": "market",
        "global": "market",
    }.get(source_category)
    if source_fallback:
        scores[source_fallback] = scores.get(source_fallback, 0) + 1
    return _dominant_category(scores) or "other"


def morning_news_status(item: NewsItem) -> str:
    text = str(item.title or "").casefold()
    if _contains(
        text,
        ("급락", "붕괴", "직격탄", "휘청", "밀려", "매도세", "폭락", "최저"),
    ):
        return "주의"
    positive = sum(keyword.casefold() in text for keyword in POSITIVE_KEYWORDS)
    caution = sum(keyword.casefold() in text for keyword in CAUTION_KEYWORDS)
    if positive > caution:
        return "기회"
    if caution > positive:
        return "주의"
    return "확인"


def _clean_text(value: object, limit: int) -> Optional[str]:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def _display_title(value: object) -> Optional[str]:
    title = re.sub(r"\s+", " ", str(value or "")).strip()
    title = re.sub(r"^(?:\[[^\]]{1,24}\]\s*)+", "", title)
    title = re.sub(r"\s*\[[^\]]{1,24}\]\s*$", "", title)
    title = re.sub(r"\s*\((?:종합(?:\d+보)?|상보|보유)\)\s*$", "", title)
    return _clean_text(title, 240)


def _normalized_title(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").casefold())


def _canonical_news_text(value: object) -> str:
    text = str(value or "").casefold()
    replacements = (
        (r"k[- ]?뷰티|화장품", " 화장품 "),
        (r"삼전닉스|삼성전자|(?:sk)?하이닉스", " 반도체 "),
        (r"소비자물가지수|소비자물가", " cpi "),
        (r"연방공개시장위원회", " fomc "),
        (r"기준\s*금리|금리\s*(?:동결|인상|인하)", " 금리 "),
        (r"뉴욕 증시", " 뉴욕증시 "),
        (r"(?:미국|美)\s*증시", " 뉴욕증시 "),
        (r"(?:중국|中)\s*증시", " 중국증시 "),
        (r"(?:장기\s*국채|장기채|국채)\s*금리", " 국채금리 "),
        (r"채권\s*발작", " 국채금리 급등 "),
        (r"오픈\s*ai|openai", " openai "),
        (r"상장(?:기업|한다는|한다|예정|추진|계획)", " 상장 "),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return re.sub(r"\s+", " ", text).strip()


def _meaningful_news_tokens(value: object) -> set[str]:
    text = _canonical_news_text(value)
    tokens = set(re.findall(r"\d+(?:\.\d+)?%?|[a-z]{2,}|[가-힣]{2,}", text))
    stopwords = {
        "속보", "종합", "단독", "기자", "관련", "대한", "통해", "가운데", "전망",
        "소식", "시장", "올해", "이번", "최근", "오늘", "어제",
    }
    return {token for token in tokens if token not in stopwords}


def _summary_matches_title(title: object, summary: object) -> bool:
    title_tokens = _meaningful_news_tokens(title)
    summary_tokens = _meaningful_news_tokens(summary)
    if not title_tokens or not summary_tokens:
        return False
    shared = {
        title_token
        for title_token in title_tokens
        if any(
            title_token == summary_token
            or (len(title_token) >= 3 and title_token in summary_token)
            or (len(summary_token) >= 3 and summary_token in title_token)
            for summary_token in summary_tokens
        )
    }
    return len(shared) >= 2 or any(len(token) >= 3 or token[0].isdigit() for token in shared)


def _story_context(item: NewsItem) -> str:
    matching_summary = (
        _clean_news_summary_text(item.summary)
        if _summary_matches_title(item.title, item.summary)
        else ""
    )
    return _canonical_news_text(f"{item.title or ''} {matching_summary or ''}")


def _titles_describe_same_story(left: NewsItem, right: NewsItem) -> bool:
    left_context = _story_context(left)
    right_context = _story_context(right)
    left_title_context = _canonical_news_text(left.title)
    right_title_context = _canonical_news_text(right.title)
    if any(
        re.search(rf"(?:^|\s){topic}(?:\s|$)", left_title_context)
        and re.search(rf"(?:^|\s){topic}(?:\s|$)", right_title_context)
        for topic in ("cpi", "fomc", "pce")
    ):
        return True
    # Similarity uses headlines rather than the generated newsletter copy. The
    # latter intentionally repeats terms such as "수급" or "금리" and would
    # otherwise merge unrelated stories that merely share an investor takeaway.
    left_tokens = _meaningful_news_tokens(left.title)
    right_tokens = _meaningful_news_tokens(right.title)
    if not left_tokens or not right_tokens:
        return _normalized_title(left.title) == _normalized_title(right.title)
    smaller, larger = (
        (left_tokens, right_tokens)
        if len(left_tokens) <= len(right_tokens)
        else (right_tokens, left_tokens)
    )
    shared = {
        token
        for token in smaller
        if any(
            token == candidate
            or (len(token) >= 3 and token in candidate)
            or (len(candidate) >= 3 and candidate in token)
            for candidate in larger
        )
    }
    semantic_shared = sum(not token[0].isdigit() for token in shared)
    anchors = {
        "코스피", "코스닥", "뉴욕증시", "나스닥", "다우", "s&p", "국채금리",
        "금리", "환율", "원·달러", "유가", "cpi", "fomc", "pce",
    }
    if len(anchors.intersection(shared)) >= 2:
        return True
    story_events = {
        "상장", "실적", "인수", "합병", "수주", "계약", "자사주", "배당",
        "증설", "급등", "급락", "파산", "제재", "판결",
    }
    generic_story_tokens = story_events | anchors | {
        "기업", "시장", "증시", "주가", "오늘", "어제", "최대", "기록",
        "확대", "축소", "상승", "하락", "전망", "소식", "첫날",
    }
    shared_entities = {
        token
        for token in shared
        if len(token) >= 4
        and not token[0].isdigit()
        and token not in generic_story_tokens
    }
    if shared_entities and story_events.intersection(shared):
        return True
    left_macro_tokens = _meaningful_news_tokens(left_context)
    right_macro_tokens = _meaningful_news_tokens(right_context)
    left_has_rate = bool({"금리", "국채금리"}.intersection(left_macro_tokens))
    right_has_rate = bool({"금리", "국채금리"}.intersection(right_macro_tokens))
    left_has_kospi = bool(re.search(r"코스피(?:지수)?", left_context))
    right_has_kospi = bool(re.search(r"코스피(?:지수)?", right_context))
    left_has_semiconductor = "반도체" in left_macro_tokens
    right_has_semiconductor = "반도체" in right_macro_tokens
    downside_markers = (
        "급락", "하락", "출렁", "휘청", "사이드카", "변동성", "쇼크", "직격탄", "삭풍",
    )
    left_is_downside = _contains(left_context, downside_markers)
    right_is_downside = _contains(right_context, downside_markers)
    if (
        left_has_kospi
        and right_has_kospi
        and left_has_semiconductor
        and right_has_semiconductor
        and left_is_downside
        and right_is_downside
    ):
        return True
    large_drop_pattern = r"(?:3(?:\.0)?|[4-9]|\d{2,})(?:\.\d+)?\s*%"
    left_has_large_drop = bool(re.search(large_drop_pattern, left_context))
    right_has_large_drop = bool(re.search(large_drop_pattern, right_context))
    if (
        left_has_kospi
        and right_has_kospi
        and left_is_downside
        and right_is_downside
        and (
            (
                left_has_rate
                and (
                    _contains(right_context, ("미국발", "미 금리"))
                    or right_has_large_drop
                )
            )
            or (
                right_has_rate
                and (
                    _contains(left_context, ("미국발", "미 금리"))
                    or left_has_large_drop
                )
            )
        )
    ):
        return True
    if (
        left_has_kospi
        and right_has_kospi
        and left_has_rate
        and right_has_rate
        and _contains(left_context, downside_markers + ("아래", "붕괴"))
        and _contains(right_context, downside_markers + ("아래", "붕괴"))
    ):
        return True
    return len(shared) >= 3 and semantic_shared >= 2 and len(shared) / len(smaller) >= 0.55


def _story_quality_score(item: NewsItem) -> tuple[int, int, tuple[int, float, int]]:
    summary = _clean_news_summary_text(item.summary)
    aligned = int(_summary_matches_title(item.title, summary))
    complete = int(bool(re.search(r"[.!?]", summary)) and not summary.endswith(("…", "...")))
    useful_length = min(len(summary), 180)
    return aligned * 3 + complete * 2, useful_length, _relevance_score(item)


def _deduplicate_stories(rows: Iterable[NewsItem]) -> list[NewsItem]:
    """Keep the strongest article for each story across every category."""

    selected: list[NewsItem] = []
    for row in sorted(rows, key=_story_quality_score, reverse=True):
        if any(_titles_describe_same_story(row, existing) for existing in selected):
            continue
        selected.append(row)
    return selected


def _select_diverse_news(rows: list[NewsItem], limit: int) -> list[NewsItem]:
    selected: list[NewsItem] = []
    for row in rows:
        if any(_titles_describe_same_story(row, existing) for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _select_policy_news(rows: list[NewsItem], limit: int) -> list[NewsItem]:
    """Keep one direct real-estate policy announcement when the window contains one."""

    if limit <= 0:
        return []
    selected: list[NewsItem] = []
    real_estate_policy = next(
        (row for row in rows if _is_real_estate_policy_text(row.title)),
        None,
    )
    if real_estate_policy is not None:
        selected.append(real_estate_policy)
    for row in rows:
        if row in selected or any(
            _titles_describe_same_story(row, existing) for existing in selected
        ):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _schedule_news_kind(item: NewsItem) -> str:
    text = f"{item.title or ''} {item.summary or ''}".casefold()
    if _contains(text, IPO_SCHEDULE_KEYWORDS):
        return "ipo"
    if _contains(text, EARNINGS_SCHEDULE_KEYWORDS):
        return "earnings"
    return "event"


def _select_schedule_news(rows: list[NewsItem], limit: int) -> list[NewsItem]:
    if limit <= 0:
        return []
    selected: list[NewsItem] = []
    for schedule_kind in ("ipo", "earnings"):
        candidate = next(
            (
                row
                for row in rows
                if _schedule_news_kind(row) == schedule_kind
                and not any(_titles_describe_same_story(row, existing) for existing in selected)
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            if len(selected) >= limit:
                return selected
    for row in rows:
        if row in selected or any(_titles_describe_same_story(row, existing) for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _is_briefing_candidate(item: NewsItem, category_key: str) -> bool:
    title = re.sub(r"\s+", " ", str(item.title or "")).casefold().strip()
    if not title or _contains(title, NON_INVESTMENT_KEYWORDS):
        return False
    list_fragments = [
        fragment.strip()
        for fragment in re.split(r"[,;/]", title)
        if fragment.strip()
    ]
    if len(list_fragments) >= 3 and not _contains(
        title,
        (
            "상승", "하락", "급등", "급락", "실적", "매출", "영업이익", "순이익",
            "수주", "계약", "인수", "합병", "투자", "발표", "공개", "전망", "%",
            "금리", "환율", "유가", "정책", "규제", "증시", "주가",
        ),
    ):
        return False
    if category_key != "other":
        return True
    if _contains(title, LOW_INFORMATION_TITLE_KEYWORDS):
        return False
    if not _summary_matches_title(item.title, item.summary):
        return False
    summary = re.sub(r"\s+", " ", str(item.summary or "")).strip()
    context = f"{title} {summary.casefold()}"
    return len(summary) >= 40 and _contains(context, OTHER_INVESTMENT_KEYWORDS)


def _friendly_sentence(value: object) -> Optional[str]:
    sentence = re.sub(r"\s+", " ", str(value or "")).strip()
    sentence = sentence.rstrip(".!? ")
    if not sentence:
        return None
    if re.search(r"(?:요|세요)$", sentence):
        return f"{sentence}."
    if sentence.endswith("입니다"):
        return f"{_friendly_copula(sentence[:-3])}."
    formal_endings = (
        ("했습니다", "했어요"),
        ("됐습니다", "됐어요"),
        ("있습니다", "있어요"),
        ("없습니다", "없어요"),
        ("합니다", "해요"),
        ("됩니다", "돼요"),
    )
    for ending, friendly_ending in formal_endings:
        if sentence.endswith(ending):
            return f"{sentence[: -len(ending)]}{friendly_ending}."
    conversational_endings = (
        ("했다", "했어요"),
        ("됐다", "됐어요"),
        ("나왔다", "나왔어요"),
        ("밝혔다", "밝혔어요"),
        ("냈다", "냈어요"),
        ("렀다", "렀어요"),
        ("랐다", "랐어요"),
        ("렸다", "렸어요"),
        ("났다", "났어요"),
        ("졌다", "졌어요"),
        ("였다", "였어요"),
        ("었다", "었어요"),
        ("았다", "았어요"),
    )
    for ending, friendly_ending in conversational_endings:
        if sentence.endswith(ending):
            return f"{sentence[: -len(ending)]}{friendly_ending}."
    for noun in (
        "관심사", "수치", "결과", "계획", "예정", "전망", "변수", "소식", "상태", "모습", "상황",
    ):
        if sentence.endswith(f"{noun}다"):
            return f"{sentence[:-1]}예요."
    if sentence.endswith("습니다"):
        return f"{sentence[:-3]}다고 해요."
    if sentence.endswith("이다"):
        return f"{_friendly_copula(sentence[:-2])}."
    if sentence.endswith("다"):
        return f"{sentence}고 해요."
    return None


def _friendly_copula(stem: str) -> str:
    """Attach 예요/이에요 with the right Korean final-consonant form."""

    normalized = stem.rstrip()
    if not normalized:
        return "이에요"
    last = normalized[-1]
    if "가" <= last <= "힣":
        has_final_consonant = (ord(last) - ord("가")) % 28 != 0
        return f"{normalized}{'이에요' if has_final_consonant else '예요'}"
    return f"{normalized}이에요"


def _quoted_friendly_summary(value: object, limit: int) -> Optional[str]:
    raw_text = re.sub(r"\s+", " ", str(value or "")).strip()
    source_is_clipped = bool(re.search(r"(?:\.{3,}|…)$", raw_text))
    text = raw_text.strip(" .!?·,…")
    if not text:
        return None
    prefix = "‘"
    suffix = "’"
    available = max(12, limit - len(prefix) - len("’이라고 전해졌어요."))
    excerpt = text[:available].rstrip()
    if len(text) > available or source_is_clipped:
        natural_endings = tuple(
            re.finditer(
                r"(?:확정|원천차단|변수|부각|증가|감소|상승|하락|급등|급락|개선|악화|"
                r"확대|축소|회복|돌파|기록|마감|동결|인상|인하|완화|우려|기대|"
                r"행진|치솟으며|치솟아|뛰충|이끈)(?=\s|$|[,.!·])",
                excerpt,
            )
        )
        natural_end = next(
            (match.end() for match in reversed(natural_endings) if match.end() >= 28),
            None,
        )
        excerpt = (
            excerpt[:natural_end]
            if natural_end is not None
            else excerpt.rsplit(" ", 1)[0]
        ).rstrip(" ,·…'‘’\"") or excerpt
        excerpt = re.sub(r"치솟(?:으며|아)$", "치솟은 흐름", excerpt)
        excerpt = re.sub(r"뛰충$", "뛰충 뛴 흐름", excerpt)
        excerpt = re.sub(r"이끈$", "이끈 흐름", excerpt)
    excerpt = excerpt.strip("‘’'\" ")
    excerpt = excerpt.rstrip(" ,·…")
    excerpt = _strip_dangling_korean_particle(excerpt)
    if not excerpt or _unsafe_quoted_excerpt(excerpt):
        return None
    quote_particle = _korean_quote_particle(excerpt)
    return f"{prefix}{excerpt}{suffix}{quote_particle} 전해졌어요."


def _korean_quote_particle(value: str) -> str:
    """Return 라고/이라고 for a quoted Korean noun fragment."""

    normalized = str(value or "").rstrip()
    if not normalized:
        return "이라고"
    if _is_incomplete_news_fragment(normalized):
        return "라고"
    last = normalized[-1]
    if "가" <= last <= "힣":
        return "이라고" if (ord(last) - ord("가")) % 28 else "라고"
    return "라고" if last.isdigit() or last in "%)]" else "이라고"


def _is_incomplete_news_fragment(value: object) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).rstrip(" .!?·,…")
    return bool(
        re.search(
            r"(?:것으로|것이며|하며|하면서|되며|되면서|이며|이어서|거나|지만|는데|[가-힣]{2,}며|[가-힣]{2,}면서|및|또는|와|과|으로)$",
            text,
        )
    )


def _hangul_has_final_consonant(value: str) -> Optional[bool]:
    if not value or not ("가" <= value[-1] <= "힣"):
        return None
    return (ord(value[-1]) - ord("가")) % 28 != 0


def _strip_dangling_korean_particle(value: str) -> str:
    """Remove a final subject/object particle only when its form fits the stem."""

    text = str(value or "").rstrip()
    match = re.search(r"(?P<stem>[가-힣]{2,})(?P<particle>이|가|은|는|을|를|와|과)$", text)
    if not match or not text[: match.start()].strip():
        return text
    stem = match.group("stem")
    particle = match.group("particle")
    has_final = _hangul_has_final_consonant(stem)
    expected_final = {
        "이": True,
        "가": False,
        "은": True,
        "는": False,
        "을": True,
        "를": False,
        "과": True,
        "와": False,
    }[particle]
    if has_final is expected_final:
        return f"{text[: match.start()]}{stem}".rstrip()
    return text


def _unsafe_quoted_excerpt(value: str) -> bool:
    text = str(value or "").strip()
    if _is_incomplete_news_fragment(text):
        return True
    last_token = text.rsplit(" ", 1)[-1]
    if "/" in last_token:
        return True
    quote_pairs = (("‘", "’"), ("“", "”"))
    if any(text.count(opening) != text.count(closing) for opening, closing in quote_pairs):
        return True
    if text.count('"') % 2 or text.count("'") % 2:
        return True
    return False


def _clean_news_summary_text(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^\([^)]{1,40}=연합뉴스\)\s*", "", text)
    text = re.sub(r"^[^=]{0,45}(?:기자|특파원)\s*=\s*", "", text)
    text = re.sub(r"^[^\]]{0,45}(?:기자|특파원)\]\s*", "", text)
    text = re.sub(
        r"^이 기사는 .{0,80}?(?:선공개|게재|출고)\s*(?:되었습니다|됐습니다)\.?\s*",
        "",
        text,
    )
    text = re.sub(
        r"\s*\[[^\]]{0,60}(?:기자|특파원)[^\]]{0,20}\].*$",
        "",
        text,
    )
    text = re.sub(
        r"\s+[\uac00-\ud7a3]{2,4}(?:\s+[\uac00-\ud7a3]{2,4}){0,2}\s+(?:기자|특파원)\s*=.*$",
        "",
        text,
    )
    if _contains(
        text.casefold(),
        (
            "퇴근길머니",
            "기자와 함께",
            "어서오십쇼",
            "어서오세요",
            "시황부터 정리",
            "돈의 흐름을 짚어드립니다",
        ),
    ):
        return ""
    return text.strip()


def _title_based_context(
    item: NewsItem,
    category: MorningBriefingCategory,
) -> Optional[str]:
    """Create a factual fallback when a feed summary is noisy or mismatched."""

    title = _canonical_news_text(item.title)
    if category.key == "market" and "코스피" in title and _contains(
        title,
        ("급락", "하락", "출렁", "휘청", "삭풍"),
    ):
        percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", title)
        magnitude = f" {percent_match.group(1)}%" if percent_match else ""
        return f"코스피가{magnitude} 급락하며 반도체 대형주를 중심으로 시장 변동성이 커졌어요."
    if category.key == "policy" and _contains(title, ("fed", "연준")) and _contains(
        title,
        ("물가", "긴축", "금리인상"),
    ):
        return "연준 의사록에서 물가가 잡히지 않으면 추가 긴축이 필요할 수 있다는 의견이 나왔어요."
    if category.key == "market" and _contains(title, ("국민연금", "연기금")) and _contains(
        title,
        ("매도", "매수", "유예", "수급"),
    ):
        return "국민연금이 시장 변동성을 이유로 국내 주식 매도를 유예했어요."
    if category.key == "money" and "단기채" in title and _contains(
        title,
        ("금리", "채권"),
    ):
        return "글로벌 장기 국채 금리가 급등한 가운데 변동성이 상대적으로 낮은 단기채의 매력이 남아 있다는 분석이 나왔어요."
    if category.key == "invest" and "etf" in title:
        return "미국 지수 추종 ETF와 반도체·채권 혼합 상품으로 투자 자금이 몰렸어요."
    if category.key == "industry" and _contains(title, ("반도체", "조선")) and _contains(
        title,
        ("실적", "전망", "쾌청"),
    ):
        return "3분기 실적 전망에서 반도체·자동차·조선 업종의 호조 기대가 커졌어요."
    return None


def _friendly_summary(value: object, limit: int = MORNING_BRIEFING_CONTEXT_LIMIT) -> Optional[str]:
    text = _clean_news_summary_text(value)
    if not text:
        return None
    if _is_incomplete_news_fragment(text):
        return None
    if re.search(r"(?:\.{3,}|…)$", text) and not re.search(r"[.!?]\s+", text.rstrip(".…")):
        return None
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    selected: list[str] = []
    for raw_sentence in raw_sentences:
        friendly = _friendly_sentence(raw_sentence)
        if friendly is None:
            if not selected:
                return _quoted_friendly_summary(raw_sentence, limit)
            break
        candidate = " ".join([*selected, friendly]).strip()
        if len(candidate) > limit:
            if selected:
                break
            return _quoted_friendly_summary(raw_sentence, limit)
        selected.append(friendly)
        if len(candidate) >= min(68, limit):
            break
    return " ".join(selected).strip() or _quoted_friendly_summary(text, limit)


def _investment_takeaway(item: NewsItem, category: MorningBriefingCategory) -> str:
    title = _canonical_news_text(item.title)
    for keywords, takeaway in CATEGORY_TAKEAWAY_RULES.get(category.key, ()):
        if _contains(title, keywords):
            return takeaway
    return category.why_it_matters


def _compose_briefing_summary(context: object, takeaway: object) -> str:
    context_sentence = re.sub(r"\s+", " ", str(context or "")).strip()
    takeaway_sentence = re.sub(r"\s+", " ", str(takeaway or "")).strip()
    if not context_sentence:
        return takeaway_sentence
    if not takeaway_sentence:
        return context_sentence
    canonical_context = _canonical_news_text(context_sentence)
    canonical_takeaway = _canonical_news_text(takeaway_sentence)
    if canonical_context == canonical_takeaway or canonical_takeaway in canonical_context:
        return context_sentence
    combined = f"{context_sentence} {takeaway_sentence}"
    return combined[:MORNING_BRIEFING_SUMMARY_LIMIT].rstrip()


def _briefing_summary(item: NewsItem, category: MorningBriefingCategory) -> str:
    context: Optional[str] = None
    if _summary_matches_title(item.title, item.summary):
        context = _friendly_summary(item.summary)
        if context is None:
            cleaned_summary = _clean_news_summary_text(item.summary)
            is_short_clipped_summary = bool(
                re.search(r"(?:\.{3,}|…)$", cleaned_summary)
                and len(cleaned_summary.rstrip("…. ")) < 48
            )
            if not is_short_clipped_summary:
                context = _quoted_friendly_summary(
                    cleaned_summary,
                    MORNING_BRIEFING_CONTEXT_LIMIT,
                )
    if context and context.startswith("‘") and context.endswith("이라고 전해졌어요."):
        context = _title_based_context(item, category) or context
    if context is None:
        # Broken snippets (dangling particles, slash-ended fragments or
        # unmatched quotes) are less useful than a safe, complete headline.
        context = _title_based_context(item, category) or _quoted_friendly_summary(
            _display_title(item.title), MORNING_BRIEFING_CONTEXT_LIMIT
        )
    return _compose_briefing_summary(context, _investment_takeaway(item, category))


def _published_at_kst(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _relevance_score(item: NewsItem) -> tuple[int, float, int]:
    text = str(item.title or "").casefold()
    impact = sum(keyword.casefold() in text for keyword in IMPACT_KEYWORDS)
    status_weight = 1 if morning_news_status(item) != "확인" else 0
    source_weight = 1 if item.source_category in {"breaking", "market", "global"} else 0
    published_at = _published_at_kst(item.published_at)
    published_timestamp = published_at.timestamp() if published_at is not None else 0.0
    return impact * 3 + status_weight + source_weight, published_timestamp, int(item.id or 0)


def _impact_score(item: NewsItem) -> tuple[int, float, int]:
    """Rank stories by investor impact, not headline recency alone."""

    base, published_timestamp, item_id = _relevance_score(item)
    context = _story_context(item)
    magnitude = 0
    for raw_value in re.findall(r"(?<!\d)(\d+(?:\.\d+)?)%", context):
        try:
            if float(raw_value) >= 3:
                magnitude = 3
                break
        except ValueError:
            continue
    systemic = min(
        4,
        _keyword_hits(
            context,
            (
                "코스피", "코스닥", "나스닥", "뉴욕증시", "국채금리", "환율",
                "cpi", "fomc", "유가", "외국인", "정책", "규제", "부동산 대책",
            ),
        ),
    )
    summary_quality = int(_summary_matches_title(item.title, item.summary))
    return base + magnitude + systemic + summary_quality, published_timestamp, item_id


def _calendar_impact_score(
    event: InvestorScheduleEvent,
    publication_date: date,
) -> tuple[int, float, int]:
    days_until = max(0, (event.starts_on - publication_date).days)
    today_weight = 5 if _schedule_event_is_today(event, publication_date) else 1
    kind_weight = 1 if event.kind in {"ipo", "earnings"} else 0
    return today_weight + kind_weight, float(-days_until), 0


def _allocate_briefing_items(
    drafts: list[dict[str, object]],
    *,
    total_limit: int,
) -> list[dict[str, object]]:
    """Give every non-empty category one item, then award high-impact extras."""

    if total_limit <= 0:
        return []
    selected_by_key: dict[str, list[dict[str, object]]] = {}
    for draft in drafts[:total_limit]:
        candidates = list(draft.get("_candidates") or [])
        if candidates:
            selected_by_key[str(draft["key"])] = [candidates[0]]

    remaining = total_limit - sum(len(items) for items in selected_by_key.values())
    extras: list[tuple[tuple[int, float, int], int, dict[str, object]]] = []
    for order, draft in enumerate(drafts):
        candidates = list(draft.get("_candidates") or [])
        for candidate in candidates[1:]:
            extras.append((candidate["score"], -order, candidate))
    for _score, _order, candidate in sorted(
        extras,
        key=lambda entry: (entry[0], entry[1]),
        reverse=True,
    ):
        if remaining <= 0:
            break
        key = str(candidate["category_key"])
        selected_by_key.setdefault(key, []).append(candidate)
        remaining -= 1

    allocated: list[dict[str, object]] = []
    for draft in drafts:
        key = str(draft["key"])
        selected = selected_by_key.get(key) or []
        if not selected:
            continue
        copy = {field: value for field, value in draft.items() if not field.startswith("_")}
        copy["_selected"] = selected
        allocated.append(copy)
    return allocated


def _select_briefing_highlights(
    entries: Iterable[dict[str, object]],
    *,
    limit: int,
) -> list[dict[str, object]]:
    """Prefer different sections and never let the agenda occupy two slots."""

    ranked = sorted(entries, key=lambda entry: entry["score"], reverse=True)
    selected: list[dict[str, object]] = []
    selected_categories: set[str] = set()

    def can_add(entry: dict[str, object], *, require_new_category: bool) -> bool:
        key = str(entry["category_key"])
        if key == "schedule" and any(
            existing["category_key"] == "schedule" for existing in selected
        ):
            return False
        if require_new_category and key in selected_categories:
            return False
        return True

    for require_new_category in (True, False):
        for entry in ranked:
            if entry in selected or not can_add(
                entry,
                require_new_category=require_new_category,
            ):
                continue
            selected.append(entry)
            selected_categories.add(str(entry["category_key"]))
            if len(selected) >= limit:
                return [dict(candidate["payload"]) for candidate in selected]
    return [dict(candidate["payload"]) for candidate in selected]


def _item_payload(item: NewsItem, category: MorningBriefingCategory) -> dict[str, object]:
    takeaway = _investment_takeaway(item, category)
    return {
        "id": item.id,
        "title": _display_title(item.title) or "제목 확인 중",
        "summary": _briefing_summary(item, category),
        "detail_url": preferred_news_url(item.source, item.external_id, item.detail_url),
        "published_at": _published_at_kst(item.published_at),
        "status": morning_news_status(item),
        "why_it_matters": takeaway,
        "schedule_kind": _schedule_news_kind(item) if category.key == "schedule" else None,
    }


def _schedule_item_payload(event: InvestorScheduleEvent) -> dict[str, object]:
    payload = event.as_briefing_item()
    payload["summary"] = _compose_briefing_summary(
        payload.get("summary"),
        payload.get("why_it_matters"),
    )
    return payload


def _schedule_event_is_today(event: InvestorScheduleEvent, publication_date: date) -> bool:
    return event.starts_on <= publication_date <= event.ends_on


def _select_calendar_events(
    events: Iterable[InvestorScheduleEvent],
    publication_date: date,
    limit: int,
) -> list[InvestorScheduleEvent]:
    upcoming = [event for event in events if event.ends_on >= publication_date]
    today = [event for event in upcoming if _schedule_event_is_today(event, publication_date)]
    future = [event for event in upcoming if event.starts_on > publication_date]
    selected: list[InvestorScheduleEvent] = []

    # Fill today's agenda before upcoming dates, while keeping IPO and earnings
    # represented when both are available on the same date tier.
    for pool in (today, future):
        for schedule_kind in ("ipo", "earnings"):
            candidate = next(
                (
                    event
                    for event in pool
                    if event.kind == schedule_kind and event not in selected
                ),
                None,
            )
            if candidate is not None:
                selected.append(candidate)
                if len(selected) >= limit:
                    return selected
        for event in pool:
            if event in selected:
                continue
            selected.append(event)
            if len(selected) >= limit:
                return selected
    return selected


def _schedule_category_copy(
    events: Iterable[InvestorScheduleEvent],
    publication_date: date,
    *,
    includes_unstructured_news: bool,
) -> tuple[str, str]:
    selected = list(events)
    has_today = any(
        _schedule_event_is_today(event, publication_date) for event in selected
    )
    has_future = any(event.starts_on > publication_date for event in selected)
    if includes_unstructured_news:
        return (
            "주요 일정",
            "IPO 청약·실적 발표·경제지표처럼 놓치지 말아야 할 일정",
        )
    if has_today and has_future:
        return (
            "오늘·다가오는 주요 일정",
            "오늘과 앞으로 예정된 IPO 청약·실적 발표·경제지표",
        )
    if has_future:
        return (
            "다가오는 주요 일정",
            "앞으로 예정된 IPO 청약·실적 발표·경제지표",
        )
    return (
        "오늘 체크할 일정",
        "IPO 청약·실적 발표·경제지표처럼 오늘 놓치지 말아야 할 일정",
    )


def build_morning_money_briefing(
    db: Session,
    *,
    now: Optional[datetime] = None,
    items_per_category: int = MORNING_BRIEFING_ITEMS_PER_CATEGORY,
    schedule_events: Optional[Iterable[InvestorScheduleEvent]] = None,
    news_rows: Optional[Iterable[NewsItem]] = None,
) -> dict[str, object]:
    current = _kst_datetime(now)
    edition = money_briefing_edition(current)
    window_start = edition.window_start
    window_end = edition.window_end
    publication_date = edition.publication_date
    # Resolve the external KIND calendar before the first ORM query. SQLAlchemy
    # checks out a connection lazily, so this order avoids holding a database
    # connection while the upstream calendar request is in flight.
    calendar_events = list(
        upcoming_investor_events(publication_date)
        if schedule_events is None
        else schedule_events
    )
    rows = (
        latest_news_items(
            db,
            limit=MORNING_BRIEFING_QUERY_LIMIT,
            from_at=window_start.replace(tzinfo=None),
            to_at=(window_end - timedelta(microseconds=1)).replace(tzinfo=None),
        )
        if news_rows is None
        else list(news_rows)
    )
    rows = [
        row
        for row in rows
        if (published_at := _published_at_kst(row.published_at)) is not None
        and window_start <= published_at < window_end
    ]

    unique_rows: list[NewsItem] = []
    seen_titles: set[str] = set()
    for row in rows:
        title_key = _normalized_title(row.title)
        if not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        unique_rows.append(row)

    grouped: dict[str, list[NewsItem]] = {
        **{category.key: [] for category in CATEGORIES},
        "other": [],
    }
    for row in _deduplicate_stories(unique_rows):
        category_key = classify_morning_news(row)
        if not _is_briefing_candidate(row, category_key):
            continue
        grouped.setdefault(category_key, []).append(row)

    drafts: list[dict[str, object]] = []
    category_limit = max(1, min(int(items_per_category), 10))
    for category in CATEGORIES:
        category_rows = sorted(grouped[category.key], key=_impact_score, reverse=True)
        if category.key == "schedule":
            selected_calendar_events = _select_calendar_events(
                calendar_events,
                publication_date,
                category_limit,
            )

            covered_kinds = {event.kind for event in selected_calendar_events}
            news_candidates = [
                row
                for row in category_rows
                if _schedule_news_kind(row) not in covered_kinds
            ]
            selected_news = _select_schedule_news(
                news_candidates,
                category_limit - len(selected_calendar_events),
            )
            schedule_candidates = [
                {
                    "item": _schedule_item_payload(event),
                    "row": None,
                    "event": event,
                    "score": _calendar_impact_score(event, publication_date),
                    "category_key": category.key,
                }
                for event in selected_calendar_events
            ] + [
                {
                    "item": _item_payload(row, category),
                    "row": row,
                    "event": None,
                    "score": _impact_score(row),
                    "category_key": category.key,
                }
                for row in selected_news
            ]
            if not schedule_candidates:
                continue
            schedule_label, schedule_description = _schedule_category_copy(
                selected_calendar_events,
                publication_date,
                includes_unstructured_news=bool(selected_news),
            )
            drafts.append(
                {
                    "key": category.key,
                    "label": schedule_label,
                    "icon": category.icon,
                    "description": schedule_description,
                    "count": len(category_rows) + len(calendar_events),
                    "_candidates": schedule_candidates,
                }
            )
            continue
        if not category_rows:
            continue
        selected = (
            _select_policy_news(category_rows, category_limit)
            if category.key == "real_estate"
            else _select_diverse_news(category_rows, category_limit)
        )
        drafts.append(
            {
                "key": category.key,
                "label": category.label,
                "icon": category.icon,
                "description": category.description,
                "count": len(category_rows),
                "_candidates": [
                    {
                        "item": _item_payload(row, category),
                        "row": row,
                        "event": None,
                        "score": _impact_score(row),
                        "category_key": category.key,
                    }
                    for row in selected
                ],
            }
        )

    allocated = _allocate_briefing_items(
        drafts,
        total_limit=MORNING_BRIEFING_TOTAL_ITEM_LIMIT,
    )
    categories: list[dict[str, object]] = []
    highlight_entries: list[dict[str, object]] = []
    for draft in allocated:
        selected_entries = list(draft.pop("_selected", []))
        if draft["key"] == "schedule":
            selected_events = [
                entry["event"] for entry in selected_entries if entry.get("event") is not None
            ]
            includes_news = any(entry.get("row") is not None for entry in selected_entries)
            label, description = _schedule_category_copy(
                selected_events,
                publication_date,
                includes_unstructured_news=includes_news,
            )
            draft["label"] = label
            draft["description"] = description

        category_items: list[dict[str, object]] = []
        for entry in selected_entries:
            item = dict(entry["item"])
            category_items.append(item)
            highlight_entries.append(
                {
                    **entry,
                    "payload": {
                        **item,
                        "category_key": draft["key"],
                        "category_label": draft["label"],
                    },
                }
            )
        draft["items"] = category_items
        categories.append(draft)

    # A high-impact item that did not confidently fit the taxonomy may still
    # appear once in the three-line opener, but never as a low-value body section.
    other_category = CATEGORY_LOOKUP["other"]
    for row in sorted(grouped["other"], key=_impact_score, reverse=True):
        score = _impact_score(row)
        if score[0] < 6:
            continue
        item = _item_payload(row, other_category)
        highlight_entries.append(
            {
                "item": item,
                "row": row,
                "event": None,
                "score": score,
                "category_key": "hot",
                "payload": {
                    **item,
                    "category_key": "hot",
                    "category_label": "핫이슈",
                },
            }
        )

    highlights = _select_briefing_highlights(
        highlight_entries,
        limit=MORNING_BRIEFING_HIGHLIGHT_LIMIT,
    )
    selected_count = sum(len(category["items"]) for category in categories)
    opportunity_count = sum(
        item["status"] == "기회"
        for category in categories
        for item in category["items"]
    )
    caution_count = sum(
        item["status"] == "주의"
        for category in categories
        for item in category["items"]
    )
    return {
        "title": "오늘의 돈이 되는 소식",
        "edition": edition.edition,
        "edition_key": edition.edition_key,
        "edition_label": edition.edition_label,
        "publication_date": publication_date,
        "timezone": "Asia/Seoul",
        "window_start": window_start,
        "window_end": window_end,
        "published_at": edition.published_at,
        "next_publication_at": edition.next_publication_at,
        "popup_start": edition.published_at,
        "popup_end": edition.next_publication_at,
        "generated_at": current,
        "total_news_count": len(unique_rows),
        "selected_news_count": selected_count,
        "opportunity_count": opportunity_count,
        "caution_count": caution_count,
        "highlights": highlights,
        "categories": categories,
        "empty_message": (
            None
            if categories
            else "해당 시간대에 수집된 핵심 소식이 아직 없습니다. 뉴스 수집이 완료되면 자동으로 반영됩니다."
        ),
    }


def build_morning_money_briefing_history(
    db: Session,
    *,
    now: Optional[datetime] = None,
    days: int = 7,
    news_rows: Optional[Iterable[NewsItem]] = None,
) -> list[dict[str, object]]:
    """Build every published 06:00, 12:00 and 16:00 edition in a KST date range.

    The content feed treats one completed publication window as one editorial
    item.  A shared seven-day news snapshot is reused for every edition so the
    history endpoint performs one database query rather than one query per
    card.
    """

    current = _kst_datetime(now)
    history_days = max(1, min(int(days), 7))
    publication_times = [
        datetime.combine(
            current.date() - timedelta(days=day_offset),
            publication_time,
            tzinfo=KST,
        )
        for day_offset in range(history_days)
        for publication_time in (
            AFTERNOON_BRIEFING_END,
            MIDDAY_BRIEFING_END,
            MORNING_BRIEFING_END,
        )
    ]
    publication_times = sorted(
        (published_at for published_at in publication_times if published_at <= current),
        reverse=True,
    )
    if not publication_times:
        return []

    editions = [money_briefing_edition(published_at) for published_at in publication_times]
    shared_rows = list(news_rows) if news_rows is not None else latest_news_items(
        db,
        limit=MORNING_BRIEFING_QUERY_LIMIT * history_days * 3,
        from_at=min(edition.window_start for edition in editions).replace(tzinfo=None),
        to_at=(
            max(edition.window_end for edition in editions) - timedelta(microseconds=1)
        ).replace(tzinfo=None),
    )
    dated_rows = [
        (row, published_at)
        for row in shared_rows
        if (published_at := _published_at_kst(row.published_at)) is not None
    ]

    payloads: list[dict[str, object]] = []
    seen_editions: set[str] = set()
    for published_at, edition in zip(publication_times, editions):
        if edition.edition_key in seen_editions:
            continue
        seen_editions.add(edition.edition_key)
        # Match the single-edition endpoint: select only the newest candidate
        # rows inside this publication window before the comparatively costly
        # semantic story de-duplication.  Without this partitioning, a seven-day
        # request repeatedly compared every source article for all 21 editions.
        edition_rows = sorted(
            (
                row
                for row, row_published_at in dated_rows
                if edition.window_start <= row_published_at < edition.window_end
            ),
            key=lambda row: _published_at_kst(row.published_at) or datetime.min.replace(tzinfo=KST),
            reverse=True,
        )[:MORNING_BRIEFING_HISTORY_CANDIDATE_LIMIT]
        payloads.append(
            build_morning_money_briefing(
                db,
                now=published_at,
                schedule_events=[],
                news_rows=edition_rows,
            )
        )
    return payloads
