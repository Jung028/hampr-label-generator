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


def _canonical_name_style():
    # Hainan Chicken Rice is the reference template for the *customer-name*
    # layer only: every template's name layer is 75pt Arial Rounded MT
    # Bold, so forcing them all to this one value is a harmless
    # consistency guard.
    #
    # The dish-name layer is deliberately NOT normalised — each template's
    # band was authored at its own size (Beef Rendang Rice 100pt, Hainan
    # 87pt, Beef Rendang Roti 83pt) and we now render each at its native
    # size so it matches that template's original artwork.
    psd = load_psd(HAINAN_CHICKEN_PSD)

    dish_layer = find_dish_name_layer(psd)
    name_layer = find_customer_name_layer(psd, dish_layer)

    return _layer_style(name_layer)


NAME_STYLE = _canonical_name_style()

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

    # Longer vegetarian/vegan descriptive phrases (e.g. "Gluten Free &
    # Vegetarian", "Vegetable, Egg & Tofu") also overflow the band, and
    # the dish-resolver template routing (see _resolve_protein_line_psd)
    # keys off these same two category words — normalize to one of them
    # so the printed label and the template choice always agree.
    lowered = choice.lower()
    if "vegan" in lowered:
        choice = "Vegan"
    elif "vegetarian" in lowered or "vegetable" in lowered:
        choice = "Vegetable"
    elif "," in choice:
        # Any other multi-ingredient combo choice — the first ingredient
        # alone is enough to identify the variant.
        choice = choice.split(",")[0].strip()

    return choice


# Crustaceans (shellfish) icon rules — see docs/ALLERGEN_RULES.md for the
# full writeup of why each dish is grouped the way it is.
#
# Mee Goreng and Nasi Goreng's sauces are sambal-based (sambal is made
# with shrimp paste), so every protein variant contains shellfish
# regardless of what protein was actually chosen — unless the order
# explicitly leaves the prawn/shrimp out, which means the sambal itself
# was left out too.
_SAMBAL_BASED_DISHES = {"Mee Goreng", "Nasi Goreng"}

# Char Kway Teow and Wat Tan Hor ("Kway Teow Siram") use a soy-sauce base
# with no sambal — Crustaceans here reflects only whether the chosen
# protein is itself a shellfish (prawn/seafood/combo).
_SOY_SAUCE_BASED_DISHES = {"Char Kway Teow", "Kway Teow Siram"}

# The rules above only apply to the "meat line" protein choices; a
# vegetable/vegan/tofu variant already has its own dedicated template
# with the correct facts baked in and must be left untouched.
_MEAT_LINE_PROTEIN_KEYWORDS = ("chicken", "beef", "prawn", "seafood", "combo")

_SHELLFISH_PROTEIN_KEYWORDS = ("prawn", "seafood", "combo")


def _is_meat_line_protein(protein):
    protein = protein.lower()
    return any(k in protein for k in _MEAT_LINE_PROTEIN_KEYWORDS)


def _protein_is_shellfish(protein):
    protein = protein.lower()
    return any(k in protein for k in _SHELLFISH_PROTEIN_KEYWORDS)


def _mentions(text, *phrases):
    text = text.lower()
    return any(phrase in text for phrase in phrases)


def _parse_name_choice(choice_name):
    """
    Parse a "Special instructions" choice repurposed to carry the
    attendee's name, optionally followed by a free-text comment on its
    own line (e.g. "Name: John Hollister\nComment: no rice"), into
    (name, comment). comment is "" when the choice carries no comment
    line.
    """

    text = choice_name[len("Name:"):].strip()
    name_part, _, rest = text.partition("\n")

    comment = ""
    rest = rest.strip()
    if rest.startswith("Comment:"):
        comment = rest[len("Comment:"):].strip()

    return name_part.strip(), comment


_CAPS_RUN_RE = re.compile(r"[A-Z]{2,}")


