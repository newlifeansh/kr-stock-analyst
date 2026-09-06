from __future__ import annotations

import json
import re
import struct
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import MANUAL_STOCK_LOGO_DIR, stock_logo
from app.models import StockLogo, StockMaster
from app.schemas import StockOut
from app.services.stock_logos import (
    PNG_SIGNATURE,
    alphasquare_stock_logo_url,
    ensure_stock_logo,
    fallback_stock_logo_bytes,
    fetch_stock_logo,
    normalize_stock_logo_code,
    sync_stock_logos,
)
from app.services.us_market import US_EQUITY_UNIVERSE


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", content_type: str = "image/png"):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def add_stock(db, code: str, name: str, market: str = "KOSPI") -> None:
    db.add(StockMaster(code=code, name=name, market=market, is_active=True))
    db.commit()


def test_alphasquare_logo_url_uses_six_digit_code() -> None:
    assert alphasquare_stock_logo_url("005930") == (
        "https://file.alphasquare.co.kr/media/images/stock_logo/kr/005930.png"
    )
    assert normalize_stock_logo_code("A005930") == "005930"
    assert normalize_stock_logo_code("0001a0") == "0001A0"
    with pytest.raises(ValueError):
        normalize_stock_logo_code("AAPL")


def test_fetch_stock_logo_accepts_png_and_marks_missing() -> None:
    png = PNG_SIGNATURE + b"cached-logo"
    ready = fetch_stock_logo(
        "005930",
        fetcher=lambda *args, **kwargs: FakeResponse(200, png),
    )
    missing = fetch_stock_logo(
        "000660",
        fetcher=lambda *args, **kwargs: FakeResponse(403),
    )

    assert ready.status == "ready"
    assert ready.image_data == png
    assert ready.content_type == "image/png"
    assert missing.status == "missing"
    assert missing.image_data is None


def test_sync_stock_logos_fetches_only_uncached_active_stocks() -> None:
    db = make_session()
    add_stock(db, "005930", "삼성전자")
    add_stock(db, "000660", "SK하이닉스")
    db.add(
        StockLogo(
            stock_code="005930",
            source_url=alphasquare_stock_logo_url("005930"),
            content_type="image/png",
            image_data=PNG_SIGNATURE + b"existing",
            status="ready",
            checked_at=datetime.utcnow(),
        )
    )
    db.commit()
    requested: list[str] = []

    def fetcher(url: str, **kwargs):
        requested.append(url)
        return FakeResponse(200, PNG_SIGNATURE + b"new")

    result = sync_stock_logos(db, fetcher=fetcher, max_workers=2)

    assert result == {"candidates": 1, "ready": 1, "missing": 0, "failed": 0}
    assert requested == [alphasquare_stock_logo_url("000660")]
    assert db.get(StockLogo, "000660").image_data == PNG_SIGNATURE + b"new"
    assert db.get(StockLogo, "005930").image_data == PNG_SIGNATURE + b"existing"


def test_sync_stock_logos_skips_checked_in_official_ci_assets() -> None:
    db = make_session()
    add_stock(db, "278470", "에이피알")
    requested: list[str] = []

    result = sync_stock_logos(
        db,
        fetcher=lambda url, **_kwargs: requested.append(url),
    )

    assert result == {"candidates": 0, "ready": 0, "missing": 0, "failed": 0}
    assert requested == []


def test_missing_logo_is_negative_cached_until_retry_window() -> None:
    db = make_session()
    add_stock(db, "005930", "삼성전자")
    calls = 0

    def fetcher(url: str, **kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse(404)

    assert ensure_stock_logo(db, "005930", fetcher=fetcher) is None
    assert ensure_stock_logo(db, "005930", fetcher=fetcher) is None
    assert calls == 1
    assert db.get(StockLogo, "005930").status == "missing"


def test_stock_response_exposes_internal_logo_url() -> None:
    stock = StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True)
    payload = StockOut.model_validate(stock)

    assert payload.logo_url == "/stock-logos/005930.png"


