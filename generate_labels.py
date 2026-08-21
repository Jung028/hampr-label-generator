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

import json
import os
import re

from psd.loader import load_psd
from psd.layers import find_customer_name_layer, find_dish_name_layer
from psd.renderer import render_psd
from psd.text import get_font_name, get_font_size
from export.png import export_png

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
RESPONSE_BODY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "response-body.json")

HAINAN_CHICKEN_PSD = os.path.join(TEMPLATES_DIR, "4a.HainanChicken.psd")


def _layer_style(layer):
    left, top, right, bottom = layer.bbox
    return (get_font_name(layer), get_font_size(layer, bottom - top))


def _canonical_styles():
    # Hainan Chicken Rice is the reference template: the customer-name and
    # dish-name layers' font/size here are what every other template's
    # equivalent layers get forced to, so labels read consistently
    # regardless of what size the original per-template PSD text happened
    # to be set at (e.g. Beef Rendang Rice's dish-name layer is 100pt in
    # its source PSD, vs. 87pt here).
    psd = load_psd(HAINAN_CHICKEN_PSD)

    dish_layer = find_dish_name_layer(psd)
    name_layer = find_customer_name_layer(psd, dish_layer)

    return _layer_style(name_layer), _layer_style(dish_layer)


NAME_STYLE, DISH_NAME_STYLE = _canonical_styles()

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


def name_review_flags(name):
    """
    Flag a customer name as worth a human glance before printing, without
    blocking generation — the label still renders whatever the order data
    says. Catches things like stray punctuation left over from a typo or
    an accidental keystroke (e.g. "Zak ebgin =,( Hamilton"), which would
    otherwise print onto a real label unnoticed.
    """

    reasons = []

    if not name.strip():
        reasons.append("empty name")
        return reasons

    if re.search(r"[^A-Za-z\s'\-.]", name):
        reasons.append("contains unusual characters")

    if len(name.strip()) < 2:
        reasons.append("very short name")

    return reasons


def _has_option(options, needle):
    needle = needle.strip().lower()
    return any(needle in opt.strip().lower() for opt in options)


def _protein_choice(options):
    # Some dishes (e.g. Hainan Chicken) carry a redundant "Standard"
    # choice alongside the actual protein selection — skip it and return
    # the most specific choice.
    choice = options[-1].strip() if options else ""
    for opt in reversed(options):
        if opt.strip().lower() != "standard":
            choice = opt.strip()
            break

    # Cut prep-detail qualifiers like "(Sliced Pieces)" — the dish-name
    # band isn't wide enough for them and the label gets clipped (e.g.
    # "Char Kway Teow - Chicken (Sliced Pi...").
    choice = re.sub(r"\s*\([^)]*\)\s*$", "", choice).strip()

    # "Combination" also overflows the band (e.g. "Char Kway Teow -
    # Combination" gets clipped); "Combo" is sufficient and matches the
    # short form some templates already use themselves (e.g. the Siram
    # Meat template's own baked-in label is "Kway Teow Siram - Combo").
    if choice.lower() == "combination":
        choice = "Combo"

    return choice


def _find_special_instructions_layer(layer_by_name):
    # Each template's special-instructions layer ships with its own
    # example placeholder text baked into its PSD name (e.g. "Special
    # Instructions: No Chilli Please", "...: Capsicum Allergy", "...: Nut
    # Allergy"), so match by prefix rather than one fixed string.
    for name, layer in layer_by_name.items():
        if name.strip().startswith("Special Instructions"):
            return layer
    return None


def _apply_special_instructions(layer_by_name, text_layers, special_instructions):
    layer = _find_special_instructions_layer(layer_by_name)
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


def _apply_customer_name(psd, dish_layer, text_layers, customer_name):
    # Every template gives the customer-name layer its own throwaway
    # placeholder text (e.g. "Jin Ju Hong", "Anonymous", "Guest Order",
    # "Louis Lee") rather than a consistent layer name, so it can't be
    # matched by name. find_customer_name_layer() locates it positionally
    # instead: the nearest text layer directly above the dish-name layer.
    layer = find_customer_name_layer(psd, dish_layer)
    if layer is None:
        return

    text_layers.append({
        "layer": layer,
        "original_text": layer.text,
        "replacement": customer_name,
        "font_override": NAME_STYLE,
    })


