from PIL import ImageDraw

from psd.text import (
    get_text_style,
    get_font_size,
    get_font_name,
    get_text_color,
    get_text_alignment,
    find_font,
    load_font,
)


def render_psd(
    psd,
    text_layers,
):

    image = psd.composite().convert(
        "RGBA"
    )

    draw = ImageDraw.Draw(
        image
    )

    for data in text_layers:

        layer = data["layer"]

        # Hidden layer stays hidden.
        if not layer.visible:
            continue

        original = data[
            "original_text"
        ]

        replacement = data[
            "replacement"
        ]

        if replacement == original:
            continue

        draw_replacement(
            image,
            draw,
            data,
        )

    return image


def draw_replacement(
    image,
    draw,
    data,
):

    layer = data["layer"]

    # =================================================
    # ORIGINAL TEXT BOX
    # =================================================

    left, top, right, bottom = (
        layer.bbox
    )

    left = int(left)
    top = int(top)
    right = int(right)
    bottom = int(bottom)

    width = right - left
    height = bottom - top

    # =================================================
    # ORIGINAL TYPOGRAPHY
    # =================================================

    style = get_text_style(
        layer
    )

    font_size = get_font_size(
        layer,
        height,
    )

    font_name = get_font_name(
        layer
    )

    font_path = find_font(
        font_name
    )

    font = load_font(
        font_path,
        font_size,
    )

    text_color = get_text_color(
        layer
    )

    alignment = get_text_alignment(
        layer
    )

    # =================================================
    # COVER OLD TEXT
    # =================================================

    cover_text_area(
        image,
        draw,
        left,
        top,
        right,
        bottom,
    )

    # =================================================
    # NORMALISE NEW TEXT
    # =================================================

    replacement = data[
        "replacement"
    ]

    replacement = replacement.replace(
        "\r\n",
        "\n",
    )

    replacement = replacement.replace(
        "\r",
        "\n",
    )

    # =================================================
    # SPLIT INTO LINES
    # =================================================
    #
    # Font stays at the original PSD size regardless of
    # how the replacement text compares to the original.
    #

    lines = replacement.split(
        "\n"
    )

    line_spacing = int(
        font_size * 1.2
    )

    # =================================================
    # CALCULATE TOTAL HEIGHT
    # =================================================
    #
    # Use the font's fixed ascent/descent metrics, not
    # each line's tight ink bbox. Ink bbox height depends
    # on which glyphs happen to be present (e.g. a "g"
    # descender makes the box taller than "Breast" has),
    # so centering off it shifts position per string. The
    # font metrics are constant regardless of content, so
    # vertical position stays put as the text is edited.

    ascent, descent = font.getmetrics()

    line_height = ascent + descent

    total_height = (
        line_height * len(lines)
        +
        line_spacing * (
            len(lines) - 1
        )
    )

    # =================================================
    # CENTER VERTICALLY
    # =================================================

    current_y = (
        top +
        (height - total_height) / 2
    )

    # =================================================
    # DRAW EACH LINE
    # =================================================

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font,
        )

        text_width = (
            bbox[2] -
            bbox[0]
        )

        # ---------------------------------------------
        # ALIGNMENT
        # ---------------------------------------------

        if alignment == "center":

            x = (
                left +
                (width - text_width) / 2
            )

        elif alignment == "right":

            x = (
                right -
                text_width
            )

        else:

            x = left

        # ---------------------------------------------
        # DRAW
        # ---------------------------------------------
        #
        # draw.text() anchors (x, y) on the ascender line
        # by default, which is exactly what current_y
        # already represents — only the horizontal ink
        # offset needs compensating.

        draw.text(
            (
                int(x - bbox[0]),
                int(current_y),
            ),
            line,
            font=font,
            fill=text_color,
        )

        current_y += (
            line_height +
            line_spacing
        )


def cover_text_area(
    image,
    draw,
    left,
    top,
    right,
    bottom,
):

    """
    Temporary background replacement.

    This can later be replaced by an intelligent
    background reconstruction method.
    """

    padding = 4

    sample_x = max(
        0,
        left - 5,
    )

    sample_y = max(
        0,
        top - 5,
    )

    background = image.getpixel(
        (
            sample_x,
            sample_y,
        )
    )

    draw.rectangle(
        (
            left - padding,
            top - padding,
            right + padding,
            bottom + padding,
        ),
        fill=background,
    )