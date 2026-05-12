/* =============================================================
   Causal Stress Atlas — frontend
   ============================================================= */
(() => {
  "use strict";

  // ------------------------------------------------------------
  // Config / palette
  // ------------------------------------------------------------
  const API_BASE = ""; // same-origin (Flask serves index.html + /api/*)
  const ROLE_COLORS = {
    driver: "#7dd3fc",
    mediator: "#a78bfa",
    outcome: "#fb7185",
    context: "#94a3b8",
  };
  const CLUSTER_COLORS = {
    drought: "#f59e0b",
    groundwater_stress: "#22d3ee",
    irrigation_challenges: "#34d399",
    rainfed_risk: "#f472b6",
    mixed: "#cbd5e1",
  };
  const ROLE_LABEL = {
    driver: "Driver",
    mediator: "Mediator",
    outcome: "Outcome",
    context: "Context",
  };
  const CLUSTER_LABEL = {
    drought: "Drought",
    groundwater_stress: "Groundwater stress",
    irrigation_challenges: "Irrigation challenges",
    rainfed_risk: "Rainfed risk",
    mixed: "Mixed",
  };
  const STRENGTH_WIDTH = { strong: 2.5, moderate: 1.5, weak: 0.6 };

  // Edge palette: pos = green-tinted; neg = rose-tinted; neutral = lavender
  const DIR_COLOR = {
    increase_causes_increase: [134, 239, 172],
    decrease_causes_decrease: [134, 239, 172],
    increase_causes_decrease: [253, 164, 175],
    decrease_causes_increase: [253, 164, 175],
    categorical_determines: [196, 181, 253],
    u_shaped: [196, 181, 253],
    inverse_u: [196, 181, 253],
    unknown: [148, 163, 184],
  };
  const DEFAULT_EDGE_RGB = [148, 163, 184];

  const DIM_NODE = "rgba(120,120,135,0.22)";
  const DIM_EDGE = "rgba(255,255,255,0.04)";
  const UPSTREAM_EDGE = "#fef3c7";
  const DOWNSTREAM_EDGE = "#a7f3d0";
  const CROSS_GLOW = "#fde68a";

  // ------------------------------------------------------------
  // State
  // ------------------------------------------------------------
  const state = {
    graph: null, // { nodes, links, meta }
    nodeById: new Map(),
    linkById: new Map(),
    Graph: null, // 3d-force-graph instance
    THREE: null,
    colorMode: "role", // "role" | "cluster_family"
    crossOnly: false,
    highlight: null, // { upEdges:Set, dnEdges:Set, upNodes:Set, dnNodes:Set, focusNode:string }
    haloTexture: null,
  };

  // ------------------------------------------------------------
  // DOM refs
  // ------------------------------------------------------------
  const $ = (sel) => document.querySelector(sel);
  const ui = {
    loader: $("#loader"),
    sidebar: $("#sidebar"),
    statNodes: $("#stat-nodes"),
    statEdges: $("#stat-edges"),
    statCross: $("#stat-cross"),
    search: $("#search"),
    colorBy: $("#color-by"),
    crossOnly: $("#cross-only"),
    resetView: $("#reset-view"),
    highlightAll: $("#highlight-all"),
    legend: $("#legend"),
    legendTitle: $("#legend-title"),
    drawer: $("#drawer"),
    drawerContent: $("#drawer-content"),
    drawerClose: $("#drawer-close"),
    tooltip: $("#tooltip"),
    graph: $("#graph"),
    infoBtn: $("#info-btn"),
    modal: $("#modal"),
    modalClose: $("#modal-close"),
  };

  // ------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------
  const escapeHTML = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const dedupe = (arr) => {
    const seen = new Set();
    const out = [];
    for (const x of arr || []) {
      if (x == null) continue;
      const k = typeof x === "string" ? x : JSON.stringify(x);
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(x);
    }
    return out;
  };

  const fmtNum = (n) => (n == null ? "—" : String(n));

  const dirCategory = (d) => {
    if (!d) return "other";
    if (d === "increase_causes_increase" || d === "decrease_causes_decrease")
      return "pos";
    if (d === "increase_causes_decrease" || d === "decrease_causes_increase")
      return "neg";
    return "other";
  };

  const nodeColor = (n) => {
    if (state.colorMode === "cluster_family") {
      return CLUSTER_COLORS[n.cluster_family] || CLUSTER_COLORS.mixed;
    }
    return ROLE_COLORS[n.role] || ROLE_COLORS.context;
  };

  // ------------------------------------------------------------
  // Halo sprite (radial-gradient canvas) for that bloom feel
  // ------------------------------------------------------------
  function makeHaloTexture(THREE) {
    const size = 128;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(
      size / 2,
      size / 2,
      0,
      size / 2,
      size / 2,
      size / 2,
    );
    g.addColorStop(0, "rgba(255,255,255,0.85)");
    g.addColorStop(0.25, "rgba(255,255,255,0.35)");
    g.addColorStop(0.6, "rgba(255,255,255,0.06)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    return tex;
  }

  function buildNodeObject(node) {
    const THREE = state.THREE;
    const isPathFocus =
      state.highlight && state.highlight.focusNode === node.id;
    const inPath =
      state.highlight &&
      (state.highlight.upNodes.has(node.id) ||
        state.highlight.dnNodes.has(node.id));
    const dimmed = state.highlight && !inPath;

    const baseColor = nodeColor(node);
    const radius = nodeRadius(node);

    const group = new THREE.Group();

    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 22, 22),
      new THREE.MeshStandardMaterial({
        color: dimmed ? new THREE.Color(0x4a4d5b) : new THREE.Color(baseColor),
        emissive: dimmed
          ? new THREE.Color(0x111118)
          : new THREE.Color(baseColor),
        emissiveIntensity: dimmed ? 0.05 : isPathFocus ? 1.4 : 0.9,
        roughness: 0.45,
        metalness: 0.15,
        transparent: true,
        opacity: dimmed ? 0.35 : 1,
      }),
    );
    group.add(sphere);

    // halo sprite
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: state.haloTexture,
        color: dimmed ? new THREE.Color(0x222230) : new THREE.Color(baseColor),
        transparent: true,
        opacity: dimmed ? 0.06 : isPathFocus ? 0.85 : 0.55,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    const haloScale = radius * (isPathFocus ? 6.5 : 4.2);
    sprite.scale.set(haloScale, haloScale, 1);
    group.add(sprite);

    return group;
  }

  function nodeRadius(n) {
    const pc = n.paper_count || 1;
    const deg = n.degree || (n.in_degree || 0) + (n.out_degree || 0);
    return Math.max(2.2, Math.log2(pc * 4) + deg * 0.35);
  }

  // ------------------------------------------------------------
  // Edge appearance
  // ------------------------------------------------------------
  function edgeColor(link) {
    if (state.highlight) {
      const id = link.id;
      if (state.highlight.upEdges.has(id)) return UPSTREAM_EDGE;
      if (state.highlight.dnEdges.has(id)) return DOWNSTREAM_EDGE;
      return DIM_EDGE;
    }
    if (link.cross_stressor) return CROSS_GLOW;
    const rgb = DIR_COLOR[link.direction] || DEFAULT_EDGE_RGB;
    const alpha =
      link.strength === "strong"
        ? 0.85
        : link.strength === "moderate"
          ? 0.6
          : 0.35;
    return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`;
  }

  function edgeWidth(link) {
    return STRENGTH_WIDTH[link.strength] || 1;
  }

  function edgeParticles(link) {
    if (state.highlight) {
      const id = link.id;
      if (
        state.highlight.upEdges.has(id) ||
        state.highlight.dnEdges.has(id)
      ) {
        return 4;
      }
      return 0;
    }
    if (link.cross_stressor) return 2;
    return 0;
  }

  function edgeParticleColor(link) {
    if (state.highlight) {
      if (state.highlight.upEdges.has(link.id)) return UPSTREAM_EDGE;
      if (state.highlight.dnEdges.has(link.id)) return DOWNSTREAM_EDGE;
    }
    if (link.cross_stressor) return CROSS_GLOW;
    return "#e2e8f0";
  }

  // ------------------------------------------------------------
  // Data fetch
  // ------------------------------------------------------------
  async function fetchGraph() {
    const r = await fetch(API_BASE + "/api/graph");
    if (!r.ok) throw new Error(`/api/graph -> ${r.status}`);
    return r.json();
  }
  async function fetchPaths(nodeId) {
    const r = await fetch(
      API_BASE + "/api/paths/" + encodeURIComponent(nodeId),
    );
    if (!r.ok) throw new Error(`/api/paths -> ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------
  // Init graph
  // ------------------------------------------------------------
  function initGraph(data) {
    const THREE = window.THREE;
    if (!THREE) {
      console.error("THREE.js not loaded");
      ui.loader.querySelector(".loader-text").textContent =
        "three.js failed to load from CDN.";
      return;
    }
    state.THREE = THREE;
    state.haloTexture = makeHaloTexture(THREE);

    state.graph = data;
    state.nodeById = new Map(data.nodes.map((n) => [n.id, n]));
    state.linkById = new Map(data.links.map((l) => [l.id, l]));

    ui.statNodes.textContent = data.nodes.length;
    ui.statEdges.textContent = data.links.length;
    ui.statCross.textContent = data.links.filter((l) => l.cross_stressor)
      .length;

    const visibleLinks = state.crossOnly
      ? data.links.filter((l) => l.cross_stressor)
      : data.links;

    state.Graph = ForceGraph3D()(ui.graph)
      .backgroundColor("#04050a")
      .graphData({ nodes: data.nodes, links: visibleLinks })
      .nodeId("id")
      .nodeRelSize(4)
      .nodeThreeObject(buildNodeObject)
      .nodeOpacity(1)
      .linkColor(edgeColor)
      .linkWidth(edgeWidth)
      .linkOpacity(0.85)
      .linkDirectionalArrowLength(3.5)
      .linkDirectionalArrowRelPos(0.92)
      .linkDirectionalArrowColor(edgeColor)
      .linkCurvature(0.08)
      .linkDirectionalParticles(edgeParticles)
      .linkDirectionalParticleSpeed(0.012)
      .linkDirectionalParticleWidth(1.6)
      .linkDirectionalParticleColor(edgeParticleColor)
      .enableNodeDrag(true)
      .onNodeHover(onNodeHover)
      .onLinkHover(onLinkHover)
      .onNodeClick(onNodeClick)
      .onLinkClick(onLinkClick)
      .onBackgroundClick(onBackgroundClick);

    // Tighter forces for ~50 nodes
    const fg = state.Graph;
    if (fg.d3Force) {
      const charge = fg.d3Force("charge");
      if (charge) charge.strength(-180);
      const link = fg.d3Force("link");
      if (link) link.distance(55);
    }

    // initial camera
    setTimeout(() => fg.zoomToFit(800, 60), 600);
  }

  // ------------------------------------------------------------
  // Hover handlers
  // ------------------------------------------------------------
  function onNodeHover(node) {
    if (!node) {
      ui.tooltip.classList.remove("show");
      ui.graph.style.cursor = "default";
      return;
    }
    ui.graph.style.cursor = "pointer";
    ui.tooltip.innerHTML =
      `<div class="tt-name">${escapeHTML(node.id)}</div>` +
      `<div class="tt-meta">${escapeHTML(ROLE_LABEL[node.role] || node.role || "—")} · ${escapeHTML(CLUSTER_LABEL[node.cluster_family] || node.cluster_family || "—")}</div>`;
    ui.tooltip.classList.add("show");
  }

  function onLinkHover(link) {
    if (!link) {
      ui.tooltip.classList.remove("show");
      ui.graph.style.cursor = "default";
      return;
    }
    ui.graph.style.cursor = "pointer";
    const src = typeof link.source === "object" ? link.source.id : link.source;
    const tgt = typeof link.target === "object" ? link.target.id : link.target;
    ui.tooltip.innerHTML =
      `<div class="tt-name">${escapeHTML(src)} → ${escapeHTML(tgt)}</div>` +
      `<div class="tt-meta">${escapeHTML(link.direction || "—")} · ${escapeHTML(link.strength || "—")}${link.cross_stressor ? " · cross-stressor" : ""}</div>`;
    ui.tooltip.classList.add("show");
  }

  document.addEventListener("mousemove", (e) => {
    if (!ui.tooltip.classList.contains("show")) return;
    const pad = 14;
    const ttw = ui.tooltip.offsetWidth;
    const tth = ui.tooltip.offsetHeight;
    let x = e.clientX + pad;
    let y = e.clientY + pad;
    if (x + ttw > window.innerWidth - 8) x = e.clientX - ttw - pad;
    if (y + tth > window.innerHeight - 8) y = e.clientY - tth - pad;
    ui.tooltip.style.left = x + "px";
    ui.tooltip.style.top = y + "px";
  });

  // ------------------------------------------------------------
  // Click handlers
  // ------------------------------------------------------------
  async function onNodeClick(node) {
    openNodeDrawer(node);
    if (!node.is_root) {
      try {
        const paths = await fetchPaths(node.id);
        applyHighlight(paths, node.id);
      } catch (err) {
        console.warn("paths fetch failed", err);
      }
    } else {
      // Root: still show downstream
      try {
        const paths = await fetchPaths(node.id);
        applyHighlight(paths, node.id);
      } catch (e) {}
    }
    // Smoothly orbit to node
    const dist = 140;
    const len = Math.hypot(node.x, node.y, node.z) || 1;
    const ratio = 1 + dist / len;
    state.Graph.cameraPosition(
      { x: node.x * ratio, y: node.y * ratio, z: node.z * ratio },
      node,
      900,
    );
  }

  function onLinkClick(link) {
    openEdgeDrawer(link);
  }

  function onBackgroundClick() {
    clearHighlight();
    closeDrawer();
  }

  // ------------------------------------------------------------
  // Highlight engine
  // ------------------------------------------------------------
  function applyHighlight(paths, focusId) {
    state.highlight = {
      upEdges: new Set(paths.upstream || []),
      dnEdges: new Set(paths.downstream || []),
      upNodes: new Set([...(paths.upstream_nodes || []), focusId]),
      dnNodes: new Set([...(paths.downstream_nodes || []), focusId]),
      focusNode: focusId,
    };
    refreshVisuals();
  }

  function clearHighlight() {
    if (!state.highlight) return;
    state.highlight = null;
    refreshVisuals();
  }

  function refreshVisuals() {
    const g = state.Graph;
    if (!g) return;
    g.nodeThreeObject(buildNodeObject);
    g.linkColor(edgeColor);
    g.linkDirectionalArrowColor(edgeColor);
    g.linkDirectionalParticles(edgeParticles);
    g.linkDirectionalParticleColor(edgeParticleColor);
    g.refresh && g.refresh();
  }

  function highlightAllPulse() {
    const g = state.Graph;
    if (!g) return;
    g.linkDirectionalParticles(2);
    g.linkDirectionalParticleColor(() => CROSS_GLOW);
    setTimeout(() => {
      g.linkDirectionalParticles(edgeParticles);
      g.linkDirectionalParticleColor(edgeParticleColor);
    }, 4500);
  }

  // ------------------------------------------------------------
  // Drawers
  // ------------------------------------------------------------
  function openNodeDrawer(node) {
    ui.drawerContent.innerHTML = renderNodeDrawer(node);
    ui.drawer.classList.add("open");
    bindDrawerClicks();
  }

  function openEdgeDrawer(link) {
    ui.drawerContent.innerHTML = renderEdgeDrawer(link);
    ui.drawer.classList.add("open");
    bindDrawerClicks();
  }

  function closeDrawer() {
    ui.drawer.classList.remove("open");
  }

  function bindDrawerClicks() {
    ui.drawerContent.querySelectorAll("[data-jump-node]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.getAttribute("data-jump-node");
        const n = state.nodeById.get(id);
        if (n) onNodeClick(n);
      });
    });
  }

  function renderNodeDrawer(node) {
    const role = node.role || "context";
    const cluster = node.cluster_family || "mixed";
    const dataSources = dedupe(node.data_sources);
    const supportingPapers = dedupe(node.supporting_papers);
    const mechDomains = dedupe(node.mechanism_domains);

    const ppr = (node.per_paper_ranges || [])
      .map(
        (p) => `
        <details class="d-collapse">
          <summary><span class="paper-title">${escapeHTML(p.paper_title || "Paper")}</span></summary>
          <div class="body">${escapeHTML(p.range_or_threshold || "—")}</div>
        </details>`,
      )
      .join("");

    return `
      <div class="d-eyebrow">Variable</div>
      <h2 class="d-title">${escapeHTML(node.id)}</h2>
      <div class="d-badges">
        <span class="badge role-${escapeHTML(role)}"><span class="dot"></span>${escapeHTML(ROLE_LABEL[role] || role)}</span>
        <span class="badge cluster-${escapeHTML(cluster)}"><span class="dot"></span>${escapeHTML(CLUSTER_LABEL[cluster] || cluster)}</span>
        ${node.is_root ? '<span class="badge">root</span>' : ""}
        ${node.is_outcome ? '<span class="badge">outcome</span>' : ""}
      </div>

      <div class="d-section">
        <h4>Description</h4>
        <p class="d-text">${escapeHTML(node.description || "—")}</p>
      </div>

      <div class="d-section">
        <h4>Quick stats</h4>
        <div class="d-grid">
          <div class="kv"><div class="k">Unit</div><div class="v">${escapeHTML(node.unit || "—")}</div></div>
          <div class="kv"><div class="k">Papers</div><div class="v">${fmtNum(node.paper_count)}</div></div>
          <div class="kv"><div class="k">Importance</div><div class="v">${fmtNum(node.importance_rank)}</div></div>
          <div class="kv"><div class="k">Confidence</div><div class="v">${escapeHTML(node.confidence || "—")}</div></div>
          <div class="kv"><div class="k">In-degree</div><div class="v">${fmtNum(node.in_degree)}</div></div>
          <div class="kv"><div class="k">Out-degree</div><div class="v">${fmtNum(node.out_degree)}</div></div>
        </div>
      </div>

      ${
        node.threshold_or_range
          ? `<div class="d-section">
        <h4>Threshold / range</h4>
        <div class="d-mono">${escapeHTML(node.threshold_or_range)}</div>
      </div>`
          : ""
      }

      ${
        mechDomains.length
          ? `<div class="d-section">
        <h4>Mechanism domains</h4>
        <div class="chips">${mechDomains.map((c) => `<span class="chip">${escapeHTML(c)}</span>`).join("")}</div>
      </div>`
          : ""
      }

      ${
        dataSources.length
          ? `<div class="d-section">
        <h4>Data sources</h4>
        <ul class="d-list">${dataSources.map((s) => {
          if (s && typeof s === "object") {
            const label = s.paper_title ? `<em>${escapeHTML(s.paper_title)}</em>: ` : "";
            return `<li>${label}${escapeHTML(s.data_source || "—")}</li>`;
          }
          return `<li>${escapeHTML(s)}</li>`;
        }).join("")}</ul>
      </div>`
          : ""
      }

      ${
        ppr
          ? `<div class="d-section">
        <h4>Per-paper ranges</h4>
        ${ppr}
      </div>`
          : ""
      }

      ${
        supportingPapers.length
          ? `<div class="d-section">
        <h4>Supporting papers (${supportingPapers.length})</h4>
        <ul class="d-list">${supportingPapers.map((p) => `<li>${escapeHTML(p)}</li>`).join("")}</ul>
      </div>`
          : ""
      }
    `;
  }

  function renderEdgeDrawer(link) {
    const src = typeof link.source === "object" ? link.source.id : link.source;
    const tgt = typeof link.target === "object" ? link.target.id : link.target;
    const dirCat = dirCategory(link.direction);
    const mechDomains = dedupe(link.mechanism_domains);
    const supportingPapers = dedupe(link.supporting_papers);

    return `
      <div class="d-eyebrow">Mechanism</div>
      <h2 class="d-title">
        <span class="edge-link" data-jump-node="${escapeHTML(src)}">${escapeHTML(src)}</span>
        <span class="edge-arrow">→</span>
        <span class="edge-link" data-jump-node="${escapeHTML(tgt)}">${escapeHTML(tgt)}</span>
      </h2>
      <div class="d-badges">
        <span class="badge dir-${dirCat}">${escapeHTML(link.direction || "unknown")}</span>
        <span class="badge strength-${escapeHTML(link.strength || "weak")}">${escapeHTML(link.strength || "weak")}</span>
        ${link.cross_stressor ? '<span class="badge cross">cross-stressor</span>' : ""}
        ${link.confidence ? `<span class="badge">conf · ${escapeHTML(link.confidence)}</span>` : ""}
      </div>

      <div class="d-section">
        <h4>Mechanism</h4>
        <p class="d-text">${escapeHTML(link.mechanism || "—")}</p>
      </div>

      ${
        link.conditions
          ? `<div class="d-section">
        <h4>Conditions</h4>
        <p class="d-text muted">${escapeHTML(link.conditions)}</p>
      </div>`
          : ""
      }

      ${
        link.from_var_value_range_merged
          ? `<div class="d-section">
        <h4>Source range — ${escapeHTML(src)}</h4>
        <div class="d-mono">${escapeHTML(link.from_var_value_range_merged)}</div>
      </div>`
          : ""
      }

      ${
        link.to_var_value_range_merged
          ? `<div class="d-section">
        <h4>Target range — ${escapeHTML(tgt)}</h4>
        <div class="d-mono">${escapeHTML(link.to_var_value_range_merged)}</div>
      </div>`
          : ""
      }

      ${
        mechDomains.length
          ? `<div class="d-section">
        <h4>Mechanism domains</h4>
        <div class="chips">${mechDomains.map((c) => `<span class="chip">${escapeHTML(c)}</span>`).join("")}</div>
      </div>`
          : ""
      }

      ${(() => {
        const fromRanges = dedupe(link.from_var_value_ranges_by_paper || []);
        const toRanges = dedupe(link.to_var_value_ranges_by_paper || []);
        const renderRangeList = (items) =>
          items.map((r) => {
            if (r && typeof r === "object") {
              const label = r.paper_title ? `<em>${escapeHTML(r.paper_title)}</em>: ` : "";
              return `<li>${label}${escapeHTML(r.value_range || "—")}</li>`;
            }
            return `<li>${escapeHTML(r)}</li>`;
          }).join("");
        return [
          fromRanges.length
            ? `<div class="d-section"><h4>Source ranges by paper — ${escapeHTML(src)}</h4><ul class="d-list">${renderRangeList(fromRanges)}</ul></div>`
            : "",
          toRanges.length
            ? `<div class="d-section"><h4>Target ranges by paper — ${escapeHTML(tgt)}</h4><ul class="d-list">${renderRangeList(toRanges)}</ul></div>`
            : "",
        ].join("");
      })()}

      ${
        supportingPapers.length
          ? `<div class="d-section">
        <h4>Supporting papers (${supportingPapers.length})</h4>
        <ul class="d-list">${supportingPapers.map((p) => {
          if (p && typeof p === "object") {
            const id = p.paper_id != null ? `<span class="chip" style="font-size:0.7rem;padding:1px 5px">#${escapeHTML(String(p.paper_id))}</span> ` : "";
            return `<li>${id}${escapeHTML(p.paper_title || "—")}</li>`;
          }
          return `<li>${escapeHTML(p)}</li>`;
        }).join("")}</ul>
      </div>`
          : ""
      }
    `;
  }

  // ------------------------------------------------------------
  // Legend
  // ------------------------------------------------------------
  function renderLegend() {
    const map = state.colorMode === "role" ? ROLE_COLORS : CLUSTER_COLORS;
    const labelMap = state.colorMode === "role" ? ROLE_LABEL : CLUSTER_LABEL;
    ui.legendTitle.textContent =
      "Legend · " + (state.colorMode === "role" ? "role" : "cluster family");
    ui.legend.innerHTML = Object.keys(map)
      .map(
        (k) =>
          `<div class="legend-row"><span class="legend-dot" style="background:${map[k]};color:${map[k]}"></span>${escapeHTML(labelMap[k] || k)}</div>`,
      )
      .join("");
  }

  // ------------------------------------------------------------
  // Sidebar wiring
  // ------------------------------------------------------------
  function wireSidebar() {
    ui.colorBy.querySelectorAll(".seg-btn").forEach((b) => {
      b.addEventListener("click", () => {
        const m = b.getAttribute("data-mode");
        if (m === state.colorMode) return;
        state.colorMode = m;
        ui.colorBy
          .querySelectorAll(".seg-btn")
          .forEach((x) => x.classList.toggle("active", x === b));
        renderLegend();
        refreshVisuals();
      });
    });

    ui.crossOnly.addEventListener("change", () => {
      state.crossOnly = ui.crossOnly.checked;
      const links = state.crossOnly
        ? state.graph.links.filter((l) => l.cross_stressor)
        : state.graph.links;
      state.Graph.graphData({ nodes: state.graph.nodes, links });
      refreshVisuals();
    });

    ui.search.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      const q = ui.search.value.trim().toLowerCase();
      if (!q) return;
      const hit =
        state.graph.nodes.find((n) => n.id.toLowerCase() === q) ||
        state.graph.nodes.find((n) => n.id.toLowerCase().includes(q)) ||
        state.graph.nodes.find(
          (n) => (n.description || "").toLowerCase().includes(q),
        );
      if (!hit) return;
      onNodeClick(hit);
    });

    ui.resetView.addEventListener("click", () => {
      clearHighlight();
      closeDrawer();
      state.Graph.zoomToFit(800, 60);
    });

    ui.highlightAll.addEventListener("click", highlightAllPulse);

    ui.drawerClose.addEventListener("click", () => {
      closeDrawer();
      clearHighlight();
    });

    ui.infoBtn.addEventListener("click", () =>
      ui.modal.classList.remove("hidden"),
    );
    ui.modalClose.addEventListener("click", () =>
      ui.modal.classList.add("hidden"),
    );
    ui.modal.addEventListener("click", (e) => {
      if (e.target === ui.modal) ui.modal.classList.add("hidden");
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        ui.modal.classList.add("hidden");
        closeDrawer();
        clearHighlight();
      }
    });

    window.addEventListener("resize", () => {
      if (state.Graph) {
        state.Graph.width(window.innerWidth).height(window.innerHeight);
      }
    });
  }

  // ------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------
  async function boot() {
    wireSidebar();
    renderLegend();

    try {
      const data = await fetchGraph();
      initGraph(data);
      // hide loader after first render
      requestAnimationFrame(() => {
        setTimeout(() => ui.loader.classList.add("hidden"), 250);
      });
    } catch (err) {
      console.error(err);
      ui.loader.querySelector(".loader-text").textContent =
        "Failed to load graph — is the backend running on port 5050?";
    }
  }

  // Boot only when both the DOM is parsed AND the inline module has assigned
  // window.THREE + window.ForceGraph3D and dispatched 'libs-ready'.
  let _booted = false;
  let _domReady = document.readyState !== "loading";
  let _libsReady = !!(window.ForceGraph3D && window.THREE);

  function maybeBoot() {
    if (_booted) return;
    if (!_domReady || !_libsReady) return;
    _booted = true;
    boot();
  }

  if (!_domReady) {
    document.addEventListener("DOMContentLoaded", () => {
      _domReady = true;
      maybeBoot();
    });
  }
  if (!_libsReady) {
    window.addEventListener("libs-ready", () => {
      _libsReady = true;
      maybeBoot();
    });
  }
  maybeBoot();
})();
