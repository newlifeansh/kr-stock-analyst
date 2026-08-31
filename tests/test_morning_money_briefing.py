from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import app, morning_money_briefing_cache
from app.models import NewsItem
from app.services.investor_calendar import InvestorScheduleEvent
from app.services.morning_money_briefing import (
    CATEGORIES,
    CATEGORY_LOOKUP,
    MORNING_BRIEFING_HIGHLIGHT_LIMIT,
    MORNING_BRIEFING_ITEMS_PER_CATEGORY,
    MORNING_BRIEFING_SUMMARY_LIMIT,
    MORNING_BRIEFING_TOTAL_ITEM_LIMIT,
    _briefing_summary,
    _friendly_sentence,
    _select_briefing_highlights,
    _titles_describe_same_story,
    build_morning_money_briefing,
    build_morning_money_briefing_history,
    classify_morning_news,
    money_briefing_edition,
    morning_briefing_window,
)


KST = ZoneInfo("Asia/Seoul")

EXPECTED_MORNING_MONEY_CATEGORIES = (
    ("schedule", "오늘 체크할 일정"),
    ("market", "증시 UP&DOWN"),
    ("money", "금융시장 동향"),
    ("invest", "투자·재테크"),
    ("industry", "산업 뉴스"),
    ("company", "기업 소식"),
    ("tech", "테크(Tech)"),
    ("policy", "정책·경제지표"),
    ("real_estate", "부동산"),
)


def _news(
    *,
    external_id: str,
    title: str,
    category: str,
    published_at: datetime,
    summary: str = "투자자가 개장 전에 확인할 핵심 내용입니다.",
) -> NewsItem:
    return NewsItem(
        source="naver_finance",
        source_category=category,
        external_id=external_id,
        title=title,
        summary=summary,
        press_name="테스트경제",
        detail_url=f"https://finance.naver.com/news/read.naver?office_id=001&article_id={external_id}",
        published_at=published_at,
    )


def test_morning_money_category_contract_has_nine_reader_facing_sections():
    assert tuple((category.key, category.label) for category in CATEGORIES) == (
        EXPECTED_MORNING_MONEY_CATEGORIES
    )
    assert {"global", "other"}.isdisjoint(category.key for category in CATEGORIES)


def test_morning_briefing_window_uses_latest_completed_kst_window():
    start, end, publication_date = morning_briefing_window(
        datetime(2026, 8, 12, 8, 0, tzinfo=KST)
    )

    assert start.isoformat() == "2026-08-11T16:00:00+09:00"
    assert end.isoformat() == "2026-08-12T06:00:00+09:00"
    assert publication_date.isoformat() == "2026-08-12"

    before_completion = morning_briefing_window(
        datetime(2026, 8, 12, 5, 59, tzinfo=KST)
    )
    assert before_completion[0].isoformat() == "2026-08-11T12:00:00+09:00"
    assert before_completion[1].isoformat() == "2026-08-11T16:00:00+09:00"
    assert before_completion[2].isoformat() == "2026-08-11"


def test_money_briefing_editions_rotate_at_06_12_and_16_kst_on_weekends():
    cases = (
        (
            datetime(2026, 8, 15, 5, 59, 59, tzinfo=KST),
            "afternoon",
            "2026-08-14:16",
            "2026-08-14T12:00:00+09:00",
            "2026-08-14T16:00:00+09:00",
            "2026-08-15T06:00:00+09:00",
        ),
        (
            datetime(2026, 8, 15, 6, 0, tzinfo=KST),
            "morning",
            "2026-08-15:06",
            "2026-08-14T16:00:00+09:00",
            "2026-08-15T06:00:00+09:00",
            "2026-08-15T12:00:00+09:00",
        ),
        (
            datetime(2026, 8, 15, 11, 59, 59, tzinfo=KST),
            "morning",
            "2026-08-15:06",
            "2026-08-14T16:00:00+09:00",
            "2026-08-15T06:00:00+09:00",
            "2026-08-15T12:00:00+09:00",
        ),
        (
            datetime(2026, 8, 15, 12, 0, tzinfo=KST),
            "midday",
            "2026-08-15:12",
            "2026-08-15T09:00:00+09:00",
            "2026-08-15T12:00:00+09:00",
            "2026-08-15T16:00:00+09:00",
        ),
        (
            datetime(2026, 8, 15, 15, 59, 59, tzinfo=KST),
            "midday",
            "2026-08-15:12",
            "2026-08-15T09:00:00+09:00",
            "2026-08-15T12:00:00+09:00",
            "2026-08-15T16:00:00+09:00",
        ),
        (
            datetime(2026, 8, 15, 16, 0, tzinfo=KST),
            "afternoon",
            "2026-08-15:16",
            "2026-08-15T12:00:00+09:00",
            "2026-08-15T16:00:00+09:00",
            "2026-08-16T06:00:00+09:00",
        ),
    )

    for now, expected_edition, key, start, end, next_at in cases:
        publication = money_briefing_edition(now)
        assert publication.edition == expected_edition
        assert publication.edition_key == key
        assert publication.window_start.isoformat() == start
        assert publication.window_end.isoformat() == end
        assert publication.published_at.isoformat() == end
        assert publication.next_publication_at.isoformat() == next_at

    utc_boundary = money_briefing_edition(
        datetime(2026, 8, 15, 3, 0, tzinfo=ZoneInfo("UTC"))
    )
    assert utc_boundary.edition_key == "2026-08-15:12"


def test_morning_news_classification_prioritizes_investor_categories():
    published_at = datetime(2026, 8, 12, 1, 0)

    assert classify_morning_news(
        _news(
            external_id="1001",
            title="미국 CPI 오늘 밤 발표 예정",
            category="global",
            published_at=published_at,
        )
    ) == "schedule"
    assert classify_morning_news(
        _news(
            external_id="1002",
            title="원·달러 환율 하락, 국채금리도 안정",
            category="market",
            published_at=published_at,
        )
    ) == "money"
    assert classify_morning_news(
        _news(
            external_id="1003",
            title="정부 반도체 세제 지원책 확대",
            category="breaking",
            published_at=published_at,
        )
    ) == "policy"
    assert classify_morning_news(
        _news(
            external_id="1004",
            title="AI 반도체 공급망 투자 확대",
            category="breaking",
            published_at=published_at,
        )
    ) == "industry"


def test_morning_news_classification_recognizes_real_estate_policy_actions():
    published_at = datetime(2026, 8, 14, 1, 0)
    policy_titles = (
        "수도권 부동산 공급 확대 방안 발표",
        "청년 4억 이하 비아파트 매수 지원…신혼부부 소득 합산 안한다",
        "이주비 대출 풀고 신속 착공하면 인센티브…재개발·재건축 숨통",
        "내년부터 비거주 1주택 전세대출 막힌다",
    )
    for index, title in enumerate(policy_titles):
        assert classify_morning_news(
            _news(
                external_id=f"real-estate-policy-{index}",
                title=title,
                category="breaking",
                published_at=published_at,
            )
        ) == "real_estate"

    ordinary_price_story = _news(
        external_id="real-estate-market-price",
        title="서울 아파트 매매가 3주 연속 상승",
        category="breaking",
        published_at=published_at,
    )
    assert classify_morning_news(ordinary_price_story) == "real_estate"


