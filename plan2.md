# Plan 2 - KG Prompt and Taxonomy Upgrade

## Objective
Build a high-fidelity causal knowledge graph where each real-world concept maps to a single canonical variable node, evidence remains paper-specific, and stressor grouping is flexible via a hybrid layered model.

## Decisions Locked
- Stressor strategy: hybrid layered
  - Keep the current 4 families for clustering and dashboard continuity.
  - Add dynamic paper-derived mechanism domains for analysis logic.
- Taxonomy scope: add all candidates now
  - Add all rows from `out/expansion_candidates.csv`, but collapse duplicates via canonicalization and alias mapping.

## Implementation Phases

### Phase 1 - Schema redesign
- Define canonical variable schema:
  - `canonical_variable_name`, `aliases`, `definition_master`, `paper_contexts`
  - Keep qualifiers (`season`, `severity`, `medium`) at evidence level, not node ID level.
- Split stressor labeling:
  - `cluster_family` for visualization
  - `mechanism_domains` for dynamic paper-derived multi-label semantics

### Phase 2 - Taxonomy ingest and normalization
- Convert `out/expansion_candidates.csv` into normalized seed entries.
- Merge duplicate concepts (for example repeated `NEW_land_surface_temp_trend`).
- Preserve context differences in per-paper usage records.
- Add alias resolution rules to prevent duplicate node creation from wording variation.

### Phase 3 - Prompt rewrite
- Update `prompts_relaxed.py` to enforce:
  - canonical variable mapping first
  - alias-aware NEW variable handling
  - dynamic `mechanism_domains` tagging
  - explicit canonicalization confidence and merge target hints
- Generate optimized `prompts.py` for the extraction pipeline.

### Phase 4 - Consolidation hardening
- Consolidation merge passes:
  1. exact canonical match
  2. alias-table match
  3. near-synonym fallback as suggestions (not automatic destructive merge)
- Keep one node per canonical variable with per-paper context payloads.

### Phase 5 - Query-focused graph outputs
For query: "Given district values, which stressors are active?"
- Add output fields:
  - `activation_score`, `activation_band`, `top_trigger_nodes`, `scope_used`, `explanation_paths`
- Use scoring model:
  - threshold breach + scope match + evidence confidence + upstream path support

For query: "Full causal chain from root cause to observable symptom?"
- Ensure complete path-safe `CAUSES` edges with mechanism, confidence, and qualifier-aware scope.

### Phase 6 - Re-extraction loop
- Re-run extraction on existing and new papers.
- Consolidate and generate master graph.
- Promote recurring strong NEW variables into canonical taxonomy.
- Re-run once after taxonomy update.
- Stop when duplicate nodes and unresolved aliases converge to low levels.

## Deliverables
- Updated `prompts_relaxed.py`
- New optimized `prompts.py`
- Re-extracted per-paper JSONs
- Consolidated master JSON
- Validation artifacts for duplicate control and target query readiness