def generate_label(order, psd_filename, dish_label, variant_suffix, output_dir=None):
    """
    Generic renderer used by every dish. dish_label is the printed base
    name (e.g. "Nasi Goreng"); variant_suffix, if given, is appended as
    "<dish_label> - <variant_suffix>" the same way the Hainan Chicken
    template already varies its own dish-name text by protein (e.g.
    "Hainan Chicken Rice - Thigh"). output_dir defaults to the module's
    OUTPUT_DIR, but callers (e.g. the web app) can point each run at its
    own folder instead.
    """

    if output_dir is None:
        output_dir = OUTPUT_DIR

    psd_path = os.path.join(TEMPLATES_DIR, psd_filename)
    psd = load_psd(psd_path)
    layer_by_name = {l.name.strip(): l for l in psd.descendants()}

    dish_layer = find_dish_name_layer(psd)
    replacement = f"{dish_label} - {variant_suffix}" if variant_suffix else dish_label

    text_layers = [{
        "layer": dish_layer,
        "original_text": dish_layer.text,
        "replacement": replacement,
        "font_override": DISH_NAME_STYLE,
    }]

    _apply_customer_name(psd, dish_layer, text_layers, order["customer_name"])
    _apply_special_instructions(layer_by_name, text_layers, order["special_instructions"])

    # GlutenFreeLogo defaults vary per template — some dishes (e.g. Beef
    # Rendang Rice) are gluten-free as a fixed fact and ship with the
    # layer already visible; others ship it hidden because it's a
    # genuine per-order customer choice. Either way, an explicit
    # "Gluten Free" selection should always turn it on; nothing should
    # ever force it off, since that could hide a fact the template
    # author baked in on purpose.
    gluten_free_layer = layer_by_name.get("GlutenFreeLogo")
    if gluten_free_layer is not None and _has_option(order["options"], "gluten free"):
        gluten_free_layer.visible = True

    image = render_psd(psd, text_layers)

    variant_part = f"_{_safe_filename(variant_suffix)}" if variant_suffix else ""
    out_name = f"{_safe_filename(order['customer_name'])}_{_safe_filename(dish_label)}{variant_part}.png"
    out_path = os.path.join(output_dir, out_name)
    export_png(image, out_path)
    return out_path


def _resolve_hainan_chicken(order):
    variant = "Thigh" if _has_option(order["options"], "thigh") else "Breast"
    return "4a.HainanChicken.psd", "Hainan Chicken Rice", variant


def _resolve_beef_rendang_rice(order):
    # No variant/protein choice for this dish.
    return "1a.BeefRendangRice.psd", "Beef Rendang Rice", None


def _resolve_beef_rendang_roti(order):
    return "1c.BeefRendangRoti.psd", "Beef Rendang Roti Canai", None


def _resolve_curry_chicken_rice(order):
    return "2a.Curry Chicken Rice.psd", "Curry Chicken Rice", None


def _resolve_ipoh_hor_fun(order):
    return "25a.IpohHorFun.psd", "Ipoh Hor Fun", None


def _resolve_wonton_noodle_soup(order):
    return "10a.WontonNoodleSoup.psd", "Wonton Noodle Soup", None


def _resolve_vegan_char_kway_teow(order):
    return "7b.CharKwayTeow_Vegan.psd", "Char Kway Teow", "Vegan"


def _resolve_ipoh_char_kway_teow(order):
    # This order's dish data only ever carries meat proteins (Chicken,
    # Beef, Combination) for the non-vegan "Ipoh Char Kway Teow" item —
    # the Vege template variant exists but has no observed trigger yet.
    return "7c.CharKwayTeow_Meat.psd", "Char Kway Teow", _protein_choice(order["options"])


def _resolve_mee_goreng(order):
    return "6c.MeeGoreng_Meat.psd", "Mee Goreng", _protein_choice(order["options"])


def _resolve_nasi_goreng(order):
    return "5c.NasiGoreng_Meat.psd", "Nasi Goreng", _protein_choice(order["options"])


def _resolve_wat_tan_hor(order):
    protein = _protein_choice(order["options"])
    if "tofu" in protein.lower():
        return "7d.Siram_Tofu.psd", "Kway Teow Siram", protein
    return "7e.Siram_Meat.psd", "Kway Teow Siram", protein


def _resolve_nasi_lemak(order):
    protein = _protein_choice(order["options"])
    if "beef" in protein.lower():
        return "9a.NasiLemak_Beef.psd", "Nasi Lemak", "Beef"
    return "9a.NasiLemak.psd", "Nasi Lemak", "Chicken"


def _resolve_laksa(order):
    protein = _protein_choice(order["options"])
    if "wonton" in protein.lower():
        # Matches the template's own established short label ("Laksa -
        # Wonton") rather than the order's raw "Steamed Wonton" text.
        return "8b.LaksaWonton.psd", "Laksa", "Wonton"
    return "8a.Laksa.psd", "Laksa", protein


DISH_RESOLVERS = {
    "Hainanese Chicken with Steamed Rice": _resolve_hainan_chicken,
    "Beef Rendang with Jasmine Rice": _resolve_beef_rendang_rice,
    "Beef Rendang Roti Canai": _resolve_beef_rendang_roti,
    "Chicken Curry with Jasmine Rice": _resolve_curry_chicken_rice,
    "Ipoh Hor Fun": _resolve_ipoh_hor_fun,
    "Wonton Noodle Soup": _resolve_wonton_noodle_soup,
    "Vegan Ipoh Char Kway Teow": _resolve_vegan_char_kway_teow,
    "Ipoh Char Kway Teow": _resolve_ipoh_char_kway_teow,
    "Mee Goreng": _resolve_mee_goreng,
    "Nasi Goreng": _resolve_nasi_goreng,
    "Wat Tan Hor (Kway Teow Siram)": _resolve_wat_tan_hor,
    "Nasi Lemak": _resolve_nasi_lemak,
    "Laksa": _resolve_laksa,
}


