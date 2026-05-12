# graph_viz

Interactive viewer for the consolidated water-stress causal graph
(`out_4/master_cross_stressor_consolidation_10papers.json`).

## Run

From this directory (`graph_viz/`):

```bash
python3 -m pip install -r backend/requirements.txt
python3 backend/app.py
```

Then open <http://127.0.0.1:5050/>.

## Layout

- `backend/app.py` — Flask server on `127.0.0.1:5050`.
- `backend/build_graph.py` — pure transformation: master JSON → `{ nodes, links, meta }`,
  plus BFS upstream/downstream path queries.
- `backend/requirements.txt` — Flask + flask-cors.
- `frontend/` — static UI (served at `/`).

## API

- `GET /api/graph` — full graph: `{ nodes, links, meta }`.
- `GET /api/node/<variable_name>` — node detail.
- `GET /api/edge/<from>__<to>__<idx>` — edge detail.
- `GET /api/paths/<variable_name>` — `{ upstream, downstream, upstream_nodes, downstream_nodes }`
  (BFS, cycle-safe; used by the frontend for the causal-ray highlight).
- `GET /api/meta` — just the meta block.
- `GET /api/health` — quick liveness check.

## Data source

All graph data is derived verbatim from the master JSON. No values are fabricated.
The master path can be overridden with `MASTER_JSON=/path/to/file.json`.
