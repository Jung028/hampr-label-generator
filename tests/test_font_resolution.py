"""
Standalone regression test for label font fidelity (no pytest needed):

    .venv-1/bin/python tests/test_font_resolution.py

Guards the root-cause fix for labels rendering in Helvetica instead of the
template's real fonts (Arial Rounded MT Bold for the customer name,
Britannic Bold for the dish-name band).

Also guards the cross-platform fix: every font the templates use must
resolve to the repo-bundled ``fonts/`` directory, not a system font
folder — otherwise a machine without those exact fonts (e.g. a stock
Windows box) silently renders plain Arial at the wrong weight and size.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from psd.loader import load_psd
from psd.layers import find_customer_name_layer, find_dish_name_layer
from psd.text import get_font_name, find_font, load_font, _BUNDLED_FONTS_DIR

TEMPLATES = os.path.join(ROOT, "templates")

# Every PostScript font name the 53 templates reference.
ALL_TEMPLATE_FONTS = (
    "ArialRoundedMTBold",
    "Arial-BoldMT",
    "Arial-ItalicMT",
    "BritannicBold",
)

FAILURES = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILURES.append(msg)


for tpl in ("1a.BeefRendangRice.psd", "4a.HainanChicken.psd", "9a.NasiLemak.psd"):
    psd = load_psd(os.path.join(TEMPLATES, tpl))
    dish = find_dish_name_layer(psd)
    name = find_customer_name_layer(psd, dish)

    name_font = get_font_name(name)
    dish_font = get_font_name(dish)

    check(name_font is not None, f"{tpl}: customer-name font name resolves (got {name_font!r})")
    check(dish_font is not None, f"{tpl}: dish-name font name resolves (got {dish_font!r})")
    check("round" in (name_font or "").lower(),
          f"{tpl}: customer-name font is the rounded one (got {name_font!r})")
    check("britannic" in (dish_font or "").lower(),
          f"{tpl}: dish-name font is Britannic (got {dish_font!r})")

    name_path = find_font(name_font)
    dish_path = find_font(dish_font)

    check(name_path is not None and "round" in os.path.basename(name_path).lower(),
          f"{tpl}: customer-name font file found (got {name_path!r})")
    check(dish_path is not None and "britan" in os.path.basename(dish_path).lower(),
          f"{tpl}: dish-name font file found (got {dish_path!r})")


# ---------------------------------------------------------------------------
# Cross-platform: every template font resolves to the bundled fonts/ dir,
# so macOS and Windows produce identical output.
# ---------------------------------------------------------------------------

for font_name in ALL_TEMPLATE_FONTS:
    path = find_font(font_name)

    check(
        path is not None,
        f"{font_name}: resolves to a file (got {path!r})",
    )
    check(
        path is not None
        and os.path.realpath(os.path.dirname(path))
        == os.path.realpath(_BUNDLED_FONTS_DIR),
        f"{font_name}: resolves inside bundled fonts/ dir (got {path!r})",
    )

    # A real scalable font honours the requested size; the bitmap
    # fallback (the old Windows failure mode) does not.
    font = load_font(path, 75)
    ascent, descent = font.getmetrics()
    check(
        ascent + descent > 40,
        f"{font_name}: loaded at size 75 is scalable, not the bitmap "
        f"default (line height {ascent + descent}px)",
    )

print()
if FAILURES:
    print(f"{len(FAILURES)} failure(s)")
    sys.exit(1)
print("all good")
