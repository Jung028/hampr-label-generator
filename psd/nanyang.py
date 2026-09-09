"""
Nanyang Tea Club label templates.

These PSDs (templates/nanyang/) are structured differently from the Ipoh
Town set:

- There is no `RedBand` pixel layer, so `psd.layers.find_dish_name_layer`
  returns nothing and the Ipoh rendering path does not apply.
- The dish name is baked into each template — one PSD per protein/sauce
  variant (e.g. "Singapore Noodle - Vegan", "Szechuan Chicken") — rather
  than rewritten per order.
- The only per-order text is the customer name and an optional free-text
  comment.
- Icon layers are left exactly as each template ships them, except the
  Crustaceans icon, which `generate_labels` toggles to match the chosen
  protein.

This module just locates the two editable text layers positionally,
since their placeholder *text* differs in every template (a different
person's name, "notes", ...).
"""

from psd.layers import get_text_layers


# Text layers whose content is fixed template chrome, never the customer
# name — matched case-insensitively against the layer's text.
_FIXED_TEXTS = {
    "www.ipohhawker.com.au",
    "allergen information",
    "contains",
    "notes",
    "no eggs;no fish;no shellfish",
}


def clean_text(text):
    """Collapse the stray carriage returns Photoshop leaves on these layers."""
    return (text or "").replace("\r", " ").strip()


def find_name_layer(psd):
    """
    The customer-name text layer: the one sitting in the band between the
    site URL and the coloured dish strip — its vertical centre is around
    y=234 on the 768px-tall canvas. Every template centres it and uses
    the same font, so position is the only reliable signal; the
    placeholder text is a different person's name in each PSD.
    """

    best = None
    best_distance = None

    for layer in get_text_layers(psd):
        if not layer.visible:
            continue

        text = clean_text(layer.text).lower()
        if text in _FIXED_TEXTS or text.startswith("special instructions"):
            continue

        _, top, _, bottom = layer.bbox
        center_y = (top + bottom) / 2
        if not (150 <= center_y <= 300):
            continue

        distance = abs(center_y - 234)
        if best_distance is None or distance < best_distance:
            best = layer
            best_distance = distance

    return best


def find_comment_layer(psd):
    """
    The optional comment layer, printed only when the order carries a
    free-text comment. Fresh templates ship a hidden "notes" placeholder
    here; a couple of templates were saved from a real order and instead
    carry a visible "Special Instructions: ..." or a leftover note in the
    same spot (centre roughly y=455-495, above the allergen row).
    """

    # Prefer the conventional placeholder.
    for layer in get_text_layers(psd):
        if clean_text(layer.text).lower() == "notes":
            return layer

    for layer in get_text_layers(psd):
        if clean_text(layer.text).lower().startswith("special instructions"):
            return layer

    for layer in get_text_layers(psd):
        if clean_text(layer.text).lower() == "no eggs;no fish;no shellfish":
            continue
        _, top, _, bottom = layer.bbox
        center_y = (top + bottom) / 2
        if 440 <= center_y <= 500:
            return layer

    return None


def find_dish_layer(psd):
    """
    The dish-name text layer: the big BritannicBold line drawn on top of
    the coloured strip ("Layer 5" here, the equivalent of the Ipoh
    templates' "RedBand"). Used to correct the printed protein when a
    variant template ("... - Combination") is reused for another protein.
    """

    band = None
    for layer in psd.descendants():
        if layer.name.strip() == "Layer 5":
            band = layer
            break
    if band is None:
        return None

    _, band_top, _, band_bottom = band.bbox

    for layer in get_text_layers(psd):
        _, top, _, bottom = layer.bbox
        center_y = (top + bottom) / 2
        if band_top <= center_y <= band_bottom:
            return layer

    return None


def notes_max_bottom(psd, comment_layer):
    """
    How far down a wrapped comment is allowed to run: the top of the
    "ALLERGEN INFORMATION" row, less a small margin, so a long note stays
    inside the white band and never collides with the icon legend.
    """

    for layer in psd.descendants():
        if layer.name.strip().upper() == "ALLERGEN INFORMATION":
            return int(layer.bbox[1]) - 12
    return int(comment_layer.bbox[3]) + 70