def test_morning_news_classification_ignores_mismatched_source_summary():
    published_at = datetime(2026, 8, 13, 1, 0)
    mismatched_summary = (
        "\ub8e8\uba58\ud140 \ud640\ub529\uc2a4\uac00 \ubaa9\ud45c\uc8fc\uac00 \ud558\ud5a5 \uc870\uc815 \ubd84\uc11d\uc774 \ub098\uc654\ub2e4."
    )
    cases = (
        (
            "\ubbf8 7\uc6d4 CPI 3.4% '\uc608\uc0c1 \ubd80\ud569'\u20269\uc6d4 \uae08\ub9ac \uc778\uc0c1 \uac00\ub2a5\uc131\u2193",
            "global",
            "policy",
        ),
        (
            "\ubc18\ub3c4\uccb4 \uac71\uc815\uc740 \ud558\ub294 \uac8c \uc544\ub2c8\ub2e4\u2026'\uc0bc\uc804\ub2c9\uc2a4 \uac15\uc138' \ucf54\uc2a4\ud53c 3.6%\u2191",
            "global",
            "market",
        ),
        (
            "\u201c\uc774 \uc815\ub3c4\uba74 \uc8fc\ub3c4\uc8fc \uad50\uccb4?\u201d\u2026K\ud654\uc7a5\ud488, \uc218\ucd9c \ub300\ubc15 \ud798\uc785\uc5b4 \uc2e0\uace0\uac00 \ud589\uc9c4",
            "breaking",
            "industry",
        ),
        (
            "[\uc18d\ubcf4]CPI \uc548\ub3c4\xb7AI \uc2e4\uc801 \ud6c8\ud48d\uc5d0\u2026\ub098\uc2a4\ub2e5 0.5%\u2191",
            "breaking",
            "market",
        ),
        (
            "\uc0c1\ud3d0 \uce74\uc6b4\ud2b8\ub2e4\uc6b4\u2026'\ub3d9\uc804\uc8fc\xb7\uc2dc\ucd1d \ubbf8\ub2ec' \uc8fc\uc758",
            "company",
            "market",
        ),
        (
            "\uc99d\uc2dc \ud65c\ud669 \ub54c \uc99d\uad8c\uc0ac\ub3c4 \uc6c3\uc5c8\ub2e4\u2026\ub300\ud615 \uc99d\uad8c\uc0ac 2\ubd84\uae30 \uc21c\uc775",
            "global",
            "company",
        ),
        (
            "[\uc62c\ub313\ucc28\uc774\ub098] \ub300\ub9cc \uc99d\uc2dc, \u7f8e \ubc18\ub3c4\uccb4\uc8fc \uac15\uc138\uc5d0 \uae30\uc220\uc8fc \ub9e4\uc218\ub85c \uc0ac\ud758\uc9f8 \uc0c1\uc2b9",
            "breaking",
            "market",
        ),
        (
            "\ubc18\ub3c4\uccb4 \ud6c8\ud48d \uc0bc전 6.68% \uae09\ub4f1\u2026 7000피 \ub2e4시 갈까",
            "breaking",
            "market",
        ),
        (
            "TDF 여러 개 샀더니 은퇴 전략 꼬인다",
            "breaking",
            "invest",
        ),
        (
            "\uc704\uba54\uc774\ub4dc 2\ubd84\uae30 \uc601\uc5c5\uc190\uc2e4 210\uc5b5\uc6d0\u2026\uc801\uc790 \ucd95\uc18c",
            "breaking",
            "company",
        ),
    )

    for index, (title, source_category, expected_category) in enumerate(cases):
        item = _news(
            external_id=f"400{index}",
            title=title,
            category=source_category,
            summary=mismatched_summary,
            published_at=published_at,
        )
        assert classify_morning_news(item) == expected_category

    matching_summary = _news(
        external_id="4099",
        title='"\ud558\uc774\ub2c9\uc2a4 \uc5c6\uc774 \uc5b4\ub5a1\ud574"\u2026\ud070\uc190 \ubcc0\ud654 \uc870\uc9d0\uc5d0 \ud655 \ubc14\ub010 \uacf5\uae30',
        category="breaking",
        summary=(
            "\uace0\uae08\ub9ac \ud658\uacbd\uc5d0\uc11c \uc704\ucd95\ub41c \ud06c\ub808\ub514\ud2b8 \ucc44\uad8c \ubc1c\ud589\uc2dc\uc7a5\uc758 "
            "\ud070\uc190\uc73c\ub85c \ub5a0\uc62c\ub790\ub358 SK\ud558\uc774\ub2c9\uc2a4\uac00 \uc218\uc694\ub97c \uc904\uc77c \uc218 \uc788\ub2e4\ub294 \uc6b0\ub824\uac00 \ub098\uc654\ub2e4."
        ),
        published_at=published_at,
    )
    assert classify_morning_news(matching_summary) == "money"

    past_corporate_action = _news(
        external_id="4098",
        title="SK\ub514\uc564\ub514, 240% \uc720\uc99d \uc7ac\ucd94\uc9c4\u2026\uc18c\uc561\uc8fc\uc8fc\ub294 \ubc18\ubc1c",
        category="breaking",
        summary=(
            "SK\ub514\uc564\ub514\uac00 \uc0c1\uc7a5\uc8fc\uc2dd \uc218 240% \uaddc\ubaa8 \uc720\uc0c1\uc99d\uc790\ub97c \uc7ac\ucd94\uc9c4\ud558\uae30\ub85c "
            "\uacb0\uc815\ud588\ub2e4. 12\uc77c \uc18c\uc561\uc8fc\uc8fc \ubc18\ubc1c\uc774 \uc774\uc5b4\uc84c\ub2e4."
        ),
        published_at=published_at,
    )
    assert classify_morning_news(past_corporate_action) == "company"


