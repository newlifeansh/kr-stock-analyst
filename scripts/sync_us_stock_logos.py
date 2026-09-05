from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sys

from PIL import Image, UnidentifiedImageError
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.official_stock_logos import (  # noqa: E402
    _image_quality_score,
    normalize_official_logo_png,
)
from app.services.us_market import US_EQUITY_UNIVERSE  # noqa: E402


LOGO_DIR = ROOT / "app" / "static" / "stock-logos"
MANIFEST_PATH = LOGO_DIR / "sources.json"
PROVIDERS = (
    ("financial-modeling-prep", "https://financialmodelingprep.com/image-stock/{symbol}.png"),
    ("companies-market-cap", "https://companiesmarketcap.com/img/company-logos/256/{symbol}.png"),
    ("parqet", "https://assets.parqet.com/logos/symbol/{symbol}?format=png"),
)
HEADERS = {
    "Accept": "image/png,image/*;q=0.8",
    "User-Agent": "SecretNoteUSLogoCollector/1.0",
}


def storage_code(symbol: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", symbol.upper())


def provider_symbol(symbol: str) -> str:
    return symbol.upper().replace(".", "-")


def fetch_logo(item: dict[str, str], timeout_seconds: int) -> tuple[str, dict[str, object] | None, str | None]:
    symbol = item["code"]
    candidate = provider_symbol(symbol)
    errors: list[str] = []
    for source_kind, template in PROVIDERS:
        source_url = template.format(symbol=candidate)
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
            quality = _image_quality_score(image)
            if quality < 0:
                raise ValueError(f"quality score {quality}")
            png_data = normalize_official_logo_png(image)
            with Image.open(BytesIO(png_data)) as normalized:
                normalized.load()
                if normalized.size != (256, 256):
                    raise ValueError("normalized dimensions are not 256x256")
            return symbol, {
                "company_name": item["name"],
                "evidence": f"public US equity logo CDN · normalized quality score {quality}",
                "height": 256,
                "homepage_url": None,
                "image_url": source_url,
                "page_url": source_url,
                "score": quality,
                "sha256": sha256(png_data).hexdigest(),
                "source_kind": source_kind,
                "ticker": symbol,
                "width": 256,
                "png_data": png_data,
            }, None
        except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
            errors.append(f"{source_kind}: {exc}")
    return symbol, None, "; ".join(errors)


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
            if len(set(rgba.resize((16, 16)).getdata())) < 2:
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
