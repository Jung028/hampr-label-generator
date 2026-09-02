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
    Resolve the layer's real PostScript font name (e.g. "BritannicBold").

    The StyleSheetData "Font" value is only an *index* into the document's
    FontSet resource table (a list of {"Name": ...} entries). Newer
    psd-tools exposes ``layer.font_names`` which does that lookup for you,
    but the version pinned here (1.11.0) does not have that attribute — the
    call raised AttributeError, the bare except swallowed it, and every
    label fell back to Helvetica. So read the FontSet directly, and only
    use ``font_names`` as a bonus path when it happens to exist.
    """

    try:

        names = layer.font_names

        if names:
            return names[0]

    except Exception:
        pass

    try:

        run = layer.engine_dict["StyleRun"]["RunArray"][0]
        index = int(run["StyleSheet"]["StyleSheetData"]["Font"])

        font_set = (
            (layer.resource_dict or {}).get("FontSet")
            or (layer.document_resources or {}).get("FontSet")
        )

        if font_set and 0 <= index < len(font_set):

            name = font_set[index].get("Name")

            if name:
                # psd-tools returns a "String" wrapper, not a plain str.
                return str(name)

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


# Foundry / style tokens that appear in a PostScript font name but not in
# the on-disk filename (or vice versa), so they must not block a match.
# "ArialRoundedMTBold" (PS name) vs "Arial Rounded Bold.ttf" (file) only
# line up once "mt" is ignored.
_FONT_NOISE_TOKENS = ("mt", "std", "pro", "regular", "roman", "book")


def _simplify_font_token(value):

    token = "".join(
        ch for ch in str(value).lower() if ch.isalnum()
    )

    for noise in _FONT_NOISE_TOKENS:
        token = token.replace(noise, "")

    return token


def _font_name_matches(target, candidate_filename):

    target = _simplify_font_token(target)

    candidate = _simplify_font_token(
        os.path.splitext(candidate_filename)[0]
    )

    if not target or not candidate:
        return False

    if target == candidate:
        return True

    # Primary direction: the (noise-stripped) font name appears in the
    # filename — "arialroundedbold" is inside "Arial Rounded Bold.ttf".
    if len(target) >= 4 and target in candidate:
        return True

    # Reverse direction only for a specific-enough filename, so a bare
    # "Arial.ttf" isn't claimed by every "Arial*" request.
    if len(candidate) >= 8 and candidate in target:
        return True

    return False


def find_font(font_name):
    """
    Search common OS font directories for a file matching font_name.

    Matching is deliberately fuzzy: the PostScript name Photoshop stores
    ("ArialRoundedMTBold") rarely equals the filename ("Arial Rounded
    Bold.ttf"), so compare on alphanumerics only with foundry/style noise
    tokens stripped, and accept a match in either direction.
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

                if _font_name_matches(font_name, filename):

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