def test_morning_news_explanation_is_rich_and_rejects_unrelated_summary():
    relevant = _news(
        external_id="4101",
        title="\ub098\uc2a4\ub2e5 \uc0c1\uc2b9\uc73c\ub85c \ub274\uc695\uc99d\uc2dc \ub9c8\uac10",
        category="global",
        summary=(
            "\ub098\uc2a4\ub2e5\uacfc \ubbf8\uad6d \uae30\uc220\uc8fc\uac00 \ub3d9\ubc18 \uc0c1\uc2b9 \ub9c8\uac10\ud588\ub2e4. "
            "\ud22c\uc790\uc2ec\ub9ac\ub3c4 \uac1c\uc120\ub410\ub2e4."
        ),
        published_at=datetime(2026, 8, 13, 5, 30),
    )
    mismatched = _news(
        external_id="4102",
        title="\ubbf8 7\uc6d4 CPI 3.4% \uc608\uc0c1 \ubd80\ud569\u2026\uae08\ub9ac \uc778\uc0c1 \uac00\ub2a5\uc131 \ud558\ub77d",
        category="global",
        summary="\ub8e8\uba58\ud140 \ud640\ub529\uc2a4\uac00 \ubaa9\ud45c\uc8fc\uac00 \ud558\ud5a5 \uc870\uc815 \ubd84\uc11d\uc774 \ub098\uc654\ub2e4.",
        published_at=datetime(2026, 8, 13, 5, 20),
    )

    relevant_summary = _briefing_summary(relevant, CATEGORY_LOOKUP["global"])
    mismatched_summary = _briefing_summary(mismatched, CATEGORY_LOOKUP["money"])
    assert "\ub098\uc2a4\ub2e5" in relevant_summary
    assert "미국 기술주 흐름" in relevant_summary
    assert len(relevant_summary) <= MORNING_BRIEFING_SUMMARY_LIMIT
    assert "\ub8e8\uba58\ud140" not in mismatched_summary
    assert "CPI" in mismatched_summary
    assert "금리 기대 변화" in mismatched_summary
    assert mismatched_summary.count("요.") >= 2

    truncated = _news(
        external_id="4103",
        title="K화장품, 수출 대박 힘입어 신고가 행진",
        category="market",
        summary=(
            "이 기사는 2026년 8월 13일 마켓인 프리미엄 콘텐츠로 선공개 되었습니다. "
            "한국콜마가 2분기 최대 실적을 기록했고 이달 들어 주가가 39% 치솟으며 "
            "K뷰티 유통 기업의 이익도 늘어나고 있다…"
        ),
        published_at=datetime(2026, 8, 13, 5, 10),
    )
    truncated_summary = _briefing_summary(truncated, CATEGORY_LOOKUP["industry"])
    assert "한국콜마" in truncated_summary
    assert "선공개" not in truncated_summary
    assert "39% 치솟은 흐름" in truncated_summary
    assert "수출 증가" in truncated_summary
    assert truncated_summary.count("요.") >= 2

    short_clipped = _news(
        external_id="4104",
        title="역대 최대 실적 코웨이, 4000억원 회사채 발행한다",
        category="company",
        summary="코웨이가 최대 4000억원 규모의 회사채 발…",
        published_at=datetime(2026, 8, 13, 5, 0),
    )
    clipped_summary = _briefing_summary(short_clipped, CATEGORY_LOOKUP["company"])
    assert "회사채 발행한다" in clipped_summary
    assert "조달 규모와 금리 부담" in clipped_summary
    assert "회사채 발…" not in clipped_summary

    headline_deck = _news(
        external_id="4105",
        title="美 CPI 예상 부합에 시장 안도",
        category="global",
        summary=(
            "7월 CPI 전월비 0.1%·전년비 3.4% 주거비 둔화·에너지 하락에 인상 경계 완화 "
            "유가·8월 지표는 변수 [더팩트｜테스트 기자] 미국의 7월 소비자물가지수는…"
        ),
        published_at=datetime(2026, 8, 13, 4, 50),
    )
    deck_summary = _briefing_summary(headline_deck, CATEGORY_LOOKUP["policy"])
    assert "8월 지표는 변수" in deck_summary
    assert "테스트 기자" not in deck_summary
    assert "미국의 7" not in deck_summary

    broadcast_intro = _news(
        external_id="4106",
        title="미국발 삭풍에 코스피 5% 급락…반도체의 반란?",
        category="market",
        summary=(
            "오늘 하루 돈의 흐름을 짚어드립니다, 퇴근길머니~"
            "오늘도 테스트 기자와 함께해요. 어서오십쇼~ 먼저 시황부터 정리해볼까요."
        ),
        published_at=datetime(2026, 8, 13, 4, 40),
    )
    broadcast_summary = _briefing_summary(broadcast_intro, CATEGORY_LOOKUP["market"])
    assert "코스피가 5% 급락" in broadcast_summary
    assert "퇴근길머니" not in broadcast_summary
    assert "기자와 함께" not in broadcast_summary
    assert "시황부터" not in broadcast_summary
    assert broadcast_summary.count("요.") >= 2

    pension_flow = _news(
        external_id="4107",
        title='국민연금 "국내주식 매도 유예, 시장 변동성 때문"',
        category="market",
        summary="",
        published_at=datetime(2026, 8, 13, 4, 30),
    )
    assert classify_morning_news(pension_flow) == "market"
    pension_summary = _briefing_summary(pension_flow, CATEGORY_LOOKUP["market"])
    assert "국내 주식 매도를 유예" in pension_summary
    assert "대형주 수급" in pension_summary
    assert "가입 조건" not in pension_summary

    clipped_decks = (
        (
            _news(
                external_id="4108",
                title="UBS, 글로벌 채권 금리 급등 속 단기채는 여전히 매력있어",
                category="bond",
                summary="글로벌 채권 매도세로 국채 금리가 최고치로 치솟고 장기 국채 금리 변동성",
                published_at=datetime(2026, 8, 13, 4, 20),
            ),
            CATEGORY_LOOKUP["money"],
            "단기채의 매력이 남아 있다는 분석",
        ),
        (
            _news(
                external_id="4109",
                title="美지수 추종 ETF에 뭉칫돈…'삼전닉스+채권' 상품도 상위권",
                category="market",
                summary="퇴직연금 계좌에서 많이 보유한 ETF는 미국 지수 추종 상품인",
                published_at=datetime(2026, 8, 13, 4, 10),
            ),
            CATEGORY_LOOKUP["invest"],
            "반도체·채권 혼합 상품으로 투자 자금이 몰렸어요.",
        ),
    )
    for item, category, expected in clipped_decks:
        rendered = _briefing_summary(item, category)
        assert expected in rendered
        assert not rendered.startswith("‘")


def test_morning_money_friendly_copy_uses_correct_korean_copula():
    cases = (
        ("가성비를 앞세운 전략 모습입니다", "가성비를 앞세운 전략 모습이에요."),
        ("성장률이 높아질 전망입니다", "성장률이 높아질 전망이에요."),
    )

    for source, expected in cases:
        rendered = _friendly_sentence(source)
        assert rendered == expected
        assert "모습이라고" not in rendered
        assert "전망라고" not in rendered


def test_build_morning_money_fetches_calendar_before_database_news(monkeypatch):
    calls: list[str] = []

    def fake_upcoming_investor_events(_publication_date):
        calls.append("calendar")
        return []

    def fake_latest_news_items(_db, **_kwargs):
        calls.append("news")
        return []

    monkeypatch.setattr(
        "app.services.morning_money_briefing.upcoming_investor_events",
        fake_upcoming_investor_events,
    )
    monkeypatch.setattr(
        "app.services.morning_money_briefing.latest_news_items",
        fake_latest_news_items,
    )

    build_morning_money_briefing(
        object(),
        now=datetime(2026, 8, 31, 8, 0, tzinfo=KST),
    )

    assert calls == ["calendar", "news"]


