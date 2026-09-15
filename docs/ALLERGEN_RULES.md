# Allergen icon rules

Most allergen/dietary icons on a label (Halal, Vegetarian, Dairy Free, and
most "Contains" icons) come straight from whichever PSD template the dish
resolver picks — they're a fixed fact of that specific template, not
computed from the order data. Two icons are the exception: **Crustaceans**
and **Eggs**, which the code actively turns on/off per order for a few
dishes, because the same dish item can be ordered with different proteins
that genuinely change what's actually in the sauce or the bowl.

This doc is the source of truth for that logic. If the rule and the code
(`generate_labels.py`, in `generate_label()`) ever disagree, that's a bug —
fix the code to match this doc, or update this doc if the underlying
recipe fact has changed.

## Crustaceans (shellfish) icon

Only touched for the **meat-line** protein choices — Chicken, Beef, Prawn,
Seafood, Combo — of four dishes. A vegetable, vegan, or tofu variant
already renders from its own dedicated template with the correct facts
baked in, and is never touched by this logic.

### Sambal-based dishes: on by default

**Mee Goreng** and **Nasi Goreng** — the sauce is sambal, and sambal is
made with shrimp paste. Every protein variant (Chicken, Prawn, Beef,
Seafood, Combo) contains shellfish because of the sauce itself,
regardless of which protein was chosen.

- Default: Crustaceans **ON** for every protein.
- Exception: if the order's special instructions say "no prawn" or "no
  shrimp", that means the sambal itself was left out (not just a
  protein swap) — Crustaceans goes **OFF**.

### Soy-sauce-based dishes: depends on the protein

**Char Kway Teow** and **Wat Tan Hor** ("Kway Teow Siram") use a
soy-sauce base with no sambal. The icon here reflects only whether the
chosen protein is itself a shellfish:

- Chicken, Beef → Crustaceans **OFF**
- Prawn, Seafood, Combo → Crustaceans **ON**

No special-instructions override applies here — if you order the prawn
protein, that's the shellfish; there's no sauce-level shellfish to ask
to leave out.

### Left alone

Vegetable, Vegan, and Tofu variants of any of the above dishes keep
whatever their own dedicated template already has baked in. This logic
never overrides them.

## Eggs icon

Applies to **any** dish that has an Eggs icon layer. If the order's
special instructions say "no egg", the Eggs icon is forced **off**.
This only ever removes the icon — it never turns it on if the template
didn't already have it, since a dish either contains egg as a fixed
recipe fact or it doesn't.

## Where this lives in code

`generate_labels.py`:

- `_SAMBAL_BASED_DISHES`, `_SOY_SAUCE_BASED_DISHES` — which dish_label
  falls in which bucket.
- `_is_meat_line_protein()` / `_protein_is_shellfish()` — keyword checks
  on the resolved protein string (Chicken/Beef/Prawn/Seafood/Combo).
- `_mentions()` — case-insensitive substring check against the order's
  special_instructions text (e.g. "no prawn", "no shrimp", "no egg").
- Both icons are toggled inside `generate_label()`, right after the
  existing GlutenFreeLogo handling.
