"""
Logic checks for the Nanyang Tea Club path in generate_labels.py.

Plain-script style, matching test_font_resolution.py: run directly, prints
PASS/FAIL lines, exits non-zero on any failure. Covers partner detection,
the Nanyang-shaped parse, template routing, and the Crustaceans rule —
i.e. the parts that are pure data, not PSD rendering (rendering is
verified by eye through the web UI).
"""

import json
import os
import sys

import generate_labels as g

HERE = os.path.dirname(os.path.abspath(__file__))
NANYANG_DIR = os.path.join(HERE, "test_response", "nanyang")

_failures = 0


def check(label, condition):
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"{status} {label}")


def _load(name):
    with open(os.path.join(NANYANG_DIR, name)) as f:
        return json.load(f)


# ---- partner detection -------------------------------------------------

for name in ("test1", "test2", "test3"):
    check(f"detect_partner({name}) == nanyang", g.detect_partner(_load(name)) == "nanyang")

check(
    "detect_partner(Ipoh Town) == normal",
    g.detect_partner({"purchaseContentDetails": {"partner": {"name": "Ipoh Town", "slug": "ipoh-town"}}}) == "normal",
)
check("detect_partner({}) == normal", g.detect_partner({}) == "normal")


# ---- parse shape -----------------------------------------------------

orders = g.parse_orders(_load("test1"))
check("test1 parses to >= 20 orders", len(orders) >= 20)
check("every parsed order is tagged partner=nanyang", all(o.get("partner") == "nanyang" for o in orders))
check("every parsed order has a customer name", all(o["customer_name"] for o in orders))

by_option = {o["option"]: o for o in orders if o["option"]}
check(
    "Make-it-Yours Gluten Free is captured",
    by_option["Vegan Singapore Noodles"]["gluten_free"] is True,
)
check(
    "a fixed dish (no Options rule) keeps the category as dish_name",
    any(o["dish_name"] == "Crispy Sweet Glazed Chicken" and o["option"] == "" for o in orders),
)


# ---- template routing ----------------------------------------------

ROUTING_CASES = [
    ("Singapore Noodles", "Vegan Singapore Noodles", "13a. Singapore Noodle_Vegan.psd"),
    ("Singapore Noodles", "Chicken Singapore Noodles", "13c. Singapore Noodle_Meat.psd"),
    ("Singapore Noodles", "Vegetarian Singapore Noodles", "13b. Singapore Noodle_Vegetarian.psd"),
    ("Fried Rice", "Seafood Fried Rice", "17c. Fried Rice_Meat.psd"),
    ("Tom Yum Fried Rice", "Vegan Tom Yum Fried Rice", "15a. Tom Yum_Vegan.psd"),
    ("Wat Tan Hor", "Combination Wat Tan Hor", "16c. Siram_Meat.psd"),
    ("Wat Tan Hor", "Tofu Wat Tan Hor", "16a. Siram_TofuVeg.psd"),
    ("Braised Eggplant", "Braised Eggplant in Home-made Soy Sauce", "11. Eggplant Only.psd"),
    ("Braised Eggplant", "Braised Eggplant & Broccoli with Garlic Sauce", "11. Eggplant Only.psd"),
    ("Braised Eggplant", "Braised Eggplant & Tofu in Garlic Soy Sauce", "12. Eggplant Tofu.psd"),
    ("Sweet & Sour", "Tender Sweet & Sour Fish", "9. Sweet & Sour.psd"),
    ("Crispy Sweet Glazed Chicken", "", "10. Sesame.psd"),
    ("Stir Fried", "Stir Fried Chicken with Ginger & Chilli Sauce", "1. Szechuan.psd"),
    ("Stir Fried", "Stir Fried Chicken with Tangy Lemon Sauce", "7. Lemon.psd"),
    ("Stir Fried", "Stir Fried Chicken with Sweet Honey Sauce & Crispy Rice Noodles", "5. Honey.psd"),
]

for category, option, expected_psd in ROUTING_CASES:
    order = {"dish_name": category, "option": option, "options": [option] if option else []}
    resolved = g.resolve_nanyang(order)
    got = resolved[0] if resolved else None
    check(f"{category!r} + {option!r} -> {expected_psd}", got == expected_psd)

