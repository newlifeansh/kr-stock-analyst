from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import re
from typing import Iterable, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, DisclosureItem, NewsItem, ResearchReport, StockMaster
from app.services.market_rankings import _base_item
from app.services.stock_dashboard import _keyword_score, _round_decimal


KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class EventTemplate:
    key: str
    month: int
    day: int
    hour: int
    minute: int
    category: str
    title: str
    importance: str
    expected_impact: str
    affected_variables: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    watch_points: tuple[str, ...]
    source_name: str
    source_url: str
    keywords: tuple[str, ...]


EVENT_TEMPLATES = (
    EventTemplate(
        "us-eia-oil",
        6,
        24,
        23,
        30,
        "원자재",
        "미국 EIA 주간 원유재고",
        "중요",
        "유가와 정유·화학·항공·해운 비용 민감도를 흔들 수 있음",
        ("WTI", "브렌트유", "정제마진", "원달러"),
        ("정유", "화학", "항공", "해운", "2차전지 소재"),
        (
            "재고 감소가 크면 유가 상승 압력, 항공·화학 비용 부담 가능",
            "재고 증가 또는 수요 둔화 신호는 정유 마진과 에너지주에 부담",
            "중동 리스크 뉴스와 함께 보면 원화·외국인 수급 영향이 커질 수 있음",
        ),
        "U.S. EIA",
        "https://www.eia.gov/petroleum/supply/weekly/",
        ("유가", "원유", "원유재고", "정유", "석유", "중동", "정제마진", "WTI", "브렌트"),
    ),
    EventTemplate(
        "kr-bsi-esi",
        6,
        25,
        6,
        0,
        "한국",
        "한국 BSI·ESI",
        "중요",
        "국내 경기심리와 내수·은행·소비재 밸류에이션 기대를 점검하는 지표",
        ("경기심리", "내수", "금리", "원화"),
        ("은행", "유통", "건설", "자동차", "소비재"),
        (
            "ESI 반등은 내수·금융주 심리 개선 재료",
            "제조업 심리 부진은 반도체·화학·철강 경기 민감주에 부담",
            "한국 금리 기대와 함께 보면 은행/보험주 해석력이 높아짐",
        ),
        "Bank of Korea",
        "https://www.bok.or.kr/eng/stats/statsPublictSchdul/listCldr.do?menuNo=400359",
        ("BSI", "ESI", "경기", "심리", "내수", "제조업", "소비"),
    ),
    EventTemplate(
        "us-pce",
        6,
        25,
        21,
        30,
        "미국",
        "미국 PCE 물가·개인소득/지출",
        "매우 중요",
        "미국 금리 경로, 성장주 할인율, 원달러 환율에 직접 영향",
        ("미국금리", "달러", "원달러", "나스닥", "금"),
        ("반도체", "인터넷", "2차전지", "자동차", "금융"),
        (
            "PCE가 예상보다 높으면 장기금리 상승과 성장주 밸류 부담",
            "소비 둔화가 동반되면 경기민감 대형주에는 혼재 신호",
            "달러 강세가 나오면 외국인 수급과 원화 약세를 같이 확인",
        ),
        "U.S. BEA",
        "https://www.bea.gov/data/personal-consumption-expenditures-price-index",
        ("PCE", "물가", "인플레이션", "금리", "환율", "원달러", "달러 강세", "달러 약세", "연준"),
    ),
    EventTemplate(
        "us-jobless-claims",
        6,
        25,
        21,
        30,
        "미국",
        "미국 주간 신규실업수당청구건수",
        "보통",
        "고용 둔화 여부를 통해 금리 인하 기대와 경기민감주 심리를 확인",
        ("미국고용", "미국금리", "달러"),
        ("반도체", "자동차", "금융", "경기민감"),
        (
            "청구건수 급증은 금리 하락 기대와 경기 둔화 우려가 동시에 발생",
            "견조한 고용은 금리 고착 리스크로 성장주에 부담 가능",
        ),
        "U.S. Department of Labor",
        "https://www.dol.gov/ui/data.pdf",
        ("고용", "실업", "신규실업수당", "금리", "연준", "경기"),
    ),
    EventTemplate(
        "kr-bank-rate",
        6,
        26,
        12,
        0,
        "한국",
        "한국 금융기관 가중평균금리",
        "중요",
        "예금·대출금리, 은행 NIM, 부동산·건설 심리에 영향을 주는 국내 금리 변수",
        ("국내금리", "대출금리", "예금금리", "부동산"),
        ("은행", "보험", "건설", "증권", "리츠"),
        (
            "대출금리 상승은 건설·리츠 부담, 은행 NIM에는 단기 우호",
            "예금금리 하락은 금융주 마진 기대와 가계 소비 심리를 같이 확인",
            "가계부채 뉴스와 결합되면 정책 리스크가 커질 수 있음",
        ),
        "Bank of Korea",
        "https://www.bok.or.kr/eng/stats/statsPublictSchdul/listCldr.do?menuNo=400359",
        ("금리", "대출", "예금", "은행", "보험", "건설", "리츠", "부동산"),
    ),
)


FOCUSED_EVENT_AXES = {
    "미국 EIA 주간 원유재고": ("원유",),
    "미국 PCE 물가·개인소득/지출": ("환율", "금리(고용)"),
    "미국 주간 신규실업수당청구건수": ("금리(고용)",),
}

