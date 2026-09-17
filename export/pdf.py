from PIL import Image

# Matches the EPSON TM-C3500 driver's configured die-cut label media
# (Media Width 101.0mm / Media Length 73.0mm, Portrait).
LABEL_WIDTH_MM = 101.0
LABEL_HEIGHT_MM = 73.0
DPI = 300


def _mm_to_px(mm, dpi=DPI):
    return round(mm / 25.4 * dpi)


def _page_image(source, page_size_px):
    """
    Fill a page of exactly `page_size_px` with `source` — scaled up or
    down as needed and center-cropped to cover the whole page, so the
    label always fills the physical die-cut area with no printed border.

    The label PSDs aren't rendered at exactly the die-cut's aspect ratio
    (e.g. 1078x768 vs. this label's 1193x862 target), and the previous
    "shrink to fit, never enlarge" behavior left a visible white margin
    on every side once the low-res render was centered on the full-size
    page. Covering instead crops a sliver off one axis — imperceptible
    at this scale — rather than leaving a border.
    """
    page_w, page_h = page_size_px
    src = source.convert("RGBA")

    scale = max(page_w / src.width, page_h / src.height)
    fitted_w = max(1, round(src.width * scale))
    fitted_h = max(1, round(src.height * scale))
    if (fitted_w, fitted_h) != src.size:
        src = src.resize((fitted_w, fitted_h), Image.LANCZOS)

    left = (fitted_w - page_w) // 2
    top = (fitted_h - page_h) // 2
    src = src.crop((left, top, left + page_w, top + page_h))

    page = Image.new("RGB", page_size_px, "white")
    page.paste(src, (0, 0), src)
    return page


def export_pdf(image_paths, path):
    """
    Render one or more label images as a PDF, one label per page, each
    page sized to exactly match the physical label (101mm x 73mm) so it
    prints correctly regardless of the destination printer/app's own
    page-size defaults.
    """
    page_size_px = (_mm_to_px(LABEL_WIDTH_MM), _mm_to_px(LABEL_HEIGHT_MM))
    pages = [_page_image(Image.open(p), page_size_px) for p in image_paths]

    first, rest = pages[0], pages[1:]
    first.save(
        path,
        "PDF",
        resolution=DPI,
        save_all=True,
        append_images=rest,
    )