# "Home-made Soy Sauce" is the menu's generic name for two dishes told
# apart only by protein: Beef (Mushroom & Broccoli) and Chicken (Cashew).
# Both resolve cleanly, with no review flag needed.
soy_chicken = g.resolve_nanyang(
    {"dish_name": "Stir Fried", "option": "Stir Fried Chicken with Home-made Soy Sauce"}
)
check("Chicken + Home-made Soy Sauce -> Cashew", soy_chicken[0] == "8. Cashew.psd")
check("Chicken + Home-made Soy Sauce carries no review flag", soy_chicken[2] == [])

soy_beef = g.resolve_nanyang(
    {"dish_name": "Stir Fried", "option": "Stir Fried Beef with Home-made Soy Sauce"}
)
check("Beef + Home-made Soy Sauce -> Beef Mushroom Broccoli", soy_beef[0] == "3. Beef Mushroom Broccoli.psd")
check("Beef + Home-made Soy Sauce carries no review flag", soy_beef[2] == [])

# Any other protein has no dedicated Home-made Soy Sauce dish on the menu,
# so it still resolves (a label must print) but is flagged for review.
soy_other = g.resolve_nanyang(
    {"dish_name": "Stir Fried", "option": "Stir Fried Tofu with Home-made Soy Sauce"}
)
check(
    "Home-made Soy Sauce review flag says why it couldn't be determined",
    soy_other[0] == "6. Hoisin.psd"
    and soy_other[2]
    and "determine template" in soy_other[2][0].lower()
    and "Home-made Soy Sauce" in soy_other[2][0]
    and "Hoisin" in soy_other[2][0],
)

unknown_sauce = g.resolve_nanyang(
    {"dish_name": "Stir Fried", "option": "Stir Fried Chicken with Mystery Glaze"}
)
check(
    "an unknown stir-fried sauce still renders but is flagged with a reason",
    unknown_sauce[0] == "1. Szechuan.psd"
    and unknown_sauce[2]
    and "determine template" in unknown_sauce[2][0].lower(),
)

# An unknown category is skipped, not crashed.
check("unknown category -> None (skipped)", g.resolve_nanyang({"dish_name": "Mystery Dish", "option": ""}) is None)

# ...and the skip carries a reason string.
_skip_result = g.process_orders(
    [{"partner": "nanyang", "customer_name": "Test", "dish_name": "Mystery Dish",
      "option": "", "options": [], "special_instructions": "", "gluten_free": False,
      "diet_tags": []}],
    output_dir="/tmp/hampr-nanyang-test/skip",
)
check(
    "a skipped Nanyang order records why it couldn't be placed",
    _skip_result["skipped"]
    and "determine template" in _skip_result["skipped"][0].get("reason", "").lower(),
)


# ---- dish-banner protein correction ------------------------------

check(
    "variant template: '... - Combination' becomes '... - Beef' for a Beef order",
    g._nanyang_dish_text("Tom Yum Fried Rice - Combination", "Beef Tom Yum Fried Rice")
    == "Tom Yum Fried Rice - Beef",
)
check(
    "variant template: keeps 'Combination' for a Combination order",
    g._nanyang_dish_text("Tom Yum Fried Rice - Combination", "Combination Tom Yum Fried Rice")
    == "Tom Yum Fried Rice - Combination",
)
check(
    "Sweet & Sour: 'Chicken' becomes 'Fish' for a Fish order",
    g._nanyang_dish_text("Sweet & Sour Chicken", "Tender Sweet & Sour Fish") == "Sweet & Sour Fish",
)
check(
    "stir-fried template: 'Szechuan Chicken' -> 'Szechuan Beef' for a Beef order",
    g._nanyang_dish_text("Szechuan Chicken", "Stir Fried Beef with Ginger & Chilli Sauce")
    == "Szechuan Beef",
)
check(
    "stir-fried template: 'Peking Beef' -> 'Peking Chicken' for a Chicken order",
    g._nanyang_dish_text("Peking Beef", "Stir Fried Chicken with Peking Sauce")
    == "Peking Chicken",
)
check(
    "stir-fried template: 'Szechuan Chicken' untouched for a Chicken order",
    g._nanyang_dish_text("Szechuan Chicken", "Stir Fried Chicken with Ginger & Chilli Sauce")
    is None,
)
check(
    "stir-fried template: 'Broccolli' typo is fixed when the banner is redrawn",
    g._nanyang_dish_text("Mushroom Broccolli Beef", "Stir Fried Beef with Mushroom & Broccoli")
    == "Mushroom Broccoli Beef",
)
check(
    "a banner with no protein word ('Braised Eggplant') is left untouched",
    g._nanyang_dish_text("Braised Eggplant", "Braised Eggplant in Home-made Soy Sauce") is None,
)
check(
    "'William Byrne III' keeps the roman suffix",
    g.normalize_customer_name("WILLIAM BYRNE III") == "William Byrne III",
)


