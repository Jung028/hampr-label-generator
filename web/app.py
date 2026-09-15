"""
Local web UI for label generation.

Thin wrapper around generate_labels.py: paste (or upload) a captured
Hampr order-detail API response, generate labels, browse/download the
results. No new business logic lives here — parsing, dish resolution,
font-consistency handling, and the name-review flag are all the same
code the CLI (generate_labels.py) uses.

Local-only tool, no auth: same trust model as running the CLI by hand on
your own machine. Do not expose this to the network.
"""

import io
import json
import os
import sys
import zipfile
from collections import Counter
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, abort, url_for
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_labels  # noqa: E402
from export.pdf import export_pdf  # noqa: E402

RUNS_DIR = os.path.join(generate_labels.OUTPUT_DIR, "runs")

app = Flask(__name__)

# run_id -> {filename: gen_dict}, keeping each run's per-label render
# state (psd_filename, dish_label, variant, special_instructions) around
# in memory so a later special-instructions edit can re-render just that
# one label. Local-only tool, single process, no persistence needed
# across restarts.
RUN_LABEL_STATE = {}

# Order-detail responses (pasted whole into the response_json textarea, a
# multipart form field) can run well past Werkzeug's 500KB default form
# memory cap, which otherwise fails the request with a 413 before our own
# JSON-size handling ever runs.
app.config["MAX_FORM_MEMORY_SIZE"] = 50 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def _safe_run_id(order_id):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{generate_labels._safe_filename(str(order_id))}-{stamp}"


def _run_dir(run_id):
    # run_id always comes from a URL path segment here — collapse it to a
    # bare filename first so a crafted "../../etc" can't escape RUNS_DIR.
    safe_id = secure_filename(run_id)
    run_dir = os.path.join(RUNS_DIR, safe_id)
    if not os.path.isdir(run_dir):
        abort(404)
    return run_dir


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    raw = request.form.get("response_json", "").strip()

    upload = request.files.get("response_file")
    if not raw and upload and upload.filename:
        raw = upload.read().decode("utf-8", errors="replace")

    if not raw:
        return render_template("index.html", error="Paste the response JSON or choose a file first.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return render_template("index.html", error=f"That doesn't look like valid JSON: {e}", raw=raw)

    try:
        orders = generate_labels.parse_orders(data)
    except (KeyError, TypeError):
        return render_template(
            "index.html",
            error="Valid JSON, but not in the expected shape (missing purchaseContentDetails.items).",
            raw=raw,
        )

    order_id = data.get("id", "order")
    run_id = _safe_run_id(order_id)
    run_dir = os.path.join(RUNS_DIR, run_id)

    result = generate_labels.process_orders(orders, output_dir=run_dir)

    flags_by_name = {
        (r["customer_name"], r["dish_label"]): r["flags"]
        for r in result["review_needed"]
    }

    RUN_LABEL_STATE[run_id] = {}
    for gen in result["generated"]:
        gen["filename"] = os.path.basename(gen["out_path"])
        gen["flags"] = flags_by_name.get((gen["customer_name"], gen["dish_label"]), [])
        gen["view_url"] = url_for("view", run_id=run_id, filename=gen["filename"])
        RUN_LABEL_STATE[run_id][gen["filename"]] = gen

    # Kitchen-prep summary: how many of each exact printed dish (base
    # name + protein/variant, e.g. "Nasi Goreng - Beef") need making,
    # sorted biggest batch first.
    dish_counts = Counter(gen["full_dish_name"] for gen in result["generated"])
    dish_summary = sorted(
        ({"dish_name": name, "quantity": qty} for name, qty in dish_counts.items()),
        key=lambda d: (-d["quantity"], d["dish_name"]),
    )
    total_dishes = sum(dish_counts.values())

    return render_template(
        "index.html",
        result=result,
        run_id=run_id,
        order_id=order_id,
        dish_summary=dish_summary,
        total_dishes=total_dishes,
    )


@app.route("/download/<run_id>/<filename>")
def download(run_id, filename):
    # Not run through secure_filename: that strips accented letters (e.g.
    # "ñ" -> "n"), which no longer matches a saved file for a customer
    # name like "Bañuelos" and 404s. send_from_directory already blocks
    # path traversal on its own, so this is safe without it.
    run_dir = _run_dir(run_id)
    return send_from_directory(run_dir, filename, as_attachment=True)


@app.route("/view/<run_id>/<filename>")
def view(run_id, filename):
    # Same file as /download, but served inline (no Content-Disposition:
    # attachment) so it can be used as an <img src> in the one-by-one
    # review viewer instead of triggering a browser download prompt.
    run_dir = _run_dir(run_id)
    return send_from_directory(run_dir, filename, as_attachment=False)


@app.route("/update-special-instructions/<run_id>/<filename>", methods=["POST"])
def update_special_instructions(run_id, filename):
    # Re-renders just this one label with edited special instructions —
    # everything else about it (customer, dish, template, protein) is
    # unchanged, so we reuse the psd_filename/dish_label/variant this
    # run already resolved for it in generate() rather than re-parsing
    # the original order.
    run_dir = _run_dir(run_id)
    state = RUN_LABEL_STATE.get(run_id)
    if state is None:
        abort(404)

    filename = os.path.basename(filename)
    gen = state.get(filename)
    if gen is None:
        abort(404)

    payload = request.get_json(silent=True) or {}
    special_instructions = str(payload.get("special_instructions", "")).strip()

    order = {
        "customer_name": gen["customer_name"],
        "options": gen["options"],
        "special_instructions": special_instructions,
    }
    generate_labels.generate_label(
        order, gen["psd_filename"], gen["dish_label"], gen["variant"], output_dir=run_dir
    )

    gen["special_instructions"] = special_instructions
    flags = generate_labels.name_review_flags(gen["customer_name"])
    if special_instructions:
        flags = flags + [f"special instructions: {special_instructions}"]
    gen["flags"] = flags

    return jsonify({"ok": True, "flags": flags})


@app.route("/download-pdf/<run_id>/<filename>")
def download_pdf(run_id, filename):
    run_dir = _run_dir(run_id)
    src_path = os.path.join(run_dir, os.path.basename(filename))
    if not os.path.isfile(src_path):
        abort(404)

    buffer = io.BytesIO()
    export_pdf([src_path], buffer)
    buffer.seek(0)

    pdf_name = os.path.splitext(os.path.basename(filename))[0] + ".pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_name,
    )


@app.route("/download-pdf-batch/<run_id>")
def download_pdf_batch(run_id):
    run_dir = _run_dir(run_id)

    # Basenamed to strip any directory components before checking the file
    # actually exists in this run's own output directory.
    filenames = [os.path.basename(f) for f in request.args.getlist("files")]
    src_paths = [os.path.join(run_dir, f) for f in filenames if os.path.isfile(os.path.join(run_dir, f))]
    if not src_paths:
        abort(400)

    buffer = io.BytesIO()
    export_pdf(src_paths, buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{run_id}-labels.pdf",
    )


@app.route("/download-zip/<run_id>")
def download_zip(run_id):
    run_dir = _run_dir(run_id)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in sorted(os.listdir(run_dir)):
            zf.write(os.path.join(run_dir, filename), arcname=filename)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{run_id}.zip",
    )


if __name__ == "__main__":
    os.makedirs(RUNS_DIR, exist_ok=True)
    app.run(debug=True)
