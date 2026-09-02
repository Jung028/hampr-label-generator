"""
Standalone regression test for label font fidelity (no pytest needed):

    .venv-1/bin/python test_font_resolution.py

Guards the root-cause fix for labels rendering in Helvetica instead of the
template's real fonts (Arial Rounded MT Bold for the customer name,
Britannic Bold for the dish-name band).
"""

import os
import sys

from psd.loader import load_psd
from psd.layers import find_customer_name_layer, find_dish_name_layer
from psd.text import get_font_name, find_font

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

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

print()
if FAILURES:
    print(f"{len(FAILURES)} failure(s)")
    sys.exit(1)
print("all good")