def test_stock_logo_endpoint_returns_404_for_missing_master() -> None:
    db = make_session()

    with pytest.raises(HTTPException) as exc_info:
        stock_logo("999999", db=db)
    assert exc_info.value.status_code == 404


def test_apr_official_logo_overrides_collected_logo() -> None:
    db = make_session()

    response = stock_logo("278470", db=db)

    assert isinstance(response, FileResponse)
    assert Path(response.path) == MANUAL_STOCK_LOGO_DIR / "278470.png"
    assert response.headers["x-stock-logo-source"] == "official-manual"
    image_data = (MANUAL_STOCK_LOGO_DIR / "278470.png").read_bytes()
    assert image_data.startswith(PNG_SIGNATURE)
    assert struct.unpack(">II", image_data[16:24]) == (256, 256)


def test_fallback_stock_logo_is_a_256_pixel_png() -> None:
    image_data = fallback_stock_logo_bytes()

    assert image_data.startswith(PNG_SIGNATURE)
    assert struct.unpack(">II", image_data[16:24]) == (256, 256)


def test_every_us_equity_has_audited_checked_in_logo_and_manifest_entry() -> None:
    manifest = json.loads((MANUAL_STOCK_LOGO_DIR / "sources.json").read_text(encoding="utf-8"))
    storage_codes = [re.sub(r"[^0-9A-Z]", "", item["code"].upper()) for item in US_EQUITY_UNIVERSE]

    assert len(storage_codes) == 518
    assert len(storage_codes) == len(set(storage_codes))
    for item, storage_code in zip(US_EQUITY_UNIVERSE, storage_codes):
        image_path = MANUAL_STOCK_LOGO_DIR / f"{storage_code}.png"
        image_data = image_path.read_bytes()
        assert image_data.startswith(PNG_SIGNATURE), item["code"]
        assert struct.unpack(">II", image_data[16:24]) == (256, 256), item["code"]
        with Image.open(image_path) as image:
            visible_bbox = image.convert("RGBA").getchannel("A").getbbox()
        assert visible_bbox is not None, item["code"]
        circle_fill_ratio = max(
            visible_bbox[2] - visible_bbox[0],
            visible_bbox[3] - visible_bbox[1],
        ) / 256
        assert circle_fill_ratio >= 0.95, item["code"]
        assert manifest[storage_code]["ticker"] == item["code"]
        assert manifest[storage_code]["source_kind"] in {
            "alphasquare",
            "financial-modeling-prep",
            "companies-market-cap",
            "parqet",
            "generated-fallback",
        }
        assert manifest[storage_code]["sha256"] == sha256(image_data).hexdigest()
        assert manifest[storage_code]["width"] == 256
        assert manifest[storage_code]["height"] == 256
        assert manifest[storage_code]["circle_fill_status"] == "pass"
        assert manifest[storage_code]["circle_fill_ratio"] == pytest.approx(
            round(circle_fill_ratio, 4)
        )
        assert manifest[storage_code]["visible_bbox"] == list(visible_bbox)

    assert manifest["NVDA"]["image_url"] == (
        "https://file.alphasquare.co.kr/media/images/stock_logo/us/NVDA.png"
    )
    assert manifest["VMRK"]["circle_fill_status"] == "pass"


def test_us_logo_endpoint_serves_ticker_and_dotted_ticker_assets() -> None:
    db = make_session()

    apple = stock_logo("AAPL", db=db)
    berkshire = stock_logo("BRK.B", db=db)

    assert isinstance(apple, FileResponse)
    assert Path(apple.path) == MANUAL_STOCK_LOGO_DIR / "AAPL.png"
    assert isinstance(berkshire, FileResponse)
    assert Path(berkshire.path) == MANUAL_STOCK_LOGO_DIR / "BRKB.png"