FOCUSED_TIMELINE_KEYWORDS = {
    "원유": ("원유", "유가", "WTI", "브렌트", "정제마진", "원유재고", "EIA"),
    "환율": ("환율", "원달러", "원/달러", "고환율", "원화", "달러 강세", "달러 약세"),
    "금리(고용)": ("금리", "PCE", "FOMC", "연준", "고용", "실업", "신규실업수당"),
}

FOCUSED_TIMELINE_LEADERS = {
    "원유": ("S-Oil", "SK이노베이션", "대한항공"),
    "환율": ("삼성전자", "SK하이닉스", "현대차"),
    "금리(고용)": ("KB금융", "NAVER", "LG에너지솔루션"),
}


SECTOR_KEYWORDS = {
    "반도체": ("삼성전자", "SK하이닉스", "삼성전기", "한미반도체", "DB하이텍", "리노공업", "HPSP", "이오테크닉스"),
    "인터넷": ("NAVER", "카카오", "크래프톤", "엔씨", "넷마블"),
    "2차전지": ("LG에너지솔루션", "삼성SDI", "포스코퓨처엠", "에코프로", "엘앤에프", "LG화학"),
    "자동차": ("현대차", "기아", "현대모비스", "HL만도", "한국타이어"),
    "금융": ("KB금융", "신한지주", "하나금융", "우리금융", "기업은행", "메리츠금융", "삼성생명", "삼성화재"),
    "은행": ("KB금융", "신한지주", "하나금융", "우리금융", "기업은행", "BNK금융"),
    "보험": ("삼성생명", "삼성화재", "DB손해보험", "현대해상", "한화생명"),
    "증권": ("미래에셋증권", "한국금융지주", "NH투자증권", "키움증권", "삼성증권"),
    "정유": ("SK이노베이션", "S-Oil", "GS", "HD현대"),
    "화학": ("LG화학", "롯데케미칼", "금호석유", "한화솔루션", "SKC"),
    "항공": ("대한항공", "아시아나"),
    "해운": ("HMM", "팬오션", "대한해운"),
    "건설": ("현대건설", "삼성E&A", "대우건설", "GS건설", "DL이앤씨"),
    "리츠": ("리츠",),
    "유통": ("BGF리테일", "이마트", "롯데쇼핑", "호텔신라", "신세계"),
    "소비재": ("KT&G", "LG생활건강", "아모레", "하이트", "오리온", "CJ제일제당"),
    "경기민감": ("POSCO", "현대제철", "대한항공", "HMM", "현대차", "기아", "HD현대중공업"),
    "조선": ("HD현대중공업", "한화오션", "삼성중공업", "HD한국조선해양"),
}

COMPANY_CATEGORY_OVERRIDES = {
    "LG전자": "대형주",
    "현대차": "대형주",
    "기아": "대형주",
    "삼성전자": "반도체",
    "SK하이닉스": "반도체",
    "NAVER": "인터넷",
}


SECTOR_OUTLOOK = {
    "미국 EIA 주간 원유재고": {
        "정유": "재고 감소/유가 상승 시 정제마진 기대, 재고 증가 시 부담",
        "화학": "유가 상승 시 원가 부담, 유가 하락 시 마진 완화",
        "항공": "유가 상승 시 연료비 부담",
        "해운": "연료비와 글로벌 물동량 기대가 동시에 작용",
        "2차전지 소재": "원자재 가격 변동이 소재 마진과 재고평가에 영향",
    },
    "한국 BSI·ESI": {
        "은행": "경기심리 개선 시 대출 성장/건전성 기대",
        "유통": "소비심리 개선 시 매출 기대",
        "건설": "심리 악화 시 부동산·수주 기대 둔화",
        "자동차": "내수와 수출 심리 양쪽을 확인",
        "소비재": "내수 심리와 가격 전가력 확인",
    },
    "미국 PCE 물가·개인소득/지출": {
        "반도체": "금리 상승은 밸류 부담, 소비 견조는 AI/서버 수요 기대",
        "인터넷": "할인율 변화에 민감한 성장주",
        "2차전지": "금리와 달러, 수요 둔화 우려에 민감",
        "자동차": "달러 강세는 수출 환산에 우호, 고금리는 수요 부담",
        "금융": "금리 고착은 보험/은행에 일부 우호이나 경기 둔화는 리스크",
    },
    "미국 주간 신규실업수당청구건수": {
        "반도체": "고용 둔화는 금리 완화 기대와 수요 둔화 우려가 공존",
        "자동차": "미국 소비/할부 수요 신호로 확인",
        "금융": "경기 둔화 시 신용 리스크, 금리 하락 시 채권평가 우호",
        "경기민감": "고용 악화는 글로벌 경기민감주에 부담",
    },
    "한국 금융기관 가중평균금리": {
        "은행": "대출금리/예대마진 확인",
        "보험": "금리 레벨과 운용수익률 기대",
        "건설": "대출금리 상승 시 분양/부동산 심리 부담",
        "증권": "금리 하락은 거래대금과 채권평가에 우호",
        "리츠": "금리 하락 시 배당 매력 회복, 금리 상승 시 부담",
    },
}


