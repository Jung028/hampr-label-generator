import os

from PIL import ImageFont


def get_text_style(layer):
    """
    Extract as much typography information as possible
    from the original Photoshop text layer.
    """

    style = {
        "font_size": None,
        "color": (0, 0, 0, 255),
        "alignment": "left",
        "line_height": None,
    }

    try:

        engine = layer.engine_dict

        # =================================================
        # STYLE RUN
        # =================================================

        style_run = engine.get(
            "StyleRun",
            {}
        )

        run_array = style_run.get(
            "RunArray",
            []
        )

        if run_array:

            first_run = run_array[0]

            style_data = (
                first_run
                .get("StyleSheet", {})
                .get("StyleSheetData", {})
            )

            # ---------------------------------------------
            # FONT SIZE
            # ---------------------------------------------

            font_size = style_data.get(
                "FontSize"
            )

            if font_size:

                style["font_size"] = int(
                    float(font_size)
                )

            # ---------------------------------------------
            # COLOUR
            # ---------------------------------------------

            fill_color = style_data.get(
                "FillColor"
            )

            if fill_color:

                values = fill_color.get(
                    "Values"
                )

                if values and len(values) >= 4:

                    style["color"] = (
                        int(values[1] * 255),
                        int(values[2] * 255),
                        int(values[3] * 255),
                        255,
                    )

    except Exception:
        pass

    # =====================================================
    # PARAGRAPH ALIGNMENT
    # =====================================================

    try:

        paragraph_run = engine.get(
            "ParagraphRun",
            {}
        )

        paragraph_array = paragraph_run.get(
            "RunArray",
            []
        )

        if paragraph_array:

            paragraph_data = (
                paragraph_array[0]
                .get("ParagraphSheet", {})
                .get("Properties", {})
            )

            justification = paragraph_data.get(
                "Justification"
            )

            if justification is not None:

                alignment_map = {
                    0: "left",
                    1: "right",
                    2: "center",
                    3: "justify",
                }

                style["alignment"] = (
                    alignment_map.get(
                        justification,
                        "left"
                    )
                )

    except Exception:
        pass

    return style


def get_font_size(
    layer,
    fallback_height,
):
    """
    Get original Photoshop font size.
    """

    style = get_text_style(
        layer
    )

    if style["font_size"]:
        return style["font_size"]

    return max(
        10,
        int(fallback_height * 0.8)
    )


def get_font_name(layer):
    """
    The StyleSheetData "Font" value is an index into the
    layer's own FontSet resource table, not a usable name
    (get_text_style() surfaces that raw index, which is
    why we don't use it here). layer.font_names already
    resolves the index to the real PostScript font name.
    """

    try:

        names = layer.font_names

        if names:
            return names[0]

    except Exception:
        pass

    return None


def get_text_color(layer):

    style = get_text_style(
        layer
    )

    return style["color"]


def get_text_alignment(layer):

    style = get_text_style(
        layer
    )

    return style["alignment"]


def find_font(font_name):
    """
    Search common OS font directories.
    """

    if not font_name:
        return None

    directories = [

        # macOS
        "/System/Library/Fonts",
        "/Library/Fonts",
        os.path.expanduser(
            "~/Library/Fonts"
        ),

        # Fonts bundled with locally installed apps
        # (e.g. Microsoft Office ships display fonts like
        # Britannic Bold that aren't registered as system
        # fonts elsewhere).
        "/Applications/Microsoft Word.app/Contents/Resources/DFonts",

        # Linux
        "/usr/share/fonts",
        "/usr/local/share/fonts",

        # Windows
        "C:/Windows/Fonts",
    ]

    target = (
        str(font_name)
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )

    for directory in directories:

        if not os.path.exists(
            directory
        ):
            continue

        for root, _, files in os.walk(
            directory
        ):

            for filename in files:

                if not filename.lower().endswith(
                    (
                        ".ttf",
                        ".otf",
                        ".ttc",
                    )
                ):
                    continue

                simplified = (
                    filename
                    .lower()
                    .replace(" ", "")
                    .replace("-", "")
                    .replace("_", "")
                )

                if target in simplified:

                    return os.path.join(
                        root,
                        filename
                    )

    return None


def load_font(
    font_path,
    size,
):

    if font_path:

        try:

            return ImageFont.truetype(
                font_path,
                size,
            )

        except Exception:
            pass

    fallback_fonts = [

        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf",
        "Arial.ttf",
    ]

    for path in fallback_fonts:

        try:

            return ImageFont.truetype(
                path,
                size,
            )

        except Exception:
            continue

    return ImageFont.load_default()