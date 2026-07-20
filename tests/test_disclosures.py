from app.collectors.disclosures import classify_disclosure_category, fetch_dart_disclosures, fetch_dart_web_disclosures
from app.config import Settings


def test_fetch_dart_web_disclosures(monkeypatch):
    html = """
    <html>
      <body>
        <tbody id="today_all_list">
          <tr>
            <td><span class="webOnly">2026.06.18</span>10:15</td>
            <td class="tL"><span class="webOnly">코스닥시장</span></td>
            <td class="tL ellipsis">
              <a href="javascript:openCorpInfoNew('01085026', 'winCorpInfo', '/dsae001/selectPopup.ax');">유진테크놀로지</a>
            </td>
            <td class="tL ellipsis">
              <a href="/dsaf001/main.do?rcpNo=20260618900140">단일판매ㆍ공급계약체결(자율공시)</a>
            </td>
          </tr>
        </tbody>
      </body>
    </html>
    """

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        return Response(html)

    monkeypatch.setattr("app.collectors.disclosures.requests.get", fake_get)

    items = fetch_dart_web_disclosures()
    assert len(items) == 1
    assert items[0].external_id == "20260618900140"
    assert items[0].company_name == "유진테크놀로지"
    assert items[0].corp_code == "01085026"
    assert items[0].corp_class == "K"
    assert items[0].disclosure_category == "supply_contract"
    assert items[0].detail_url == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260618900140"


def test_classify_disclosure_category():
    assert classify_disclosure_category("기업설명회(IR) 개최(안내공시)") == "ir"
    assert classify_disclosure_category("영업(잠정)실적(공정공시)") == "earnings_flash"
    assert classify_disclosure_category("임원ㆍ주요주주특정증권등소유상황보고서") == "insider_trade"
    assert classify_disclosure_category("주식등의대량보유상황보고서") == "major_holder"
    assert classify_disclosure_category("현금ㆍ현물배당결정") == "dividend"
    assert classify_disclosure_category("자기주식취득결정") == "treasury_stock"
    assert classify_disclosure_category("단일판매ㆍ공급계약체결") == "supply_contract"
    assert classify_disclosure_category("신규시설투자등") == "facility_investment"
    assert classify_disclosure_category("유상증자결정") == "rights_offering"
    assert classify_disclosure_category("사업보고서 (2025.12)") == "business_report"


def test_fetch_dart_disclosures_falls_back_to_web_when_api_key_is_invalid(monkeypatch):
    html = """
    <html>
      <body>
        <tbody id="today_all_list">
          <tr>
            <td><span class="webOnly">2026.06.19</span>09:15</td>
            <td class="tL"><span class="webOnly">유가증권시장</span></td>
            <td class="tL ellipsis">
              <a href="javascript:openCorpInfoNew('00120182', 'winCorpInfo', '/dsae001/selectPopup.ax');">NH투자증권</a>
            </td>
            <td class="tL ellipsis">
              <a href="/dsaf001/main.do?rcpNo=20260619000032">증권발행실적보고서</a>
            </td>
          </tr>
        </tbody>
      </body>
    </html>
    """

    class Response:
        def __init__(self, text=""):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *args, **kwargs):
        return Response(text=html)

    def fake_fetch_json(*args, **kwargs):
        return {"status": "010", "message": "등록되지 않은 인증키입니다."}

    monkeypatch.setattr("app.collectors.disclosures.requests.get", fake_get)
    monkeypatch.setattr("app.collectors.disclosures.fetch_opendart_json", fake_fetch_json)

    result = fetch_dart_disclosures(
        settings=Settings(dart_api_key="invalid-test-key"),
        days_back=7,
        page_count=100,
    )

    assert result.requested_source == "dart_api"
    assert result.resolved_source == "dart_web"
    assert result.message == "등록되지 않은 인증키입니다."
    assert len(result.items) == 1
    assert result.items[0].company_name == "NH투자증권"


def test_fetch_dart_disclosures_uses_api_when_transport_succeeds(monkeypatch):
    def fake_fetch_json(*args, **kwargs):
        return {
            "status": "000",
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "corp_cls": "Y",
                    "report_nm": "사업보고서 (2025.12)",
                    "rcept_no": "20260619000123",
                    "flr_nm": "삼성전자",
                    "rcept_dt": "20260619",
                    "rm": "유",
                }
            ],
        }

    monkeypatch.setattr("app.collectors.disclosures.fetch_opendart_json", fake_fetch_json)

    result = fetch_dart_disclosures(
        settings=Settings(dart_api_key="valid-test-key"),
        days_back=7,
        page_count=100,
    )

    assert result.requested_source == "dart_api"
    assert result.resolved_source == "dart_api"
    assert result.message is None
    assert len(result.items) == 1
    assert result.items[0].source == "dart_api"
    assert result.items[0].external_id == "20260619000123"
