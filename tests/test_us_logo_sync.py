from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT_PATH = ROOT / "scripts" / "sync_us_stock_logos.py"
SYNC_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "sync_us_stock_logos", SYNC_SCRIPT_PATH
)
assert SYNC_SCRIPT_SPEC and SYNC_SCRIPT_SPEC.loader
SYNC_SCRIPT = importlib.util.module_from_spec(SYNC_SCRIPT_SPEC)
SYNC_SCRIPT_SPEC.loader.exec_module(SYNC_SCRIPT)
audit_logo = SYNC_SCRIPT.audit_logo
is_visually_blank_image = SYNC_SCRIPT.is_visually_blank_image


def test_visual_blank_detector_rejects_solid_or_transparent_provider_assets():
    transparent = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    solid = Image.new("RGBA", (64, 64), (244, 92, 45, 255))
    branded = solid.copy()
    ImageDraw.Draw(branded).rectangle((18, 20, 46, 44), fill="white")

    assert is_visually_blank_image(transparent)
    assert is_visually_blank_image(solid)
    assert not is_visually_blank_image(branded)


def test_logo_audit_requires_circle_fill_and_nonblank_content(tmp_path: Path):
    too_small = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(too_small).ellipse((64, 64, 192, 192), fill="#2463EB")
    too_small_path = tmp_path / "too-small.png"
    too_small.save(too_small_path)

    blank_path = tmp_path / "blank.png"
    Image.new("RGBA", (256, 256), "#F45C2D").save(blank_path)

    full_path = tmp_path / "full.png"
    full = Image.new("RGBA", (256, 256), "#F45C2D")
    ImageDraw.Draw(full).rectangle((80, 92, 176, 164), fill="white")
    full.save(full_path)

    assert audit_logo(too_small_path) == "circle fill ratio 0.5039 below 0.95"
    assert audit_logo(blank_path) == "visually blank"
    assert audit_logo(full_path) is None
