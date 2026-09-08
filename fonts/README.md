# Bundled fonts

These are the exact typefaces the `templates/*.psd` files were designed
with. They are shipped here so a label renders **identically on macOS,
Windows and Linux** — the renderer (`psd/text.py`) searches this folder
first, before any OS font directory.

| File | PostScript name in the PSD | Used for |
|------|----------------------------|----------|
| `ArialRoundedMTBold.ttf` | `ArialRoundedMTBold` | customer name |
| `Arial-BoldMT.ttf` | `Arial-BoldMT` | headings / "CONTAINS" etc. |
| `Arial-ItalicMT.ttf` | `Arial-ItalicMT` | italic captions |
| `BritannicBold.ttf` | `BritannicBold` | dish name (red band) |

The filename of each font is its PostScript name, so `find_font()` can
match it exactly.

## Why this exists

Before bundling, the renderer resolved these fonts from each OS's own
font folders. macOS has all four (Arial family in
`/System/Library/Fonts/Supplemental`, Britannic Bold from MS Office). A
stock Windows box often has none of them under a name the matcher could
recognise, so every label silently fell back to plain Arial Regular —
wrong weight, wrong width, wrong apparent size, different line wrapping.

## Licensing note

Arial (Monotype) and Britannic Bold (Monotype) are proprietary fonts,
licensed to you as part of macOS / Windows / Microsoft Office. Keep this
repository private. If it is ever made public, remove this folder and
have each machine supply the fonts locally, or substitute
metric-compatible open fonts.

To point the renderer at a different fonts folder without editing code,
set the `HAMPR_FONTS_DIR` environment variable.
