from io import BytesIO
import json

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import CompanyProfile, StockLogo, StockMaster
from app.services.official_stock_logos import (
    backfill_official_stock_logos,
    collect_official_stock_logo,
    discover_official_logo_candidates,
    normalize_official_homepage_url,
    parse_krx_kind_official_homepages,
)


class FakeResponse:
    def __init__(
        self,
        content: bytes,
        *,
        url: str,
        content_type: str,
        status_code: int = 200,
        encoding: str = "utf-8",
    ):
        self.content = content
        self.url = url
        self.status_code = status_code
        self.encoding = encoding
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(content)),
        }

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _png(width: int, height: int, color=(20, 110, 180, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (width, height), color).save(output, format="PNG")
    return output.getvalue()


def _session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_official_homepage_normalization_rejects_dart_placeholders():
    assert (
        normalize_official_homepage_url("www.example.co.kr")
        == "https://www.example.co.kr"
    )
    assert normalize_official_homepage_url("https://-") is None
    assert normalize_official_homepage_url("없음") is None


def test_krx_kind_homepage_parser_maps_alphanumeric_stock_codes():
    payload = """
    <table>
      <tr><th>회사명</th><th>종목코드</th><th>홈페이지</th></tr>
      <tr><td>해치텍</td><td>0155E0</td><td>http://www.haechitech.com</td></tr>
      <tr><td>없음</td><td>123456</td><td>-</td></tr>
    </table>
    """.encode("euc-kr")

    assert parse_krx_kind_official_homepages(payload) == {
        "0155E0": "http://www.haechitech.com"
    }


def test_candidate_discovery_prefers_header_ci_and_large_touch_icon():
    candidates = discover_official_logo_candidates(
        """
        <link rel="apple-touch-icon" sizes="180x180" href="/touch.png">
        <header><img class="company-logo" src="/logo.svg" alt="Example CI"></header>
        <footer><img class="partner-logo" src="/partner.png" alt="partner"></footer>
        """,
        "https://example.co.kr/about",
    )

    assert [item.image_url for item in candidates[:2]] == [
        "https://example.co.kr/logo.svg",
        "https://example.co.kr/touch.png",
    ]
    assert all("partner.png" not in item.image_url for item in candidates)
    assert any(item.source_kind == "google-site-icon" for item in candidates)


def test_collection_uses_square_official_icon_over_tiny_horizontal_wordmark():
    homepage = "https://example.co.kr"
    html = b"""
      <link rel="apple-touch-icon" sizes="180x180" href="/touch.png">
      <header><img class="company-logo" src="/wide.png" alt="Example logo"></header>
    """

    def requester(url, **_kwargs):
        if url == homepage:
            return FakeResponse(html, url=url, content_type="text/html")
        if url.endswith("/touch.png"):
            return FakeResponse(_png(180, 180), url=url, content_type="image/png")
        if url.endswith("/wide.png"):
            return FakeResponse(_png(600, 50), url=url, content_type="image/png")
        return FakeResponse(
            b"missing", url=url, content_type="text/plain", status_code=404
        )

    result = collect_official_stock_logo(
        "123456",
        "예시회사",
        homepage,
        requester=requester,
    )

    assert result.status == "ready"
    assert result.image_url == "https://example.co.kr/touch.png"
    assert result.source_kind == "official-site-icon"
    assert result.png_data is not None
    with Image.open(BytesIO(result.png_data)) as image:
        assert image.size == (256, 256)
        assert image.format == "PNG"


def test_collection_rejects_homepage_redirect_to_another_registered_domain():
    def requester(url, **_kwargs):
        return FakeResponse(
            b'<link rel="icon" href="/wrong-company.png">',
            url="https://unrelated-example.com/landing",
            content_type="text/html",
        )

    result = collect_official_stock_logo(
        "123456",
        "예시회사",
        "https://example.co.kr",
        requester=requester,
    )

    assert result.status == "homepage_domain_mismatch"
    assert result.homepage_url == "https://example.co.kr"
    assert result.page_url == "https://unrelated-example.com/landing"
    assert result.png_data is None
    assert "different registered domain" in str(result.error)


def test_backfill_writes_traced_company_logo_and_excludes_etf(tmp_path):
    db = _session()
    try:
        company = StockMaster(
            code="123456", name="예시회사", market="KOSDAQ", is_active=True
        )
        etf = StockMaster(
            code="069500", name="KODEX 200", market="KOSPI", is_active=True
        )
        db.add_all([company, etf])
        db.flush()
        db.add_all(
            [
                CompanyProfile(
                    stock_code="123456",
                    corp_code="00000001",
                    corp_name="예시회사(주)",
                    homepage_url="https://example.co.kr",
                ),
                CompanyProfile(
                    stock_code="069500",
                    corp_code="00000002",
                    corp_name="KODEX 200",
                    homepage_url="https://asset.example.co.kr",
                ),
                StockLogo(
                    stock_code="123456",
                    source_url="https://old.example/logo.png",
                    status="missing",
                ),
                StockLogo(
                    stock_code="069500",
                    source_url="https://old.example/etf.png",
                    status="missing",
                ),
            ]
        )
        db.commit()

        html = b'<link rel="apple-touch-icon" sizes="192x192" href="/logo.png">'

        def requester(url, **_kwargs):
            if url == "https://example.co.kr":
                return FakeResponse(html, url=url, content_type="text/html")
            if url == "https://example.co.kr/logo.png":
                return FakeResponse(_png(192, 192), url=url, content_type="image/png")
            return FakeResponse(
                b"missing", url=url, content_type="text/plain", status_code=404
            )

        logo_dir = tmp_path / "logos"
        manifest_path = logo_dir / "sources.json"
        result = backfill_official_stock_logos(
            db,
            logo_dir=logo_dir,
            manifest_path=manifest_path,
            requester=requester,
            max_workers=1,
        )

        assert result["target"] == 1
        assert result["ready"] == 1
        assert (logo_dir / "123456.png").is_file()
        assert not (logo_dir / "069500.png").exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["123456"]["company_name"] == "예시회사"
        assert manifest["123456"]["homepage_url"] == "https://example.co.kr"
        assert manifest["123456"]["image_url"] == "https://example.co.kr/logo.png"
        assert len(manifest["123456"]["sha256"]) == 64
    finally:
        db.close()