SCENARIOS = {
    "미국 EIA 주간 원유재고": (
        {"key": "bull", "label": "재고 감소/유가 상승", "description": "정유·에너지에는 우호, 항공·화학·해운에는 비용 부담"},
        {"key": "bear", "label": "재고 증가/유가 하락", "description": "항공·화학 비용 부담 완화, 정유 마진 기대는 약화"},
    ),
    "한국 BSI·ESI": (
        {"key": "bull", "label": "경기심리 개선", "description": "내수·금융·소비재 심리 개선"},
        {"key": "bear", "label": "경기심리 악화", "description": "경기민감·내수주 실적 기대 둔화"},
    ),
    "미국 PCE 물가·개인소득/지출": (
        {"key": "bull", "label": "PCE 둔화/금리 하락", "description": "성장주 할인율 부담 완화, 달러 강세 압력 완화"},
        {"key": "bear", "label": "PCE 상회/금리 상승", "description": "성장주 밸류 부담, 금융 일부 수혜와 경기 부담 공존"},
    ),
    "미국 주간 신규실업수당청구건수": (
        {"key": "bull", "label": "고용 완만 둔화", "description": "금리 완화 기대가 커지되 경기 침체 우려는 제한"},
        {"key": "bear", "label": "고용 급격 악화", "description": "경기 둔화 우려가 금리 완화 기대를 압도"},
    ),
    "한국 금융기관 가중평균금리": (
        {"key": "bull", "label": "금리 하락/완화", "description": "건설·리츠·증권에 우호, 은행 NIM 기대는 둔화"},
        {"key": "bear", "label": "금리 상승/고착", "description": "은행·보험에는 일부 우호, 건설·리츠에는 부담"},
    ),
}


SECTOR_SCENARIO_BIAS = {
    "미국 EIA 주간 원유재고": {
        "bull": {"정유": 1, "화학": -1, "항공": -1, "해운": -1, "2차전지": -1},
        "bear": {"정유": -1, "화학": 1, "항공": 1, "해운": 1, "2차전지": 1},
    },
    "한국 BSI·ESI": {
        "bull": {"은행": 1, "유통": 1, "건설": 1, "자동차": 1, "소비재": 1},
        "bear": {"은행": -1, "유통": -1, "건설": -1, "자동차": -1, "소비재": -1},
    },
    "미국 PCE 물가·개인소득/지출": {
        "bull": {"반도체": 1, "인터넷": 1, "2차전지": 1, "자동차": 1, "금융": -1},
        "bear": {"반도체": -1, "인터넷": -1, "2차전지": -1, "자동차": -1, "금융": 1, "은행": 1, "보험": 1},
    },
    "미국 주간 신규실업수당청구건수": {
        "bull": {"반도체": 1, "자동차": 1, "금융": 1, "경기민감": 1},
        "bear": {"반도체": -1, "자동차": -1, "금융": -1, "경기민감": -1},
    },
    "한국 금융기관 가중평균금리": {
        "bull": {"은행": -1, "보험": -1, "건설": 1, "증권": 1, "리츠": 1},
        "bear": {"은행": 1, "보험": 1, "건설": -1, "증권": -1, "리츠": -1},
    },
}


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _event_datetime(year: int, template: EventTemplate) -> datetime:
    return datetime.combine(datetime(year, template.month, template.day).date(), time(template.hour, template.minute))


def _event_id(template: EventTemplate, starts_at: datetime) -> str:
    return f"{template.key}-{starts_at.strftime('%Y%m%d%H%M')}"


def _weekly_occurrences_between(
    start: datetime,
    end: datetime,
    *,
    weekday: int,
    hour: int,
    minute: int,
) -> list[datetime]:
    if start > end:
        return []
    cursor = datetime.combine(start.date(), time(hour, minute))
    offset = (weekday - cursor.weekday()) % 7
    cursor += timedelta(days=offset)
    if cursor < start:
        cursor += timedelta(days=7)
    items: list[datetime] = []
    while cursor <= end:
        items.append(cursor)
        cursor += timedelta(days=7)
    return items