def test_build_morning_money_briefing_filters_window_deduplicates_and_groups():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 12, 8, 0, tzinfo=KST)

    rows = [
        _news(
            external_id="2001",
            title="미국 CPI 오늘 밤 발표 예정",
            category="global",
            published_at=datetime(2026, 8, 12, 5, 30),
        ),
        _news(
            external_id="2002",
            title="코스피 외국인 매수 확대, 반도체 강세",
            category="market",
            published_at=datetime(2026, 8, 12, 1, 20),
        ),
        _news(
            external_id="2003",
            title="뉴욕증시 나스닥 상승 마감",
            category="global",
            published_at=datetime(2026, 8, 12, 5, 10),
        ),
        _news(
            external_id="2004",
            title="원·달러 환율 하락, 국제유가 안정",
            category="fx",
            published_at=datetime(2026, 8, 11, 23, 40),
        ),
        _news(
            external_id="2005",
            title="정부 수출 지원책 확대",
            category="breaking",
            published_at=datetime(2026, 8, 11, 19, 10),
        ),
        _news(
            external_id="2006",
            title="AI 반도체 공급망 투자 확대",
            category="breaking",
            published_at=datetime(2026, 8, 11, 20, 20),
        ),
        _news(
            external_id="2007",
            title="테스트기업 2분기 영업이익 증가",
            category="company",
            published_at=datetime(2026, 8, 11, 18, 0),
        ),
        _news(
            external_id="2008",
            title="코스피 외국인 매수 확대, 반도체 강세",
            category="breaking",
            published_at=datetime(2026, 8, 12, 1, 19),
        ),
        _news(
            external_id="2009",
            title="시간 범위를 벗어난 오래된 소식",
            category="breaking",
            published_at=datetime(2026, 8, 11, 15, 59),
        ),
    ]

    with session_factory() as db:
        db.add_all(rows)
        db.commit()
        payload = build_morning_money_briefing(db, now=now, schedule_events=[])

    assert payload["publication_date"].isoformat() == "2026-08-12"
    assert payload["edition"] == "morning"
    assert payload["edition_key"] == "2026-08-12:06"
    assert payload["edition_label"] == "오전판"
    assert payload["published_at"].isoformat() == "2026-08-12T06:00:00+09:00"
    assert payload["next_publication_at"].isoformat() == "2026-08-12T12:00:00+09:00"
    assert payload["popup_start"].isoformat() == "2026-08-12T06:00:00+09:00"
    assert payload["popup_end"].isoformat() == "2026-08-12T12:00:00+09:00"
    assert payload["total_news_count"] == 7
    assert payload["selected_news_count"] == 7
    assert len(payload["highlights"]) == 3
    assert payload["empty_message"] is None
    categories = {category["key"]: category for category in payload["categories"]}
    assert {
        "schedule",
        "market",
        "money",
        "policy",
        "industry",
        "company",
    } <= set(categories)
    assert {"global", "other"}.isdisjoint(categories)
    assert categories["market"]["count"] == 2
    assert any(
        "뉴욕증시" in item["title"] for item in categories["market"]["items"]
    )
    assert categories["market"]["items"][0]["status"] == "기회"
    assert categories["market"]["items"][0]["detail_url"].startswith(
        "https://n.news.naver.com/mnews/article/001/"
    )
    assert all(
        item["summary"].endswith("요.")
        for category in payload["categories"]
        for item in category["items"]
    )
    assert all(
        item["summary"].count("요.") >= 2
        for category in payload["categories"]
        for item in category["items"]
    )
    assert all(
        "press_name" not in item
        for category in payload["categories"]
        for item in category["items"]
    )


def test_morning_money_briefing_enforces_taxonomy_budget_and_highlight_diversity():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 20, 8, 0, tzinfo=KST)
    base_time = datetime(2026, 8, 19, 17, 0)
    category_titles = {
        "market": (
            "코스피 외국인 수급 급등",
            "뉴욕증시 나스닥 다우 동반 상승",
        ),
        "money": (
            "원·달러 환율과 국채금리 하락",
            "국제유가 브렌트유 원자재 가격 상승",
        ),
        "invest": (
            "퇴직연금 TDF ETF 수수료 비교",
            "ISA 절세 펀드 자산배분 전략",
        ),
        "industry": (
            "이차전지 배터리 소재 공급망 가동률 개선",
            "조선 방산 원전 수주 산업 성장",
        ),
        "company": (
            "테스트기업 2분기 영업이익 매출 증가",
            "샘플기업 자사주 배당 주주환원 확대",
        ),
        "tech": (
            "오픈AI 생성형 AI 소프트웨어 모델 공개",
            "클라우드 플랫폼 사이버보안 기술 강화",
        ),
        "policy": (
            "정부 수출 보조금 세제 지원책 확대",
            "한국은행 물가 고용 정책 변화",
        ),
        "real_estate": (
            "수도권 주택 공급 부동산 대책 확정",
            "서울 아파트 전세 대출 규제 변화",
        ),
    }
    rows = []
    for category_index, (expected_category, titles) in enumerate(category_titles.items()):
        for title_index, title in enumerate(titles):
            row = _news(
                external_id=f"budget-{category_index}-{title_index}",
                title=title,
                category=(
                    "global"
                    if expected_category == "market" and title_index == 1
                    else "breaking"
                ),
                published_at=base_time + timedelta(
                    minutes=(category_index * 2) + title_index
                ),
            )
            assert classify_morning_news(row) == expected_category
            rows.append(row)
    rows.append(
        _news(
            external_id="budget-other",
            title="행운 거북이 굿즈 인기",
            category="breaking",
            summary="행운을 비는 상품이 판매되고 있습니다.",
            published_at=base_time + timedelta(minutes=30),
        )
    )
    schedule_events = [
        InvestorScheduleEvent(
            key="budget-ipo",
            kind="ipo",
            company_name="IPO테크",
            title="8월 20일 · IPO테크 공모주 청약",
            summary="공모주 청약을 진행해요.",
            starts_on=date(2026, 8, 20),
            ends_on=date(2026, 8, 20),
            starts_at=None,
            detail_url="https://kind.krx.co.kr/ipo",
        ),
        InvestorScheduleEvent(
            key="budget-earnings",
            kind="earnings",
            company_name="실적전자",
            title="8월 20일 · 실적전자 실적 발표",
            summary="10:00에 2분기 실적을 발표해요.",
            starts_on=date(2026, 8, 20),
            ends_on=date(2026, 8, 20),
            starts_at=time(10, 0),
            detail_url="https://kind.krx.co.kr/ir",
        ),
    ]

    with session_factory() as db:
        db.add_all(rows)
        db.commit()
        payload = build_morning_money_briefing(
            db,
            now=now,
            schedule_events=schedule_events,
        )

    categories = payload["categories"]
    category_keys = [category["key"] for category in categories]
    assert category_keys == [key for key, _label in EXPECTED_MORNING_MONEY_CATEGORIES]
    assert [(category["key"], category["label"]) for category in categories] == list(
        EXPECTED_MORNING_MONEY_CATEGORIES
    )
    assert {"global", "other"}.isdisjoint(category_keys)
    assert MORNING_BRIEFING_TOTAL_ITEM_LIMIT == 12
    assert payload["selected_news_count"] == MORNING_BRIEFING_TOTAL_ITEM_LIMIT
    assert sum(len(category["items"]) for category in categories) == 12
    assert all(
        1 <= len(category["items"]) <= MORNING_BRIEFING_ITEMS_PER_CATEGORY
        for category in categories
    )
    body_ids = [
        item["id"]
        for category in categories
        for item in category["items"]
    ]
    assert len(body_ids) == len(set(body_ids))

    highlights = payload["highlights"]
    highlight_categories = [item["category_key"] for item in highlights]
    assert MORNING_BRIEFING_HIGHLIGHT_LIMIT == 3
    assert len(highlights) == MORNING_BRIEFING_HIGHLIGHT_LIMIT
    assert len(highlight_categories) == len(set(highlight_categories))
    assert highlight_categories.count("schedule") <= 1
    assert all("press_name" not in item for item in highlights)
    assert all(
        forbidden not in str(item["summary"])
        for category in categories
        for item in category["items"]
        for forbidden in ("모습이라고", "전망라고")
    )


