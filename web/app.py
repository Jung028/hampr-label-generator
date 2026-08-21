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
from datetime import datetime

from flask import Flask, render_template, request, send_file, send_from_directory, abort, url_for
from werkzeug.utils import secure_filename

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_labels  # noqa: E402

RUNS_DIR = os.path.join(generate_labels.OUTPUT_DIR, "runs")

app = Flask(__name__)


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

    for gen in result["generated"]:
        gen["filename"] = os.path.basename(gen["out_path"])
        gen["flags"] = flags_by_name.get((gen["customer_name"], gen["dish_label"]), [])
        gen["view_url"] = url_for("view", run_id=run_id, filename=gen["filename"])

    return render_template("index.html", result=result, run_id=run_id, order_id=order_id)


@app.route("/download/<run_id>/<filename>")
def download(run_id, filename):
    run_dir = _run_dir(run_id)
    return send_from_directory(run_dir, secure_filename(filename), as_attachment=True)


@app.route("/view/<run_id>/<filename>")
def view(run_id, filename):
    # Same file as /download, but served inline (no Content-Disposition:
    # attachment) so it can be used as an <img src> in the one-by-one
    # review viewer instead of triggering a browser download prompt.
    run_dir = _run_dir(run_id)
    return send_from_directory(run_dir, secure_filename(filename), as_attachment=False)


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
