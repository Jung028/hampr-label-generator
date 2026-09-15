"""
Generate synthetic test_response order-detail JSON files that exercise
every dish x every protein/option variant x a rotation of special-
instruction shapes, for both the Nanyang and the normal (Ipoh Town)
paths.

Writes:
  test_response/nanyang/gen_matrix          - every category x every option
  test_response/nanyang/gen_special_instr   - dish variety x comment shapes
  test_response/normal/gen_matrix           - every DISH_RESOLVERS dish x protein
  test_response/normal/gen_special_instr    - dish variety x comment shapes
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

NANYANG_PARTNER = {
    "id": 727,
    "name": "Nanyang Tea Club",
    "slug": "Nanyang Tea House",
    "commissionRate": 0.19,
}
IPOH_PARTNER = {
    "id": 161,
    "name": "Ipoh Town",
    "slug": "ipoh-town",
    "commissionRate": 0.19,
}

# --- special-instruction shapes -------------------------------------------
# (label, comment-text or None).  None => only a "Name:" choice, no comment.
SPECIAL_SHAPES = [
    ("none", None),
    ("short", "No onion"),
    ("allergy", "Peanut allergy - please keep separate"),
    ("no_egg", "No egg please"),
    ("no_prawn", "No prawn / no shrimp"),
    (
        "long",
        "Please make this one extra spicy with plenty of fresh chilli, "
        "and leave off the spring onion and coriander garnish on top, "
        "and put the sauce on the side if you can - thank you so much!",
    ),
]


# A pool of realistic attendee names, cycled so every generated config
# gets a plausible label instead of a giant synthetic string that would
# only ever be testing the name layer's overflow behaviour.
_NAME_POOL = [
    "Alex Tan", "Priya Nair", "Sam Wong", "Jordan Lee", "Mia Chen",
    "Ben Foster", "Chloe Ng", "Ravi Patel", "Ella Brooks", "Tom Zhao",
    "Grace Lim", "Noah Reid", "Ivy Koh", "Leo Marsh", "Zara Ali",
    "Owen Park", "Ruby Shah", "Finn Doyle", "Anya Rao", "Cody Hale",
    "Nina Fox", "Eli Bass", "Lara Vann", "Kai Ross", "Ada Cole",
]
_name_i = [0]


def _next_name():
    n = _NAME_POOL[_name_i[0] % len(_NAME_POOL)]
    _name_i[0] += 1
    return n


def _config(rules):
    return {"config": rules, "quantity": 1, "uuid": "cfg"}


def _options_rule(option, diet_tags=None):
    return {
        "ruleName": "Options",
        "selectedChoices": [
            {
                "name": option,
                "dietTags": [{"name": t} for t in (diet_tags or [])],
                "serveTags": [],
            }
        ],
    }


def _make_it_yours_rule():
    return {
        "ruleName": "Make it  Yours",
        "selectedChoices": [{"name": "Gluten Free", "dietTags": [], "serveTags": []}],
    }


def _special_rule(name, comment=None):
    if comment:
        text = f"Name: {name}\nComment: {comment}"
    else:
        text = f"Name: {name}"
    return {
        "ruleName": "Special instructions",
        "selectedChoices": [{"name": text, "dietTags": [], "serveTags": []}],
    }


def _item(category, configs):
    return {"item": {"name": category}, "configs": configs, "uuid": "item"}


def _envelope(order_id, partner, items):
    return {
        "id": order_id,
        "eventDate": "2026-09-15",
        "numberOfAttendees": sum(len(it["configs"]) for it in items),
        "purchaseContentDetails": {"partner": partner, "items": items},
        "version": 1,
    }


def _write(rel_path, doc):
    path = os.path.join(REPO, rel_path)
    with open(path, "w") as f:
        json.dump(doc, f, indent=1)
    n = len(doc["purchaseContentDetails"]["items"])
    configs = sum(len(it["configs"]) for it in doc["purchaseContentDetails"]["items"])
    print(f"wrote {rel_path}: {n} items, {configs} configs")


# =======================================================================
# Nanyang
# =======================================================================

# category -> list of Options choices (empty list => fixed dish, no rule)
NANYANG_MATRIX = {
    "Sweet & Sour": [
        "Tender Sweet & Sour Fish",
        "Tender Sweet & Sour Chicken",
    ],
    "Crispy Sweet Glazed Chicken": [],  # fixed
    "Fried Rice": [
        "Vegan Fried Rice",
        "Vegetarian Fried Rice",
        "Chicken Fried Rice",
        "Beef Fried Rice",
        "Seafood Fried Rice",
        "Combination Fried Rice",
    ],
    "Singapore Noodles": [
        "Vegan Singapore Noodles",
        "Vegetarian Singapore Noodles",
        "Chicken Singapore Noodles",
        "Beef Singapore Noodles",
        "Seafood Singapore Noodles",
        "Combination Singapore Noodles",
    ],
    "Hokkien Mee": [
        "Vegan Hokkien Mee",
        "Vegetarian Hokkien Mee",
        "Chicken Hokkien Mee",
        "Beef Hokkien Mee",
        "Seafood Hokkien Mee",
        "Combination Hokkien Mee",
    ],
    "Tom Yum Fried Rice": [
        "Vegan Tom Yum Fried Rice",
        "Vegetarian Tom Yum Fried Rice",
        "Chicken Tom Yum Fried Rice",
        "Beef Tom Yum Fried Rice",
        "Seafood Tom Yum Fried Rice",
        "Combination Tom Yum Fried Rice",
    ],
    "Wat Tan Hor": [
        "Tofu Wat Tan Hor",
        "Chicken Wat Tan Hor",
        "Beef Wat Tan Hor",
        "Combination Wat Tan Hor",
    ],
    "Braised Eggplant": [
        "Braised Eggplant in Home-made Soy Sauce",
        "Braised Eggplant & Broccoli with Garlic Sauce",
        "Braised Eggplant & Tofu in Garlic Soy Sauce",
    ],
    "Stir Fried": [
        f"Stir Fried {protein} with {sauce}"
        for protein in ("Chicken", "Beef")
        for sauce in (
            "Ginger & Chilli Sauce",
            "Peking Sauce",
            "Mushroom & Broccoli",
            "Black Pepper Sauce",
            "Sweet Honey Sauce & Crispy Rice Noodles",
            "Hoisin Sauce",
            "Tangy Lemon Sauce",
            "Cashew Nuts",
            "Sweet & Sour Sauce",
            "Home-made Soy Sauce",
        )
    ],
}

# diet tags that ride along with certain proteins, mirroring the real data
NANYANG_DIET_TAGS = {
    "seafood": ["Dairy Free", "Contains Seafood"],
    "combination": ["Contains Seafood"],
    "prawn": ["Contains Seafood", "Contains Crustaceans"],
    "fish": ["Dairy Free", "Contains Seafood"],
    "vegan": ["Vegan", "Dairy Free"],
    "vegetarian": ["Vegetarian"],
}


def _diet_for(option):
    low = option.lower()
    for key, tags in NANYANG_DIET_TAGS.items():
        if key in low:
            return tags
    return []


def build_nanyang_matrix():
    items = []
    i = 0
    for category, options in NANYANG_MATRIX.items():
        configs = []
        if not options:
            i += 1
            configs.append(
                _config([_special_rule(_next_name())])
            )
        else:
            for option in options:
                i += 1
                rules = [_options_rule(option, _diet_for(option))]
                rules.append(_special_rule(_next_name()))
                configs.append(_config(rules))
        items.append(_item(category, configs))
    return _envelope("gen-nanyang-matrix", NANYANG_PARTNER, items)


def build_nanyang_special():
    # A representative dish from each template family, crossed with every
    # special-instruction shape; plus a couple of Gluten-Free add-ons and
    # ALL-CAPS / roman-suffix names.
    sample_options = [
        ("Sweet & Sour", "Tender Sweet & Sour Fish"),
        ("Crispy Sweet Glazed Chicken", None),
        ("Fried Rice", "Combination Fried Rice"),
        ("Singapore Noodles", "Seafood Singapore Noodles"),
        ("Hokkien Mee", "Beef Hokkien Mee"),
        ("Tom Yum Fried Rice", "Vegan Tom Yum Fried Rice"),
        ("Wat Tan Hor", "Chicken Wat Tan Hor"),
        ("Braised Eggplant", "Braised Eggplant & Tofu in Garlic Soy Sauce"),
        ("Stir Fried", "Stir Fried Chicken with Ginger & Chilli Sauce"),
    ]
    items = []
    i = 0
    for category, option in sample_options:
        configs = []
        for shape_label, comment in SPECIAL_SHAPES:
            i += 1
            rules = []
            if option is not None:
                rules.append(_options_rule(option, _diet_for(option)))
            rules.append(
                _special_rule(_next_name(), comment)
            )
            configs.append(_config(rules))
        items.append(_item(category, configs))

    # Gluten-Free add-ons via the "Make it Yours" rule.
    gf_configs = []
    for category, option in [
        ("Singapore Noodles", "Vegan Singapore Noodles"),
        ("Fried Rice", "Chicken Fried Rice"),
    ]:
        gf_configs.append(
            _config(
                [
                    _options_rule(option, _diet_for(option)),
                    _make_it_yours_rule(),
                    _special_rule(_next_name()),
                ]
            )
        )
    items.append(_item("Singapore Noodles", [gf_configs[0]]))
    items.append(_item("Fried Rice", [gf_configs[1]]))

    # Name-normalisation edge cases — each in a category-consistent item.
    items.append(
        _item(
            "Singapore Noodles",
            [
                _config(
                    [_options_rule("Chicken Singapore Noodles"), _special_rule("ROBIN CHIN")]
                ),
                _config(
                    [_options_rule("Beef Singapore Noodles"), _special_rule("Spare meal")]
                ),
            ],
        )
    )
    items.append(
        _item(
            "Sweet & Sour",
            [
                _config(
                    [
                        _options_rule("Tender Sweet & Sour Fish", _diet_for("fish")),
                        _special_rule("William Byrne III"),
                    ]
                )
            ],
        )
    )

    return _envelope("gen-nanyang-special", NANYANG_PARTNER, items)


# =======================================================================
# Normal (Ipoh Town)
# =======================================================================

NORMAL_MATRIX = {
    "Hainanese Chicken with Steamed Rice": ["Chicken Breast", "Chicken Thigh"],
    "Beef Rendang with Jasmine Rice": [],
    "Beef Rendang Roti Canai": [],
    "Chicken Curry with Jasmine Rice": [],
    "Ipoh Hor Fun": [],
    "Wonton Noodle Soup": [],
    "Har Mee": [],
    "Vegan Ipoh Char Kway Teow": [],
    "Ipoh Char Kway Teow": [
        "Vegetable, Egg & Tofu",
        "Chicken (Sliced Pieces)",
        "Prawn",
        "Combination",
    ],
    "Mee Goreng": ["Chicken", "Prawn", "Combination", "Vegetable", "Vegan"],
    "Nasi Goreng": ["Chicken", "Prawn", "Combination", "Vegetable", "Vegan"],
    "Wat Tan Hor (Kway Teow Siram)": [
        "Beef (Sliced Pieces)",
        "Chicken (Sliced Pieces)",
        "Tofu",
    ],
    "Nasi Lemak": ["Chicken Curry", "Beef Rendang"],
    "Laksa": ["Chicken", "Prawn", "Combination", "Steamed Wonton"],
    "Vegan Mee Goreng": [],
    "Tofu Salad": [],
    "Spring Roll": [],
    "Stir-fried Mixed Vegetables": [],
    "Tofu & Broccoli with Garlic Sauce": [],
    "Curry Vegetable": [],
    "Curry Fish": [],
    "Satay Chicken Salad": [],
    "Laksa Prawn": [],
}


def build_normal_matrix():
    items = []
    i = 0
    for dish, options in NORMAL_MATRIX.items():
        configs = []
        if not options:
            i += 1
            configs.append(_config([_special_rule(_next_name())]))
        else:
            for option in options:
                i += 1
                configs.append(
                    _config(
                        [
                            {
                                "ruleName": "Options",
                                "selectedChoices": [{"name": option}],
                            },
                            _special_rule(_next_name()),
                        ]
                    )
                )
        items.append(_item(dish, configs))
    return _envelope("gen-normal-matrix", IPOH_PARTNER, items)


def build_normal_special():
    sample = [
        ("Hainanese Chicken with Steamed Rice", "Chicken Thigh"),
        ("Ipoh Char Kway Teow", "Prawn"),
        ("Nasi Goreng", "Vegan"),
        ("Mee Goreng", "Combination"),
        ("Laksa", "Steamed Wonton"),
        ("Nasi Lemak", "Beef Rendang"),
        ("Wat Tan Hor (Kway Teow Siram)", "Tofu"),
        ("Beef Rendang with Jasmine Rice", None),
        ("Curry Fish", None),
    ]
    items = []
    i = 0
    for dish, option in sample:
        configs = []
        for shape_label, comment in SPECIAL_SHAPES + [
            ("gluten_free", "gluten free please"),
            ("no_rice", "no rice"),
        ]:
            i += 1
            rules = []
            if option is not None:
                rules.append(
                    {"ruleName": "Options", "selectedChoices": [{"name": option}]}
                )
            rules.append(_special_rule(_next_name(), comment))
            configs.append(_config(rules))
        items.append(_item(dish, configs))

    # Name-normalisation edge cases.
    items.append(
        _item(
            "Beef Rendang with Jasmine Rice",
            [
                _config([_special_rule("SIVA RAJAH")]),
                _config([_special_rule("mary o'brien")]),
                _config([_special_rule("Spare meal")]),
            ],
        )
    )
    return _envelope("gen-normal-special", IPOH_PARTNER, items)


if __name__ == "__main__":
    _write("test_response/nanyang/gen_matrix", build_nanyang_matrix())
    _write("test_response/nanyang/gen_special_instr", build_nanyang_special())
    _write("test_response/normal/gen_matrix", build_normal_matrix())
    _write("test_response/normal/gen_special_instr", build_normal_special())