def test_morning_money_highlights_are_robust_from_zero_to_three_items():
    category_keys = ("market", "money", "company")
    entries = [
        {
            "score": (10 - index, 0.0, index),
            "category_key": category_key,
            "payload": {
                "id": index + 1,
                "title": f"핵심 소식 {index + 1}",
                "category_key": category_key,
            },
        }
        for index, category_key in enumerate(category_keys)
    ]

    for item_count in range(4):
        highlights = _select_briefing_highlights(
            entries[:item_count],
            limit=MORNING_BRIEFING_HIGHLIGHT_LIMIT,
        )
        assert len(highlights) == item_count
        assert [item["title"] for item in highlights] == [
            f"핵심 소식 {index + 1}" for index in range(item_count)
        ]

    schedule_heavy_entries = [
        {
            "score": (20, 0.0, 1),
            "category_key": "schedule",
            "payload": {"id": 10, "title": "일정 1", "category_key": "schedule"},
        },
        {
            "score": (19, 0.0, 2),
            "category_key": "schedule",
            "payload": {"id": 11, "title": "일정 2", "category_key": "schedule"},
        },
        *entries,
    ]
    highlights = _select_briefing_highlights(
        schedule_heavy_entries,
        limit=MORNING_BRIEFING_HIGHLIGHT_LIMIT,
    )
    highlight_categories = [item["category_key"] for item in highlights]
    assert len(highlights) == MORNING_BRIEFING_HIGHLIGHT_LIMIT
    assert len(highlight_categories) == len(set(highlight_categories))
    assert highlight_categories.count("schedule") == 1


def test_midday_and_afternoon_editions_use_half_open_news_windows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    rows = (
        _news(
            external_id="boundary-085959",
            title="코스피 장전 수급 점검",
            category="market",
            published_at=datetime(2026, 8, 15, 8, 59, 59),
        ),
        _news(
            external_id="boundary-090000",
            title="코스피 오전 외국인 수급 개선",
            category="market",
            published_at=datetime(2026, 8, 15, 9, 0),
        ),
        _news(
            external_id="boundary-115959",
            title="코스닥 오전 거래대금 증가",
            category="market",
            published_at=datetime(2026, 8, 15, 11, 59, 59),
        ),
        _news(
            external_id="boundary-120000",
            title="코스피 오후 기관 수급 확대",
            category="market",
            published_at=datetime(2026, 8, 15, 12, 0),
        ),
        _news(
            external_id="boundary-155959",
            title="코스닥 오후 거래대금 확대",
            category="market",
            published_at=datetime(2026, 8, 15, 15, 59, 59),
        ),
        _news(
            external_id="boundary-160000",
            title="코스피 장 마감 수급 점검",
            category="market",
            published_at=datetime(2026, 8, 15, 16, 0),
        ),
    )

    with session_factory() as db:
        db.add_all(rows)
        db.commit()
        row_ids = {row.external_id: row.id for row in rows}
        midday = build_morning_money_briefing(
            db,
            now=datetime(2026, 8, 15, 12, 0, tzinfo=KST),
            items_per_category=10,
            schedule_events=[],
        )
        afternoon = build_morning_money_briefing(
            db,
            now=datetime(2026, 8, 15, 16, 0, tzinfo=KST),
            items_per_category=10,
            schedule_events=[],
        )

    midday_ids = {
        item["id"]
        for category in midday["categories"]
        for item in category["items"]
    }
    afternoon_ids = {
        item["id"]
        for category in afternoon["categories"]
        for item in category["items"]
    }
    assert midday["edition_key"] == "2026-08-15:12"
    assert midday["total_news_count"] == 2
    assert midday_ids == {row_ids["boundary-090000"], row_ids["boundary-115959"]}
    assert afternoon["edition_key"] == "2026-08-15:16"
    assert afternoon["total_news_count"] == 2
    assert afternoon_ids == {row_ids["boundary-120000"], row_ids["boundary-155959"]}
    assert midday_ids.isdisjoint(afternoon_ids)
    assert row_ids["boundary-160000"] not in afternoon_ids


def test_morning_money_briefing_keeps_only_two_items_per_category():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 12, 8, 0, tzinfo=KST)

    with session_factory() as db:
        db.add_all(
            [
                _news(
                    external_id=f"300{index}",
                    title=title,
                    category="market",
                    published_at=datetime(2026, 8, 12, index, 0),
                )
                for index, title in enumerate(
                    (
                        "코스피 외국인 매수 확대",
                        "코스닥 개인 수급 개선",
                        "코스피 거래대금 증가",
                    ),
                    start=1,
                )
            ]
        )
        db.commit()
        payload = build_morning_money_briefing(db, now=now, schedule_events=[])

    market = next(category for category in payload["categories"] if category["key"] == "market")
    assert MORNING_BRIEFING_ITEMS_PER_CATEGORY == 2
    assert market["count"] == 3
    assert len(market["items"]) == 2
    assert payload["selected_news_count"] == 2


def test_morning_money_briefing_keeps_real_estate_announcements_in_their_own_section():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 14, 8, 0, tzinfo=KST)
    real_estate_title = "수도권 부동산 공급 확대 방안 발표"

    with session_factory() as db:
        db.add_all(
            [
                _news(
                    external_id="real-estate-policy-slot",
                    title=real_estate_title,
                    category="breaking",
                    summary=(
                        "수도권 주택 공급을 확대하고 부동산 시장 안정을 유도하는 "
                        "방안이 발표됐습니다."
                    ),
                    published_at=datetime(2026, 8, 13, 19, 17),
                ),
                _news(
                    external_id="generic-policy-1",
                    title="국내 레버리지 규제, 해외 투자 문턱까지 높였다",
                    category="breaking",
                    published_at=datetime(2026, 8, 14, 4, 0),
                ),
                _news(
                    external_id="generic-policy-2",
                    title="금감원 투자 규제 강화…지원책과 세제 조정",
                    category="breaking",
                    published_at=datetime(2026, 8, 14, 3, 50),
                ),
            ]
        )
        db.commit()
        payload = build_morning_money_briefing(db, now=now, schedule_events=[])

    real_estate = next(
        category for category in payload["categories"] if category["key"] == "real_estate"
    )
    policy = next(
        category for category in payload["categories"] if category["key"] == "policy"
    )
    selected_titles = [item["title"] for item in real_estate["items"]]
    assert real_estate["label"] == "부동산"
    assert real_estate["count"] == 1
    assert selected_titles == [real_estate_title]
    assert policy["label"] == "정책·경제지표"
    assert policy["count"] == 2
    assert len(policy["items"]) == 2
    assert all(real_estate_title != item["title"] for item in policy["items"])
    real_estate_item = real_estate["items"][0]
    assert "건설·은행·리츠" in real_estate_item["why_it_matters"]