def load_orders_from_response(path):
    """
    Load and parse a captured Hampr order-detail API response file. Thin
    wrapper around parse_orders() for the common case of reading straight
    from disk (e.g. the response-body.json file dropped at the repo
    root) — see parse_orders() for the actual parsing logic, which also
    backs the web app's paste/upload flow.
    """

    with open(path) as f:
        data = json.load(f)

    return parse_orders(data)


def parse_orders(data):
    """
    Parse an already-decoded Hampr order-detail API response (a dict,
    e.g. from json.load/json.loads) into the same {customer_name,
    dish_name, options, special_instructions} shape as the hand-typed
    ORDERS list.

    Each order item can be ordered by multiple attendees, one per
    `configs` entry. Within a config, choices are grouped by rule:
    "Options" holds protein/variant selections, and — in this response
    shape — "Special instructions" is repurposed to carry the
    attendee's name as a "Name: <name>" choice rather than free text.
    """

    orders = []

    for item in data["purchaseContentDetails"]["items"]:
        dish_name = item["item"]["name"]

        for config in item["configs"]:
            options = []
            customer_name = ""

            for rule in config["config"]:
                choice_names = [c["name"] for c in rule["selectedChoices"]]

                if rule["ruleName"] == "Options":
                    options.extend(choice_names)
                elif rule["ruleName"] == "Special instructions":
                    for choice_name in choice_names:
                        if choice_name.startswith("Name:"):
                            customer_name = choice_name[len("Name:"):].strip()

            orders.append({
                "customer_name": customer_name,
                "dish_name": dish_name,
                "options": options,
                "special_instructions": "",
            })

    return orders


def process_orders(orders, output_dir=None):
    """
    Run every order through its dish resolver and generate_label(),
    without printing anything — used by both the CLI (main(), below) and
    the web app, so they share one code path. Returns:

        {
            "generated": [{"customer_name", "dish_label", "variant", "full_dish_name", "out_path"}, ...],
            "skipped": [{"customer_name", "dish_name"}, ...],
            "review_needed": [{"customer_name", "dish_label", "flags"}, ...],
        }

    full_dish_name is dish_label with its variant suffix appended (e.g.
    "Nasi Goreng - Beef"), matching the text actually printed on the
    label — the unit a kitchen-prep dish summary should count by.
    """

    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    result = {"generated": [], "skipped": [], "review_needed": []}

    for order in orders:
        resolver = DISH_RESOLVERS.get(order["dish_name"])
        if resolver is None:
            result["skipped"].append({
                "customer_name": order["customer_name"],
                "dish_name": order["dish_name"],
            })
            continue

        psd_filename, dish_label, variant_suffix = resolver(order)
        out_path = generate_label(order, psd_filename, dish_label, variant_suffix, output_dir=output_dir)

        full_dish_name = f"{dish_label} - {variant_suffix}" if variant_suffix else dish_label

        result["generated"].append({
            "customer_name": order["customer_name"],
            "dish_label": dish_label,
            "variant": variant_suffix,
            "full_dish_name": full_dish_name,
            "out_path": out_path,
        })

        flags = name_review_flags(order["customer_name"])
        if flags:
            result["review_needed"].append({
                "customer_name": order["customer_name"],
                "dish_label": dish_label,
                "flags": flags,
            })

    return result


def main():
    if os.path.exists(RESPONSE_BODY_PATH):
        orders = load_orders_from_response(RESPONSE_BODY_PATH)
    else:
        orders = ORDERS

    result = process_orders(orders, OUTPUT_DIR)

    review_flags_by_name = {
        (r["customer_name"], r["dish_label"]): r["flags"]
        for r in result["review_needed"]
    }

    for skipped in result["skipped"]:
        print(f"SKIP  {skipped['customer_name']}: no handler for dish {skipped['dish_name']!r}")

    for gen in result["generated"]:
        flags = review_flags_by_name.get((gen["customer_name"], gen["dish_label"]))
        if flags:
            print(f"OK    {gen['customer_name']} -> {gen['out_path']}  [REVIEW: {', '.join(flags)}]")
        else:
            print(f"OK    {gen['customer_name']} -> {gen['out_path']}")

    if result["review_needed"]:
        print(f"\n=== {len(result['review_needed'])} name(s) need review before printing ===")
        for r in result["review_needed"]:
            print(f"  {r['customer_name']!r} ({r['dish_label']}): {', '.join(r['flags'])}")


if __name__ == "__main__":
    main()
