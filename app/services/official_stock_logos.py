from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageChops, UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.opendart import fetch_opendart_json
from app.models import CompanyProfile, DisclosureItem, StockLogo, StockMaster
from app.services.company_profiles import DART_COMPANY_URL, dart_corp_code_map
from app.services.etf_profiles import is_likely_etf_name

OFFICIAL_STOCK_LOGO_DIR = Path(__file__).resolve().parents[1] / "static" / "stock-logos"
OFFICIAL_STOCK_LOGO_MANIFEST = OFFICIAL_STOCK_LOGO_DIR / "sources.json"
KRX_KIND_LISTED_COMPANIES_URL = (
    "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"
)
OFFICIAL_LOGO_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 "
    "SecretNoteOfficialLogoCollector/1.0"
)
MAX_HTML_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MIN_SOURCE_EDGE = 24
OUTPUT_SIZE = 256
OUTPUT_INSET = 20
INVALID_HOMEPAGE_VALUES = {
    "-",
    "--",
    ".",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "www",
    "www.",
    "없음",
    "해당없음",
}
IMAGE_URL_PATTERN = re.compile(
    r"(?:url\(\s*)?[\"']?([^\"')\s]+\.(?:png|jpe?g|gif|webp|svg|ico)(?:\?[^\"')\s]*)?)[\"']?\s*\)?",
    flags=re.IGNORECASE,
)
POSITIVE_LOGO_PATTERN = re.compile(
    r"(?:^|[\W_\-])(logo|logotype|brand|ci|symbol|identity|emblem|wordmark|"
    r"로고|심볼|브랜드|씨아이)(?:$|[\W_\-])",
    flags=re.IGNORECASE,
)
NEGATIVE_LOGO_PATTERN = re.compile(
    r"(?:family|partner|customer|client|award|certif|korea[_-]?logo|payment|banner|"
    r"kcp|ssl[_-]?logo|escrow|inicis|nicepay|premium|promotion|advert|track|logo[_-]?line|"
    r"wa[_-]?logo|accessibility|blog|kosdaq|krx|growing|sitemap|background|section[_-]?bg|"
    r"main[_-]?brand|brand[_-]?item|imgpopup|popup|photo|puma|"
    r"kakao|naver|instagram|youtube|facebook|linkedin)",
    flags=re.IGNORECASE,
)
KOREAN_SECOND_LEVEL_DOMAINS = {
    "co.kr",
    "go.kr",
    "ne.kr",
    "or.kr",
    "pe.kr",
    "re.kr",
}


@dataclass(frozen=True)
class OfficialLogoCandidate:
    image_url: str
    page_url: str
    source_kind: str
    semantic_score: int
    evidence: str


@dataclass(frozen=True)
class OfficialLogoCollectionResult:
    code: str
    company_name: str
    status: str
    homepage_url: str | None = None
    homepage_source: str | None = None
    page_url: str | None = None
    image_url: str | None = None
    source_kind: str | None = None
    evidence: str | None = None
    png_data: bytes | None = None
    score: int | None = None
    error: str | None = None


def normalize_official_homepage_url(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw.lower().rstrip("/") in INVALID_HOMEPAGE_VALUES:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw.lstrip('/')}"
    parsed = urlparse(raw)
    hostname = str(parsed.hostname or "").strip().lower().rstrip(".")
    if (
        not hostname
        or "." not in hostname
        or hostname in INVALID_HOMEPAGE_VALUES
        or any(char.isspace() for char in hostname)
    ):
        return None
    return raw


def parse_krx_kind_official_homepages(payload: bytes) -> dict[str, str]:
    try:
        html = payload.decode("euc-kr")
    except UnicodeDecodeError:
        html = payload.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tr")
    if not rows:
        return {}
    headers = [cell.get_text(" ", strip=True) for cell in rows[0].select("th,td")]
    try:
        code_index = headers.index("종목코드")
        homepage_index = headers.index("홈페이지")
    except ValueError:
        return {}
    mapping: dict[str, str] = {}
    for row in rows[1:]:
        cells = row.select("td")
        if len(cells) <= max(code_index, homepage_index):
            continue
        code = re.sub(
            r"[^0-9A-Z]", "", cells[code_index].get_text(" ", strip=True).upper()
        )
        homepage = normalize_official_homepage_url(
            cells[homepage_index].get_text(" ", strip=True)
        )
        if re.fullmatch(r"[0-9A-Z]{6}", code) and homepage:
            mapping[code] = homepage
    return mapping


