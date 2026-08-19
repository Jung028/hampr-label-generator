def get_all_layers(psd):
    """
    Return every layer in the PSD, including layers
    nested inside groups.
    """
    return list(psd.descendants())


def get_text_layers(psd):
    """
    Return all actual Photoshop text layers.
    """

    result = []

    for layer in psd.descendants():

        if layer.kind != "type":
            continue

        try:
            text = layer.text
        except Exception:
            continue

        if not text:
            continue

        result.append(layer)

    return result


def find_special_instructions_layer(psd):
    """
    Find the Special Instructions text layer.

    We still allow several common Photoshop layer names.
    """

    possible_names = {
        "special instructions",
        "special instruction",
        "instructions",
    }

    for layer in get_text_layers(psd):

        if layer.name.strip().lower() in possible_names:
            return layer

    return None


def find_variant_layers(psd):
    """
    Find layers using:

        Hainan Chicken Rice - Breast

    The part after ' - ' is editable.
    """

    result = []

    for layer in get_text_layers(psd):

        if " - " not in layer.name:
            continue

        prefix, editable = layer.name.rsplit(
            " - ",
            1,
        )

        result.append({
            "layer": layer,
            "type": "variant",
            "label": prefix,
            "prefix": prefix,
            "original_text": layer.text,
            "replacement": editable,
        })

    return result


def find_item_name_layer(
    psd,
    variant_layers,
):
    """
    Find the item-name text layer.

    The item name is the text layer that shares the same
    item name as the variant prefix.

    Example:

        Item layer:
            Hainan Chicken Rice

        Variant layer:
            Hainan Chicken Rice - Breast

    Therefore:

        Item name = Hainan Chicken Rice
        Variant   = Breast
    """

    text_layers = get_text_layers(psd)

    for variant in variant_layers:

        prefix = variant["prefix"].strip()

        for layer in text_layers:

            # Don't identify the variant layer itself.
            if layer is variant["layer"]:
                continue

            try:
                text = layer.text.strip()
            except Exception:
                continue

            if text == prefix:

                return layer

    return None


def find_customer_name_layer(
    psd,
    item_name_layer,
):
    """
    Find the customer name.

    The customer name is the text layer ABOVE the item name
    and below the logo/header area.

    We therefore use the layer's physical Y position.

    The closest text layer above the item name is selected.
    """

    if item_name_layer is None:
        return None

    item_left, item_top, item_right, item_bottom = (
        item_name_layer.bbox
    )

    candidates = []

    for layer in get_text_layers(psd):

        if layer is item_name_layer:
            continue

        left, top, right, bottom = layer.bbox

        # Must be above the item name.
        if bottom >= item_top:
            continue

        # Prefer text roughly aligned horizontally.
        item_center = (
            item_left + item_right
        ) / 2

        layer_center = (
            left + right
        ) / 2

        horizontal_distance = abs(
            item_center - layer_center
        )

        vertical_distance = (
            item_top - bottom
        )

        candidates.append({
            "layer": layer,
            "horizontal_distance": horizontal_distance,
            "vertical_distance": vertical_distance,
        })

    if not candidates:
        return None

    # Prefer a layer that is:
    # 1. horizontally aligned
    # 2. closest vertically

    candidates.sort(
        key=lambda x: (
            x["horizontal_distance"],
            x["vertical_distance"],
        )
    )

    return candidates[0]["layer"]


def get_editable_text_layers(psd):
    """
    Build the complete editable-text model.

    Supported:

        Customer Name
        Item Name
        Variant
        Special Instructions
    """

    result = []

    # =====================================================
    # VARIANT
    # =====================================================

    variants = find_variant_layers(
        psd
    )

    for variant in variants:
        result.append(variant)

    # =====================================================
    # ITEM NAME
    # =====================================================

    item_layer = find_item_name_layer(
        psd,
        variants,
    )

    if item_layer:

        result.append({
            "layer": item_layer,
            "type": "item_name",
            "label": "Item Name",
            "prefix": "",
            "original_text": item_layer.text,
            "replacement": item_layer.text,
        })

    # =====================================================
    # CUSTOMER NAME
    # =====================================================

    customer_layer = find_customer_name_layer(
        psd,
        item_layer,
    )

    if customer_layer:

        # Avoid accidentally adding the same layer twice.
        already_added = any(
            data["layer"] is customer_layer
            for data in result
        )

        if not already_added:

            result.append({
                "layer": customer_layer,
                "type": "customer_name",
                "label": "Customer Name",
                "prefix": "",
                "original_text": customer_layer.text,
                "replacement": customer_layer.text,
            })

    # =====================================================
    # SPECIAL INSTRUCTIONS
    # =====================================================

    instructions_layer = (
        find_special_instructions_layer(
            psd
        )
    )

    if instructions_layer:

        already_added = any(
            data["layer"] is instructions_layer
            for data in result
        )

        if not already_added:

            result.append({
                "layer": instructions_layer,
                "type": "special_instructions",
                "label": "Special Instructions",
                "prefix": "",
                "original_text": instructions_layer.text,
                "replacement": instructions_layer.text,
            })

    return result