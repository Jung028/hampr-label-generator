from functools import lru_cache

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


@lru_cache(maxsize=256)
def _load_font_cached(font_path, size):
    return load_font(font_path, size)


def _line_advance(font):
    # Baseline-to-baseline distance for wrapped text. The font's own
    # ascent + descent is natural single spacing; the renderer used to
    # add another ~1.2em of leading on top of that, which left a wrapped
    # note looking almost double-spaced. Single spacing keeps the lines
    # of one comment visually together.
    ascent, descent = font.getmetrics()
    return ascent + descent


def _block_fits(num_lines, font, top, max_bottom):
    if max_bottom is None:
        return True

    cap_box = font.getbbox("H")
    cap_height = cap_box[3] - cap_box[1]

    _, descent = font.getmetrics()

    first_baseline_y = top + cap_height
    last_baseline_y = first_baseline_y + (num_lines - 1) * _line_advance(font)

    return last_baseline_y + descent <= max_bottom


def fit_text_to_box(
    text,
    font_path,
    base_font_size,
    width,
    top,
    max_bottom,
    short_text=None,
    min_font_size=None,
):
    """
    Word-wrap `text` to `width` so the whole block fits above `max_bottom`
    (the top of whatever sits below this layer in the template, e.g. the
    allergen icon row), shrinking the font if it has to.

    Starts at `base_font_size`; if the wrapped block is too tall, steps
    the size down one pixel at a time to `min_font_size` (default: 60% of
    base, floored at 12px) and returns the first size the full text fits
    at. Only if the full text will not fit even at `min_font_size` does it
    fall back to the caller's `short_text` (a business-logic-shortened
    version of the same content), tried the same way, and finally to
    truncating the last line with an ellipsis at `min_font_size`.

    Returns (font, lines).
    """

    base_font_size = int(base_font_size)
    if min_font_size is None:
        min_font_size = max(12, int(base_font_size * 0.6))
    min_font_size = min(min_font_size, base_font_size)

    def _largest_fit(candidate_text):
        for size in range(base_font_size, min_font_size - 1, -1):
            font = _load_font_cached(font_path, size)
            wrapped = _wrap_text(candidate_text, font, width)
            if _block_fits(len(wrapped), font, top, max_bottom):
                return font, wrapped
        return None

    fitted = _largest_fit(text)
    if fitted is not None:
        return fitted

    if short_text is not None:
        fitted = _largest_fit(short_text)
        if fitted is not None:
            return fitted

    # Won't fit even at the floor size — truncate the last line there.
    font = _load_font_cached(font_path, min_font_size)
    source = short_text if short_text is not None else text
    lines = _wrap_text(source, font, width)

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

    # A caller can widen the drawing box beyond the placeholder's tight
    # ink bounds — needed for the Nanyang comment layer, whose "notes"
    # placeholder is only wide enough for that one word but which has to
    # hold a full free-text comment. The box stays centred on the
    # placeholder (every such layer is centre-aligned), so the wider box
    # just gives the wrap logic and the old-text cover more room.
    width_override = data.get("width_override")
    if width_override:
        center_x = (left + right) / 2
        left = int(center_x - width_override / 2)
        right = int(center_x + width_override / 2)
        width = int(width_override)

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

    line_advance = _line_advance(font)

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

        baseline_y = first_baseline_y + index * line_advance

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