def fetch_krx_kind_official_homepages(
    *,
    timeout_seconds: int = 20,
    requester: Callable[..., requests.Response] = requests.get,
) -> dict[str, str]:
    response = requester(
        KRX_KIND_LISTED_COMPANIES_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "User-Agent": OFFICIAL_LOGO_USER_AGENT,
        },
        timeout=max(2, timeout_seconds),
        allow_redirects=True,
    )
    response.raise_for_status()
    return parse_krx_kind_official_homepages(
        _response_bytes(response, maximum=MAX_HTML_BYTES)
    )


def _absolute_image_url(page_url: str, raw_url: object) -> str | None:
    value = str(raw_url or "").strip().strip("\"'")
    if not value or value.startswith(("data:", "javascript:", "blob:")):
        return None
    absolute = urljoin(page_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return absolute


def _candidate_text(node: Any, raw_url: str) -> str:
    attrs = getattr(node, "attrs", {}) or {}
    values: list[str] = [raw_url]
    for key in ("alt", "title", "class", "id", "rel", "aria-label"):
        value = attrs.get(key)
        if isinstance(value, (list, tuple)):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    parent = getattr(node, "parent", None)
    for _ in range(4):
        parent_attrs = getattr(parent, "attrs", {}) or {}
        for key in ("class", "id", "aria-label"):
            value = parent_attrs.get(key)
            if isinstance(value, (list, tuple)):
                values.extend(str(item) for item in value)
            elif value:
                values.append(str(value))
        parent = getattr(parent, "parent", None)
    return " ".join(values)


def _registered_domain_hint(url: str) -> str:
    hostname = str(urlparse(url).hostname or "").lower().rstrip(".")
    labels = [label for label in hostname.split(".") if label]
    if len(labels) <= 2:
        return hostname
    suffix = ".".join(labels[-2:])
    if suffix in KOREAN_SECOND_LEVEL_DOMAINS and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix


def _add_candidate(
    candidates: dict[str, OfficialLogoCandidate],
    *,
    page_url: str,
    raw_url: object,
    source_kind: str,
    semantic_score: int,
    evidence: str,
) -> None:
    absolute = _absolute_image_url(page_url, raw_url)
    if not absolute:
        return
    candidate = OfficialLogoCandidate(
        image_url=absolute,
        page_url=page_url,
        source_kind=source_kind,
        semantic_score=semantic_score,
        evidence=evidence[:500],
    )
    previous = candidates.get(absolute)
    if previous is None or candidate.semantic_score > previous.semantic_score:
        candidates[absolute] = candidate


def discover_official_logo_candidates(
    html: str, page_url: str
) -> list[OfficialLogoCandidate]:
    soup = BeautifulSoup(html or "", "html.parser")
    base = soup.find("base", href=True)
    resolved_page_url = urljoin(page_url, base.get("href")) if base else page_url
    candidates: dict[str, OfficialLogoCandidate] = {}

    for node in soup.find_all("link", href=True):
        rel = " ".join(str(value).lower() for value in (node.get("rel") or []))
        if "icon" not in rel:
            continue
        raw_url = str(node.get("href") or "")
        sizes = str(node.get("sizes") or "").lower()
        score = 84 if "apple-touch-icon" in rel else 64
        if re.search(r"(?:128|144|152|180|192|256|512)x", sizes):
            score += 20
        if raw_url.lower().endswith(".svg"):
            score += 8
        _add_candidate(
            candidates,
            page_url=resolved_page_url,
            raw_url=raw_url,
            source_kind="official-site-icon",
            semantic_score=score,
            evidence=f"link rel={rel} sizes={sizes}",
        )

    for node in soup.find_all("meta"):
        property_name = str(node.get("property") or node.get("name") or "").lower()
        if property_name not in {"og:image", "twitter:image", "twitter:image:src"}:
            continue
        raw_url = str(node.get("content") or "")
        evidence = f"{property_name} {raw_url}"
        if not POSITIVE_LOGO_PATTERN.search(evidence):
            continue
        _add_candidate(
            candidates,
            page_url=resolved_page_url,
            raw_url=raw_url,
            source_kind="official-site-social-image",
            semantic_score=72,
            evidence=evidence,
        )

    for node in soup.find_all(("img", "source")):
        raw_values: list[str] = []
        for attribute in ("src", "data-src", "data-lazy-src", "data-original"):
            if node.get(attribute):
                raw_values.append(str(node.get(attribute)))
        srcset = str(node.get("srcset") or node.get("data-srcset") or "")
        if srcset:
            raw_values.extend(
                part.strip().split(" ", 1)[0]
                for part in srcset.split(",")
                if part.strip()
            )
        for raw_url in raw_values:
            evidence = _candidate_text(node, raw_url)
            positive = bool(POSITIVE_LOGO_PATTERN.search(evidence))
            if not positive and node.name != "img":
                continue
            score = 104 if positive else 12
            lowered = evidence.lower()
            if any(
                token in lowered
                for token in ("header", "navbar", "gnb", "standard-logo")
            ):
                score += 16
            if any(token in lowered for token in ("symbol", "emblem", "mark")):
                score += 12
            if any(
                token in lowered for token in ("white", "light", "footer", "foot-logo")
            ):
                score -= 34
            if NEGATIVE_LOGO_PATTERN.search(evidence):
                continue
            if score < 20:
                continue
            _add_candidate(
                candidates,
                page_url=resolved_page_url,
                raw_url=raw_url,
                source_kind="official-site-logo",
                semantic_score=score,
                evidence=evidence,
            )

    for node in soup.find_all(style=True):
        style = str(node.get("style") or "")
        evidence = _candidate_text(node, style)
        if not POSITIVE_LOGO_PATTERN.search(evidence):
            continue
        for match in IMAGE_URL_PATTERN.finditer(style):
            _add_candidate(
                candidates,
                page_url=resolved_page_url,
                raw_url=match.group(1),
                source_kind="official-site-logo",
                semantic_score=88,
                evidence=evidence,
            )

    _add_candidate(
        candidates,
        page_url=resolved_page_url,
        raw_url="/favicon.ico",
        source_kind="official-site-icon",
        semantic_score=18,
        evidence="conventional favicon path",
    )
    homepage = normalize_official_homepage_url(page_url)
    if homepage:
        hostname = urlparse(homepage).hostname or ""
        _add_candidate(
            candidates,
            page_url=resolved_page_url,
            raw_url=(
                "https://www.google.com/s2/favicons"
                f"?domain_url=https://{hostname}&sz={OUTPUT_SIZE}"
            ),
            source_kind="google-site-icon",
            semantic_score=8,
            evidence=f"Google site icon for official domain {hostname}",
        )
    return sorted(
        candidates.values(),
        key=lambda item: (-item.semantic_score, item.image_url),
    )


def _response_bytes(response: requests.Response, *, maximum: int) -> bytes:
    declared = response.headers.get("content-length")
    if declared:
        try:
            if int(declared) > maximum:
                raise ValueError("response exceeds size limit")
        except ValueError as exc:
            if str(exc) == "response exceeds size limit":
                raise
    payload = bytes(response.content or b"")
    if len(payload) > maximum:
        raise ValueError("response exceeds size limit")
    return payload


def _svg_to_png(payload: bytes) -> bytes:
    try:
        import cairosvg  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("SVG logo requires the optional CairoSVG package") from exc
    try:
        return bytes(cairosvg.svg2png(bytestring=payload, output_width=1024))
    except Exception as exc:
        raise ValueError("SVG logo could not be rendered") from exc


def _load_source_image(
    payload: bytes, content_type: str, image_url: str
) -> Image.Image:
    is_svg = "svg" in content_type.lower() or image_url.lower().split("?", 1)[
        0
    ].endswith(".svg")
    raster_payload = _svg_to_png(payload) if is_svg else payload
    try:
        with Image.open(BytesIO(raster_payload)) as source:
            source.seek(0)
            source.load()
            return source.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("response is not a supported image") from exc


def _visible_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return alpha.point(lambda value: 255 if value > 10 else 0).getbbox()
    corners = (
        image.getpixel((0, 0)),
        image.getpixel((image.width - 1, 0)),
        image.getpixel((0, image.height - 1)),
        image.getpixel((image.width - 1, image.height - 1)),
    )
    if all(min(pixel[:3]) >= 238 for pixel in corners):
        difference = ImageChops.difference(
            image.convert("RGB"),
            Image.new("RGB", image.size, (255, 255, 255)),
        ).convert("L")
        content_bbox = difference.point(
            lambda value: 255 if value > 12 else 0
        ).getbbox()
        if content_bbox:
            return content_bbox
    return image.getbbox()


def _is_light_only_transparent_logo(image: Image.Image) -> bool:
    if image.getchannel("A").getextrema()[0] == 255:
        return False
    sample = image.copy()
    sample.thumbnail((128, 128), Image.Resampling.BILINEAR)
    visible_pixels = [
        (red, green, blue) for red, green, blue, alpha in sample.getdata() if alpha > 24
    ]
    if not visible_pixels:
        return False
    near_white = sum(
        1
        for red, green, blue in visible_pixels
        if min(red, green, blue) >= 235
        and max(red, green, blue) - min(red, green, blue) < 18
    )
    return near_white / len(visible_pixels) > 0.96


def normalize_official_logo_png(image: Image.Image) -> bytes:
    if image.width < MIN_SOURCE_EDGE or image.height < MIN_SOURCE_EDGE:
        raise ValueError("source logo is too small")
    if image.width > 8192 or image.height > 8192:
        raise ValueError("source logo dimensions are unsafe")
    bbox = _visible_bbox(image)
    if not bbox:
        raise ValueError("source logo is empty")
    visible = image.crop(bbox)
    maximum = OUTPUT_SIZE - (OUTPUT_INSET * 2)
    scale = min(maximum / visible.width, maximum / visible.height)
    resized = visible.resize(
        (max(1, round(visible.width * scale)), max(1, round(visible.height * scale))),
        Image.Resampling.LANCZOS,
    )
    background = (
        (24, 31, 43, 255) if _is_light_only_transparent_logo(image) else (0, 0, 0, 0)
    )
    canvas = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), background)
    left = (OUTPUT_SIZE - resized.width) // 2
    top = (OUTPUT_SIZE - resized.height) // 2
    canvas.alpha_composite(resized, (left, top))
    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _image_quality_score(image: Image.Image) -> int:
    bbox = _visible_bbox(image)
    if not bbox:
        return -10_000
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if width < MIN_SOURCE_EDGE or height < MIN_SOURCE_EDGE:
        return -10_000
    shortest = min(width, height)
    longest = max(width, height)
    aspect = longest / shortest
    score = 0
    if shortest >= 192:
        score += 34
    elif shortest >= 128:
        score += 26
    elif shortest >= 64:
        score += 14
    elif shortest >= 32:
        score += 4
    if aspect <= 1.25:
        score += 32
    elif aspect <= 1.8:
        score += 22
    elif aspect <= 3.2:
        score += 8
    elif aspect > 10:
        score -= 20
    elif aspect > 6:
        score -= 10
    if image.getchannel("A").getextrema()[0] < 255:
        score += 6
        if _is_light_only_transparent_logo(image):
            score -= 12
    return score


