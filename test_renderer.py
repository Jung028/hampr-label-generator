"""
Checks for the special-instructions text fitter in psd/renderer.py:
shrink-to-fit (a long note drops font size instead of being cut) and the
tightened single line spacing.

Plain-script style: run directly, prints PASS/FAIL, exits non-zero on any
failure.
"""

import sys

from psd.renderer import _line_advance, _load_font_cached, fit_text_to_box
from psd.text import find_font

_failures = 0


def check(label, condition):
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"{status} {label}")


FONT_PATH = find_font("Arial-BoldMT")
check("bundled test font resolves", bool(FONT_PATH))

BASE = 25
WIDTH = 760

SHORT = "No onion please"
LONG = (
    "Please make this one extra spicy with plenty of fresh chilli, and "
    "leave off the spring onion and coriander garnish on top, and put the "
    "sauce on the side if you can - thank you so much!"
)


# ---- line spacing -------------------------------------------------

_font = _load_font_cached(FONT_PATH, BASE)
_ascent, _descent = _font.getmetrics()
check(
    "line advance is single-spaced (== ascent + descent, no extra leading)",
    _line_advance(_font) == _ascent + _descent,
)
check(
    "line advance is well under the old doubled value",
    _line_advance(_font) < (_ascent + _descent) + int(BASE * 1.2),
)


# ---- shrink to fit ----------------------------------------------

# Plenty of vertical room: a short note stays at the template size.
font, lines = fit_text_to_box(SHORT, FONT_PATH, BASE, WIDTH, top=0, max_bottom=400)
check("short note keeps the base font size", font.size == BASE)
check("short note is one line", len(lines) == 1)
check("short note is not truncated", "…" not in "".join(lines))

# Long note + a box too short for it at 25px but roomy enough once shrunk:
# it must come out whole (no ellipsis) at a smaller size.
font, lines = fit_text_to_box(LONG, FONT_PATH, BASE, WIDTH, top=0, max_bottom=70)
joined = " ".join(lines)
check("long note shrinks below the base font size", font.size < BASE)
check("long note stays at or above the 60% floor", font.size >= int(BASE * 0.6))
check("long note is rendered in full, not truncated", "…" not in joined)
check(
    "long note keeps its first and last words",
    joined.startswith("Please make") and joined.rstrip().endswith("so much!"),
)

# Narrow box, far too short for the note even at the floor size: fall
# back to truncation with an ellipsis rather than overflow.
font, lines = fit_text_to_box(LONG, FONT_PATH, BASE, width=220, top=0, max_bottom=50)
check("impossible box: still returns at least one line", len(lines) >= 1)
check("impossible box: last line ends with an ellipsis", lines[-1].endswith("…"))
check("impossible box: bottoms out at the floor size", font.size == int(BASE * 0.6))

# min_font_size floor is honoured when supplied explicitly.
font, _ = fit_text_to_box(
    LONG, FONT_PATH, BASE, WIDTH, top=0, max_bottom=60, min_font_size=18
)
check("explicit min_font_size is a hard floor", font.size >= 18)


print()
if _failures:
    print(f"{_failures} failure(s)")
    sys.exit(1)
print("all good")
