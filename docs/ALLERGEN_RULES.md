# Allergen icon rules

Most allergen/dietary icons on a label (Halal, Vegetarian, Dairy Free, and
most "Contains" icons) come straight from whichever PSD template the dish
resolver picks — they're a fixed fact of that specific template, not
computed from the order data. Three icons are the exception: **Crustaceans**,
**Eggs**, and **Gluten Free**, which the code actively toggles per order,
because the same dish item can be ordered with different proteins (or a
customer request) that genuinely change what's actually in the sauce or
the bowl.

This doc is the source of truth for that logic. Ipoh Town ("normal")
orders and Nanyang orders use two different mechanisms to arrive at the
same rule — see "Where this lives in code" below for which applies to
which. If the rule and the code (`generate_labels.py`) ever disagree,
that's a bug — fix the code to match this doc, or update this doc if the
underlying recipe fact has changed.

## Ipoh Town ("normal") orders

Computed inside `generate_label()`, from the dish name, the chosen
protein, and the special-instructions text.

### Crustaceans (shellfish) icon

The per-dish bucket logic below (sambal vs soy-sauce) is only applied to
the **meat-line** protein choices — Chicken, Beef, Prawn, Seafood, Combo
— of four dishes. A vegetable, vegan, or tofu variant already renders
from its own dedicated template with the correct facts baked in, and is
never touched by that logic. On top of that, one order-level override
applies to **every** dish: a "no prawn" / "no shrimp" instruction always
clears the icon.

**Sambal-based dishes: on by default.** Mee Goreng and Nasi Goreng — the
sauce is sambal, and sambal is made with shrimp paste. Every protein
variant (Chicken, Prawn, Beef, Seafood, Combo) contains shellfish because
of the sauce itself, regardless of which protein was chosen.

- Default: Crustaceans **ON** for every protein.
- Exception: if the order's special instructions say "no prawn" or "no
  shrimp", that means the sambal itself was left out (not just a
  protein swap) — Crustaceans goes **OFF**.

**Soy-sauce-based dishes: depends on the protein.** Char Kway Teow and Wat
Tan Hor ("Kway Teow Siram") use a soy-sauce base with no sambal. The icon
here reflects only whether the chosen protein is itself a shellfish:

- Chicken, Beef → Crustaceans **OFF**
- Prawn, Seafood, Combo → Crustaceans **ON**

No special-instructions override applies here — if you order the prawn
protein, that's the shellfish; there's no sauce-level shellfish to ask
to leave out.

**Left alone.** Vegetable, Vegan, and Tofu variants of any of the above
dishes keep whatever their own dedicated template already has baked in.
This logic never overrides them.

**"No prawn" / "no shrimp": always removes the icon.** Independent of the
dish buckets above, if the order's special instructions say "no prawn" or
"no shrimp", the Crustaceans icon is forced **off** for **any** dish —
the customer has asked for the shellfish to be left out. Only ever
removes the icon, never adds one.

### Eggs icon

Applies to any dish that has an Eggs icon layer. If the order's special
instructions say "no egg", the Eggs icon is forced **off**. This only
ever removes the icon — it never turns it on if the template didn't
already have it, since a dish either contains egg as a fixed recipe fact
or it doesn't.

### Gluten Free icon

GlutenFreeLogo defaults vary per template — some dishes (e.g. Beef
Rendang Rice) are gluten-free as a fixed fact and ship with the layer
already visible; others ship it hidden because it's a genuine per-order
customer choice. Either way, an explicit request — via the "Gluten Free"
Options rule choice, or typed into the special-instructions comment
(e.g. "gluten free please") — always turns the icon **on**. Nothing ever
forces it off, since that could hide a fact the template author baked in
on purpose.

## Nanyang orders

Computed inside `generate_nanyang_label()`. Nanyang dishes don't use the
sambal/soy-sauce dish buckets above — instead, Hampr attaches "diet tag"
facts (e.g. `Contains Seafood`, `Contains Egg`, `Gluten Free`) directly to
the specific option the attendee chose, and the code reads those facts
straight off the order rather than guessing from the dish or protein
name. This is more reliable than the Ipoh Town bucket logic: e.g. Chicken
Fried Rice is still tagged `Contains Seafood` because the recipe includes
shrimp, which a per-dish/per-protein guess would miss.

### Crustaceans (shellfish) icon

- On if the order's diet tags include `Contains Seafood` (case-insensitive
  substring match on "seafood"), off otherwise — this **can** override
  whatever the template shipped with, in either direction.
- Independent override: if the special instructions say "no prawn" or
  "no shrimp", the icon is forced **off** regardless of the diet tags —
  same treatment as Ipoh Town.

### Eggs icon

- On if the order's diet tags include `Contains Egg`, off otherwise —
  same diet-tag-driven treatment as Crustaceans.
- Independent override: if the special instructions say "no egg", the
  icon is forced **off** regardless of the diet tags.

### Gluten Free icon

Turned **on** if any of the following say the order is gluten free —
never forced off, same "only ever adds" rule as Ipoh Town:

- the order's diet tags include `Gluten Free`;
- the customer picked "Gluten Free" under the "Make it Yours" rule
  (`order["gluten_free"]`); or
- the special instructions mention "gluten free" as free text.

## Where this lives in code

`generate_labels.py`:

**Ipoh Town path** (`generate_label()`):
- `_SAMBAL_BASED_DISHES`, `_SOY_SAUCE_BASED_DISHES` — which dish_label
  falls in which bucket.
- `_is_meat_line_protein()` / `_protein_is_shellfish()` — keyword checks
  on the resolved protein string (Chicken/Beef/Prawn/Seafood/Combo).
- `_mentions()` — case-insensitive substring check against the order's
  special_instructions text (e.g. "no prawn", "no shrimp", "no egg",
  "gluten free").
- All three icons are toggled inside `generate_label()`.

**Nanyang path** (`generate_nanyang_label()`):
- `_nanyang_wants_crustaceans()` / `_nanyang_wants_eggs()` — substring
  checks ("seafood" / "egg") against the order's `diet_tags` list, which
  is populated from each chosen option's `dietTags` in
  `_parse_nanyang_orders`.
- `order["gluten_free"]` — set from the "Make it Yours: Gluten Free"
  choice, also in `_parse_nanyang_orders`.
- `_mentions()` — same special-instructions overrides as Ipoh Town.
- All three icons are toggled inside `generate_nanyang_label()`.