def collect_official_stock_logo(
    code: str,
    company_name: str,
    homepage_url: object,
    *,
    homepage_source: str = "company-profile",
    timeout_seconds: int = 12,
    requester: Callable[..., requests.Response] = requests.get,
) -> OfficialLogoCollectionResult:
    homepage = normalize_official_homepage_url(homepage_url)
    if homepage is None:
        return OfficialLogoCollectionResult(
            code=code,
            company_name=company_name,
            status="no_homepage",
            homepage_source=homepage_source,
            error="official homepage is unavailable",
        )
    request_headers = {
        "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/png,image/*;q=0.8,*/*;q=0.5",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6",
        "User-Agent": OFFICIAL_LOGO_USER_AGENT,
    }
    page_error: str | None = None
    try:
        response = requester(
            homepage,
            headers=request_headers,
            timeout=max(2, timeout_seconds),
            allow_redirects=True,
        )
        response.raise_for_status()
        html_payload = _response_bytes(response, maximum=MAX_HTML_BYTES)
        page_url = str(getattr(response, "url", None) or homepage)
        if _registered_domain_hint(page_url) != _registered_domain_hint(homepage):
            return OfficialLogoCollectionResult(
                code=code,
                company_name=company_name,
                status="homepage_domain_mismatch",
                homepage_url=homepage,
                homepage_source=homepage_source,
                page_url=page_url,
                error="official homepage redirected to a different registered domain",
            )
        html = html_payload.decode(response.encoding or "utf-8", errors="replace")
    except Exception as exc:
        # A regulator-reported official domain can have legacy TLS or bot defenses.
        # The conventional favicon and Google's cache remain safe, domain-bound fallbacks.
        page_error = str(exc)[:500]
        page_url = homepage
        html = ""

    best: tuple[int, OfficialLogoCandidate, bytes] | None = None
    candidate_errors: list[str] = []
    for candidate in discover_official_logo_candidates(html, page_url)[:18]:
        try:
            image_response = requester(
                candidate.image_url,
                headers={
                    **request_headers,
                    "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.9,*/*;q=0.3",
                    "Referer": candidate.page_url,
                },
                timeout=max(2, timeout_seconds),
                allow_redirects=True,
            )
            image_response.raise_for_status()
            payload = _response_bytes(image_response, maximum=MAX_IMAGE_BYTES)
            content_type = str(image_response.headers.get("content-type") or "")
            image = _load_source_image(payload, content_type, candidate.image_url)
            total_score = candidate.semantic_score + _image_quality_score(image)
            if total_score < 42:
                raise ValueError("image candidate quality is too low")
            png_data = normalize_official_logo_png(image)
        except Exception as exc:
            candidate_errors.append(f"{candidate.image_url}: {exc}")
            continue
        if best is None or total_score > best[0]:
            best = (total_score, candidate, png_data)

    if best is None:
        return OfficialLogoCollectionResult(
            code=code,
            company_name=company_name,
            status="homepage_failed" if page_error else "logo_missing",
            homepage_url=homepage,
            homepage_source=homepage_source,
            page_url=page_url,
            error=(
                "; ".join(([page_error] if page_error else []) + candidate_errors[:4])[
                    :1000
                ]
                or "official logo candidate was not found"
            ),
        )
    score, candidate, png_data = best
    return OfficialLogoCollectionResult(
        code=code,
        company_name=company_name,
        status="ready",
        homepage_url=homepage,
        homepage_source=homepage_source,
        page_url=candidate.page_url,
        image_url=candidate.image_url,
        source_kind=candidate.source_kind,
        evidence=candidate.evidence,
        png_data=png_data,
        score=score,
    )


