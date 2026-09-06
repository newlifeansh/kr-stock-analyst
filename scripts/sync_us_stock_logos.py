from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.official_stock_logos import (
    _image_quality_score,
    normalize_official_logo_png,
)
from app.services.us_market import US_EQUITY_UNIVERSE

LOGO_DIR = ROOT / "app" / "static" / "stock-logos"
MANIFEST_PATH = LOGO_DIR / "sources.json"
ALPHASQUARE_US_LOGO_BASE_URL = "https://file.alphasquare.co.kr/media/images/stock_logo/us"
PROVIDERS = (
    ("alphasquare", f"{ALPHASQUARE_US_LOGO_BASE_URL}/{{symbol}}.png"),
    ("financial-modeling-prep", "https://financialmodelingprep.com/image-stock/{symbol}.png"),
    ("companies-market-cap", "https://companiesmarketcap.com/img/company-logos/64/{symbol}.png"),
    ("parqet", "https://assets.parqet.com/logos/symbol/{symbol}?format=png"),
)
PROVIDER_LABELS = {
    "alphasquare": "AlphaSquare US stock logo CDN",
    "financial-modeling-prep": "Financial Modeling Prep stock image CDN",
    "companies-market-cap": "CompaniesMarketCap company logo CDN",
    "parqet": "Parqet symbol logo CDN",
}
PROVIDER_QUALITY_BONUS = {
    "alphasquare": 8,
    "financial-modeling-prep": 4,
    "companies-market-cap": 0,
    "parqet": 0,
}
OFFICIAL_HOMEPAGES = {"VMRK": "https://www.vivmark.com/"}
HEADERS = {
    "Accept": "image/png,image/*;q=0.8",
    "User-Agent": "SecretNoteUSLogoCollector/1.0",
}
MIN_CIRCLE_FILL_RATIO = 0.95


def storage_code(symbol: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", symbol.upper())


def generated_fallback_logo(symbol: str) -> bytes:
    image = Image.new("RGBA", (256, 256), "#152238")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=48, outline="#3E79D8", width=8)
    text = storage_code(symbol)[:5]
    font = ImageFont.load_default(size=48)
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(((256 - width) / 2, (256 - height) / 2), text, fill="white", font=font)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def is_visually_blank_image(image: Image.Image) -> bool:
    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").point(lambda alpha: 255 if alpha > 24 else 0).getbbox()
    if bbox is None:
        return True
    visible = rgba.crop(bbox)
    visible.thumbnail((96, 96), Image.Resampling.BILINEAR)
    raw_pixels = visible.tobytes()
    pixels = [
        tuple(raw_pixels[offset : offset + 4])
        for offset in range(0, len(raw_pixels), 4)
        if raw_pixels[offset + 3] > 24
    ]
    if not pixels:
        return True
    coverage = len(pixels) / (visible.width * visible.height)
    channel_spans = [
        max(pixel[channel] for pixel in pixels) - min(pixel[channel] for pixel in pixels)
        for channel in range(3)
    ]
    return coverage > 0.90 and max(channel_spans) < 18