def _clean_name_word(word):
    # Fix obvious case artifacts from however the customer typed their
    # name into the order form: ALL CAPS, all lowercase, or a caps-lock
    # run stuck onto part of a word (e.g. "siVARAJAH"). Leave a word
    # alone if it's already a plausible mixed-case name (e.g. "McDonald",
    # "O'Brien") — those only ever have a single embedded capital, never
    # a run of two or more, so they never match here.
    if not word.isalpha():
        return word
    if word.isupper() or word.islower() or _CAPS_RUN_RE.search(word):
        return word.capitalize()
    return word


def normalize_customer_name(name):
    return " ".join(_clean_name_word(w) for w in name.split(" "))


def _find_special_instructions_layer(layer_by_name):
    # Each template's special-instructions layer ships with its own
    # example placeholder text baked into its PSD name (e.g. "Special
    # Instructions: No Chilli Please", "...: Capsicum Allergy", "...: Nut
    # Allergy"), so match by prefix rather than one fixed string.
    for name, layer in layer_by_name.items():
        if name.strip().startswith("Special Instructions"):
            return layer
    return None


def _find_layer_below(all_layers, reference_layer):
    _, _, _, ref_bottom = reference_layer.bbox
    candidates = [
        layer for layer in all_layers
        if layer is not reference_layer and layer.bbox[1] >= ref_bottom
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda layer: layer.bbox[1])


_SAFETY_LABELS = (
    ("coeliac", "Coeliac"),
    ("celiac", "Coeliac"),
    ("gluten", "Gluten Free"),
    ("shellfish", "Shellfish Allergy"),
    ("nut", "Nut Allergy"),
    ("dairy", "Dairy Free"),
    ("halal", "Halal"),
    ("vegan", "Vegan"),
    ("vegetarian", "Vegetarian"),
    ("egg", "Egg Allergy"),
)

_ACTIONABLE_PREFIXES = (
    "no ", "no/less", "less ", "more ", "extra ", "add ", "please",
    "spicy", "mild", "hot",
)


def _extract_key_phrase(text):
    # When a comment is too long to fit the label at full size, pull out
    # just the key words instead of shrinking the font to cram in the
    # whole thing. Two kinds of key words, in priority order:
    #
    # 1. Allergy/dietary-safety facts (coeliac, shellfish, gluten, ...)
    #    anywhere in the text, reduced to a short canonical tag ("Coeliac"
    #    rather than quoting the whole "Chris is a coeliac (GF)" clause)
    #    — this box is often only wide enough for a couple of words, and
    #    a safety fact is what the kitchen can least afford to lose if
    #    the result still has to be truncated to fit.
    # 2. Actionable requests ("No Onions", "Please add chicken"), taken
    #    from splitting on sentence/line breaks plus " - " and " and " so
    #    a single long run-on sentence still breaks into short clauses.
    #    Question segments ("...can it be flagged?") are dropped since
    #    they're not an instruction for the kitchen.
    #
    # Falls back to the original text unchanged if nothing matches, so
    # the caller's normal truncation still applies.
    lowered_text = text.lower()
    safety = []

    for keyword, label in _SAFETY_LABELS:
        if keyword in lowered_text and label not in safety:
            safety.append(label)

    if not safety and "allerg" in lowered_text:
        safety.append("Allergy")

    segments = re.split(r"[\n.!]+|\s+-\s+|\band\b", text)
    actionable = []

    for segment in segments:
        segment = segment.strip(" ,")

        if not segment or segment.endswith("?"):
            continue

        if segment.lower().startswith(_ACTIONABLE_PREFIXES):
            actionable.append(segment)

    kept = safety + actionable

    if kept:
        return ", ".join(kept)

    return text


