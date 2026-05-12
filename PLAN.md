Plan: Causal Chain Extraction & Knowledge Graph Pipeline
Automate extraction of measurable variables AND causal mechanism chains from research papers using Gemini API, producing structured JSON that directly feeds a knowledge graph. Start with water scarcity (4 causal stressors, ~24-28 papers), then extend.

Key recommendation: Design your extraction schema WITH the KG in mind from the start. Your current prompts extract flat variable lists with free-text key_relationships — that's not enough for building a real causal graph. You need explicit directed edges (variable A → variable B, with mechanism) extracted per paper. This avoids re-extracting later.

Phase 1: Enhanced Extraction Schema & Prompts
Your current JSON output has mapped_variables and new_variables as flat lists, and key_relationships as free-text strings. Add these structured fields:

causal_chains — explicit directed edges:

[{from_var, to_var, mechanism, direction, strength, conditions, excerpt}]
Example: precipitation_annual_average →(decreases recharge)→ annual_trend_g →(reduces availability)→ cropping_intensity
variable_roles — classify each variable as driver (root cause), mediator (mechanism step), outcome (what farmers see), or context (moderator like policy/geology)

mechanism_blocks — named sub-mechanisms from the paper (e.g., "recharge_deficit_mechanism", "extraction_incentive_mechanism"), each grouping a subset of causal chains

conditional_thresholds — when a relationship holds (e.g., "annual_trend_g decline > 0.2m/year indicates stress WHEN soge_class_name = Over-exploited")

Steps: Rewrite system prompt, extraction prompt, verification prompt, and consolidation prompt to demand graph-structured output. Store in prompts.py + models.py.

Phase 2: Automated Extraction Pipeline (extract.py)
Replace Gemini chat with a script:

Input: Pattern from CSV + folder of PDFs (e.g., papers/groundwater_stress/)
PDF → Text: pypdf (already working in your env)
Text → Chunks: ~80k char chunks with overlap
Chunk → Gemini API: Enhanced prompts from Phase 1, with retry/backoff
Self-Verify: Send extraction back to Gemini with verification prompt, auto-correct
Save: Per-paper JSON in extractions/{pattern_name}/{paper_stem}.json
CLI: python extract.py --pattern groundwater_stress --papers-dir papers/groundwater_stress/

Rate estimate: ~2 Gemini calls/paper × 7 papers × 4 patterns = ~56 calls, ~15-20 min with delays.

Phase 3: Cross-Paper Consolidation (consolidate.py)
Per pattern: Merge all per-paper JSONs — deduplicate variables, merge causal edges (same edge from multiple papers → higher confidence), combine mechanism blocks
Across patterns: Find shared variables between groundwater_stress, drought, rainfed_risk, irrigation_challenges → build the full causal DAG for "water scarcity"
Output: extractions/water_scarcity_consolidated.json
Phase 4: Knowledge Graph (kg_build.py)
Recommendation: NetworkX + JSON (no infra, exportable to Neo4j later).

Node types: Variable, Stressor, Pattern, Paper
Edge types: CAUSES (var→var + mechanism), INDICATES (var→stressor + threshold), MODERATES (context→edge), EVIDENCED_BY (edge→paper)

Target queries:

"Given variable values for a district, which stressors are active?" — traverse INDICATES edges, check thresholds
"Full causal chain from root cause to observable symptom?" — traverse CAUSES edges, return mechanism descriptions along path