def _last_weekday_of_month(year: int, month: int, *, weekday: int, hour: int, minute: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    cursor = datetime(year, month, last_day, hour, minute)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _fixed_occurrences_between(template: EventTemplate, start: datetime, end: datetime) -> list[datetime]:
    years = range(start.year - 1, end.year + 2)
    items = []
    for year in years:
        occurs_at = _event_datetime(year, template)
        if start <= occurs_at <= end:
            items.append(occurs_at)
    items.sort()
    return items


def _scheduled_occurrences_between(template: EventTemplate, start: datetime, end: datetime) -> list[datetime]:
    if template.key == "us-eia-oil":
        return _weekly_occurrences_between(start, end, weekday=2, hour=23, minute=30)
    if template.key == "us-jobless-claims":
        return _weekly_occurrences_between(start, end, weekday=3, hour=21, minute=30)
    if template.key == "us-pce":
        items: list[datetime] = []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            occurs_at = _last_weekday_of_month(year, month, weekday=3, hour=21, minute=30)
            if start <= occurs_at <= end:
                items.append(occurs_at)
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        return items
    return _fixed_occurrences_between(template, start, end)


def _focused_axes_for_text(text: str) -> list[str]:
    axes: list[str] = []
    for axis, keywords in FOCUSED_TIMELINE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            axes.append(axis)
    return axes


def _company_category_for_name(name: str) -> Optional[str]:
    if name in COMPANY_CATEGORY_OVERRIDES:
        return COMPANY_CATEGORY_OVERRIDES[name]
    for sector, names in SECTOR_KEYWORDS.items():
        if name in names:
            if sector in {"반도체", "인터넷"}:
                return sector
            if sector in {"금융", "은행", "보험", "증권"}:
                return "금융"
            if sector in {"자동차", "조선", "항공", "해운", "건설", "리츠", "경기민감"}:
                return "대형주"
            if sector in {"정유", "화학"}:
                return "원자재"
    return None


def _is_matchable_stock_name(name: str) -> bool:
    cleaned = (name or "").strip()
    if not cleaned or cleaned == "리츠":
        return False
    if len(cleaned) >= 3:
        return True
    return cleaned in {"GS"}


def _contains_stock_name(text: str, name: str) -> bool:
    if not text or not name:
        return False
    if re.fullmatch(r"[A-Za-z0-9&.+\- ]+", name):
        pattern = rf"(?<![A-Z0-9]){re.escape(name.upper())}(?![A-Z0-9])"
        return re.search(pattern, text.upper()) is not None
    return name in text


def _stock_name_candidates(db: Session) -> list[str]:
    rows = db.scalars(select(StockMaster.name).where(StockMaster.name.is_not(None)).order_by(func.length(StockMaster.name).desc()))
    seen: set[str] = set()
    names: list[str] = []
    for raw_name in rows:
        name = (raw_name or "").strip()
        if not _is_matchable_stock_name(name) or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _mentioned_stocks_for_text(text: str, stock_candidates: Sequence[str], limit: int = 3) -> list[str]:
    leaders: list[str] = []
    for name in stock_candidates:
        if any(name in leader or leader in name for leader in leaders):
            continue
        if _contains_stock_name(text, name) and name not in leaders:
            leaders.append(name)
        if len(leaders) >= limit:
            break
    return leaders


def _impact_for_text(text: str) -> str:
    score = _keyword_score(text)
    positive_hints = (
        "기대",
        "반등",
        "회복",
        "확대",
        "상승",
        "승인",
        "급등",
        "강화",
        "유지",
        "매수",
        "↑",
    )
    negative_hints = (
        "우려",
        "압박",
        "급락",
        "부담",
        "리스크",
        "실패",
        "고갈",
        "소진",
        "악세",
        "약화",
        "축소",
        "매도",
        "↓",
    )
    score += sum(1 for word in positive_hints if word in text)
    score -= sum(1 for word in negative_hints if word in text)

    axes = _focused_axes_for_text(text)
    if "환율" in axes:
        if any(word in text for word in ("환율 상승", "고환율", "원화 약세", "달러 강세", "1500원")):
            score -= 2
        if any(word in text for word in ("환율 하락", "원화 강세", "달러 약세", "환율 안정")):
            score += 2
    if "금리(고용)" in axes:
        if any(word in text for word in ("금리 인상", "물가 상회", "고용 견조", "금리 고착")):
            score -= 2
        if any(word in text for word in ("금리 인하", "물가 둔화", "고용 둔화", "완화 기대")):
            score += 2
    if "원유" in axes:
        if any(word in text for word in ("유가 상승", "원유 상승", "재고 감소", "중동 리스크")):
            score -= 1
        if any(word in text for word in ("유가 하락", "원유 하락", "재고 증가")):
            score += 1

    if score > 0:
        return "호재"
    if score < 0:
        return "악재"
    return "악재" if axes else "호재"


def _category_for_text(text: str, hinted_names: Optional[Iterable[str]] = None) -> str:
    for name in hinted_names or ():
        category = _company_category_for_name(name)
        if category:
            return category
    if any(word in text for word in ("금리", "FOMC", "연준", "물가", "PCE", "환율", "원달러", "고환율", "원화")):
        return "매크로"
    if any(word in text for word in ("유가", "원유", "금", "구리", "원자재", "중동")):
        return "원자재"
    if any(word in text for word in ("반도체", "HBM", "메모리", "삼성전자", "SK하이닉스", "한미반도체")):
        return "반도체"
    if any(word in text for word in ("은행", "보험", "증권", "금융")):
        return "금융"
    if any(word in text for word in ("자동차", "조선", "항공", "해운", "건설", "리츠")):
        return "대형주"
    return "시장"


TIMELINE_LEADER_STOCKS = {
    "매크로": ("삼성전자", "SK하이닉스", "NAVER"),
    "원자재": ("SK이노베이션", "S-Oil", "대한항공"),
    "반도체": ("삼성전자", "SK하이닉스", "한미반도체"),
    "금융": ("KB금융", "신한지주", "삼성생명"),
    "대형주": ("현대차", "한화오션", "HD현대중공업"),
    "시장": ("삼성전자", "현대차", "NAVER"),
}


def _leader_stocks_for_text(
    text: str,
    category: str,
    hinted_names: Optional[Iterable[str]] = None,
    stock_candidates: Optional[Sequence[str]] = None,
) -> list[str]:
    leaders: list[str] = []
    hinted = [cleaned for cleaned in ((name or "").strip() for name in hinted_names or ()) if _is_matchable_stock_name(cleaned)]

    for cleaned in hinted:
        if cleaned not in leaders:
            leaders.append(cleaned)
        if len(leaders) >= 3:
            return leaders

    if stock_candidates and not hinted:
        for name in _mentioned_stocks_for_text(text, stock_candidates, limit=3):
            if name not in leaders:
                leaders.append(name)
        if len(leaders) >= 3:
            return leaders

    for axis in _focused_axes_for_text(text):
        for name in FOCUSED_TIMELINE_LEADERS.get(axis, ()):
            if name not in leaders:
                leaders.append(name)
            if len(leaders) >= 3:
                return leaders

    for name in TIMELINE_LEADER_STOCKS.get(category, TIMELINE_LEADER_STOCKS["시장"]):
        if name not in leaders:
            leaders.append(name)
    return leaders[:3]


def _timeline_item(
    prefix: str,
    idx: int,
    title: str,
    source: str,
    url: Optional[str],
    published_at: Optional[datetime],
    related_event: Optional[str] = None,
    analysis_text: Optional[str] = None,
    hinted_names: Optional[Iterable[str]] = None,
    stock_candidates: Optional[Sequence[str]] = None,
) -> dict[str, object]:
    analysis_source = analysis_text or title
    category = _category_for_text(analysis_source, hinted_names=hinted_names)
    return {
        "id": f"{prefix}-{idx}",
        "published_at": published_at,
        "title": title,
        "source": source,
        "url": url,
        "category": category,
        "impact": _impact_for_text(analysis_source),
        "leader_stocks": _leader_stocks_for_text(title, category, hinted_names=hinted_names, stock_candidates=stock_candidates),
        "related_event": related_event,
    }


def _node(node_id: str, label: str, kind: str, detail: Optional[str] = None, polarity: str = "neutral") -> dict[str, object]:
    return {"id": node_id, "label": label, "kind": kind, "detail": detail, "polarity": polarity}


def _template_by_id(event_id: str) -> tuple[Optional[EventTemplate], Optional[datetime]]:
    for template in EVENT_TEMPLATES:
        prefix = f"{template.key}-"
        if not event_id.startswith(prefix):
            continue
        raw_dt = event_id[len(prefix):]
        try:
            return template, datetime.strptime(raw_dt, "%Y%m%d%H%M")
        except ValueError:
            return None, None
    return None, None


def _latest_timeline(db: Session, limit: int = 80) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen_titles: set[str] = set()
    stock_candidates = _stock_name_candidates(db)

    news_rows = list(
        db.scalars(select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(limit))
    )
    for idx, row in enumerate(news_rows, start=1):
        if row.title in seen_titles:
            continue
        seen_titles.add(row.title)
        items.append(
            _timeline_item(
                "news",
                idx,
                row.title,
                row.press_name or row.source,
                row.detail_url,
                row.published_at,
                analysis_text=f"{row.title} {row.summary or ''}",
                stock_candidates=stock_candidates,
            )
        )

    report_rows = list(
        db.scalars(select(ResearchReport).order_by(ResearchReport.published_at.desc(), ResearchReport.id.desc()).limit(25))
    )
    for idx, row in enumerate(report_rows, start=1):
        title = f"{row.company_name or row.subject_name or '리포트'}: {row.title}"
        if title in seen_titles:
            continue
        seen_titles.add(title)
        hinted_names = [name for name in (row.company_name, row.subject_name) if name]
        items.append(
            _timeline_item(
                "report",
                idx,
                title,
                row.broker_name or row.source,
                row.detail_url or row.pdf_url,
                row.published_at,
                analysis_text=f"{title} {row.opinion or ''}",
                hinted_names=hinted_names,
                stock_candidates=stock_candidates,
            )
        )

    disclosure_rows = list(
        db.scalars(select(DisclosureItem).order_by(DisclosureItem.published_at.desc(), DisclosureItem.id.desc()).limit(25))
    )
    for idx, row in enumerate(disclosure_rows, start=1):
        title = f"{row.company_name}: {row.report_name}"
        if title in seen_titles:
            continue
        seen_titles.add(title)
        items.append(
            _timeline_item(
                "disclosure",
                idx,
                title,
                row.source,
                row.detail_url,
                row.published_at,
                hinted_names=[row.company_name],
                stock_candidates=stock_candidates,
            )
        )

    items.sort(key=lambda item: item["published_at"] or datetime.min, reverse=True)
    return items[:limit]


def _event_timeline(event: dict[str, object], timeline: list[dict[str, object]], limit: int = 5) -> list[dict[str, object]]:
    keywords = event.pop("_keywords")
    matched = []
    for item in timeline:
        title = str(item["title"])
        if any(keyword and keyword in title for keyword in keywords):
            linked = dict(item)
            linked["related_event"] = event["id"]
            matched.append(linked)
        if len(matched) >= limit:
            break
    return matched


def _latest_cap_date(db: Session) -> Optional[datetime.date]:
    return db.scalar(select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap.is_not(None)))


