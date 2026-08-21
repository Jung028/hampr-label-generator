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

Order data comes from `response-body.json` — a captured Hampr
order-detail API response — parsed by `load_orders_from_response()` in
`generate_labels.py`. If that file isn't present, it falls back to the
hand-typed `ORDERS` list (typed in from a real Hampr "Orders" page
screenshot) as a stand-in. Once a browser extension scrapes and POSTs
real order data here, either path can be swapped for it — the rendering
logic itself does not need to change.

Every dish is handled by one generic renderer (`generate_label()` in
`generate_labels.py`) driven by a per-dish `DISH_RESOLVERS` table, rather
than a hand-written function per dish. Each resolver just returns which
PSD template to use and the dish-name text to print (including any
protein/variant suffix, e.g. "Nasi Goreng - Beef"); the shared renderer
handles locating the customer-name and dish-name layers, applying
consistent typography (see below), toggling `GlutenFreeLogo`, and
exporting the PNG. A dish with no `DISH_RESOLVERS` entry is skipped with
a `SKIP` line rather than failing the whole run.

### Text-layer detection

Layer *names* aren't a reliable way to find the customer-name or
dish-name text layer — every template gives them different placeholder
names (`"Jin Ju Hong"`, `"Anonymous"`, `"Guest Order"`, `"Louis Lee"`,
...). Instead, `psd/layers.py` locates them positionally:

- **Dish name**: the text layer whose bounding box sits inside the
  `RedBand` pixel layer (the coloured strip every template renders the
  dish name on top of).
- **Customer name**: the text layer closest *above* the dish-name layer
  (vertical distance first, horizontal alignment as a tiebreaker).

### Font/size consistency

Every template's customer-name and dish-name layers are forced to the
same font and size, taken from the Hainan Chicken Rice template as the
reference (`NAME_STYLE` / `DISH_NAME_STYLE` in `generate_labels.py`) —
some source PSDs had drifted (e.g. Beef Rendang Rice's dish-name layer
was authored at 100pt vs. Hainan's 87pt). Color and alignment still come
from each layer's own PSD styling; only font and size are overridden.

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
  and POST structured order data here directly, instead of relying on a
  manually captured `response-body.json`.
- `DISH_RESOLVERS` currently covers the 13 dishes seen in the captured
  order; templates like Korma Vege, Curry Vege/Fish, Szechuan, etc. have
  no resolver yet and will `SKIP`. Some resolved dishes (Mee Goreng,
  Nasi Goreng, Ipoh Char Kway Teow) only ever route to the "Meat"
  template variant because no vegetarian/vegan option has appeared in
  captured order data yet — worth confirming against a real vege/vegan
  order before this goes into production use.

ToDo : 
1. Find at least 2-3 more response that can used for testing, need to find gluten free, extra instructions, and special instructions
3. Fix the print format, what size, in windows. follow from photoship print. 
4. Collect Data response at least 3-5 for Nanyang. and get all the templates for this as well. 
5. A design - maybe we can add open button for this psd in photoshop app directly to edit, and print. 