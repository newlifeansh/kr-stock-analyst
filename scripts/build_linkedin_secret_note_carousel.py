from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "linkedin" / "secret-note-mvp"
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
CANVAS_SIZE = (1080, 1350)

INK = "#101828"
MUTED = "#667085"
SURFACE = "#F6F7F9"
WHITE = "#FFFFFF"
RED = "#ED2B3A"
BLUE = "#1477D4"
GREEN = "#12A873"
BORDER = "#DFE3E8"
DARK = "#111827"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    indexes = {"regular": 0, "medium": 2, "semibold": 4, "bold": 6, "extra": 14}
    return ImageFont.truetype(FONT_PATH, size=size, index=indexes[weight])


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def paste_phone(
    canvas: Image.Image,
    screenshot_path: Path,
    *,
    width: int,
    y: int,
    border: int = 12,
) -> tuple[int, int, int, int]:
    source = Image.open(screenshot_path).convert("RGB")
    height = round(width * source.height / source.width)
    source = source.resize((width, height), Image.Resampling.LANCZOS)
    outer_w = width + border * 2
    outer_h = height + border * 2
    x = (CANVAS_SIZE[0] - outer_w) // 2

    shadow = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    shadow_mask = rounded_mask((outer_w, outer_h), 34)
    shadow_shape = Image.new("RGBA", (outer_w, outer_h), (16, 24, 40, 72))
    shadow_shape.putalpha(shadow_mask.point(lambda value: round(value * 0.28)))
    shadow.alpha_composite(shadow_shape, (x, y + 18))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    canvas.alpha_composite(shadow)

    frame = Image.new("RGBA", (outer_w, outer_h), WHITE)
    frame.putalpha(rounded_mask((outer_w, outer_h), 34))
    canvas.alpha_composite(frame, (x, y))

    screenshot = source.convert("RGBA")
    screenshot.putalpha(rounded_mask((width, height), 25))
    canvas.alpha_composite(screenshot, (x + border, y + border))
    return x, y, outer_w, outer_h


def draw_header(
    draw: ImageDraw.ImageDraw,
    *,
    eyebrow: str,
    title: str,
    description: str,
    dark: bool = False,
) -> None:
    main_color = WHITE if dark else INK
    muted_color = "#CBD5E1" if dark else MUTED
    draw.text((72, 54), "비밀노트", font=font(27, "bold"), fill=main_color)

    draw.text((72, 128), eyebrow, font=font(24, "bold"), fill=RED if dark else BLUE)
    draw.multiline_text(
        (72, 171),
        title,
        font=font(56, "extra"),
        fill=main_color,
        spacing=8,
    )
    title_lines = title.count("\n") + 1
    description_y = 171 + title_lines * 68 + 18
    draw.text((72, description_y), description, font=font(27, "medium"), fill=muted_color)


def new_canvas(background: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    canvas = Image.new("RGBA", CANVAS_SIZE, background)
    return canvas, ImageDraw.Draw(canvas)


def save(canvas: Image.Image, filename: str) -> None:
    canvas.convert("RGB").save(OUTPUT_DIR / filename, "PNG", optimize=True)


def build_cover() -> None:
    canvas, draw = new_canvas(DARK)
    draw.text((72, 58), "SECRET NOTE · KOREA MARKET", font=font(22, "bold"), fill="#94A3B8")
    draw.text((72, 118), "한국증시\n비밀노트", font=font(78, "extra"), fill=WHITE, spacing=3)
    draw.multiline_text(
        (72, 302),
        "데이터가 기준을 만들고,\nAI가 확인 순서를 정리합니다.",
        font=font(34, "semibold"),
        fill="#D8DEE9",
        spacing=8,
    )
    paste_phone(canvas, OUTPUT_DIR / "raw-home.png", width=360, y=465, border=10)
    save(canvas, "01-secret-note-cover.png")


def build_feature_slide(
    *,
    filename: str,
    screenshot: str,
    eyebrow: str,
    title: str,
    description: str,
    page: str,
) -> None:
    canvas, draw = new_canvas(SURFACE)
    draw_header(draw, eyebrow=eyebrow, title=title, description=description)
    paste_phone(canvas, OUTPUT_DIR / screenshot, width=400, y=380)
    draw.text((72, 1301), page, font=font(22, "bold"), fill=MUTED)
    draw.line((127, 1315, 1008, 1315), fill=BORDER, width=2)
    save(canvas, filename)


def build_cta_slide() -> None:
    canvas, draw = new_canvas(DARK)
    draw_header(
        draw,
        eyebrow="05 · SMART ALERTS",
        title="중요한 변화가 생기면\n알림으로 확인합니다",
        description="AI 모델 신호 · 급등락 · 공시 · 리포트",
        dark=True,
    )
    paste_phone(canvas, OUTPUT_DIR / "raw-alerts.png", width=330, y=385, border=10)
    save(canvas, "06-secret-note-invite.png")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_cover()
    build_feature_slide(
        filename="02-secret-note-watchlist.png",
        screenshot="raw-watchlist.png",
        eyebrow="01 · WATCHLIST",
        title="내 종목의 우선순위를\n먼저 보여줍니다",
        description="AI 시황 브리핑 · 먼저 볼 종목 · 오늘의 대응",
        page="01 / 05",
    )
    build_feature_slide(
        filename="03-secret-note-stock-detail.png",
        screenshot="raw-stock-home.png",
        eyebrow="02 · STOCK DETAIL",
        title="한 종목에 필요한 근거를\n한 화면에 모았습니다",
        description="가격 · 거래량 · 수급 · 리포트 · 뉴스",
        page="02 / 05",
    )
    build_feature_slide(
        filename="04-secret-note-ai-signal.png",
        screenshot="raw-ai-signal.png",
        eyebrow="03 · AI MODEL SIGNAL",
        title="신호만 보여주지 않고\n판단 기준까지 함께",
        description="모델 매수·보유·매도 · 최근 1년 모의검증",
        page="03 / 05",
    )
    build_feature_slide(
        filename="05-secret-note-market-impact.png",
        screenshot="raw-market-impact.png",
        eyebrow="04 · MARKET IMPACT",
        title="흩어진 시장 변수를\n관계로 읽습니다",
        description="위험자산 · 원자재 · 금리 · 채권 · 달러 영향",
        page="04 / 05",
    )
    build_cta_slide()


if __name__ == "__main__":
    main()