def test_morning_money_briefing_deduplicates_one_story_across_all_categories():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 12, 8, 0, tzinfo=KST)

    with session_factory() as db:
        market_angle = _news(
            external_id="4201",
            title="코스피 외국인 매수 확대 삼성전자 반도체 급등",
            category="market",
            published_at=datetime(2026, 8, 12, 5, 30),
        )
        company_angle = _news(
            external_id="4202",
            title="삼성전자 반도체 2분기 영업이익 급등 외국인 매수 확대",
            category="company",
            published_at=datetime(2026, 8, 12, 5, 20),
        )
        independent_story = _news(
            external_id="4203",
            title="원·달러 환율 하락과 국채금리 안정",
            category="fx",
            published_at=datetime(2026, 8, 12, 4, 50),
        )
        assert classify_morning_news(market_angle) == "market"
        assert classify_morning_news(company_angle) == "company"
        db.add_all([market_angle, company_angle, independent_story])
        db.commit()
        payload = build_morning_money_briefing(db, now=now, schedule_events=[])

    body_items = [
        item for category in payload["categories"] for item in category["items"]
    ]
    assert len(body_items) == 2
    assert sum("삼성전자" in item["title"] for item in body_items) == 1
    assert any("환율" in item["title"] for item in body_items)
    assert {"global", "other"}.isdisjoint(
        category["key"] for category in payload["categories"]
    )


def test_morning_money_story_dedup_handles_live_entity_and_macro_angles():
    duplicate_pairs = (
        (
            "中유니트리, 상장 첫날 460% 급등…창업자 90허우 최대부호 등극",
            "中 로봇 스타트업 유니트리 상장 첫날 460% 급등…시총 70.9조원",
        ),
        (
            "美국채금리 급등 직격탄… 코스피, 6500선 아래로",
            "미 금리 쇼크에 아시아 증시 동반 급락…코스피 5.8%↓",
        ),
        (
            "미국발 삭풍에 코스피 5% 급락…'불닭 반도체'의 반란?",
            "美국채 금리 급등에 코스피 출렁…하이닉스 주주환원 효과 주목",
        ),
        (
            "대어 오픈AI, 내년 상장한다…IPO 일정 첫 공개",
            "오픈AI CFO 2027년 상장기업 될 것…더 빨라질 수도",
        ),
    )

    for left_title, right_title in duplicate_pairs:
        assert _titles_describe_same_story(
            NewsItem(title=left_title),
            NewsItem(title=right_title),
        )

    assert _titles_describe_same_story(
        NewsItem(
            title="美국채금리 급등 직격탄… 코스피, 6500선 아래로",
            summary="코스피가 반도체 급락과 미국 장기 국채금리 충격으로 5% 넘게 빠졌어요.",
        ),
        NewsItem(
            title="채권 유탄에 반도체株 휘청…하이닉스 주주환원",
            summary="코스피 6500선이 붕괴하고 반도체주가 금리 인상 우려에 급락했어요.",
        ),
    )
    assert _titles_describe_same_story(
        NewsItem(
            title="미국발 삭풍에 코스피 5% 급락…'불닭 반도체'의 반란?",
            summary="오늘 하루 돈의 흐름을 짚어드립니다, 퇴근길머니~기자와 함께해요.",
        ),
        NewsItem(
            title="국채 금리 발작 경고음…가계·기업 충격에 선제 대응을",
            summary="주요국 국채 금리 급등에 코스피지수가 5% 이상 급락했어요.",
        ),
    )


def test_morning_money_real_estate_deal_is_not_misclassified_as_retirement_investing():
    item = NewsItem(
        title="캐나다연금 합작법인, 홍대 LC타워 인수",
        summary=(
            "캐나다연금투자위원회와 합작법인을 구성한 운용사가 "
            "상가건물을 호텔로 전환할 계획이에요."
        ),
        source_category="breaking",
    )

    assert classify_morning_news(item) == "real_estate"


def test_morning_money_multi_sector_outlook_is_industry_news():
    item = NewsItem(
        title='"3분기 실적 역대급"…반도체·차·조선 쾌청',
        summary=(
            "상장사 230곳의 3분기 매출과 영업이익 전망이 개선됐고 "
            "반도체·자동차·조선 업종이 증가세를 이끌었어요."
        ),
        source_category="breaking",
    )

    assert classify_morning_news(item) == "industry"


def test_morning_money_briefing_excludes_entertainment_and_thin_digest_items():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 12, 8, 0, tzinfo=KST)

    with session_factory() as db:
        db.add_all(
            [
                _news(
                    external_id="4301",
                    title="\uac00수 \ub2e8\ub3c5 \ucf58\uc11c\ud2b8 10\uc6d4 \uac1c\ucd5c \uc608\uc815",
                    category="breaking",
                    summary="\uc778\uae30 \uac00\uc218\uac00 10\uc6d4 \ub2e8\ub3c5 \ucf58\uc11c\ud2b8\ub97c \uac1c\ucd5c\ud558\uace0 \uad00\uac1d\uacfc \ub9cc\ub09c\ub2e4.",
                    published_at=datetime(2026, 8, 12, 5, 30),
                ),
                _news(
                    external_id="4302",
                    title="[\uc8fc\uc694\uacbd\uc81c\uc9c0\ud45c] 2026\ub144 8\uc6d4 12\uc77c\uc790",
                    category="breaking",
                    summary="2026\ub144 8\uc6d4 12\uc77c\uc790",
                    published_at=datetime(2026, 8, 12, 5, 20),
                ),
                _news(
                    external_id="4303",
                    title="\ubbf8\uad6d CPI \uc624\ub298 \ubc24 \ubc1c\ud45c \uc608\uc815",
                    category="global",
                    summary="\ubbf8\uad6d CPI \ubc1c\ud45c\uac00 \uc624\ub298 \ubc24 \uc608\uc815\ub3fc \uc788\uc5b4 \uc2dc\uc7a5 \ubcc0\ub3d9\uc131\uc774 \ucee4\uc9c8 \uc218 \uc788\ub2e4.",
                    published_at=datetime(2026, 8, 12, 5, 10),
                ),
                _news(
                    external_id="4304",
                    title="\ud589\uc6b4 \uac70\ubd81\uc774\ubd80\ud130 \ubd80\uc801\uae4c\uc9c0 \ud589\uc6b4 \uad7f\uc988 \uc778\uae30",
                    category="breaking",
                    summary="\uc80a\uc740 \uc138\ub300 \uc0ac\uc774\uc5d0\uc11c \ud589\uc6b4\uc744 \ube44\ub294 \uac70\ubd81\uc774\uc640 \ubd80\uc801 \uad7f\uc988\uac00 \uc778\uae30\ub97c \ub04c\uba70 \ub2e4\uc591\ud55c \uc0c1\ud488\uc774 \ud310\ub9e4\ub418\uace0 \uc788\ub2e4.",
                    published_at=datetime(2026, 8, 12, 5, 0),
                ),
            ]
        )
        db.commit()
        payload = build_morning_money_briefing(db, now=now, schedule_events=[])

    titles = [
        item["title"]
        for category in payload["categories"]
        for item in category["items"]
    ]
    assert titles == ["\ubbf8\uad6d CPI \uc624\ub298 \ubc24 \ubc1c\ud45c \uc608\uc815"]