def _top_market_cap_codes(db: Session, limit: int = 100) -> list[str]:
    cap_date = _latest_cap_date(db)
    if cap_date is None:
        return []
    rows = db.execute(
        select(DailyPrice.code)
        .where(DailyPrice.trade_date == cap_date)
        .where(DailyPrice.market_cap.is_not(None))
        .order_by(DailyPrice.market_cap.desc())
        .limit(limit)
    )
    return [code for (code,) in rows]


def _price_groups_for_codes(db: Session, codes: list[str]) -> dict[str, tuple[StockMaster, list[DailyPrice]]]:
    if not codes:
        return {}
    latest_date = db.scalar(select(func.max(DailyPrice.trade_date)))
    if not latest_date:
        return {}
    from_date = latest_date - timedelta(days=150)
    statement = (
        select(StockMaster, DailyPrice)
        .join(DailyPrice, DailyPrice.code == StockMaster.code)
        .where(DailyPrice.code.in_(codes))
        .where(DailyPrice.trade_date >= from_date)
        .order_by(StockMaster.code, DailyPrice.trade_date)
    )
    groups: dict[str, tuple[StockMaster, list[DailyPrice]]] = {}
    for stock, price in db.execute(statement):
        if stock.code not in groups:
            groups[stock.code] = (stock, [])
        groups[stock.code][1].append(price)
    return groups


