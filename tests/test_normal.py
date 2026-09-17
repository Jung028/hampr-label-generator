"""
Logic + end-to-end checks for the normal (Ipoh Town) path in
generate_labels.py.

Plain-script style, matching test_nanyang.py / test_font_resolution.py:
run directly, prints PASS/FAIL lines, exits non-zero on any failure.

Covers partner detection, that every DISH_RESOLVERS dish is exercised by
the synthetic matrix fixture, and that every fixture (real captures plus
the generated matrix / special-instruction fan-outs) renders with no
skipped orders and a PNG on disk for every generated label.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import generate_labels as g

NORMAL_DIR = os.path.join(ROOT, "test_response", "normal")

_failures = 0


def check(label, condition):
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"{status} {label}")


def _load(name):
    with open(os.path.join(NORMAL_DIR, name)) as f:
        return json.load(f)


# ---- partner detection -------------------------------------------------

for name in ("order_5_9_26", "order_netflix", "gen_matrix", "gen_special_instr"):
    check(f"detect_partner({name}) == normal", g.detect_partner(_load(name)) == "normal")


# ---- parse shape -----------------------------------------------------

orders = g.parse_orders(_load("gen_matrix"))
check("gen_matrix parses to >= 30 orders", len(orders) >= 30)
check("no parsed order carries a nanyang tag", all(o.get("partner") != "nanyang" for o in orders))
check("every parsed order has a customer name", all(o["customer_name"] for o in orders))


# ---- every resolver is exercised by the matrix ---------------------

matrix_dishes = {o["dish_name"] for o in orders}
for dish in g.DISH_RESOLVERS:
    check(f"gen_matrix covers DISH_RESOLVERS dish {dish!r}", dish in matrix_dishes)


# ---- every fixture renders with no skips --------------------------

for name in ("order_5_9_26", "order_netflix", "gen_matrix", "gen_special_instr"):
    out_dir = os.path.join("/tmp", "hampr-normal-test", name)
    result = g.process_orders(g.parse_orders(_load(name)), output_dir=out_dir)
    check(
        f"{name}: all orders generated, none skipped ({len(result['generated'])} labels)",
        len(result["generated"]) > 0 and not result["skipped"],
    )
    check(
        f"{name}: every generated label wrote a PNG that exists",
        all(os.path.exists(gen["out_path"]) for gen in result["generated"]),
    )


# ---- name normalisation edge cases -------------------------------

check("ALL CAPS name -> title case", g.normalize_customer_name("SIVA RAJAH") == "Siva Rajah")
check("all lower name -> title case", g.normalize_customer_name("alex tan") == "Alex Tan")


print()
if _failures:
    print(f"{_failures} failure(s)")
    sys.exit(1)
print("all good")