def fetch_logo(
    item: dict[str, str],
    timeout_seconds: int,
) -> tuple[str, dict[str, object] | None, str | None]:
    symbol = item["code"]
    errors: list[str] = []
    candidates: list[tuple[int, dict[str, object]]] = []
    for source_kind, template in PROVIDERS:
        source_url = template.format(symbol=symbol.upper())
        try:
            response = requests.get(
                source_url,
                headers=HEADERS,
                timeout=max(3, timeout_seconds),
                allow_redirects=True,
            )
            response.raise_for_status()
            payload = bytes(response.content or b"")
            if not payload or len(payload) > 2 * 1024 * 1024:
                raise ValueError("invalid payload size")
            with Image.open(BytesIO(payload)) as source:
                source.seek(0)
                source.load()
                image = source.convert("RGBA")
            if is_visually_blank_image(image):
                raise ValueError("source image is visually blank")
            quality = _image_quality_score(image)
            if quality < 0:
                raise ValueError(f"quality score {quality}")
            png_data = normalize_official_logo_png(image, circle_fill=True)
            with Image.open(BytesIO(png_data)) as normalized:
                normalized.load()
                if normalized.size != (256, 256):
                    raise ValueError("normalized dimensions are not 256x256")
                visible_bbox = normalized.convert("RGBA").getchannel("A").getbbox()
                if visible_bbox is None:
                    raise ValueError("normalized logo is fully transparent")
                fill_ratio = max(
                    visible_bbox[2] - visible_bbox[0],
                    visible_bbox[3] - visible_bbox[1],
                ) / 256
                if fill_ratio < MIN_CIRCLE_FILL_RATIO:
                    raise ValueError(f"circle fill ratio {fill_ratio:.4f}")
            result = {
                "company_name": item["name"],
                "evidence": f"{PROVIDER_LABELS[source_kind]} · circle-fit quality score {quality}",
                "height": 256,
                "circle_fill_ratio": round(fill_ratio, 4),
                "circle_fill_status": "pass",
                "homepage_url": None,
                "image_url": source_url,
                "page_url": source_url,
                "score": quality,
                "sha256": sha256(png_data).hexdigest(),
                "source_kind": source_kind,
                "ticker": symbol,
                "width": 256,
                "visible_bbox": list(visible_bbox),
                "png_data": png_data,
            }
            selection_score = quality + PROVIDER_QUALITY_BONUS[source_kind]
            candidates.append((selection_score, result))
        except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
            errors.append(f"{source_kind}: {exc}")
    if candidates:
        _, best = max(candidates, key=lambda candidate: candidate[0])
        best["candidate_count"] = len(candidates)
        best["rejected_source_count"] = len(errors)
        return symbol, best, None
    png_data = generated_fallback_logo(symbol)
    return symbol, {
        "company_name": item["name"],
        "evidence": "No verified provider asset was available; generated deterministic ticker tile",
        "height": 256,
        "circle_fill_ratio": 1.0,
        "circle_fill_status": "pass",
        "homepage_url": OFFICIAL_HOMEPAGES.get(symbol),
        "image_url": None,
        "page_url": OFFICIAL_HOMEPAGES.get(symbol),
        "score": 0,
        "sha256": sha256(png_data).hexdigest(),
        "source_kind": "generated-fallback",
        "ticker": symbol,
        "width": 256,
        "visible_bbox": [0, 0, 256, 256],
        "png_data": png_data,
    }, None


def load_manifest() -> dict[str, dict[str, object]]:
    if not MANIFEST_PATH.is_file():
        return {}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def audit_logo(path: Path) -> str | None:
    try:
        payload = path.read_bytes()
        with Image.open(BytesIO(payload)) as image:
            image.load()
            if image.format != "PNG":
                return "not PNG"
            if image.size != (256, 256):
                return f"unexpected size {image.size}"
            rgba = image.convert("RGBA")
            if rgba.getchannel("A").getbbox() is None:
                return "fully transparent"
            visible_bbox = rgba.getchannel("A").getbbox()
            fill_ratio = max(
                visible_bbox[2] - visible_bbox[0],
                visible_bbox[3] - visible_bbox[1],
            ) / 256
            if fill_ratio < MIN_CIRCLE_FILL_RATIO:
                return f"circle fill ratio {fill_ratio:.4f} below {MIN_CIRCLE_FILL_RATIO}"
            if is_visually_blank_image(rgba):
                return "visually blank"
    except (OSError, UnidentifiedImageError) as exc:
        return str(exc)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and audit the US stock universe logos.")
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=12)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    failures: dict[str, str] = {}
    written = 0
    if not args.audit_only:
        with ThreadPoolExecutor(max_workers=max(1, min(args.max_workers, 16))) as executor:
            futures = {
                executor.submit(fetch_logo, item, args.timeout_seconds): item
                for item in US_EQUITY_UNIVERSE
            }
            for future in as_completed(futures):
                symbol, result, error = future.result()
                if result is None:
                    failures[symbol] = error or "logo unavailable"
                    continue
                png_data = result.pop("png_data")
                target = LOGO_DIR / f"{storage_code(symbol)}.png"
                target.write_bytes(png_data)
                manifest[storage_code(symbol)] = result
                written += 1
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    audit_failures: dict[str, str] = {}
    for item in US_EQUITY_UNIVERSE:
        symbol = item["code"]
        path = LOGO_DIR / f"{storage_code(symbol)}.png"
        if not path.is_file():
            audit_failures[symbol] = "missing"
            continue
        error = audit_logo(path)
        if error:
            audit_failures[symbol] = error

    summary = {
        "universe": len(US_EQUITY_UNIVERSE),
        "written": written,
        "download_failures": failures,
        "audit_failures": audit_failures,
        "ready": len(US_EQUITY_UNIVERSE) - len(audit_failures),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures or audit_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
