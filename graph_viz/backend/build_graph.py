"""Pure transformation: master consolidation JSON -> { nodes, links, meta }.

All graph data comes from the master JSON; nothing here is fabricated.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


# ---------- Loading ----------

def load_master(master_path: str | Path) -> dict[str, Any]:
    with open(master_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Transformation ----------

# Fields copied verbatim from each consolidated_variable into the node.
_NODE_PASSTHROUGH = (
    "variable_name",
    "description",
    "unit",
    "role",
    "data_sources",
    "threshold_or_range",
    "per_paper_ranges",
    "indicator_direction",
    "relevance",
    "cluster_family",
    "cluster_families_reported",
    "mechanism_domains",
    "seasons_reported",
    "severities_reported",
    "media_reported",
    "per_paper_qualifiers",
    "confidence",
    "paper_count",
    "importance_rank",
)

# Fields copied verbatim from each consolidated_causal_chain into the link.
_LINK_PASSTHROUGH = (
    "from_var",
    "to_var",
    "mechanism",
    "direction",
    "strength",
    "conditions",
    "from_var_value_range_merged",
    "from_var_value_ranges_by_paper",
    "to_var_value_range_merged",
    "to_var_value_ranges_by_paper",
    "from_cluster_family",
    "to_cluster_family",
    "mechanism_domains",
    "is_cross_stressor",
    "season_scope",
    "seasons_scope_reported",
    "severity_scope",
    "severities_scope_reported",
    "medium_scope",
    "media_scope_reported",
    "supporting_papers",
    "confidence",
)


def build_graph(master: dict[str, Any]) -> dict[str, Any]:
    raw_vars = master.get("consolidated_variables", []) or []
    raw_edges = master.get("consolidated_causal_chains", []) or []

    # Build node dict in input order, keyed by variable_name (which is also the public id).
    nodes_by_id: dict[str, dict[str, Any]] = {}
    for v in raw_vars:
        name = v.get("variable_name")
        if not name:
            continue
        node = {k: v.get(k) for k in _NODE_PASSTHROUGH}
        node["id"] = name
        # Will be populated below.
        node["in_degree"] = 0
        node["out_degree"] = 0
        node["degree"] = 0
        node["is_root"] = False
        node["is_outcome"] = False
        node["supporting_papers"] = []  # union from edges touching this node
        nodes_by_id[name] = node

    # Build links and accumulate degree + supporting_papers.
    links: list[dict[str, Any]] = []
    paper_sets: dict[str, set[str]] = defaultdict(set)
    for i, e in enumerate(raw_edges):
        src = e.get("from_var")
        dst = e.get("to_var")
        if src not in nodes_by_id or dst not in nodes_by_id:
            print(
                f"[build_graph] WARN: dropping edge {i} ({src!r} -> {dst!r}); "
                f"variable not in consolidated_variables",
                file=sys.stderr,
            )
            continue
        link = {k: e.get(k) for k in _LINK_PASSTHROUGH}
        link_id = f"{src}__{dst}__{i}"
        link["id"] = link_id
        link["source"] = src
        link["target"] = dst
        link["cross_stressor"] = bool(e.get("is_cross_stressor"))
        links.append(link)

        nodes_by_id[src]["out_degree"] += 1
        nodes_by_id[dst]["in_degree"] += 1

        for paper in e.get("supporting_papers") or []:
            # Schema v14: supporting_papers items are {paper_id, paper_title};
            # fall back to plain string for older files.
            title = paper.get("paper_title") if isinstance(paper, dict) else paper
            if title:
                paper_sets[src].add(title)
                paper_sets[dst].add(title)

    # Finalise per-node derived fields.
    for name, node in nodes_by_id.items():
        node["degree"] = node["in_degree"] + node["out_degree"]
        node["is_root"] = node["in_degree"] == 0 or node.get("role") == "driver"
        node["is_outcome"] = node["out_degree"] == 0 or node.get("role") == "outcome"
        node["supporting_papers"] = sorted(paper_sets.get(name, set()))

    nodes = list(nodes_by_id.values())

    role_counts = Counter(n.get("role") for n in nodes)
    cluster_counts = Counter(n.get("cluster_family") for n in nodes)

    meta = {
        "total_nodes": len(nodes),
        "total_edges": len(links),
        "roles": dict(role_counts),
        "cluster_families": dict(cluster_counts),
        "source_papers": master.get("source_papers_profile", []) or [],
        "pattern": master.get("pattern"),
        "consolidation_mode": master.get("consolidation_mode"),
        "consolidation_summary": master.get("consolidation_summary"),
    }

    return {"nodes": nodes, "links": links, "meta": meta}


# ---------- Path queries ----------

def build_adjacency(links: list[dict[str, Any]]):
    """Returns (forward, reverse) adjacency.

    forward[u] = list of (neighbor_v, edge_id)  (edge u -> v)
    reverse[v] = list of (neighbor_u, edge_id)  (edge u -> v, reversed)
    """
    forward: dict[str, list[tuple[str, str]]] = defaultdict(list)
    reverse: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for link in links:
        u = link["source"]
        v = link["target"]
        eid = link["id"]
        forward[u].append((v, eid))
        reverse[v].append((u, eid))
    return forward, reverse


def bfs_paths(
    start: str,
    adjacency: dict[str, list[tuple[str, str]]],
) -> tuple[list[str], list[str]]:
    """BFS over `adjacency` from `start`. Cycle-safe.

    Returns (edge_ids, node_ids). node_ids includes `start`.
    """
    visited_nodes: set[str] = {start}
    visited_edges: set[str] = set()
    # Preserve discovery order for the frontend.
    nodes_order: list[str] = [start]
    edges_order: list[str] = []

    q: deque[str] = deque([start])
    while q:
        u = q.popleft()
        for nbr, eid in adjacency.get(u, []):
            if eid not in visited_edges:
                visited_edges.add(eid)
                edges_order.append(eid)
            if nbr not in visited_nodes:
                visited_nodes.add(nbr)
                nodes_order.append(nbr)
                q.append(nbr)
    return edges_order, nodes_order


def compute_paths(node_id: str, links: list[dict[str, Any]]) -> dict[str, Any]:
    forward, reverse = build_adjacency(links)
    down_edges, down_nodes = bfs_paths(node_id, forward)
    up_edges, up_nodes = bfs_paths(node_id, reverse)
    return {
        "node_id": node_id,
        "upstream": up_edges,
        "downstream": down_edges,
        "upstream_nodes": up_nodes,
        "downstream_nodes": down_nodes,
    }


# ---------- Convenience ----------

def index_nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in graph["nodes"]}


def index_links(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {l["id"]: l for l in graph["links"]}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument(
        "--master",
        default=str(
            Path(__file__).resolve().parents[2]
            / "master_cross_stressor_consolidation_14papers.json"
        ),
    )
    args = p.parse_args()
    g = build_graph(load_master(args.master))
    print(
        json.dumps(
            {
                "total_nodes": g["meta"]["total_nodes"],
                "total_edges": g["meta"]["total_edges"],
                "roles": g["meta"]["roles"],
                "cluster_families": g["meta"]["cluster_families"],
                "first_node_id": g["nodes"][0]["id"] if g["nodes"] else None,
                "first_link_id": g["links"][0]["id"] if g["links"] else None,
            },
            indent=2,
        )
    )
