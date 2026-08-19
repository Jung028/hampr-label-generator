from psd_tools import PSDImage


def load_psd(path):
    """
    Open a PSD file and return the PSDImage object.
    """

    return PSDImage.open(path)