def _stock_sectors(stock: StockMaster) -> set[str]:
    text = f"{stock.name} {stock.sector or ''} {stock.industry or ''}"
    sectors = set()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            sectors.add(sector)
    return sectors


def _matched_template_sectors(template: EventTemplate, sectors: set[str]) -> set[str]:
    matched = sectors.intersection(set(template.affected_sectors))
    if matched:
        return matched
    if "2차전지 소재" in template.affected_sectors and "2차전지" in sectors:
        matched.add("2차전지")
    if "경기민감" in template.affected_sectors:
        cyclical = sectors.intersection({"경기민감", "자동차", "조선", "해운", "화학"})
        if cyclical:
            matched.add(sorted(cyclical)[0])
    return matched


def _fallback_stock_names_for_template(template: EventTemplate, limit: int = 18) -> list[str]:
    names: list[str] = []
    candidate_sectors: list[str] = []
    for sector in template.affected_sectors:
        if sector == "2차전지 소재":
            candidate_sectors.append("2차전지")
        else:
            candidate_sectors.append(sector)

    for sector in candidate_sectors:
        for name in SECTOR_KEYWORDS.get(sector, ()):
            cleaned = (name or "").strip()
            if not _is_matchable_stock_name(cleaned) or cleaned in names:
                continue
            names.append(cleaned)
            if len(names) >= limit:
                return names

    for axis in FOCUSED_EVENT_AXES.get(template.title, ()):
        for name in FOCUSED_TIMELINE_LEADERS.get(axis, ()):
            cleaned = (name or "").strip()
            if not _is_matchable_stock_name(cleaned) or cleaned in names:
                continue
            names.append(cleaned)
            if len(names) >= limit:
                return names

    fallback_category = "원자재" if template.category == "원자재" else "매크로"
    for name in TIMELINE_LEADER_STOCKS.get(fallback_category, TIMELINE_LEADER_STOCKS["시장"]):
        cleaned = (name or "").strip()
        if not _is_matchable_stock_name(cleaned) or cleaned in names:
            continue
        names.append(cleaned)
        if len(names) >= limit:
            return names
    return names


def _stocks_by_names(db: Session, names: Sequence[str]) -> list[StockMaster]:
    if not names:
        return []
    rows = list(db.scalars(select(StockMaster).where(StockMaster.name.in_(names))))
    order = {name: idx for idx, name in enumerate(names)}
    rows.sort(key=lambda stock: order.get(stock.name, len(order)))
    return rows


def _fallback_impact_score(matched_sectors: set[str], rank: int) -> Decimal:
    base = Decimal("64") + Decimal(len(matched_sectors)) * Decimal("6") - Decimal(max(rank - 1, 0)) * Decimal("2.5")
    return _round_decimal(max(Decimal("38"), min(Decimal("86"), base))) or Decimal("50")


def _scenario_reason_text(bias: int) -> str:
    if bias > 0:
        return "선택 시나리오에서 수혜 방향"
    if bias < 0:
        return "선택 시나리오에서 부담 방향"
    return "결과 값에 따라 수혜/부담이 갈리는 조건부 영향"


def _impact_row(
    template: EventTemplate,
    scenario: str,
    stock: StockMaster,
    matched: set[str],
    rank: int,
    item: Optional[dict[str, object]] = None,
    prices: Optional[list[DailyPrice]] = None,
    fallback_used: bool = False,
) -> dict[str, object]:
    sector = sorted(matched)[0]
    score = _stock_impact_score(item, matched, rank) if item else _fallback_impact_score(matched, rank)
    bias = _scenario_bias(template, scenario, matched)
    if bias:
        score = _round_decimal(max(Decimal("0"), min(Decimal("100"), score + Decimal(bias * 14)))) or score
    market_cap = prices[-1].market_cap if prices else None
    lead_reason = f"시가총액 상위 100위 내 {sector} 노출"
    if fallback_used:
        lead_reason = f"{sector} 대표주 기준 이벤트 민감도 우선 매칭"
    return {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "market_cap": market_cap,
        "impact_score": score,
        "impact_direction": _scenario_direction(template, scenario, sector, bias),
        "reasons": [
            lead_reason,
            SECTOR_OUTLOOK.get(template.title, {}).get(sector, template.expected_impact),
            _scenario_reason_text(bias),
        ],
    }


