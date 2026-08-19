# hampr-label-generator

Standalone label-generation engine for Ipoh Town / Hampr catering orders.

This is a clean extraction of the PSD-parsing and icon-toggle rendering
logic originally built in `catering-label-automation/backend/prototype`,
decoupled from that repo's backend (which has its own, currently broken,
CSV-based pipeline). This project has no dependency on that backend.

## What this does today

`generate_labels.py` takes structured order data (customer name, dish,
selected options, special instructions) and renders a print-ready label
PNG per order, by:

1. Loading the dish's source PSD template from `templates/`.
2. Replacing the dish-name/variant text layer, customer-name layer, and
   (if present) special-instructions text layer.
3. Toggling icon layers' visibility based on the order's selected options
   (e.g. a "Gluten Free" option turns on the `GlutenFreeLogo` layer).
4. Compositing and exporting the result to `output/`.

There is no live order source wired up yet. `ORDERS` in
`generate_labels.py` is typed in by hand from a real Hampr "Orders" page
screenshot, as a stand-in for what a browser extension will eventually
scrape and POST here. Once page access is available, replace that list
with real scraped data using the same shape — the rendering logic itself
does not need to change.

## Structure

```
psd/           # PSD parsing/rendering (loader, layer/font handling, compositor)
export/        # PNG export
templates/     # Source .psd files for each dish
output/        # Generated label PNGs (gitignored)
generate_labels.py
```

## Layer-toggle mechanism

There is no special "variant" system — toggling an icon is just PSD
layer visibility:

1. Load the PSD (`psd_tools.PSDImage.open`) — every layer has a
   `.visible` boolean.
2. Look up the layer by name.
3. Set `.visible = True/False`.
4. Render (`psd/renderer.py::render_psd`) — this calls `psd.composite()`,
   which reflattens the canvas respecting current `.visible` flags.
5. Export the resulting image to PNG.

Known per-template quirks (from the source repo's exploration):
- Not every dish template has a `GlutenFreeLogo` layer — check the
  actual layers before assuming a standard icon set.
- Some templates bake gluten-free in as a *static* fact (e.g. Beef
  Rendang Rice's `GlutenFreeLogo` is `visible=True` by default, not a
  customer-selected option) rather than a per-order toggle.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 generate_labels.py
```

## Next steps (not built yet)

- Browser extension (Manifest V3) to scrape the real Hampr Orders page
  and POST structured order data here instead of the hand-typed `ORDERS`
  list — deferred until page access is available.
- More dish templates beyond Hainan Chicken / Beef Rendang, as needed.


Resume  : claude --resume 002f53e0-d6e8-4d70-8dd3-c4c410a7a9bc
