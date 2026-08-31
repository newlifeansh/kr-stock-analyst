from app.collectors.news import (
    naver_news_detail_url,
    normalize_naver_news_url,
    parse_naver_news_list_html,
    preferred_news_url,
)


NEWS_HTML = """
<html>
  <body>
    <ul class="realtimeNewsList">
      <li class="newsList top">
        <dl>
          <dt class="thumb">
            <a href="/news/news_read.naver?article_id=0001234567&office_id=008"><img src="https://img.test/thumb.jpg" /></a>
          </dt>
          <dd class="articleSubject">
            <a href="/news/news_read.naver?article_id=0001234567&office_id=008" title="미래에셋증권 자사주 취득">미래에셋증권 자사주 취득</a>
          </dd>
          <dd class="articleSummary">
            자사주 매입 소식에 강세
            <span class="press">머니투데이</span>
            <span class="bar">|</span>
            <span class="wdate">2026-06-17 18:03</span>
          </dd>
        </dl>
      </li>
    </ul>
  </body>
</html>
"""


def test_parse_naver_news_list_html():
    items = parse_naver_news_list_html(NEWS_HTML, "company")
    assert len(items) == 1
    item = items[0]
    assert item.source_category == "company"
    assert item.external_id == "008:0001234567"
    assert item.title == "미래에셋증권 자사주 취득"
    assert item.press_name == "머니투데이"
    assert item.summary and "자사주" in item.summary
    assert item.image_url == "https://img.test/thumb.jpg"


def test_parse_naver_news_list_html_pairs_each_grouped_subject_with_its_summary():
    grouped_html = """
    <ul class="realtimeNewsList">
      <li class="newsList top">
        <dl>
          <dt class="articleSubject">
            <a href="/news/news_read.naver?article_id=0000000001&amp;office_id=001"
               title="Lumentum earnings">Lumentum earnings</a>
          </dt>
          <dd class="articleSummary">
            Optical equipment earnings improved.
            <span class="press">Press A</span><span class="bar">|</span>
            <span class="wdate">2026-08-12 22:41</span>
          </dd>
          <dt class="thumb">
            <a href="/news/news_read.naver?article_id=0000000002&amp;office_id=002">
              <img src="https://img.test/cpi.jpg" />
            </a>
          </dt>
          <dd class="articleSubject">
            <a href="/news/news_read.naver?article_id=0000000002&amp;office_id=002"
               title="US CPI matched forecasts">US CPI matched forecasts</a>
          </dd>
          <dd class="articleSummary">
            Consumer prices matched market forecasts.
            <span class="press">Press B</span><span class="bar">|</span>
            <span class="wdate">2026-08-12 22:03</span>
          </dd>
        </dl>
      </li>
    </ul>
    """

    items = parse_naver_news_list_html(grouped_html, "global")

    assert [item.title for item in items] == [
        "Lumentum earnings",
        "US CPI matched forecasts",
    ]
    assert items[0].summary == "Optical equipment earnings improved."
    assert items[0].press_name == "Press A"
    assert items[0].image_url is None
    assert items[1].summary == "Consumer prices matched market forecasts."
    assert items[1].press_name == "Press B"
    assert items[1].image_url == "https://img.test/cpi.jpg"


def test_parse_naver_news_prefers_visible_title_when_title_attribute_is_clipped():
    malformed_title_html = '''
    <ul class="realtimeNewsList">
      <li class="newsList">
        <dl>
          <dt class="articleSubject">
            <a href="/news/news_read.naver?article_id=0005806717&amp;office_id=277"
               title="[속보]美 재무 "이란 위해 자금세탁하면 달러 시스템서 제외될 것"">
              [속보]美 재무 "이란 위해 자금세탁하면 달러 시스템서 제외될 것"
            </a>
          </dt>
          <dd class="articleSummary">
            미국 재무부 발언
            <span class="press">아시아경제</span>
            <span class="wdate">2026-08-25 02:32</span>
          </dd>
        </dl>
      </li>
    </ul>
    '''

    items = parse_naver_news_list_html(malformed_title_html, "global")

    assert items[0].title == '[속보]美 재무 "이란 위해 자금세탁하면 달러 시스템서 제외될 것"'


def test_normalize_naver_news_url_repairs_section_entity():
    url = normalize_naver_news_url(
        "/news/news_read.naver?article_id=0004633062&office_id=011&mode=LSS2D&type=0§ion_id=101§ion_id2=258"
    )
    assert url == (
        "https://finance.naver.com/news/news_read.naver?"
        "article_id=0004633062&office_id=011&mode=LSS2D&type=0&section_id=101&section_id2=258"
    )


def test_preferred_news_url_repairs_naver_news_home_link():
    assert preferred_news_url(
        "naver_finance",
        "011:0004633062",
        "https://finance.naver.com/news/",
    ) == "https://n.news.naver.com/mnews/article/011/0004633062"


def test_preferred_news_url_rewrites_legacy_finance_article_url():
    detail_url = "https://finance.naver.com/news/news_read.naver?article_id=1&office_id=2&page=3"
    assert preferred_news_url("naver_finance", "011:0004633062", detail_url) == (
        "https://n.news.naver.com/mnews/article/2/1"
    )


def test_preferred_news_url_keeps_naver_article_as_canonical_detail():
    assert preferred_news_url(
        "naver_finance",
        "011:0004648965",
        "https://n.news.naver.com/article/011/0004648965?sid=101",
    ) == "https://n.news.naver.com/mnews/article/011/0004648965"


def test_naver_news_detail_url_builds_roiter_shareholder_return_article():
    assert naver_news_detail_url("011:0004648965") == (
        "https://n.news.naver.com/mnews/article/011/0004648965"
    )