def resolve_dart_official_homepage(
    stock_code: str,
    corp_mapping: dict[str, str],
    *,
    api_key: str,
    timeout_seconds: int = 12,
    fetcher: Callable[..., dict[str, object]] = fetch_opendart_json,
) -> str | None:
    corp_code = str(corp_mapping.get(stock_code) or "").strip()
    if not corp_code or not api_key:
        return None
    for attempt in range(4):
        try:
            payload = fetcher(
                DART_COMPANY_URL,
                {"crtfc_key": api_key, "corp_code": corp_code},
                timeout=max(2, timeout_seconds),
            )
        except Exception:
            payload = {}
        status = str(payload.get("status") or "")
        if status == "000":
            return normalize_official_homepage_url(payload.get("hm_url"))
        if status not in {"020", "800", "900"}:
            return None
        if attempt < 3:
            time.sleep(0.35 * (2**attempt))
    return None


def _load_manifest(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_manifest(path: Path, payload: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def official_logo_targets(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    codes: Iterable[str] | None = None,
    logo_dir: Path = OFFICIAL_STOCK_LOGO_DIR,
    overwrite: bool = False,
) -> list[tuple[StockMaster, str | None]]:
    market_values = [
        value.strip().upper() for value in markets.split(",") if value.strip()
    ]
    requested_codes = {
        str(value).strip().upper() for value in (codes or []) if str(value).strip()
    }
    statement = (
        select(StockMaster, CompanyProfile.homepage_url)
        .outerjoin(StockLogo, StockLogo.stock_code == StockMaster.code)
        .outerjoin(CompanyProfile, CompanyProfile.stock_code == StockMaster.code)
        .where(StockMaster.is_active.is_(True))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if market_values:
        statement = statement.where(StockMaster.market.in_(market_values))
    if requested_codes:
        statement = statement.where(StockMaster.code.in_(requested_codes))
    elif not overwrite:
        statement = statement.where(
            or_(
                StockLogo.stock_code.is_(None),
                StockLogo.status != "ready",
                StockLogo.image_data.is_(None),
            )
        )
    targets: list[tuple[StockMaster, str | None]] = []
    for stock, homepage_url in db.execute(statement).all():
        if is_likely_etf_name(stock.name):
            continue
        if not overwrite and (logo_dir / f"{stock.code}.png").is_file():
            continue
        targets.append((stock, homepage_url))
    return targets


def backfill_official_stock_logos(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    codes: Iterable[str] | None = None,
    limit: int | None = None,
    max_workers: int = 4,
    timeout_seconds: int = 12,
    logo_dir: Path = OFFICIAL_STOCK_LOGO_DIR,
    manifest_path: Path = OFFICIAL_STOCK_LOGO_MANIFEST,
    overwrite: bool = False,
    discover_homepages: bool = True,
    requester: Callable[..., requests.Response] = requests.get,
    kind_requester: Callable[..., requests.Response] = requests.get,
    dart_fetcher: Callable[..., dict[str, object]] = fetch_opendart_json,
) -> dict[str, object]:
    targets = official_logo_targets(
        db,
        markets=markets,
        codes=codes,
        logo_dir=logo_dir,
        overwrite=overwrite,
    )
    if limit is not None:
        targets = targets[: max(0, limit)]
    summary: dict[str, object] = {
        "target": len(targets),
        "ready": 0,
        "no_homepage": 0,
        "homepage_failed": 0,
        "homepage_domain_mismatch": 0,
        "logo_missing": 0,
        "errors": {},
    }
    if not targets:
        return summary

    logo_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)
    settings = get_settings()
    missing_homepage_codes = {
        stock.code
        for stock, homepage_url in targets
        if normalize_official_homepage_url(homepage_url) is None
    }
    kind_homepages: dict[str, str] = {}
    if discover_homepages and missing_homepage_codes:
        try:
            kind_homepages = fetch_krx_kind_official_homepages(
                timeout_seconds=max(20, timeout_seconds),
                requester=kind_requester,
            )
        except Exception:
            kind_homepages = {}
    corp_mapping: dict[str, str] = {}
    if (
        discover_homepages
        and settings.dart_api_key
        and any(
            normalize_official_homepage_url(homepage_url) is None
            for _, homepage_url in targets
        )
    ):
        target_codes = [stock.code for stock, _ in targets]
        corp_mapping.update(
            {
                str(stock_code): str(corp_code)
                for stock_code, corp_code in db.execute(
                    select(DisclosureItem.stock_code, DisclosureItem.corp_code)
                    .where(DisclosureItem.stock_code.in_(target_codes))
                    .where(DisclosureItem.corp_code.is_not(None))
                    .distinct()
                ).all()
                if stock_code and corp_code
            }
        )
        if any(code not in corp_mapping for code in target_codes):
            try:
                corp_mapping.update(dart_corp_code_map(settings))
            except Exception:
                pass

    def collect_target(stock: StockMaster, homepage_url: object):
        resolved_homepage = normalize_official_homepage_url(homepage_url)
        homepage_source = "company-profile"
        if resolved_homepage is None and discover_homepages:
            resolved_homepage = kind_homepages.get(stock.code)
            if resolved_homepage:
                homepage_source = "krx-kind"
        if (
            resolved_homepage is None
            and discover_homepages
            and settings.dart_api_key
            and corp_mapping
        ):
            resolved_homepage = resolve_dart_official_homepage(
                stock.code,
                corp_mapping,
                api_key=settings.dart_api_key,
                timeout_seconds=timeout_seconds,
                fetcher=dart_fetcher,
            )
            if resolved_homepage:
                homepage_source = "opendart"
        return collect_official_stock_logo(
            stock.code,
            stock.name,
            resolved_homepage,
            homepage_source=homepage_source,
            timeout_seconds=timeout_seconds,
            requester=requester,
        )

    worker_count = min(max(1, max_workers), len(targets))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                collect_target,
                stock,
                homepage_url,
            ): stock
            for stock, homepage_url in targets
        }
        for future in as_completed(futures):
            stock = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = OfficialLogoCollectionResult(
                    code=stock.code,
                    company_name=stock.name,
                    status="logo_missing",
                    error=str(exc)[:500],
                )
            summary[result.status] = int(summary.get(result.status, 0)) + 1
            if result.status != "ready" or not result.png_data or not result.image_url:
                errors = summary["errors"]
                assert isinstance(errors, dict)
                errors[result.code] = result.error or result.status
                continue
            output_path = logo_dir / f"{result.code}.png"
            output_path.write_bytes(result.png_data)
            manifest[result.code] = {
                "company_name": result.company_name,
                "homepage_url": result.homepage_url,
                "homepage_source": result.homepage_source,
                "page_url": result.page_url,
                "image_url": result.image_url,
                "source_kind": result.source_kind,
                "evidence": result.evidence,
                "score": result.score,
                "sha256": sha256(result.png_data).hexdigest(),
                "width": OUTPUT_SIZE,
                "height": OUTPUT_SIZE,
            }
    _write_manifest(manifest_path, manifest)
    return summary
