def export_png(
    image,
    path,
):
    """
    Export the rendered image as PNG.
    """

    image.save(
        path,
        "PNG",
    )