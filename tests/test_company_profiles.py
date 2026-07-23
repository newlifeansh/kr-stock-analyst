from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.models import DisclosureItem, StockMaster
from app.services import company_profiles


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _report_archive() -> bytes:
    document = """
    <DOCUMENT>
      <TITLE>II. 사업의 내용</TITLE>
      <TITLE>1. 사업의 개요</TITLE>
      <TITLE>2. 주요 제품 및 서비스</TITLE>
      <TITLE>III. 재무에 관한 사항</TITLE>
      <TITLE>II. 사업의 내용</TITLE>
      <TITLE>1. 사업의 개요</TITLE>
      <P>당사는 메모리 반도체 제품을 개발하고 생산하여 국내외 고객에게 판매하는 사업을 영위하고 있습니다.</P>
      <P>주요 제품은 디램과 낸드플래시이며 인공지능 서버 시장을 위한 고대역폭 메모리 사업을 확대하고 있습니다.</P>
      <TITLE>2. 주요 제품 및 서비스</TITLE>
      <P>세계 최초 신제품 개발 성과와 세부 사양을 제품별로 나열하는 내용입니다.</P>
      <TITLE>III. 재무에 관한 사항</TITLE>
      <P>연결재무제표 내용입니다.</P>
    </DOCUMENT>
    """
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("report.xml", document)
    return buffer.getvalue()


def test_extract_business_summary_uses_business_section_only():
    summary = company_profiles.extract_business_summary(_report_archive())

    assert summary is not None
    assert "메모리 반도체" in summary
    assert "고대역폭 메모리" in summary
    assert "연결재무제표" not in summary


def test_company_profile_is_collected_from_dart_and_stored(monkeypatch):
    db = _session()
    try:
        stock = StockMaster(
            code="000660",
            name="SK하이닉스",
            market="KOSPI",
            sector="전기전자",
            industry="반도체 제조업",
        )
        disclosure = DisclosureItem(
            source="dart",
            external_id="20260701000001",
            disclosure_category="filings",
            company_name="SK하이닉스",
            stock_code="000660",
            corp_code="00164779",
            report_name="사업보고서 (2025.12)",
        )
        db.add_all([stock, disclosure])
        db.commit()

        def fake_json(url, _params, timeout=30):
            if url == company_profiles.DART_COMPANY_URL:
                return {
                    "status": "000",
                    "corp_name": "에스케이하이닉스(주)",
                    "corp_name_eng": "SK hynix Inc.",
                    "ceo_nm": "곽노정",
                    "corp_cls": "Y",
                    "adres": "경기도 이천시",
                    "hm_url": "www.skhynix.com",
                    "ir_url": "news.skhynix.co.kr/ir",
                    "induty_code": "26120",
                    "est_dt": "19491015",
                    "acc_mt": "12",
                    "modify_date": "20260701",
                }
            assert url == company_profiles.DART_DISCLOSURE_LIST_URL
            return {
                "status": "000",
                "list": [
                    {
                        "rcept_no": "20260318000123",
                        "report_nm": "사업보고서 (2025.12)",
                        "rcept_dt": "20260318",
                    }
                ],
            }

        monkeypatch.setattr(company_profiles, "fetch_opendart_json", fake_json)
        monkeypatch.setattr(company_profiles, "fetch_opendart_bytes", lambda *_args, **_kwargs: _report_archive())

        profile = company_profiles.ensure_company_profile(
            db,
            stock,
            settings=Settings(dart_api_key="test-key"),
        )
        payload = company_profiles.company_profile_payload(db, stock)

        assert profile is not None
        assert profile.summary_source == "dart_business_report"
        assert "메모리 반도체" in (profile.business_summary or "")
        assert payload["ceo_name"] == "곽노정"
        assert payload["short_summary"] == "주력 분야는 디램과 낸드플래시입니다."
        assert payload["industry"] == "반도체 제조업"
        assert payload["source_label"] == "DART 사업보고서"
        assert payload["source_url"].endswith("20260318000123")
    finally:
        db.close()
