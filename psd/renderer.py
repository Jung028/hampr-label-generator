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


def _wrap_to_width(line, font, max_width):
    words = line.split(" ")

    if not words:
        return [line]

    wrapped = [words[0]]

    for word in words[1:]:

        candidate = f"{wrapped[-1]} {word}"

        if font.getlength(candidate) <= max_width:
            wrapped[-1] = candidate
        else:
            wrapped.append(word)

    return wrapped


def _wrap_text(text, font, max_width):
    # Word-wrap each existing line independently, so an explicit line
    # break the caller already chose is preserved rather than merged
    # into the paragraph.
    lines = []

    for line in text.split("\n"):
        lines.extend(_wrap_to_width(line, font, max_width))

    return lines


def _block_fits(num_lines, font, top, max_bottom):
    if max_bottom is None:
        return True

    cap_box = font.getbbox("H")
    cap_height = cap_box[3] - cap_box[1]

    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    line_spacing = int(font.size * 1.2)

    first_baseline_y = top + cap_height
    last_baseline_y = first_baseline_y + (num_lines - 1) * (line_height + line_spacing)

    return last_baseline_y + descent <= max_bottom


def fit_text_to_box(text, font_path, base_font_size, width, top, max_bottom, short_text=None):
    """
    Word-wrap `text` to `width` at a fixed `base_font_size` — the font
    never shrinks, so the label stays as legible as any short comment.
    If the full text doesn't fit above `max_bottom` (the top of whatever
    sits below this layer in the template, e.g. the allergen icon row)
    and the caller supplied a `short_text` fallback (a shortened,
    business-logic-chosen version of the same content), that is tried
    next, still at the same size. If nothing fits, the last line is
    truncated with an ellipsis, still at the same size.
    Returns (font, lines).
    """

    font = load_font(font_path, base_font_size)

    lines = _wrap_text(text, font, width)
    if _block_fits(len(lines), font, top, max_bottom):
        return font, lines

    if short_text is not None:
        short_lines = _wrap_text(short_text, font, width)
        if _block_fits(len(short_lines), font, top, max_bottom):
            return font, short_lines
        lines = short_lines

    max_lines = 1
    while max_lines < len(lines) and _block_fits(max_lines + 1, font, top, max_bottom):
        max_lines += 1

    kept = lines[:max_lines]

    if len(kept) < len(lines):
        last = kept[-1]
        while font.getlength(last + "…") > width and " " in last:
            last = last.rsplit(" ", 1)[0]
        kept[-1] = last + "…"

    return font, kept


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

        # A layer with a font_override must always be redrawn, even if
        # its text happens to already match — otherwise a template whose
        # default dish-name text is coincidentally already correct would
        # keep its own (possibly inconsistent) original PSD font/size.
        if (
            replacement == original
            and not data.get("font_override")
        ):
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

    font_override = data.get(
        "font_override"
    )

    if font_override:

        font_name, font_size = (
            font_override
        )

    else:

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
    # Font stays at the original PSD size regardless of how the
    # replacement text compares to the original — UNLESS the caller
    # opted in with "max_bottom" (currently just the special-instructions
    # layer), in which case a long comment is word-wrapped at that same
    # fixed size, and shortened to its key phrase if it still doesn't
    # fit, rather than running off the sides or down into whatever sits
    # below it in the template (e.g. the allergen icons).
    #

    max_bottom = data.get(
        "max_bottom"
    )

    if max_bottom is not None:

        font, lines = fit_text_to_box(
            replacement,
            font_path,
            font_size,
            width,
            top,
            max_bottom,
            short_text=data.get("replacement_short"),
        )

    else:

        lines = replacement.split(
            "\n"
        )

    line_spacing = int(
        font.size * 1.2
    )

    # =================================================
    # VERTICAL PLACEMENT
    # =================================================
    #
    # layer.bbox is the tight ink box of the template's
    # placeholder text, and every placeholder here starts
    # with a capital, so bbox `top` is the cap line. Put
    # the replacement's cap line there too and it lands
    # where Photoshop drew the original.
    #
    # All measurements are font metrics (constant for a
    # given font+size), never the replacement string's own
    # ink bounds — so the position doesn't drift as the
    # text is edited or when a line has/​lacks descenders.

    ascent, descent = font.getmetrics()

    line_height = ascent + descent

    # Distance from the drawn baseline up to the cap line,
    # from the ink box of a capital H.
    cap_box = font.getbbox("H")
    cap_height = cap_box[3] - cap_box[1]

    first_baseline_y = top + cap_height

    # PIL anchor: first char horizontal (l/m/r), second
    # vertical — "s" = baseline.
    if alignment == "center":
        anchor = "ms"
        anchor_x = left + width / 2
    elif alignment == "right":
        anchor = "rs"
        anchor_x = right
    else:
        anchor = "ls"
        anchor_x = left

    # =================================================
    # DRAW EACH LINE
    # =================================================

    for index, line in enumerate(lines):

        baseline_y = (
            first_baseline_y
            + index * (line_height + line_spacing)
        )

        draw.text(
            (
                int(anchor_x),
                int(baseline_y),
            ),
            line,
            font=font,
            fill=text_color,
            anchor=anchor,
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