# ---- Crustaceans rule --------------------------------------------

for diet_tags, expected in [
    ([], False),
    (["Halal Friendly"], False),
    (["Dairy Free"], False),
    (["Contains Seafood"], True),
    (["Vegan", "Dairy Free"], False),
    (["Dairy Free", "Contains Seafood"], True),
    (["Contains Seafood", "Contains Crustaceans"], True),
]:
    check(
        f"_nanyang_wants_crustaceans({diet_tags!r}) is {expected}",
        g._nanyang_wants_crustaceans(diet_tags) is expected,
    )


# ---- end-to-end: every test file renders with no skips --------------
#
# test1-3 are real captured orders; gen_matrix / gen_special_instr are
# synthetic fixtures (scripts/make_fixtures.py) that fan out every
# category x every protein option x a rotation of special-instruction
# shapes, so a routing or rendering regression on any combination shows
# up here rather than only on whatever the three real orders happened to
# contain.

for name in ("test1", "test2", "test3", "gen_matrix", "gen_special_instr"):
    out_dir = os.path.join("/tmp", "hampr-nanyang-test", name)
    result = g.process_orders(g.parse_orders(_load(name)), output_dir=out_dir)
    check(
        f"{name}: all orders generated, none skipped ({len(result['generated'])} labels)",
        len(result["generated"]) > 0 and not result["skipped"],
    )
    check(
        f"{name}: every generated label wrote a PNG that exists",
        all(os.path.exists(gen["out_path"]) for gen in result["generated"]),
    )


# ---- synthetic matrix: routing + dish-banner + crustaceans ---------
#
# For every order in the generated matrix, the resolver must return a
# template that exists on disk, the printed dish banner must name the
# protein that was actually ordered (not the one the shared _Meat
# template was drawn for), and the Crustaceans icon decision must follow
# the protein.

_matrix_orders = g.parse_orders(_load("gen_matrix"))
check("gen_matrix parsed to >= 50 orders", len(_matrix_orders) >= 50)

for _o in _matrix_orders:
    _resolved = g.resolve_nanyang(_o)
    check(f"gen_matrix: {_o['option'] or _o['dish_name']} resolves", _resolved is not None)
    if not _resolved:
        continue
    _psd_name, _label, _flags = _resolved
    check(
        f"gen_matrix: template {_psd_name!r} exists on disk",
        os.path.exists(os.path.join(g.NANYANG_TEMPLATES_DIR, _psd_name)),
    )

    _opt_lower = (_o.get("option") or "").lower()
    # A protein-variant dish (one whose option starts with a protein
    # word) must, once corrected, print that protein in the banner.
    _protein = next(
        (w for w in g._NANYANG_PROTEIN_WORDS if _opt_lower.startswith(w)), None
    )
    if _protein and " " in (_o.get("option") or ""):
        _corrected = g._nanyang_dish_text(f"Some Dish - Placeholder", _o["option"])
        # _nanyang_dish_text only rewrites a "<base> - <protein>" banner;
        # when it returns something, the suffix must be the ordered protein.
        if _corrected is not None:
            check(
                f"gen_matrix: {_o['option']!r} banner suffix -> {_protein.capitalize()}",
                _corrected.endswith(f"- {_protein.capitalize()}"),
            )

    _wants = g._nanyang_wants_crustaceans(_o.get("diet_tags", []))
    _expected = any("seafood" in tag.lower() for tag in _o.get("diet_tags", []))
    check(
        f"gen_matrix: crustaceans({_o['option']!r}, tags={_o.get('diet_tags')!r}) == {_expected}",
        _wants is _expected,
    )


print()
if _failures:
    print(f"{_failures} failure(s)")
    sys.exit(1)
print("all good")
