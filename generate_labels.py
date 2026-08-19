"""
Generates print-ready label PNGs from Hampr order data.

This is the standalone rendering engine, ported from the
catering-label-automation prototype's psd-parsing/icon-toggle logic
(psd/loader.py, psd/layers.py, psd/text.py, psd/renderer.py). It has no
dependency on that repo's (currently broken) backend.

There is no live scrape source yet — the ORDERS list below is typed in
by hand from a real Hampr "Orders" page screenshot, standing in for what
a browser extension will eventually POST here. Once page access is
available, replace ORDERS with real scraped data using the same shape.
"""

import os

from psd.loader import load_psd
from psd.renderer import render_psd
from export.png import export_png

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

HAINAN_CHICKEN_PSD = os.path.join(TEMPLATES_DIR, "4a.HainanChicken.psd")
BEEF_RENDANG_PSD = os.path.join(TEMPLATES_DIR, "1a.BeefRendangRice.psd")

# Typed in by hand from the Hampr Orders page screenshot.
ORDERS = [
    {
        "customer_name": "Elmira Naghizadeh",
        "dish_name": "Hainanese Chicken with Steamed Rice",
        "options": ["Chicken Thigh"],
        "special_instructions": "add extra chilli on the side please",
    },
    {
        "customer_name": "ebony stanley",
        "dish_name": "Hainanese Chicken with Steamed Rice",
        "options": ["Gluten Free", "Chicken Breast"],
        "special_instructions": "",
    },
    {
        "customer_name": "Tye Grieve",
        "dish_name": "Beef Rendang with Jasmine Rice",
        "options": [],
        "special_instructions": "",
    },
    {
        "customer_name": "Chris Browne",
        "dish_name": "Beef Rendang with Jasmine Rice",
        "options": [],
        "special_instructions": "",
    },
]


def _safe_filename(value):
    return "".join(c if c.isalnum() else "_" for c in value).strip("_")


def _has_option(options, needle):
    needle = needle.strip().lower()
    return any(needle in opt.strip().lower() for opt in options)


def _apply_special_instructions(layer_by_name, text_layers, special_instructions):
    layer = layer_by_name.get("Special Instructions: No Chilli Please")
    if layer is None:
        return

    special_instructions = special_instructions.strip()
    layer.visible = bool(special_instructions)

    if special_instructions:
        text_layers.append({
            "layer": layer,
            "original_text": layer.text,
            "replacement": special_instructions,
        })


def _apply_customer_name(layer_by_name, text_layers, customer_name):
    # The "Name" layer's own PSD name carries trailing whitespace/CRs
    # left over from the template's original placeholder text, so match
    # by prefix rather than an exact string.
    for name, layer in layer_by_name.items():
        if name.strip().startswith(("Name", "Jin Ju Hong")):
            text_layers.append({
                "layer": layer,
                "original_text": layer.text,
                "replacement": customer_name,
            })
            return


def generate_hainan_chicken(order):
    psd = load_psd(HAINAN_CHICKEN_PSD)
    layer_by_name = {l.name.strip(): l for l in psd.descendants()}

    variant = "Thigh" if _has_option(order["options"], "thigh") else "Breast"

    dish_layer = layer_by_name["Hainan Chicken Rice - Breast"]
    text_layers = [{
        "layer": dish_layer,
        "original_text": dish_layer.text,
        "replacement": f"Hainan Chicken Rice - {variant}",
    }]

    _apply_customer_name(layer_by_name, text_layers, order["customer_name"])
    _apply_special_instructions(layer_by_name, text_layers, order["special_instructions"])

    # GlutenFreeLogo is off by default on this template — it's a genuine
    # per-order customer choice here, not a fixed dish attribute.
    layer_by_name["GlutenFreeLogo"].visible = _has_option(order["options"], "gluten free")

    image = render_psd(psd, text_layers)

    out_name = f"{_safe_filename(order['customer_name'])}_Hainan_Chicken_Rice_-_{variant}.png"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    export_png(image, out_path)
    return out_path


def generate_beef_rendang(order):
    psd = load_psd(BEEF_RENDANG_PSD)
    layer_by_name = {l.name.strip(): l for l in psd.descendants()}

    # No variant/protein choice for this dish, and GlutenFreeLogo is
    # visible=True by default here — Beef Rendang Rice is gluten-free as
    # a fixed fact of the dish, not a customer-selected option (matches
    # the "Gluten Free" + "Halal Friendly" tags shown as dish-level
    # badges, not under a per-order "Options:" line, on the real page).
    dish_layer = layer_by_name["Beef Rendang Rice"]
    text_layers = [{
        "layer": dish_layer,
        "original_text": dish_layer.text,
        "replacement": "Beef Rendang Rice",
    }]

    _apply_customer_name(layer_by_name, text_layers, order["customer_name"])
    _apply_special_instructions(layer_by_name, text_layers, order["special_instructions"])

    image = render_psd(psd, text_layers)

    out_name = f"{_safe_filename(order['customer_name'])}_Beef_Rendang_Rice.png"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    export_png(image, out_path)
    return out_path


DISH_HANDLERS = {
    "Hainanese Chicken with Steamed Rice": generate_hainan_chicken,
    "Beef Rendang with Jasmine Rice": generate_beef_rendang,
}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for order in ORDERS:
        handler = DISH_HANDLERS.get(order["dish_name"])
        if handler is None:
            print(f"SKIP  {order['customer_name']}: no handler for dish {order['dish_name']!r}")
            continue

        out_path = handler(order)
        print(f"OK    {order['customer_name']} -> {out_path}")


if __name__ == "__main__":
    main()