def test_morning_money_schedule_prioritizes_ipo_and_earnings_calendar_items():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 12, 8, 0, tzinfo=KST)
    ipo = InvestorScheduleEvent(
        key="ipo:테스트테크:2026-08-12:2026-08-13",
        kind="ipo",
        company_name="테스트테크",
        title="8월 12~13일 · 테스트테크 공모주 청약",
        summary="공모가는 12,000원이고 테스트증권에서 청약해요.",
        starts_on=date(2026, 8, 12),
        ends_on=date(2026, 8, 13),
        starts_at=None,
        detail_url="https://kind.krx.co.kr/ipo",
    )
    earnings = InvestorScheduleEvent(
        key="earnings:테스트전자:2026-08-12:14:00",
        kind="earnings",
        company_name="테스트전자",
        title="8월 12일 · 테스트전자 실적 발표",
        summary="14:00에 테스트전자의 2분기 실적을 발표해요.",
        starts_on=date(2026, 8, 12),
        ends_on=date(2026, 8, 12),
        starts_at=time(14, 0),
        detail_url="https://kind.krx.co.kr/ir",
    )

    with session_factory() as db:
        db.add(
            _news(
                external_id="4401",
                title="미국 CPI 오늘 밤 발표 예정",
                category="global",
                published_at=datetime(2026, 8, 12, 5, 20),
            )
        )
        db.commit()
        payload = build_morning_money_briefing(
            db,
            now=now,
            schedule_events=[earnings, ipo],
        )

    schedule = next(
        category for category in payload["categories"] if category["key"] == "schedule"
    )
    assert schedule["label"] == "오늘 체크할 일정"
    assert [item["schedule_kind"] for item in schedule["items"]] == ["ipo", "earnings"]
    assert "공모주 청약" in schedule["items"][0]["title"]
    assert "실적 발표" in schedule["items"][1]["title"]
    assert all(item["summary"].endswith("요.") for item in schedule["items"])
    assert all(item["summary"].count("요.") >= 2 for item in schedule["items"])
    assert "청약 시작·마감일" in schedule["items"][0]["summary"]
    assert "발표 전후 실적 기대" in schedule["items"][1]["summary"]
    assert all("press_name" not in item for item in schedule["items"])


def test_morning_money_schedule_labels_future_only_events_as_upcoming():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 16, 8, 0, tzinfo=KST)
    future_ipo = InvestorScheduleEvent(
        key="ipo:미래테크:2026-08-18:2026-08-19",
        kind="ipo",
        company_name="미래테크",
        title="8월 18~19일 · 미래테크 공모주 청약",
        summary="8월 18~19일 동안 테스트증권에서 청약해요.",
        starts_on=date(2026, 8, 18),
        ends_on=date(2026, 8, 19),
        starts_at=None,
        detail_url="https://kind.krx.co.kr/ipo",
    )
    future_earnings = InvestorScheduleEvent(
        key="earnings:DN오토모티브:2026-08-18:09:00",
        kind="earnings",
        company_name="DN오토모티브",
        title="8월 18일 · DN오토모티브 실적 발표",
        summary="09:00에 DN오토모티브의 2분기 실적을 발표해요.",
        starts_on=date(2026, 8, 18),
        ends_on=date(2026, 8, 18),
        starts_at=time(9, 0),
        detail_url="https://kind.krx.co.kr/ir",
    )

    with session_factory() as db:
        payload = build_morning_money_briefing(
            db,
            now=now,
            schedule_events=[future_earnings, future_ipo],
        )

    schedule = next(
        category for category in payload["categories"] if category["key"] == "schedule"
    )
    assert schedule["label"] == "다가오는 주요 일정"
    assert "오늘" not in schedule["description"]
    assert [item["schedule_kind"] for item in schedule["items"]] == ["ipo", "earnings"]
    assert all(
        item["category_label"] == "다가오는 주요 일정"
        for item in payload["highlights"]
        if item["category_key"] == "schedule"
    )


def test_morning_money_schedule_prioritizes_today_and_labels_mixed_dates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    now = datetime(2026, 8, 16, 8, 0, tzinfo=KST)
    today_earnings = InvestorScheduleEvent(
        key="earnings:오늘전자:2026-08-16:10:00",
        kind="earnings",
        company_name="오늘전자",
        title="8월 16일 · 오늘전자 실적 발표",
        summary="10:00에 오늘전자의 2분기 실적을 발표해요.",
        starts_on=date(2026, 8, 16),
        ends_on=date(2026, 8, 16),
        starts_at=time(10, 0),
        detail_url="https://kind.krx.co.kr/ir",
    )
    future_ipo = InvestorScheduleEvent(
        key="ipo:내일테크:2026-08-17:2026-08-18",
        kind="ipo",
        company_name="내일테크",
        title="8월 17~18일 · 내일테크 공모주 청약",
        summary="8월 17~18일 동안 테스트증권에서 청약해요.",
        starts_on=date(2026, 8, 17),
        ends_on=date(2026, 8, 18),
        starts_at=None,
        detail_url="https://kind.krx.co.kr/ipo",
    )

    with session_factory() as db:
        payload = build_morning_money_briefing(
            db,
            now=now,
            schedule_events=[future_ipo, today_earnings],
        )

    schedule = next(
        category for category in payload["categories"] if category["key"] == "schedule"
    )
    assert schedule["label"] == "오늘·다가오는 주요 일정"
    assert [item["title"] for item in schedule["items"]] == [
        today_earnings.title,
        future_ipo.title,
    ]


def test_morning_money_history_returns_one_complete_edition_per_time_for_seven_days():
    current = datetime(2026, 8, 27, 18, 0, tzinfo=KST)
    rows: list[NewsItem] = []
    for day_offset in range(7):
        publication_date = current.date() - timedelta(days=day_offset)
        for publication_hour, source_hour in ((6, 5), (12, 11), (16, 15)):
            rows.append(
                _news(
                    external_id=f"history-{publication_date}-{publication_hour}",
                    title=f"코스피 외국인 매수 확대 {publication_date} {publication_hour}시",
                    category="market",
                    published_at=datetime.combine(
                        publication_date,
                        time(source_hour, 30),
                    ),
                )
            )

    history = build_morning_money_briefing_history(
        object(),
        now=current,
        days=7,
        news_rows=rows,
    )

    assert len(history) == 21
    assert [item["edition_key"] for item in history[:3]] == [
        "2026-08-27:16",
        "2026-08-27:12",
        "2026-08-27:06",
    ]
    assert history[-1]["edition_key"] == "2026-08-21:06"
    assert len({item["publication_date"] for item in history}) == 7
    assert all(item["selected_news_count"] == 1 for item in history)


def test_morning_money_history_endpoint_contract(monkeypatch):
    morning_money_briefing_cache.clear()
    fixed_payload = {
        "title": "오늘의 돈이 되는 소식",
        "edition": "afternoon",
        "edition_key": "2026-08-27:16",
        "edition_label": "오후판",
        "publication_date": "2026-08-27",
        "timezone": "Asia/Seoul",
        "window_start": "2026-08-27T12:00:00+09:00",
        "window_end": "2026-08-27T16:00:00+09:00",
        "published_at": "2026-08-27T16:00:00+09:00",
        "next_publication_at": "2026-08-28T06:00:00+09:00",
        "popup_start": "2026-08-27T16:00:00+09:00",
        "popup_end": "2026-08-28T06:00:00+09:00",
        "generated_at": "2026-08-27T18:00:00+09:00",
        "total_news_count": 2,
        "selected_news_count": 2,
        "opportunity_count": 1,
        "caution_count": 1,
        "highlights": [],
        "categories": [],
        "empty_message": None,
    }
    calls: list[int] = []

    def fake_history(_db, *, days):
        calls.append(days)
        return [fixed_payload]

    monkeypatch.setattr(
        "app.main.build_morning_money_briefing_history",
        fake_history,
    )
    client = TestClient(app)
    response = client.get("/briefings/morning-money/history?days=7")
    cached_response = client.get("/briefings/morning-money/history?days=7")

    assert response.status_code == 200
    assert response.json() == [fixed_payload]
    assert cached_response.json() == [fixed_payload]
    assert calls == [7]
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )


