from app.collectors.news import normalize_naver_news_url, parse_naver_news_list_html


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


def test_normalize_naver_news_url_repairs_section_entity():
    url = normalize_naver_news_url(
        "/news/news_read.naver?article_id=0004633062&office_id=011&mode=LSS2D&type=0§ion_id=101§ion_id2=258"
    )
    assert url == (
        "https://finance.naver.com/news/news_read.naver?"
        "article_id=0004633062&office_id=011&mode=LSS2D&type=0&section_id=101&section_id2=258"
    )
