from app.collectors.research import parse_naver_listing_html


COMPANY_HTML = """
<html>
  <body>
    <table class="type_1">
      <tr><th>header</th></tr>
      <tr><th>header</th></tr>
      <tr>
        <td><a href="/item/main.naver?code=005930">삼성전자</a></td>
        <td><a href="company_read.naver?nid=12345&page=1">반도체 업황 점검</a></td>
        <td>하나증권</td>
        <td><a href="https://stock.pstatic.net/stock-research/company/01/test.pdf">pdf</a></td>
        <td>26.06.17</td>
        <td>1,234</td>
      </tr>
    </table>
  </body>
</html>
"""


INDUSTRY_HTML = """
<html>
  <body>
    <table class="type_1">
      <tr><th>header</th></tr>
      <tr><th>header</th></tr>
      <tr>
        <td>반도체</td>
        <td><a href="industry_read.naver?nid=54321&page=1">Higher, Better, More!</a></td>
        <td>DS투자증권</td>
        <td><a href="https://stock.pstatic.net/stock-research/industry/01/test.pdf">pdf</a></td>
        <td>26.06.17</td>
        <td>2,345</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parse_company_listing_html():
    items = parse_naver_listing_html(COMPANY_HTML, "company")
    assert len(items) == 1
    item = items[0]
    assert item.company_name == "삼성전자"
    assert item.stock_code == "005930"
    assert item.title == "반도체 업황 점검"
    assert item.broker_name == "하나증권"
    assert item.external_id == "12345"
    assert item.pdf_url and item.pdf_url.endswith("test.pdf")


def test_parse_industry_listing_html():
    items = parse_naver_listing_html(INDUSTRY_HTML, "industry")
    assert len(items) == 1
    item = items[0]
    assert item.subject_name == "반도체"
    assert item.company_name is None
    assert item.title == "Higher, Better, More!"
    assert item.external_id == "54321"
