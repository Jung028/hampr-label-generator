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
    Place `source` on a white page of exactly `page_size_px`, scaled down
    to fit (never up) and centered — the same "contain" behavior the
    on-screen/print preview uses, so the PDF matches what users already
    see, but without relying on a browser's print pipeline to honor a
    custom @page size.
    """
    page_w, page_h = page_size_px
    page = Image.new("RGB", page_size_px, "white")

    src = source.convert("RGBA")
    scale = min(page_w / src.width, page_h / src.height, 1.0)
    fitted_w = max(1, round(src.width * scale))
    fitted_h = max(1, round(src.height * scale))
    if (fitted_w, fitted_h) != src.size:
        src = src.resize((fitted_w, fitted_h), Image.LANCZOS)

    offset = ((page_w - fitted_w) // 2, (page_h - fitted_h) // 2)
    page.paste(src, offset, src)
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