def _fallback_event_stock_impacts(
    db: Session,
    template: EventTemplate,
    scenario: str,
    limit: int = 10,
    existing_codes: Optional[set[str]] = None,
) -> list[dict[str, object]]:
    codes_to_skip = existing_codes or set()
    stocks = [stock for stock in _stocks_by_names(db, _fallback_stock_names_for_template(template)) if stock.code not in codes_to_skip]
    if not stocks:
        return []
    groups = _price_groups_for_codes(db, [stock.code for stock in stocks])
    rows: list[dict[str, object]] = []
    for rank, stock in enumerate(stocks, start=1):
        sectors = _stock_sectors(stock)
        matched = _matched_template_sectors(template, sectors)
        if not matched:
            continue
        group = groups.get(stock.code)
        item = None
        prices = None
        if group:
            _, prices = group
            item = _base_item(stock, prices)
        rows.append(
            _impact_row(
                template,
                scenario,
                stock,
                matched,
                rank,
                item=item,
                prices=prices,
                fallback_used=True,
            )
        )
        if len(rows) >= limit:
            break
    return rows


def _direction_for_sector(template: EventTemplate, sector: str) -> str:
    if template.title == "미국 EIA 주간 원유재고":
        if sector in {"정유"}:
            return "조건부 수혜"
        if sector in {"화학", "항공", "해운"}:
            return "비용 민감"
    if template.title == "미국 PCE 물가·개인소득/지출":
        if sector in {"반도체", "인터넷", "2차전지"}:
            return "금리 민감"
        if sector in {"자동차"}:
            return "환율/수요 혼재"
        if sector in {"금융", "보험", "은행"}:
            return "금리 수혜/경기 리스크"
    if template.title == "한국 금융기관 가중평균금리":
        if sector in {"은행", "보험"}:
            return "금리 수혜"
        if sector in {"건설", "리츠"}:
            return "금리 부담"
    if template.title == "한국 BSI·ESI":
        return "경기심리 민감"
    if template.title == "미국 주간 신규실업수당청구건수":
        return "고용/금리 민감"
    return "민감"


def _stock_impact_score(item: dict[str, object], matched_sectors: set[str], rank: int) -> Decimal:
    one_month = Decimal(str(item.get("one_month_return") or 0))
    three_month = Decimal(str(item.get("three_month_return") or 0))
    base = Decimal("42") + Decimal(len(matched_sectors)) * Decimal("14")
    rank_bonus = max(Decimal("0"), Decimal("20") - Decimal(rank) / Decimal("5"))
    momentum = max(Decimal("-8"), min(Decimal("10"), one_month / Decimal("4") + three_month / Decimal("12")))
    return _round_decimal(max(Decimal("0"), min(Decimal("100"), base + rank_bonus + momentum))) or Decimal("0")


def _scenario_bias(template: EventTemplate, scenario: str, sectors: set[str]) -> int:
    scenario_map = SECTOR_SCENARIO_BIAS.get(template.title, {})
    sector_map = scenario_map.get(scenario, {})
    values = [sector_map.get(sector, 0) for sector in sectors]
    if any(value > 0 for value in values):
        return 1
    if any(value < 0 for value in values):
        return -1
    return 0


def _scenario_direction(template: EventTemplate, scenario: str, sector: str, bias: int) -> str:
    if scenario == "base" or bias == 0:
        return _direction_for_sector(template, sector)
    if bias > 0:
        return "시나리오 수혜"
    return "시나리오 부담"


def _event_stock_impacts(db: Session, template: EventTemplate, scenario: str = "base", limit: int = 10) -> list[dict[str, object]]:
    top_codes = _top_market_cap_codes(db)
    groups = _price_groups_for_codes(db, top_codes)
    rows = []
    for rank, code in enumerate(top_codes, start=1):
        group = groups.get(code)
        if not group:
            continue
        stock, prices = group
        item = _base_item(stock, prices)
        if not item:
            continue
        sectors = _stock_sectors(stock)
        matched = _matched_template_sectors(template, sectors)
        if not matched:
            continue
        rows.append(_impact_row(template, scenario, stock, matched, rank, item=item, prices=prices))

    if len(rows) < limit:
        rows.extend(
            _fallback_event_stock_impacts(
                db,
                template,
                scenario,
                limit=limit - len(rows),
                existing_codes={str(row["code"]) for row in rows},
            )
        )
    rows.sort(key=lambda row: row["impact_score"], reverse=True)
    return rows[:limit]


def _scenario_for_template(template: EventTemplate) -> str:
    if template.title == "미국 PCE 물가·개인소득/지출":
        return "PCE가 예상보다 높으면 금리·달러 상승 경로, 낮으면 할인율 완화 경로로 해석합니다."
    if template.title == "미국 EIA 주간 원유재고":
        return "재고 감소는 유가 상승/정유 수혜/비용주 부담, 재고 증가는 그 반대 경로로 봅니다."
    if template.title == "한국 금융기관 가중평균금리":
        return "대출·예금금리 상승은 금융주 마진과 건설/리츠 부담을 동시에 키우는 경로입니다."
    if template.title == "한국 BSI·ESI":
        return "경기심리 개선은 내수·금융·자동차 심리 회복, 악화는 경기민감주 부담으로 연결됩니다."
    if template.title == "미국 주간 신규실업수당청구건수":
        return "고용 악화는 금리 완화 기대와 경기 둔화 우려가 동시에 생기는 경로입니다."
    return template.expected_impact


