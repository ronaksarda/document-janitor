import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request, send_from_directory, render_template

from janitor_engine import plan, apply_plan, undo, load_journal, get_bin_counts, ALLOWED_FOLDERS, apply_single_item, finish_active_run

app = Flask(__name__, static_folder="assets", template_folder="templates")
TARGET_DIR = Path(".").resolve()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/assets/<path:filename>")
def serve_asset(filename):
    return send_from_directory("assets", filename)

@app.route("/api/plan", methods=["GET"])
def api_plan():
    items = plan(TARGET_DIR)
    bins = get_bin_counts(TARGET_DIR)
    return jsonify({
        "plan": items,
        "bins": bins,
        "target_dir": str(TARGET_DIR),
        "allowed_folders": ALLOWED_FOLDERS
    })

@app.route("/api/set_dir", methods=["POST"])
def api_set_dir():
    global TARGET_DIR
    data = request.get_json() or {}
    new_dir = data.get("dir")
    if new_dir:
        p = Path(new_dir).resolve()
        if p.exists() and p.is_dir():
            TARGET_DIR = p
            return jsonify({"ok": True, "target_dir": str(TARGET_DIR)})
        return jsonify({"error": f"Directory not found: {new_dir}"}), 400
    return jsonify({"error": "No directory provided"}), 400

@app.route("/api/apply", methods=["POST"])
def api_apply():
    data = request.get_json() or {}
    selected = data.get("selected")
    items = plan(TARGET_DIR)
    result = apply_plan(TARGET_DIR, items, selected_files=selected)
    bins = get_bin_counts(TARGET_DIR)
    result["bins"] = bins
    return jsonify(result)

@app.route("/api/apply_single", methods=["POST"])
def api_apply_single():
    data = request.get_json() or {}
    filename = data.get("file")
    dest = data.get("dest")
    rule = data.get("rule", "")
    reason = data.get("reason", "")
    sha256 = data.get("sha256", "")
    if not filename or not dest:
        return jsonify({"error": "Missing file or dest"}), 400
    item = {
        "file": filename,
        "size": 0,
        "action": "move",
        "dest": dest,
        "rule": rule,
        "reason": reason,
        "sha256": sha256
    }
    result = apply_single_item(TARGET_DIR, item)
    bins = get_bin_counts(TARGET_DIR)
    result["bins"] = bins
    return jsonify(result)

@app.route("/api/undo", methods=["POST"])
def api_undo():
    data = request.get_json() or {}
    run_id = data.get("run_id")
    file_name = data.get("file")
    result = undo(TARGET_DIR, run_id=run_id, file_name=file_name)
    bins = get_bin_counts(TARGET_DIR)
    result["bins"] = bins
    return jsonify(result)

@app.route("/api/history", methods=["GET"])
def api_history():
    runs = load_journal(TARGET_DIR)
    return jsonify({"runs": runs})

@app.route("/api/finish_run", methods=["POST"])
def api_finish_run():
    finish_active_run()
    return jsonify({"ok": True})

@app.route("/api/bins", methods=["GET"])
def api_bins():
    bins = get_bin_counts(TARGET_DIR)
    return jsonify({"bins": bins})

@app.route("/api/stats", methods=["GET"])
def api_stats():
    runs = load_journal(TARGET_DIR)
    total_sorted = sum(len(r.get("moves", [])) for r in runs)
    last_run = runs[-1]["timestamp"] if runs else None
    return jsonify({
        "total_sorted": total_sorted,
        "last_run": last_run,
        "runs_count": len(runs)
    })

def start_server(target_dir, port=5000):
    global TARGET_DIR
    TARGET_DIR = Path(target_dir).resolve()
    print(f"Starting Downloads Janitor on http://localhost:{port} (target: {TARGET_DIR})")
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    target = sys.argv[2] if len(sys.argv) > 2 else "."
    start_server(Path(target), port=port)
