"""Flask server for the consolidated water-stress causal graph viewer.

Run from .../graph_viz/:
    python3 -m pip install -r backend/requirements.txt
    python3 backend/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover - flask_cors is in requirements but stay safe
    CORS = None

from build_graph import (
    build_graph,
    compute_paths,
    index_links,
    index_nodes,
    load_master,
)


# ---------- Paths ----------

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent                # .../graph_viz
REPO_DIR = PROJECT_DIR.parent                   # .../COD891
FRONTEND_DIR = PROJECT_DIR / "frontend"
DEFAULT_MASTER = (
    REPO_DIR / "master_cross_stressor_consolidation_14papers.json"
)
MASTER_PATH = Path(os.environ.get("MASTER_JSON", str(DEFAULT_MASTER)))


# ---------- App + data ----------

app = Flask(__name__, static_folder=None)
if CORS is not None:
    CORS(app, resources={r"/api/*": {"origins": "*"}})

print(f"[app] loading master JSON: {MASTER_PATH}", flush=True)
_MASTER = load_master(MASTER_PATH)
_GRAPH = build_graph(_MASTER)
_NODES = index_nodes(_GRAPH)
_LINKS = index_links(_GRAPH)
print(
    f"[app] loaded: {_GRAPH['meta']['total_nodes']} nodes, "
    f"{_GRAPH['meta']['total_edges']} edges",
    flush=True,
)


# ---------- API ----------

@app.get("/api/graph")
def api_graph():
    return jsonify(_GRAPH)


@app.get("/api/node/<path:node_id>")
def api_node(node_id: str):
    node = _NODES.get(node_id)
    if node is None:
        abort(404, description=f"node {node_id!r} not found")
    return jsonify(node)


@app.get("/api/edge/<path:edge_id>")
def api_edge(edge_id: str):
    link = _LINKS.get(edge_id)
    if link is None:
        abort(404, description=f"edge {edge_id!r} not found")
    return jsonify(link)


@app.get("/api/paths/<path:node_id>")
def api_paths(node_id: str):
    if node_id not in _NODES:
        abort(404, description=f"node {node_id!r} not found")
    return jsonify(compute_paths(node_id, _GRAPH["links"]))


@app.get("/api/meta")
def api_meta():
    return jsonify(_GRAPH["meta"])


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ok": True,
            "nodes": _GRAPH["meta"]["total_nodes"],
            "edges": _GRAPH["meta"]["total_edges"],
            "master": str(MASTER_PATH),
        }
    )


# ---------- Static frontend ----------

@app.get("/")
def index():
    index_html = FRONTEND_DIR / "index.html"
    if not index_html.exists():
        # Friendly placeholder until the frontend lands.
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<title>graph_viz</title>"
            "<h1>graph_viz backend is running</h1>"
            "<p>Frontend not yet built. API is live:</p>"
            "<ul>"
            "<li><a href='/api/graph'>/api/graph</a></li>"
            "<li><a href='/api/meta'>/api/meta</a></li>"
            "<li><a href='/api/health'>/api/health</a></li>"
            "</ul>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename: str):
    # Don't shadow API; Flask will route /api/* before this since those routes are
    # registered first, but be defensive.
    if filename.startswith("api/"):
        abort(404)
    target = FRONTEND_DIR / filename
    if not target.is_file():
        abort(404)
    return send_from_directory(FRONTEND_DIR, filename)


# ---------- Entrypoint ----------

if __name__ == "__main__":
    # Single-process so the in-memory graph is shared.
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