def _scenario_options(template: EventTemplate) -> list[dict[str, str]]:
    return [{"key": "base", "label": "기본", "description": _scenario_for_template(template)}, *SCENARIOS.get(template.title, ())]


def _split_scenarios(template: EventTemplate) -> tuple[dict[str, str], dict[str, str]]:
    options = list(SCENARIOS.get(template.title, ()))
    if len(options) >= 2:
        return options[1], options[0]
    return (
        {"key": "bear", "label": "부정 시나리오", "description": "이벤트 결과가 시장에 부담으로 해석되는 경우"},
        {"key": "bull", "label": "긍정 시나리오", "description": "이벤트 결과가 시장에 우호적으로 해석되는 경우"},
    )


def build_event_graph(db: Session, event_id: str) -> Optional[dict[str, object]]:
    now = _now_kst()
    template, starts_at = _template_by_id(event_id)
    if template is None or starts_at is None:
        return None
    negative_scenario, positive_scenario = _split_scenarios(template)
    variables = [
        _node(f"var-{idx}", value, "variable", "1차 변수", "neutral")
        for idx, value in enumerate(template.affected_variables, start=1)
    ]
    sectors = [
        _node(
            f"sector-{idx}",
            value,
            "sector",
            SECTOR_OUTLOOK.get(template.title, {}).get(value, "이벤트 결과에 따라 이익 추정과 밸류에이션이 변동"),
            "mixed",
        )
        for idx, value in enumerate(template.affected_sectors, start=1)
    ]
    outcomes = [
        _node("outcome-rate", "할인율/환율 재평가", "outcome", "금리와 달러 변화가 외국인 수급과 성장주 밸류에이션으로 확산", "mixed"),
        _node("outcome-earnings", "이익률·수요 기대 변화", "outcome", "원가, 소비, 수출 전망이 실적 추정에 반영", "mixed"),
        _node("outcome-flow", "외국인/기관 수급 이동", "outcome", "대형주 중심으로 위험 선호와 업종 로테이션 발생", "mixed"),
    ]
    negative_stocks = _event_stock_impacts(db, template, negative_scenario["key"])
    positive_stocks = _event_stock_impacts(db, template, positive_scenario["key"])
    stock_nodes = [
        _node(f"stock-{stock['code']}", stock["name"], "stock", stock["impact_direction"], "mixed")
        for stock in (negative_stocks[:4] + positive_stocks[:4])
    ]
    return {
        "event_id": event_id,
        "title": template.title,
        "starts_at": starts_at,
        "as_of": now,
        "summary": template.expected_impact,
        "scenario": _scenario_for_template(template),
        "negative_label": negative_scenario["label"],
        "positive_label": positive_scenario["label"],
        "layers": [
            {"title": "이벤트", "nodes": [_node("event", template.title, "event", template.importance, "neutral")]},
            {"title": "1차 변수", "nodes": variables},
            {"title": "2차 영향", "nodes": sectors},
            {"title": "N차 흐름", "nodes": outcomes},
            {"title": "결과 종목", "nodes": stock_nodes},
        ],
        "negative_stocks": negative_stocks,
        "positive_stocks": positive_stocks,
    }


def _headline_for_events(events: list[dict[str, object]]) -> str:
    axes: list[str] = []
    for item in events:
        for axis in item.get("event_axes", []):
            if axis not in axes:
                axes.append(axis)
    if axes:
        return f"이번 1주일은 {', '.join(axes[:3])} 이벤트를 중심으로 봅니다."
    return "이번 1주일은 예정된 핵심 이벤트가 적어 최근 타임라인을 함께 봅니다."


def build_trend_analysis(db: Session, days: int = 7) -> dict[str, object]:
    now = _now_kst()
    window_start = now
    window_end = now + timedelta(days=days)
    past_window_start = now - timedelta(days=14)
    timeline = _latest_timeline(db)

    events: list[dict[str, object]] = []
    past_events: list[dict[str, object]] = []
    for template in EVENT_TEMPLATES:
        axes = FOCUSED_EVENT_AXES.get(template.title)
        if axes is None:
            continue
        for starts_at in _scheduled_occurrences_between(template, past_window_start, window_end):
            event = {
                "id": _event_id(template, starts_at),
                "starts_at": starts_at,
                "event_axes": list(axes),
                "category": template.category,
                "title": template.title,
                "importance": template.importance,
                "expected_impact": template.expected_impact,
                "affected_variables": list(template.affected_variables),
                "affected_sectors": list(template.affected_sectors),
                "watch_points": list(template.watch_points),
                "source_name": template.source_name,
                "source_url": template.source_url,
                "_keywords": template.keywords,
            }
            event["timeline"] = _event_timeline(event, timeline)
            if starts_at < now:
                past_events.append(event)
            else:
                events.append(event)

    events.sort(key=lambda item: item["starts_at"])
    past_events.sort(key=lambda item: item["starts_at"], reverse=True)
    return {
        "as_of": now,
        "window_start": window_start,
        "window_end": window_end,
        "headline": _headline_for_events(events),
        "events": events,
        "past_events": past_events,
        "timeline": timeline[:60],
    }