def _apply_special_instructions(psd, layer_by_name, text_layers, special_instructions):
    layer = _find_special_instructions_layer(layer_by_name)
    if layer is None:
        return

    special_instructions = special_instructions.strip()
    layer.visible = bool(special_instructions)

    if special_instructions:
        # A long comment (e.g. an allergy note) would otherwise run off
        # both edges of the layer's own placeholder-sized text box — cap
        # it at whatever sits directly below (e.g. the allergen icon
        # row) so the renderer knows how far it's allowed to wrap.
        next_layer = _find_layer_below(psd.descendants(), layer)
        max_bottom = int(next_layer.bbox[1]) - 6 if next_layer is not None else None

        key_phrase = _extract_key_phrase(special_instructions)
        replacement_short = (
            f"Special Instructions: {key_phrase}"
            if key_phrase != special_instructions
            else None
        )

        text_layers.append({
            "layer": layer,
            "original_text": layer.text,
            "replacement": f"Special Instructions: {special_instructions}",
            "replacement_short": replacement_short,
            "max_bottom": max_bottom,
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

    # No font_override for the dish name: the renderer reads the font and
    # size straight off each template's own band layer, so every dish
    # prints at its native size (see _canonical_name_style). If the
    # template's placeholder band text already equals `replacement`, the
    # renderer keeps the original Photoshop raster untouched.
    text_layers = [{
        "layer": dish_layer,
        "original_text": dish_layer.text,
        "replacement": replacement,
    }]

    _apply_customer_name(psd, dish_layer, text_layers, order["customer_name"])
    _apply_special_instructions(psd, layer_by_name, text_layers, order["special_instructions"])

    # GlutenFreeLogo defaults vary per template — some dishes (e.g. Beef
    # Rendang Rice) are gluten-free as a fixed fact and ship with the
    # layer already visible; others ship it hidden because it's a
    # genuine per-order customer choice. Either way, an explicit
    # "Gluten Free" selection — via the Options rule or typed into the
    # special-instructions comment (e.g. "gluten free please") — should
    # always turn it on; nothing should ever force it off, since that
    # could hide a fact the template author baked in on purpose.
    gluten_free_layer = layer_by_name.get("GlutenFreeLogo")
    wants_gluten_free = (
        _has_option(order["options"], "gluten free")
        or "gluten free" in order["special_instructions"].lower()
    )
    if gluten_free_layer is not None and wants_gluten_free:
        gluten_free_layer.visible = True

    # Crustaceans (shellfish) icon — only touched for the meat-line
    # protein choices of the four dishes below; a vegetable/vegan/tofu
    # variant keeps whatever its own dedicated template already has
    # baked in. See docs/ALLERGEN_RULES.md for the reasoning.
    crustaceans_layer = layer_by_name.get("Crustaceans Icon")
    protein = variant_suffix or ""
    if crustaceans_layer is not None and _is_meat_line_protein(protein):
        if dish_label in _SAMBAL_BASED_DISHES:
            crustaceans_layer.visible = not _mentions(
                order["special_instructions"], "no prawn", "no shrimp"
            )
        elif dish_label in _SOY_SAUCE_BASED_DISHES:
            crustaceans_layer.visible = _protein_is_shellfish(protein)

    # Eggs icon: an explicit "no egg" instruction always removes it,
    # regardless of dish. Only ever turns it off, never on — the
    # template's own default stands otherwise.
    egg_layer = layer_by_name.get("Egg Icon")
    if egg_layer is not None and _mentions(order["special_instructions"], "no egg"):
        egg_layer.visible = False

    image = render_psd(psd, text_layers)

    variant_part = f"_{_safe_filename(variant_suffix)}" if variant_suffix else ""
    out_name = f"{_safe_filename(order['customer_name'])}_{_safe_filename(dish_label)}{variant_part}.png"
    out_path = os.path.join(output_dir, out_name)
    export_png(image, out_path)
    return out_path


def _resolve_protein_line_psd(protein, vege_psd, vegan_psd, meat_psd):
    # Ipoh Char Kway Teow, Mee Goreng, and Nasi Goreng are each one menu
    # item whose protein option can be a meat/prawn choice, a vegetarian
    # choice, or a vegan choice — each of the three has its own
    # dedicated template with the correct allergen facts baked in, so
    # the resolver must route by protein rather than always using one
    # template for every choice.
    protein_lower = protein.lower()
    if "vegan" in protein_lower:
        return vegan_psd
    if "vegetable" in protein_lower or "vegetarian" in protein_lower:
        return vege_psd
    return meat_psd


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


def _resolve_har_mee(order):
    return "26a.HarMee.psd", "Har Mee", None


def _resolve_vegan_char_kway_teow(order):
    return "7b.CharKwayTeow_Vegan.psd", "Char Kway Teow", "Vegan"


def _resolve_ipoh_char_kway_teow(order):
    protein = _protein_choice(order["options"])
    # A vegetarian or vegan protein choice carries its own allergen facts
    # (no shellfish, and vegetarian/vegan/gluten-free facts) baked into a
    # dedicated template — using the meat template for it would wrongly
    # claim "Contains Crustaceans" and drop those other icons. This
    # matters even when the order also asks (in a comment) to add a meat
    # protein on top — e.g. a shellfish-allergy customer ordering the
    # vegetarian option and asking the kitchen to add chicken still needs
    # the vegetarian template's "no shellfish" fact on the printed label.
    psd_filename = _resolve_protein_line_psd(
        protein,
        vege_psd="7a.CharKwayTeow_Vege.psd",
        vegan_psd="7b.CharKwayTeow_Vegan.psd",
        meat_psd="7c.CharKwayTeow_Meat.psd",
    )
    return psd_filename, "Char Kway Teow", protein


def _resolve_mee_goreng(order):
    protein = _protein_choice(order["options"])
    psd_filename = _resolve_protein_line_psd(
        protein,
        vege_psd="6a.MeeGoreng_Vege.psd",
        vegan_psd="6bMeeGoreng_Vegan.psd",
        meat_psd="6c.MeeGoreng_Meat.psd",
    )
    return psd_filename, "Mee Goreng", protein


def _resolve_nasi_goreng(order):
    protein = _protein_choice(order["options"])
    psd_filename = _resolve_protein_line_psd(
        protein,
        vege_psd="5a.NasiGoreng_Vege.psd",
        vegan_psd="5b.NasiGoreng_Vegan.psd",
        meat_psd="5c.NasiGoreng_Meat.psd",
    )
    return psd_filename, "Nasi Goreng", protein


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


def _resolve_vegan_mee_goreng(order):
    return "6bMeeGoreng_Vegan.psd", "Mee Goreng", "Vegan"


def _resolve_tofu_salad(order):
    return "3d.TofuSalad.psd", "Tofu Salad", None


def _resolve_spring_roll(order):
    return "23a.Spring Roll.psd", "Spring Roll", None


def _resolve_stir_fried_mixed_vegetables(order):
    return "24d. VegetablesStir-fry.psd", "Stir-fried Mixed Vegetables", None


def _resolve_tofu_broccoli_garlic_sauce(order):
    return "24e. TofuBroccoliwithGarlicSauce.psd", "Tofu & Broccoli with Garlic Sauce", None


def _resolve_curry_vegetable(order):
    return "19a.Curry Vege.psd", "Curry Vegetable", None


def _resolve_curry_fish(order):
    return "19b.Curry Fish.psd", "Curry Fish", None


def _resolve_satay_chicken_salad(order):
    return "3b.ChickenSataySalad.psd", "Satay Chicken Salad", None


def _resolve_laksa_prawn(order):
    # Same base template as the plain "Laksa" item — here the protein is
    # baked into the item name itself rather than chosen via an Options
    # rule, so it's a fixed "Prawn" variant rather than _protein_choice().
    return "8a.Laksa.psd", "Laksa", "Prawn"


DISH_RESOLVERS = {
    "Hainanese Chicken with Steamed Rice": _resolve_hainan_chicken,
    "Beef Rendang with Jasmine Rice": _resolve_beef_rendang_rice,
    "Beef Rendang Roti Canai": _resolve_beef_rendang_roti,
    "Chicken Curry with Jasmine Rice": _resolve_curry_chicken_rice,
    "Ipoh Hor Fun": _resolve_ipoh_hor_fun,
    "Wonton Noodle Soup": _resolve_wonton_noodle_soup,
    "Har Mee": _resolve_har_mee,
    "Vegan Ipoh Char Kway Teow": _resolve_vegan_char_kway_teow,
    "Ipoh Char Kway Teow": _resolve_ipoh_char_kway_teow,
    "Mee Goreng": _resolve_mee_goreng,
    "Nasi Goreng": _resolve_nasi_goreng,
    "Wat Tan Hor (Kway Teow Siram)": _resolve_wat_tan_hor,
    "Nasi Lemak": _resolve_nasi_lemak,
    "Laksa": _resolve_laksa,
    "Vegan Mee Goreng": _resolve_vegan_mee_goreng,
    "Tofu Salad": _resolve_tofu_salad,
    "Spring Roll": _resolve_spring_roll,
    "Stir-fried Mixed Vegetables": _resolve_stir_fried_mixed_vegetables,
    "Tofu & Broccoli with Garlic Sauce": _resolve_tofu_broccoli_garlic_sauce,
    "Curry Vegetable": _resolve_curry_vegetable,
    "Curry Fish": _resolve_curry_fish,
    "Satay Chicken Salad": _resolve_satay_chicken_salad,
    "Laksa Prawn": _resolve_laksa_prawn,
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
    attendee's name as a "Name: <name>" choice, optionally followed by a
    "Comment: <text>" line carrying an actual free-text instruction
    (e.g. "Name: John Hollister\nComment: no rice") rather than the
    hand-typed ORDERS shape's plain special_instructions string.
    """

    orders = []

    for item in data["purchaseContentDetails"]["items"]:
        # Source data occasionally carries a stray trailing space on the
        # item name (e.g. "Vegan Mee Goreng "), which would otherwise look
        # like a distinct, unhandled dish to DISH_RESOLVERS.
        dish_name = item["item"]["name"].strip()

        for config in item["configs"]:
            if "config" not in config:
                # A bulk/tray line ordered by quantity alone (e.g. "3x
                # Beef Rendang Platter" for the whole order) — just a
                # cost/quantity record, no per-attendee choices to parse.
                # Skip it rather than crash the whole order over one
                # line neither this parser nor any dish resolver yet
                # knows how to handle.
                continue

            options = []
            customer_name = ""
            special_instructions = ""

            for rule in config["config"]:
                choice_names = [c["name"] for c in rule["selectedChoices"]]

                if rule["ruleName"] == "Options":
                    for choice_name in choice_names:
                        # Some menus carry a redundant copy of the
                        # item's own name at the front of the option
                        # text (e.g. "Ipoh Char Kway Teow Beef", "Mee
                        # Goreng Chicken") instead of just "Beef" —
                        # strip it so protein parsing sees the same
                        # short form as every other order.
                        if choice_name.lower().startswith(dish_name.lower()):
                            choice_name = choice_name[len(dish_name):].strip()
                        options.append(choice_name)
                elif rule["ruleName"] == "Special instructions":
                    for choice_name in choice_names:
                        if choice_name.startswith("Name:"):
                            customer_name, special_instructions = _parse_name_choice(choice_name)
                        elif choice_name.startswith("Comment:"):
                            # A shared/bulk config (e.g. an 80-portion tray)
                            # carries a comment with no attendee name at all.
                            special_instructions = choice_name[len("Comment:"):].strip()

            orders.append({
                "customer_name": normalize_customer_name(customer_name),
                "dish_name": dish_name,
                "options": options,
                "special_instructions": special_instructions,
            })

    return orders


def process_orders(orders, output_dir=None):
    """
    Run every order through its dish resolver and generate_label(),
    without printing anything — used by both the CLI (main(), below) and
    the web app, so they share one code path. Returns:

        {
            "generated": [{"customer_name", "dish_label", "variant", "full_dish_name",
                           "out_path", "psd_filename", "options", "special_instructions"}, ...],
            "skipped": [{"customer_name", "dish_name"}, ...],
            "review_needed": [{"customer_name", "dish_label", "flags"}, ...],
        }

    full_dish_name is dish_label with its variant suffix appended (e.g.
    "Nasi Goreng - Beef"), matching the text actually printed on the
    label — the unit a kitchen-prep dish summary should count by.

    psd_filename, options and special_instructions are carried through
    per generated label so a caller (e.g. the web app) can later
    reconstruct the same order dict and re-render just this one label
    after editing its special instructions, without re-resolving the
    dish or re-running the whole order set.
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
            "psd_filename": psd_filename,
            "options": order["options"],
            "special_instructions": order["special_instructions"],
        })

        flags = name_review_flags(order["customer_name"])
        if order["special_instructions"]:
            flags = flags + [f"special instructions: {order['special_instructions']}"]
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