def test_morning_money_briefing_endpoint_and_dashboard_contract(monkeypatch):
    morning_money_briefing_cache.clear()
    fixed_payload = {
        "title": "오늘의 돈이 되는 소식",
        "edition": "morning",
        "edition_key": "2026-08-12:06",
        "edition_label": "오전판",
        "publication_date": "2026-08-12",
        "timezone": "Asia/Seoul",
        "window_start": "2026-08-11T16:00:00+09:00",
        "window_end": "2026-08-12T06:00:00+09:00",
        "published_at": "2026-08-12T06:00:00+09:00",
        "next_publication_at": "2026-08-12T12:00:00+09:00",
        "popup_start": "2026-08-12T06:00:00+09:00",
        "popup_end": "2026-08-12T12:00:00+09:00",
        "generated_at": "2026-08-12T08:00:00+09:00",
        "total_news_count": 1,
        "selected_news_count": 1,
        "opportunity_count": 1,
        "caution_count": 0,
        "highlights": [],
        "categories": [],
        "empty_message": None,
    }
    calls: list[str] = []

    def fake_briefing(_db):
        calls.append("build")
        return fixed_payload

    monkeypatch.setattr("app.main.build_morning_money_briefing", fake_briefing)
    client = TestClient(app)

    response = client.get("/briefings/morning-money")
    cached_response = client.get("/briefings/morning-money")
    assert response.status_code == 200
    assert cached_response.json() == fixed_payload
    assert calls == ["build"]
    assert response.json()["title"] == "오늘의 돈이 되는 소식"
    assert response.json()["edition_key"] == "2026-08-12:06"
    assert response.json()["popup_end"] == "2026-08-12T12:00:00+09:00"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"

    shell = client.get("/dashboard?view=home").text
    source = client.get("/dashboard-app-v170.js").text
    styles = client.get("/assets/dashboard/styles.css").text
    assert 'id="morning-money-popover"' in shell
    assert 'id="morning-money-briefing-view"' in shell
    assert 'id="morning-money-briefing-window"' not in shell
    assert 'id="morning-money-briefing-lead"' not in shell
    assert "전날 16시부터 오늘 6시까지" not in shell
    assert "카테고리마다 핵심 소식을 최대 2개씩" not in shell
    assert "formatMorningMoneyWindow" not in source
    assert "맥락과 투자 포인트를 함께 정리했어요" not in shell
    assert 'id="morning-money-briefing-view" class="app-page morning-money-briefing-page" data-ui-version="3.0"' in shell
    assert 'id="morning-money-overview-intro"' in shell
    assert 'id="morning-money-digest"' in shell
    assert 'id="morning-money-digest-list"' in shell
    assert "오늘 돈의 흐름 세 줄 요약" in shell
    assert 'class="morning-money-briefing-divider"' in shell
    assert 'role="separator" aria-label="경제뉴스 브리핑"' in shell
    popover_start = shell.index('<aside class="morning-money-popover"')
    popover_end = shell.index("</aside>", popover_start)
    popover = shell[popover_start:popover_end]
    assert "🪙" in popover
    assert 'aria-label="아침에 보는 돈이 되는 소식"' in popover
    assert 'class="morning-money-popover-title"' in popover
    assert '<span id="morning-money-popover-edition">아침에 보는</span>' in popover
    assert "<span>돈이 되는 소식</span>" in popover
    assert "morning-money-popover-detail" not in popover
    assert ">06<" not in popover
    assert "morning-money-popover-arrow" not in popover
    assert 'id="morning-money-category-nav"' not in shell
    assert "morning-money-metrics" not in shell
    assert "morning-money-highlights" not in shell
    assert "function shouldShowMorningMoneyBriefing" in source
    assert "hour >= 6 && hour < 15" not in source
    assert "function morningMoneyEdition" in source
    assert "function syncMorningMoneyPopoverCopy" in source
    assert 'morning: "아침에 보는"' in source
    assert 'midday: "점심에 보는"' in source
    assert 'afternoon: "오후에 보는"' in source
    assert "syncMorningMoneyPopoverCopy(now);" in source
    assert 'editionKey: `${publicationDate}:${publicationHour}`' in source
    assert "morningMoneyEdition(now).editionKey" in source
    assert "function isCurrentMorningMoneyBriefing" in source
    assert "function scheduleMorningMoneyBriefingRefresh" in source
    assert "payload.next_publication_at" in source
    assert 'state.view === "morning-briefing"' in source
    assert 'const MORNING_MONEY_BRIEFING_TIMEZONE = "Asia/Seoul";' in source
    assert "function renderMorningMoneyBriefing" in source
    assert "function refreshMorningMoneyBriefingVisibility" in source
    assert 'const list = el("ul", "morning-money-news-list");' in source
    assert 'const letter = el("p", "morning-money-news-letter", displaySummary);' in source
    assert 'summary.startsWith(safeFallbackLead)' in source
    assert 'const title = el("strong", className);' in source
    assert "function renderMorningMoneyDigest(highlights = [], categories = [])" in source
    assert ".slice(0, 3);" in source
    assert "list.replaceChildren();" in source
    assert "digest.hidden = rows.length === 0;" in source
    assert "renderMorningMoneyDigest(payload.highlights || [], categories);" in source
    assert "elements.morningMoneyOverviewIntro.textContent = presentation.intro;" in source
    item_renderer = source[
        source.index("function createMorningMoneyNewsItem"):
        source.index("function renderMorningMoneyCategories")
    ]
    assert "morning-money-news-meta" not in item_renderer
    assert "item.press_name" not in item_renderer
    assert "morningMoneyPopoverDetail" not in source
    assert "핵심 ${formatNumber(payload.selected_news_count)}개 · 2~3분" not in source
    assert "개장 전 2~3분 브리핑" not in shell
    assert 'id="morning-money-briefing-edition"' in shell
    assert "아침판 · 06:00 발행" in source
    assert "점심판 · 12:00 발행" in source
    assert "장 마감판 · 16:00 발행" in source
    assert ".morning-money-popover" in styles
    assert ".morning-money-popover-coin" in styles
    assert ".morning-money-popover-title > span" in styles
    assert ".morning-money-popover-copy small" not in styles
    assert "Morning money briefing 3.0" in styles
    assert ".morning-money-overview-intro" in styles
    assert ".morning-money-digest[hidden]" in styles
    assert ".morning-money-briefing-divider::before" in styles
    assert ".morning-money-news-item::marker" in styles
    assert ".morning-money-news-letter" in styles
    assert ".morning-money-news-meta" not in styles
