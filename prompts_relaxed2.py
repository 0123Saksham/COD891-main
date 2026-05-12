"""
Relaxed LLM prompt templates for cross-stressor causal extraction (MECHANISM-FIRST VARIANT).

Same overall goals and downstream consolidation/graph prompts as prompts_relaxed.py,
but EXTRACTION_PROMPT is reorganised so the model first identifies paper mechanisms and
draft causal edges inside mechanism_blocks, then deduplicates them into causal_chains
with stable edge_id values (e1..en), and finally fills mechanism_blocks.edge_ids to
reference those canonical edges (no duplicated edge objects in mechanism_blocks).
"""

VARIABLE_TAXONOMY = """
EXISTING VARIABLE TAXONOMY (from prior case study):

Each entry below lists:
- variable_name — canonical snake_case identifier used in edges and JSON outputs.
- definition — what the variable measures, the typical unit, and how it is computed.
- season_qualifier — if the variable supports seasonal disaggregation (kharif / rabi /
  zaid / annual), the extractor MUST set the `season` field on that variable to indicate
  which season(s) the paper refers to; otherwise set `season` to "not_applicable".

HYDROGEOLOGY:
- acquifer
  * Aquifer type or hydrogeological class (categorical: alluvial, hard-rock, basalt,
    coastal, etc.). Determines storage, transmissivity, and recharge behaviour of the
    block/district. season_qualifier: not_applicable.

PRECIPITATION & CLIMATE:
- prec_annual_avg_rain
  * Average annual rainfall at block/district level, typically in mm/year, computed
    from IMD gridded rainfall or gauge-based time series. season_qualifier:
    not_applicable (annual aggregate already).
- drought_weeks_trend
  * Trend (slope, weeks/year or fraction/year) in the number of weeks classified as
    drought by SPI/SPEI over the study period. severity_qualifier: REQUIRED —
    "mild" | "moderate" | "severe". The extractor MUST set `severity` on every
    instance so that mild / moderate / severe drought trends remain distinguishable
    during downstream analysis. If the paper presents multiple severity levels, emit
    ONE variable instance per severity using the same canonical name and different
    `severity` values. season_qualifier: not_applicable.
- drysp_4w_trend
  * Trend in the count/duration of rolling 4-week dry spells per year at the
    block/district. Unit: weeks/year or events/year. season_qualifier: not_applicable.
- drought_freq
  * Frequency of drought events per decade at the block/district, from SPI/SPEI or
    official drought declarations. Unit: events/decade. season_qualifier: not_applicable.

WATER BALANCE:
- runoff_annual_avg
  * Annual average surface runoff, typically in mm/year or m^3, from SWAT-type or
    remote-sensed water-balance products. season_qualifier: not_applicable (annual).
- et_annual_avg
  * Annual average actual evapotranspiration, typically in mm/year, from MODIS /
    SSEBop / paper-reported ET estimates. season_qualifier: not_applicable (annual).
- recharge_rate
  * Groundwater recharge / aquifer replenishment rate at block/district. Unit:
    mm/year or m^3/year. Source: CGWB Groundwater Resource Assessment (GEC norms),
    SWAT/VIC modelling, or paper-reported water-balance estimates.
    season_qualifier: not_applicable (typically annual).

GROUNDWATER:
- g_annual_trend
  * Trend in groundwater level or depth-to-water-table at block/district, typically
    in m/year or cm/year. Negative values indicate decline. Source: CGWB well network
    or GRACE-derived anomalies. season_qualifier: not_applicable (annual trend).
- soge_class_name
  * Stage of groundwater extraction class (categorical: Safe, Semi-Critical, Critical,
    Over-Exploited, Saline) as per CGWB Groundwater Resource Assessment.
    season_qualifier: not_applicable.
- well_depth
  * Typical depth of operational tube-wells / bore-wells in the block/district, in m.
    Proxy for how deep farmers must drill to reach a reliable aquifer. Source: CGWB
    well inventories, minor irrigation census, field surveys. season_qualifier:
    not_applicable.

SALINITY:
- salinity_level
  * Salinity concentration in a water or soil medium. Unit: dS/m (electrical
    conductivity) or mg/L / ppm (dissolved solids). Source: CGWB water-quality
    monitoring (groundwater EC), soil-testing labs / ICAR soil-salinity maps (soil).
    medium_qualifier: REQUIRED — "groundwater" | "soil". The extractor MUST set
    `medium` on every instance so that groundwater salinity and soil salinity remain
    distinguishable. If the paper presents both, emit ONE variable instance per
    medium using the same canonical name and different `medium` values.
    season_qualifier: not_applicable.

SURFACE WATER AREA TRENDS:
- surface_water_area_trend
  * Trend in surface water body area (ponds, tanks, reservoirs) from Sentinel/Landsat
    time series. Unit: ha/year or km^2/year. season_qualifier: REQUIRED —
    "kharif" | "rabi" | "zaid" | "annual". The extractor MUST set `season` on every
    instance so that the annual aggregate and the season-specific trends remain
    distinguishable during downstream analysis.

SURFACE WATER AREA AVERAGES:
- surface_water_area_avg
  * Average surface water body area over the study period, in ha or km^2.
    season_qualifier: REQUIRED — "kharif" | "rabi" | "zaid" | "annual".

BLOCK MEDIAN OF SURFACE WATER AREA:
- block_median_surface_water
  * Block-level median of surface water body area across years within a season/annual
    window. Used as a robust central tendency indicator. season_qualifier: REQUIRED —
    "kharif" | "rabi" | "zaid" | "annual".

IRRIGATION:
- irrigated_area_fraction
  * Fraction of cropped area that is irrigated at block/district level. Unit: %
    or dimensionless fraction. Source: Minor Irrigation Census, MoA LUS tables,
    ICRISAT district database, remote-sensed irrigated-area products. Indicates
    exposure to irrigation-supply risk vs rainfed dependence. season_qualifier:
    not_applicable (typically reported annually; if the paper reports season-wise
    irrigated fractions, set season accordingly).
- irrigation_demand
  * Irrigation water demand or withdrawal at block/district level. Unit: mm/year,
    m^3/year, or ha-m/year. Source: CGWB GEC irrigation draft estimates, state
    irrigation department reports, or paper-reported crop-water-requirement models.
    season_qualifier: not_applicable.

CROPPING:
- cropping_area_trend
  * Trend in cropped area at block/district level, unit ha/year or %/year, from
    MoA LUS or remote-sensed cropland products. season_qualifier: REQUIRED —
    "kharif" | "rabi" | "zaid" | "annual". If the paper discusses multiple seasons,
    emit one variable instance per season (same canonical name, different `season`).
- double_crop_trend
  * Trend in double-cropped area (same plot cropped in two seasons). Unit: ha/year
    or %/year. season_qualifier: not_applicable (concept is inherently multi-season).
- cropping_intensity_trend
  * Trend in cropping intensity (gross cropped area / net sown area). Unit: %/year.
    season_qualifier: not_applicable.
- crop_yield_trend
  * Trend in crop yield (output per unit area) at block/district level. Unit:
    kg/ha/year, t/ha/year, or %/year. Source: MoA / Agricultural Statistics, DES
    crop-yield series, or remote-sensed yield proxies (e.g. NDVI-calibrated).
    season_qualifier: not_applicable by default; if the paper reports a specific
    season's yield trend, set season accordingly.

LAND USE:
- deforestation
  * Forest-cover loss rate at block/district, typically from Hansen/FSI data.
    Unit: ha/year or %/year. season_qualifier: not_applicable.

PARENT VARIABLE QUALIFIER RULES:
- Some parent variables are SINGLE canonical names that represent a family of related
  measurements. They are distinguished at extraction time by REQUIRED qualifier
  field(s), not by different canonical names.
- Current parent variables with qualifiers:
  * season_qualifier "REQUIRED" — cropping_area_trend, surface_water_area_trend,
    surface_water_area_avg, block_median_surface_water. Extractor MUST set `season`.
  * severity_qualifier "REQUIRED" — drought_weeks_trend. Extractor MUST set `severity`.
  * medium_qualifier "REQUIRED" — salinity_level. Extractor MUST set `medium`.
- Allowed `season` values: "kharif" | "rabi" | "zaid" | "annual" | "not_applicable".
- Allowed `severity` values: "mild" | "moderate" | "severe" | "not_applicable".
- Allowed `medium` values: "groundwater" | "soil" | "not_applicable".
- When the same parent variable is discussed for multiple qualifier values, emit ONE
  variable instance per qualifier value, all sharing the same canonical variable_name
  but differing in `season`, `severity`, and/or `medium`. This preserves clarity in
  extraction while keeping the taxonomy compact.
- In causal edges, use the same canonical name and ensure the relevant qualifier
  field(s) are carried on the referenced variable definition. If an edge is
  qualifier-specific (e.g. rainfall -> cropping_area_trend only in kharif, rainfall
  -> drought_weeks_trend only for severe drought, or salinity_level -> crop_yield_trend
  only in the soil medium), also include a `season_scope`, `severity_scope`, and/or
  `medium_scope` field on the edge set to the relevant qualifier value.
- For variables whose parent does NOT take a given qualifier, set that qualifier to
  "not_applicable".

TAXONOMY EXPANSION (CANONICALIZED NEW VARIABLES FROM expansion_candidates):
- The following NEW_ variables are now part of the active taxonomy for extraction.
- Use these names EXACTLY when concept matches.
- Keep qualifiers at evidence level (season/severity/medium), not in variable names.

CLIMATE / ECOLOGICAL RESPONSE:
- NEW_land_surface_temp_trend
  * Trend/anomaly in near-surface temperature (air or land surface) affecting ET demand
    and water stress propagation. season_qualifier: not_applicable.
- NEW_gross_primary_productivity
  * Cropland gross primary productivity as drought-stress physiological outcome.
    season_qualifier: not_applicable.
- NEW_leaf_area_index
  * Canopy structural index for crop stress and growth suppression detection.
    season_qualifier: not_applicable.
- NEW_solar_induced_fluorescence
  * Photosynthetic activity proxy from SIF products for drought response.
    season_qualifier: not_applicable.
- NEW_vegetation_health_index
  * Vegetation health/greenness proxy (for example NDVI-family indicators).
    season_qualifier: not_applicable.
- NEW_wind_velocity
  * Near-surface wind speed influencing ET and erosion pressure.
    season_qualifier: not_applicable.
- NEW_moisture_index
  * Composite climatic moisture index (for example P-PET based dryness/wetness measure).
    season_qualifier: not_applicable.

SOIL / HYDROLOGICAL MEDIATORS:
- NEW_soil_moisture_index
  * Root-zone or near-surface soil moisture condition mediating climate-to-crop/recharge links.
    season_qualifier: not_applicable.
- NEW_soil_organic_carbon
  * Soil organic carbon level indicating soil health and moisture retention capacity.
    medium_qualifier: REQUIRED — "soil". season_qualifier: not_applicable.
- NEW_soil_erosion
  * Wind/water erosion rate reducing soil depth, fertility, and water retention.
    medium_qualifier: REQUIRED — "soil". season_qualifier: not_applicable.
- NEW_water_holding_capacity
  * Soil water-holding capacity controlling moisture persistence between rainfall events.
    medium_qualifier: REQUIRED — "soil". season_qualifier: not_applicable.
- NEW_soil_texture_permeability
  * Soil texture/permeability class controlling infiltration/percolation behaviour.
    season_qualifier: not_applicable.
- NEW_topographic_wetness_index
  * Topographic wetness index proxy for flow accumulation and groundwater potential.
    season_qualifier: not_applicable.
- NEW_surface_water_availability
  * Reservoir/river/lake water availability/storage condition for hydrological drought status.
    season_qualifier: not_applicable.

GROUNDWATER / GEOLOGY CONTEXT:
- NEW_aquifer_resistivity
  * Geophysical resistivity indicator for aquifer saturation and subsurface structure.
    season_qualifier: not_applicable.
- NEW_aquifer_thickness
  * Thickness of weathered/saturated zone indicating storage potential.
    season_qualifier: not_applicable.
- NEW_aquifer_transmissivity
  * Aquifer transmissivity/hydraulic property controlling groundwater response.
    season_qualifier: not_applicable.
- NEW_lineament_density
  * Fracture/lineament density proxy for secondary permeability.
    season_qualifier: not_applicable.
- NEW_drainage_density
  * Stream density proxy for runoff concentration versus infiltration potential.
    season_qualifier: not_applicable.
- NEW_slope
  * Terrain slope controlling runoff-infiltration partitioning.
    season_qualifier: not_applicable.
- NEW_gw_storage_anomaly
  * Groundwater storage anomaly (for example gravity-derived basin signal).
    season_qualifier: not_applicable.
- NEW_nitrate_groundwater_concentration
  * Groundwater nitrate concentration indicating irrigation/agrochemical water-quality stress.
    medium_qualifier: REQUIRED — "groundwater". season_qualifier: not_applicable.

LAND USE / DEMAND / POLICY DRIVERS:
- NEW_population_density
  * Population density/growth pressure driving water demand and land-use pressure.
    season_qualifier: not_applicable.
- NEW_builtup_area
  * Built-up urban area extent influencing infiltration and runoff regimes.
    season_qualifier: not_applicable.
- NEW_urban_area_fraction
  * Fraction/trend of urban impervious area linked to recharge suppression.
    season_qualifier: not_applicable.
- NEW_non_agricultural_water_demand
  * Industrial/domestic/commercial demand competing with irrigation allocation.
    season_qualifier: not_applicable.
- NEW_electricity_subsidy_intensity
  * Policy/institutional pumping incentive intensity affecting extraction behaviour.
    season_qualifier: not_applicable.
- NEW_rainwater_harvesting_coverage
  * Coverage of watershed/rainwater-harvesting interventions moderating drought impacts.
    season_qualifier: not_applicable.

IRRIGATION / FARM MANAGEMENT / ECONOMICS:
- NEW_irrigation_water_supply_reliability
  * Reliability of irrigation supply relative to demand.
    season_qualifier: not_applicable.
- NEW_shadow_price_of_water
  * Marginal opportunity cost of irrigation water under scarcity.
    season_qualifier: not_applicable.
- NEW_crop_water_requirement
  * Crop-specific water requirement/intensity governing irrigation demand.
    season_qualifier: not_applicable.
- NEW_micro_irrigation_adoption
  * Adoption share of drip/sprinkler systems as a water-saving adaptation.
    season_qualifier: not_applicable.
- NEW_canal_seepage_loss
  * Conveyance seepage losses in canals affecting reliability/waterlogging pathways.
    season_qualifier: not_applicable.
- NEW_water_use_efficiency
  * Efficiency of converting water input into biomass/yield.
    season_qualifier: not_applicable.
- NEW_waterlogging_area
  * Area affected by shallow water table/waterlogging due to irrigation/drainage imbalance.
    season_qualifier: not_applicable.
- NEW_energy_cost_pumping
  * Energy use/cost intensity for groundwater pumping.
    season_qualifier: not_applicable.

RAINFED ADAPTATION / LIVELIHOOD CONTEXT:
- NEW_crop_insurance_adoption
  * Adoption share of crop insurance as risk-transfer strategy.
    season_qualifier: not_applicable.
- NEW_drought_tolerant_variety_adoption
  * Adoption share of drought-tolerant varieties. season_qualifier: OPTIONAL (often kharif).
- NEW_intercropping_adoption
  * Adoption share of intercropping as diversification risk-management strategy.
    season_qualifier: OPTIONAL (often kharif).
- NEW_varietal_diversification_index
  * Variety diversification index (for example 1-HHI) for ex-ante risk reduction.
    season_qualifier: OPTIONAL (often kharif).
- NEW_farmer_organization_membership
  * Membership in cooperatives/producer groups influencing adaptation uptake.
    season_qualifier: not_applicable.
- NEW_institutional_credit_access
  * Access to formal agricultural credit enabling adaptation investment.
    season_qualifier: not_applicable.
- NEW_non_farm_income_availability
  * Availability of non-farm income buffering risk and affecting decisions.
    season_qualifier: not_applicable.
- NEW_land_holding_size
  * Operational landholding size as structural context for adoption capacity.
    season_qualifier: not_applicable.
- NEW_fertilizer_use_intensity
  * Fertilizer application intensity (kg/ha scale) as input-pressure driver.
    season_qualifier: not_applicable.
- NEW_fertilizer_consumption
  * Fertilizer consumption level/share as agronomic context variable.
    season_qualifier: not_applicable.
- NEW_crop_residue_burning
  * Residue burning share as management practice affecting soil/ecosystem stress.
    season_qualifier: not_applicable.
- NEW_livestock_mortality
  * Livestock mortality/migration outcome under drought-linked fodder/water stress.
    season_qualifier: not_applicable.

MACRO OUTCOMES:
- NEW_food_trade_balance
  * Net food trade balance response under domestic water-scarcity shocks.
    season_qualifier: not_applicable.
- NEW_welfare_loss
  * Monetized welfare loss attributable to water scarcity and linked impacts.
    season_qualifier: not_applicable.

ALIAS / MERGE HINTS (avoid duplicate NEW nodes):
- Temperature-related aliases (NEW_temperature_rise, LST trend, warming trend)
  should map to NEW_land_surface_temp_trend unless paper clearly defines a distinct variable.
- Urbanization aliases (NEW_builtup_area, NEW_urban_area_fraction, impervious share)
  should usually map to one canonical concept for the run; preserve exact wording in
  alias_used_in_paper.
- Fertilizer aliases (NEW_fertilizer_use_intensity, NEW_fertilizer_consumption)
  should be merged when they refer to comparable application-intensity constructs.
"""

KG_SCHEMA_RULES = """
CANONICALIZATION + HYBRID LAYER RULES:
- The knowledge graph MUST have one node per concept, so every extracted variable must
  resolve to a single `canonical_variable_name`.
- Keep qualifiers (`season`, `severity`, `medium`) at instance/evidence level, NOT in
  the node id. Never create ids like kharif_xxx, severe_xxx, groundwater_xxx.
- Use a two-layer stressor representation:
  * `cluster_family`: one of groundwater_stress | drought | rainfed_risk |
    irrigation_challenges | mixed | unknown (for clustering/visualization).
  * `mechanism_domains`: dynamic multi-label tags derived from the paper's mechanism text.
    These tags are NOT fixed and may include additional domains discovered in papers.
- If extraction wording varies but meaning is same, map to same canonical variable and
  keep wording in `alias_used_in_paper`.
- For uncertain NEW_ mappings, emit:
  * `canonicalization_confidence`: high | medium | low
  * `candidate_merge_target`: canonical variable suggestion or null

ALIAS RESOLUTION RULES:
- First try exact canonical match.
- Else try alias-table match (known synonym/legacy term -> canonical name).
- Else keep NEW_ variable but add candidate_merge_target when a near-synonym exists.
- Never auto-split one concept into multiple node ids due to wording.
"""


# ---------------------------------------------------------------------------
# SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an expert agricultural scientist and data analyst specialising "
    "in causal mechanism analysis. Your job is to extract TWO things from research papers:\n\n"
    "1. MEASURABLE VARIABLES that can detect agricultural stressors at district/block level\n"
    "2. CAUSAL CHAINS showing HOW variables connect — the step-by-step mechanism from\n"
    "   root driver to observable outcome\n\n"
    "CRITICAL DEFINITIONS:\n"
    "- A \"variable\" is a quantifiable, measurable feature obtainable from data sources\n"
    "  (remote sensing, census, weather stations, surveys, government databases).\n"
    "- A \"causal chain\" is a directed sequence: Variable_A -> Variable_B -> Variable_C\n"
    "  where each arrow has a MECHANISM explaining WHY A affects B.\n"
    "- Variables must be CONCRETE and COMPUTABLE. \"Farmer perception\" is NOT a variable.\n"
    "  \"Groundwater table depth in meters\" IS a variable.\n\n"
    "VARIABLE ROLES — classify every variable as one of:\n"
    "- driver: exogenous root cause (e.g., precipitation, geology, policy)\n"
    "- mediator: intermediate mechanism step (e.g., recharge rate, soil moisture)\n"
    "- outcome: observable effect that farmers see (e.g., crop yield, well depth)\n"
    "- context: moderating factor that determines WHEN a mechanism is active\n"
    "  (e.g., aquifer type, landholding size, subsidy policy)\n\n"
    "CAUSAL CHAIN RULES:\n" 
    "- Each edge must have: from_var, to_var, mechanism (1-2 sentences of WHY),\n"
    "  direction, strength, conditions (when does this hold)\n"
    "- Build COMPLETE chains from drivers -> mediators -> outcomes\n"
    "- If Paper says \"A leads to B which causes C\", extract TWO edges: A->B and B->C\n"
    "- Use taxonomy variable names in edges whenever possible\n"
    "- Capture the MECHANISM, not just the correlation\n"
    "- CROSS-STRESSOR LINKS ARE VALID AND REQUIRED when the paper supports them.\n"
    "  Examples of valid cross-stressor edges:\n"
    "    * groundwater_stress variable -> drought variable\n"
    "    * drought variable -> rainfed_risk variable\n"
    "    * rainfed_risk variable -> irrigation_challenges variable\n"
    "  Do NOT discard such edges as \"out of scope\" — they are essential for the\n"
    "  cross-stressor knowledge graph.\n"
    "- Where the paper gives NUMERIC RANGES or THRESHOLDS for variables on a causal link,\n"
    "  record them on causal_chains edges so downstream\n"
    "  rules can compare observed district/block values to paper-derived stressed ranges.\n\n"
    + VARIABLE_TAXONOMY
    + "\nHYBRID STRESSOR LAYERING:\n"
    "- cluster_family (fixed set for dashboards): groundwater_stress | drought |\n"
    "  rainfed_risk | irrigation_challenges | mixed | unknown\n"
    "- mechanism_domains (dynamic multi-label, paper-derived):\n"
    "  examples include climate_forcing, hydrogeology, recharge_dynamics,\n"
    "  crop_water_demand, irrigation_infrastructure, adaptation_capacity,\n"
    "  policy_incentives, land_use_transition, water_quality, socio_economic_pressure.\n"
    "  You may emit additional mechanism domains when justified by the paper.\n\n"
    "NAMING RULES:\n"
    "1. If a variable matches the taxonomy above, use EXACTLY that taxonomy name\n"
    "2. If genuinely new, prefix with NEW_ (e.g., NEW_soil_moisture_index)\n"
    "3. When in doubt, map to existing\n"
    "4. Always emit canonical_variable_name and alias_used_in_paper\n\n"
    + KG_SCHEMA_RULES
    + "\n"
    "Return ONLY valid JSON. No markdown, no preamble."
)


# ---------------------------------------------------------------------------
# EXTRACTION PROMPT
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """Extract variables AND causal chains from this research paper
for water-scarcity mechanism discovery in Indian districts/blocks.

PATTERN CONTEXT:
- Production system: Agriculture
- Observational stressor (what farmers see): Water Scarcity
- Primary causal stressor label for this run: rainfed risk
- Stressor type: Causal

RELAXED SCOPE (CRITICAL):
- Extract ALL water-scarcity-relevant causal links present in the paper, not only links
  that stay inside one stressor family.
- Cross-stressor chains (e.g. groundwater_stress -> drought -> rainfed_risk ->
  irrigation_challenges) are EXPECTED whenever evidence supports them.
- The rainfed risk label above tells you the run's entry focus, but you must NOT
  filter out edges whose endpoints belong to other stressor families.
- Apply the same variable-naming rigor and evidence standards as a single-stressor run.

PAPER CONTENT:
Title: {paper_title} - pdf provided below
{paper_text} - pdf provided 
---
VARIABLE NAMING — MANDATORY MAPPINGS:
- Paper says "depth to water table trend" / "groundwater trend" -> use "g_annual_trend"
- Paper says "rainfall" / "precipitation" -> use "prec_annual_avg_rain"
- Paper says "groundwater extraction stage" -> use "soge_class_name"
- Paper says "net sown area ratio" / "cropping intensity" -> use "cropping_intensity_trend"
- Paper says "double cropping" / "doubly cropped area" -> use "double_crop_trend"
- Paper says "drought severity" / "SPI" / "mild drought weeks" / "moderate drought weeks"
  / "severe drought weeks" -> use parent "drought_weeks_trend" with `severity` set to
  "mild" | "moderate" | "severe" depending on the severity the paper discusses. If the
  paper presents multiple severity levels, emit ONE variable instance per severity using
  the same canonical name and different `severity` values.
- Paper says "dry spell" -> use "drysp_4w_trend"
- Paper says "drought frequency" -> use "drought_freq"
- Paper says "evapotranspiration" -> use "et_annual_avg"
- Paper says "aquifer type" -> use "acquifer"
- Paper says "runoff" -> use "runoff_annual_avg"
- Paper says "surface water area trend" -> use parent "surface_water_area_trend" with
  `season` set to "kharif" | "rabi" | "zaid" | "annual" depending on the season the
  paper discusses. Do NOT invent season-specific names.
- Paper says "surface water area" / "water body area" -> use parent
  "surface_water_area_avg" with `season` set to the relevant season.
- Paper says "block-median surface water" -> use parent "block_median_surface_water"
  with `season` set to the relevant season.
- Paper says "crop area trend" / "seasonal cropped area trend" -> use parent
  "cropping_area_trend" with `season` set to "kharif" | "rabi" | "zaid" | "annual".
  If the paper presents multiple seasons, emit ONE variable instance per season using
  the same canonical name and different `season` values.
- Paper says "crop yield trend" / "yield change" -> use "crop_yield_trend"
- Paper says "groundwater recharge" / "aquifer recharge" / "replenishment rate"
  -> use "recharge_rate"
- Paper says "well depth" / "borewell depth" / "tubewell depth" -> use "well_depth"
- Paper says "irrigated area" / "irrigated fraction" / "percent irrigated"
  -> use "irrigated_area_fraction"
- Paper says "irrigation demand" / "irrigation withdrawal" / "crop water demand from
  irrigation" -> use "irrigation_demand"
- Paper says "groundwater salinity" / "groundwater EC" / "electrical conductivity of
  groundwater" / "soil salinity" / "soil EC" -> use parent "salinity_level" with
  `medium` set to "groundwater" | "soil" depending on the medium the paper discusses.
  If the paper presents both media, emit ONE variable instance per medium using the
  same canonical name and different `medium` values.
- Paper says "deforestation" / "forest loss" -> use "deforestation"
- IMPORTANT CLASSIFICATION RULE:
  * The full EXISTING taxonomy includes BOTH:
    (a) base taxonomy names (e.g., g_annual_trend, crop_yield_trend), AND
    (b) taxonomy-expansion canonical names listed in SYSTEM_PROMPT under
        "TAXONOMY EXPANSION (CANONICALIZED NEW VARIABLES ...)" such as
        NEW_soil_moisture_index, NEW_water_use_efficiency, NEW_population_density, etc.
  * Therefore, if a variable matches ANY listed canonical name in that full taxonomy
    (including names that start with NEW_), it MUST go to "mapped_variables"
    (taxonomy_name = canonical_variable_name), NOT "new_variables".
  * Use "new_variables" ONLY for truly unseen concepts that are not present anywhere
    in the full taxonomy list (base + taxonomy expansion).
- Only create a brand-new NEW_ name if the concept is genuinely not covered by the
  full existing taxonomy list.

NEW_ VARIABLE NAMING RULES (ONLY for truly unseen variables not in full taxonomy):
- Use lowercase snake_case: NEW_descriptive_concept_name
- Prefer generic concept names, NOT paper-specific jargon or acronym-heavy names
  GOOD: NEW_soil_moisture_index, NEW_crop_water_requirement, NEW_population_density
  BAD:  NEW_smi_from_modis, NEW_grace_gws_anomaly, NEW_ndvi_vci_composite
- Use consistent naming patterns so the SAME concept from different papers gets the SAME name:
  * Crop water requirement / consumptive use -> NEW_crop_water_requirement
  * Soil moisture / soil water content -> NEW_soil_moisture_index
  * Soil organic carbon / soil health index -> NEW_soil_organic_carbon
  * Groundwater storage anomaly (GRACE) -> NEW_gw_storage_anomaly
  * Vegetation health / NDVI trend -> NEW_vegetation_health_index
  * Land surface temperature trend -> NEW_land_surface_temp_trend
  * Population density / growth rate -> NEW_population_density
  * Water use efficiency -> NEW_water_use_efficiency
- If uncertain whether a concept matches an above pattern, use the pattern name

HYBRID LAYER TAGGING FOR VARIABLES AND EDGES:
- Assign BOTH:
  * cluster_family (fixed set): groundwater_stress | drought | rainfed_risk |
    irrigation_challenges | mixed | unknown
  * mechanism_domains: one or more paper-derived mechanism labels.
- For EVERY draft edge inside mechanism_blocks.edge_drafts AND every final edge in
  causal_chains, assign from_cluster_family and to_cluster_family.
- An edge is "cross-stressor" when from_cluster_family != to_cluster_family
  (both sides not "mixed" / "unknown"). Keep it — do not discard.

EXTRACTION RULES:
- Variables must be QUANTIFIABLE and OBTAINABLE from real data sources
- Do NOT extract qualitative opinions, farmer perceptions, or policy descriptions
- DO extract thresholds, index values, trends, rates, areas, depths, percentages
- For EVERY variable, assign a role: driver | mediator | outcome | context
- MECHANISM-FIRST WORKFLOW (must follow this order inside the JSON you output):
  1) Identify the paper's distinct mechanisms and emit mechanism_blocks FIRST, each with
     ordered edge_drafts (the causal arrows the paper supports for that mechanism story).
  2) Build causal_chains SECOND as the DEDUPLICATED union of all edge_drafts across blocks:
     - assign unique sequential edge_id values (e1, e2, ..., en) in causal_chains
     - if the same (from_var, to_var, direction) appears in multiple mechanisms, keep ONE
       canonical causal_chains entry and merge supporting text/ranges/excerpts carefully ensuring that we covered all of the mechanisms in the paper.
  3) Fill mechanism_blocks.edge_ids THIRD so every block references only edge_id strings
     that exist in causal_chains, in the same causal order as edge_drafts.
- Do NOT invent causal_chains edges that are not supported by at least one mechanism
  block edge_draft (except you may SPLIT a draft into two causal_chains edges if the
  paper clearly states a missing intermediate step — then update edge_drafts accordingly).
- VALUE RANGES ON EDGES (required wherever the paper states numbers for those variables):
  For EVERY draft edge in mechanism_blocks.edge_drafts AND every final edge in
  "causal_chains", include the paper-reported numeric range or threshold for the FROM
  variable and the TO variable as it applies to THAT link (copy from text, tables, or
  figures). Use the SAME variable names as from_var/to_var. If the paper gives no number
  for an endpoint, use null. Units must match the variable (or state unit explicitly in
  the string).
  Example: from_var_value_range: "-6.52 to -19.83 mm/year (GW trend, NW India)",
  to_var_value_range: "5073.61 km²/year (cropland expansion)".

Return this EXACT JSON structure:

{{
  "schema_version": "2.0",
  "paper_title": "string",
  "paper_identity": {"paper_id": 41, "paper_title": "same as paper_title"},
  "paper_summary": "2-3 sentences on what the paper studies and key findings",
  "study_region": "where the study was conducted",
  "study_period": "time period covered",
  "methodology": "brief: regression/GIS/remote sensing/survey/modeling etc.",
  "paper_type": "mechanism | case_study | technical | policy | review",
  "paper_type_rationale": "1-2 sentences: WHY this classification fits (e.g. 'Uses LP optimization and MSP procurement rules — policy-focused' or 'Panel regressions testing causal links — mechanism study'). Must align with paper_type.",

  "cluster_families_covered": ["groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown"],
  "mechanism_domains_covered": ["dynamic_label_1", "dynamic_label_2"],

  "mapped_variables": [
    {{
      "taxonomy_name": "EXACT name from full existing taxonomy (base + taxonomy expansion; parent name; no qualifier suffix)",
      "canonical_variable_name": "same as taxonomy_name for mapped variables",
      "alias_used_in_paper": "exact wording used in paper for this variable",
      "definition_source": "taxonomy | paper | merged",
      "canonicalization_confidence": "high | medium | low",
      "candidate_merge_target": "canonical variable suggestion or null",
      "paper_terminology": "what the paper calls it",
      "description": "what it measures and why it matters",
      "unit": "mm | m | ha | % | index | etc.",
      "role": "driver | mediator | outcome | context",
      "season": "kharif | rabi | zaid | annual | not_applicable",
      "severity": "mild | moderate | severe | not_applicable",
      "medium": "groundwater | soil | not_applicable",
      "data_source_in_paper": "source used in the paper",
      "indian_data_source": "Indian public source, or 'same'",
      "threshold_or_range": "specific number if paper gives one, else null",
      "indicator_direction": "high_means_stressed | low_means_stressed | increasing_trend_means_stressed | decreasing_trend_means_stressed | categorical",
      "relevance": "direct | proxy | contextual",
      "cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "paper_context_id": "paper_slug::var_key::qualifier_key",
      "source_paper": {"paper_id": 0, "paper_title": "string"},
      "excerpt": "1-2 key sentences from the paper"
    }}
  ],

  "new_variables": [
    {{
      "variable_name": "NEW_descriptive_name (ONLY if not present in full existing taxonomy list)",
      "canonical_variable_name": "NEW_descriptive_name (or chosen unified NEW_ name)",
      "alias_used_in_paper": "exact wording used in paper",
      "definition_source": "paper | merged",
      "canonicalization_confidence": "high | medium | low",
      "candidate_merge_target": "existing canonical variable name or null",
      "why_new": "why no existing taxonomy variable fits",
      "description": "what it measures",
      "unit": "string",
      "role": "driver | mediator | outcome | context",
      "season": "kharif | rabi | zaid | annual | not_applicable",
      "severity": "mild | moderate | severe | not_applicable",
      "medium": "groundwater | soil | not_applicable",
      "data_source_in_paper": "string",
      "indian_data_source": "string",
      "threshold_or_range": "string or null",
      "indicator_direction": "string",
      "relevance": "direct | proxy | contextual",
      "cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "paper_context_id": "paper_slug::new_var_key::qualifier_key",
      "source_paper": {"paper_id": 0, "paper_title": "string"},
      "excerpt": "1-2 key sentences"
    }}
  ],

  "mechanism_blocks": [
    {{
      "name": "short_mechanism_name (e.g. recharge_deficit_mechanism)",
      "description": "narrative of how this mechanism works end-to-end",
      "stressor_scope": "within_stressor | cross_stressor | mixed",
      "edge_drafts": [
        {{
          "from_var": "taxonomy_name or NEW_name of the CAUSE variable (parent name; no qualifier suffix)",
          "from_var_source": {"paper_id": 0, "paper_title": "string"},
          "to_var": "taxonomy_name or NEW_name of the EFFECT variable (parent name; no qualifier suffix)",
          "to_var_source": {"paper_id": 0, "paper_title": "string"},
          "mechanism": "1-2 sentences explaining WHY from_var affects to_var",
          "direction": "increase_causes_increase | increase_causes_decrease | decrease_causes_increase | decrease_causes_decrease | categorical_determines",
          "strength": "strong | moderate | weak | unspecified",
          "conditions": "under what context is this link active (or null)",
          "from_var_value_range": "numeric range/threshold from paper for from_var on this edge, or null",
          "from_var_value_range_source": {"paper_id": 0, "paper_title": "string"},
          "to_var_value_range": "numeric range/threshold from paper for to_var on this edge, or null",
          "to_var_value_range_source": {"paper_id": 0, "paper_title": "string"},
          "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
          "is_cross_stressor": true,
          "season_scope": "kharif | rabi | zaid | annual | not_applicable",
          "severity_scope": "mild | moderate | severe | not_applicable",
          "medium_scope": "groundwater | soil | not_applicable",
          "excerpt": "supporting sentence from the paper"
        }}
      ],
      "edge_ids": ["e1", "e2", "e3"],
      "context_variables": ["variables that moderate this mechanism"]
    }}
  ],

  "causal_chains": [
    {{
      "edge_id": "e1 | e2 | ... | en (unique within this paper JSON)",
      "from_var": "taxonomy_name or NEW_name of the CAUSE variable (parent name; no qualifier suffix)",
      "from_var_source": {"paper_id": 0, "paper_title": "string"},
      "to_var": "taxonomy_name or NEW_name of the EFFECT variable (parent name; no qualifier suffix)",
      "to_var_source": {"paper_id": 0, "paper_title": "string"},
      "mechanism": "1-2 sentences explaining WHY from_var affects to_var",
      "direction": "increase_causes_increase | increase_causes_decrease | decrease_causes_increase | decrease_causes_decrease | categorical_determines",
      "strength": "strong | moderate | weak | unspecified",
      "conditions": "under what context is this link active (or null)",
      "from_var_value_range": "numeric range/threshold from paper for from_var on this edge, or null",
      "from_var_value_range_source": {"paper_id": 0, "paper_title": "string"},
      "to_var_value_range": "numeric range/threshold from paper for to_var on this edge, or null",
      "to_var_value_range_source": {"paper_id": 0, "paper_title": "string"},
      "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "is_cross_stressor": true,
      "season_scope": "kharif | rabi | zaid | annual | not_applicable",
      "severity_scope": "mild | moderate | severe | not_applicable",
      "medium_scope": "groundwater | soil | not_applicable",
      "excerpt": "supporting sentence from the paper"
    }}
  ],

  "conditional_thresholds": [
    {{
      "variable": "taxonomy_name",
      "threshold": "specific value",
      "condition": "when/where this threshold applies",
      "implication": "what exceeding this threshold means for the stressor"
    }}
  ],

  "key_relationships": [
    "Important relationships using taxonomy names. Include r-values, correlations, causal statements."
  ],

  "alias_resolution_rules": [
    {
      "alias_text": "paper-specific term",
      "canonical_variable_name": "resolved canonical variable",
      "resolution_method": "exact_canonical_match | alias_table_match | near_synonym_suggestion",
      "resolution_confidence": "high | medium | low",
      "notes": "optional rationale"
    }
  ],

  "mapping_notes": "Variables you were unsure about mapping",
  "limitations": "caveats about transferability or data quality",

  "important_variables": [
    {{
      "variable_name": "taxonomy_name or NEW_name",
      "significance": "why this variable is critical for understanding or detecting the stressor — cite evidence from the paper",
      "evidence_strength": "strong | moderate",
      "recommendation": "existing_taxonomy | candidate_for_taxonomy"
    }}
  ],

  "important_variables_narrative": "3-5 sentence summary of the paper's most significant variables and their role in the stressor mechanism. Focus on which variables the paper treats as most explanatory or predictive, and why they matter for detecting the stressor at district/block level."
}}

IMPORTANT_VARIABLES INSTRUCTIONS:
- Include ONLY variables that the paper treats as highly significant — strong statistical
  evidence (high R², significant p-values, key regression coefficients) OR central to the
  paper's main causal mechanism. Do NOT list every variable mentioned.
- For variables already present in the full taxonomy list (including taxonomy-expansion
  names that start with NEW_), set recommendation to "existing_taxonomy".
- For truly unseen variables created in "new_variables": set recommendation to
  "candidate_for_taxonomy" if the variable seems universally important (would matter
  across multiple studies/regions), not just paper-specific.
- There is no fixed count — include as many or as few as genuinely deserve it.

Be thorough. A good extraction finds 5-20 variables and 5-15 causal edges, and explicitly
includes cross-stressor edges when the paper supports them. Return ONLY the JSON. Save the json in the file called {paper_title}.json in out_5/stressor_name folder"""


# ---------------------------------------------------------------------------
# VERIFICATION PROMPT
# ---------------------------------------------------------------------------

VERIFICATION_PROMPT = """Review the extraction you produced for "{paper_title}-- provided pdf". Check:

1. MAPPING ACCURACY:
   - Is every taxonomy_name an EXACT match from the taxonomy list (PARENT names only;
     no season-suffixed, severity-suffixed, or medium-suffixed names)?
   - Treat taxonomy-expansion canonical names (the listed NEW_* names in SYSTEM_PROMPT)
     as EXISTING taxonomy entries: they must be in mapped_variables, not new_variables.
   - Should any NEW_ variable actually map to an existing parent? Common mistakes:
     * Groundwater level/depth/trend -> g_annual_trend
     * Well/borewell/tubewell depth -> well_depth
     * Rainfall/precipitation -> prec_annual_avg_rain
     * Drought severity weeks trend (mild / moderate / severe drought weeks) -> parent
       "drought_weeks_trend" with severity set to mild / moderate / severe
       (NOT mild_weeks_trend / moderate_weeks_trend / severe_weeks_trend)
     * Dry spells -> drysp_4w_trend
     * Drought frequency -> drought_freq
     * Crop area trend by season -> parent "cropping_area_trend" with season set to
       kharif / rabi / zaid / annual (NOT kharif_cropping_area_trend etc.)
     * Cropping intensity -> cropping_intensity_trend
     * Double cropping -> double_crop_trend
     * Crop yield trend -> crop_yield_trend
     * Groundwater extraction rate/category -> soge_class_name
     * Groundwater recharge / aquifer replenishment -> recharge_rate
     * Surface water area trend -> parent "surface_water_area_trend" with season set
       to kharif / rabi / zaid / annual
     * Surface water area average -> parent "surface_water_area_avg" with season set
       to kharif / rabi / zaid / annual
     * Block median surface water -> parent "block_median_surface_water" with season
       set to kharif / rabi / zaid / annual
     * Evapotranspiration -> et_annual_avg
     * Runoff -> runoff_annual_avg
     * Aquifer type -> acquifer
     * Irrigated area / irrigated fraction -> irrigated_area_fraction
     * Irrigation demand / withdrawal -> irrigation_demand
     * Groundwater or soil salinity (EC) -> parent "salinity_level" with medium set
       to groundwater / soil (NOT NEW_groundwater_ec or NEW_soil_salinity)
     * Deforestation/forest loss -> deforestation

2. CAUSAL CHAIN COMPLETENESS:
   - Are chains connected end-to-end (driver -> mediator -> outcome)?
   - Does every edge have a mechanism explanation (not just "causes")?
   - Does every causal edge include a unique edge_id in sequence (e1..en)?
   - Do all causal_chain variable names exist in mapped_variables or new_variables?
   - Are there intermediate steps missing? E.g., "rainfall -> crop yield" should have
     "rainfall -> soil moisture -> crop yield" if the paper describes that path.
   - MECHANISM-FIRST CONSISTENCY:
     * Every causal_chains edge must be traceable to at least one mechanism_blocks.edge_drafts
       entry (same from_var, to_var, direction; merge duplicates consistently).
     * causal_chains must be the deduplicated union of all edge_drafts (no orphan edges).
   - CROSS-STRESSOR EDGES MUST BE PRESERVED. Do NOT remove an edge simply because
     from_cluster_family differs from to_cluster_family. Only remove if the paper
     does not actually support it.

3. VARIABLE ROLES:
   - Is every variable assigned a role (driver/mediator/outcome/context)?
   - Do roles make sense? Drivers should be exogenous, outcomes should be observable.

4. MECHANISM BLOCKS:
   - Does each mechanism_block tell a coherent story?
   - Does each mechanism_block include non-empty edge_drafts with correct causal ordering?
   - Does each mechanism_block.edge_ids reference ONLY causal_chains.edge_id values (no
     duplicated full edge objects in edge_ids)?
   - Do all mechanism_blocks.edge_ids exist in causal_chains.edge_id?
   - Is EVERY causal_chains.edge_id included in at least one mechanism_block.edge_ids?
   - For each mechanism_block, does edge_ids follow the same causal order as edge_drafts
     (after deduplication mapping drafts -> canonical edge_id)?
   - Does EVERY edge in causal_chains include from_var_value_range and to_var_value_range
     where the paper states numbers? (Use null only when truly unavailable.)
   - Is stressor_scope (within_stressor | cross_stressor | mixed) correctly set on each block?

4b. PAPER TYPE:
   - Is paper_type one of: mechanism | case_study | technical | policy | review?
   - Does paper_type_rationale clearly justify the choice (policy vs mechanism vs review, etc.)?

4c. HYBRID LAYER TAGS:
   - Is every variable tagged with a plausible cluster_family?
   - Does every variable include at least one plausible mechanism_domains label?
   - Is every edge (in causal_chains) tagged with from_cluster_family,
     to_cluster_family, and is_cross_stressor?
   - Is is_cross_stressor computed consistently (true when the two cluster families differ
     and neither is "unknown")?

4d. CANONICALIZATION + ALIAS QUALITY:
   - Does every variable include canonical_variable_name and alias_used_in_paper?
   - Does every variable include source_paper with both paper_id and paper_title?
   - For mapped_variables, is canonical_variable_name equal to taxonomy_name?
   - Are taxonomy-expansion NEW_* names placed in mapped_variables (not new_variables)?
   - For NEW_ variables, when semantic overlap with an existing canonical variable is likely,
     is candidate_merge_target provided with a reasonable canonicalization_confidence?
   - Are alias_resolution_rules present and consistent with mapped/new variable names?

4f. PROVENANCE COMPLETENESS:
   - Is top-level paper_identity present with paper_id and paper_title?
   - For each causal_chains edge, are from_var_source/to_var_source present?
   - For each causal_chains edge range field, are from_var_value_range_source/to_var_value_range_source present?

4e. PARENT-VARIABLE QUALIFIERS (season / severity / medium):
   - For every variable whose parent supports seasons (cropping_area_trend,
     surface_water_area_trend, surface_water_area_avg, block_median_surface_water),
     is `season` set to exactly one of kharif | rabi | zaid | annual?
   - For every variable whose parent supports severity (drought_weeks_trend), is
     `severity` set to exactly one of mild | moderate | severe?
   - For every variable whose parent supports medium (salinity_level), is `medium`
     set to exactly one of groundwater | soil?
   - If the paper discusses multiple qualifier values for the same parent (multiple
     seasons, severities, or media), are there multiple variable instances sharing
     the same canonical name but differing in `season`, `severity`, and/or `medium`?
   - For variables whose parent does not support a given qualifier, is that qualifier
     set to "not_applicable"?
   - On every edge, are `season_scope`, `severity_scope`, and `medium_scope` set and
     consistent with the qualifier values of the connected variables?

5. THRESHOLDS:
   - Are thresholds specific with numbers where the paper provides them?
   - E.g., not just "high decline" but "decline > 0.2 m/year"

6. COMPLETENESS:
   - Check tables, figures, and supplementary descriptions for missed variables
   - Are there derived indices or composite scores not captured?
   - Were any cross-stressor mechanisms (e.g. rainfall deficit -> groundwater extraction
     -> aquifer decline -> irrigation failure) missed and need to be added?

7. IMPORTANT VARIABLES QUALITY:
   - Are the important_variables well-chosen? They should represent the paper's truly
     significant findings — variables with strong statistical evidence or central causal
     role — NOT just every variable mentioned.
   - For NEW_ variables marked "candidate_for_taxonomy": are they genuinely universal
     (relevant across studies/regions), or paper-specific? Downgrade if paper-specific.
   - Does the important_variables_narrative accurately capture the paper's key message
     about which variables matter most and why?

{extraction_json} -- provided along with the pdf

Always output a full JSON file named {paper_title}_verified.json in out_5/stressor_name folder.
If corrections are needed, output the CORRECTED full JSON in that file.
If the extraction is already accurate, output the SAME JSON (unchanged except normalization needed for strict schema compliance) in that _verified file.
"""


# ---------------------------------------------------------------------------
# CAUSAL GRAPH PROMPT (build full causal graph from extractions)
# ---------------------------------------------------------------------------

CAUSAL_GRAPH_PROMPT = """You are given variable extraction JSON(s) from research papers
studying water scarcity mechanisms in Indian districts/blocks.

  Production system: {production_system}
  Observational stressor: {observational_stressor}
  Primary causal stressor label: {causal_stressor}

Your task is to build a COMPLETE CAUSAL GRAPH from ALL the causal edges and variables
in the extraction(s) below. This is NOT a summary — you must include EVERY edge and
EVERY variable from the source extractions, then discover and enumerate ALL possible
directed paths through the resulting graph.

CRITICAL: cross-stressor edges (where from_cluster_family != to_cluster_family) MUST
be retained. They are essential for the final knowledge graph.

SOURCE EXTRACTIONS:
{all_extractions}

---

STEP-BY-STEP INSTRUCTIONS:

STEP 1 — COLLECT NODES:
- List every unique variable from mapped_variables (use taxonomy_name, PARENT name only)
  and new_variables (use variable_name) across all extractions.
- For each node, carry over: role, description, unit, threshold_or_range,
  indicator_direction, data_source, cluster_family, mechanism_domains.
- Collect qualifiers:
  * `seasons_reported` = set of `season` values reported across papers for this parent
    variable (subset of kharif / rabi / zaid / annual / not_applicable).
  * `severities_reported` = set of `severity` values reported across papers for this
    parent variable (subset of mild / moderate / severe / not_applicable).
  * `media_reported` = set of `medium` values reported across papers for this parent
    variable (subset of groundwater / soil / not_applicable).
  If only one qualifier value is reported, still record it as a single-element list.
  The node id MUST be the parent name (no season, severity, or medium suffix).
  Qualifier specificity is carried in `seasons_reported` / `severities_reported` /
  `media_reported`, not in the id.
- Reject any node whose id is an old qualifier-suffixed name. If an extraction uses
  such a legacy name, normalize it to the correct parent in this step
  (e.g. kharif_cropping_area_trend -> cropping_area_trend with season "kharif";
  mild_weeks_trend -> drought_weeks_trend with severity "mild";
  groundwater_ec / soil_salinity -> salinity_level with medium set accordingly).
- If multiple papers give different numeric ranges for the same variable,
  MERGE into threshold_or_range as a combined envelope (e.g. "papers report
  X in [a,b], Y in [c,d] -> combined [min(a,c), max(b,d)]" when units match)
  or as a semicolon-separated list of paper-specific ranges when not comparable.
- If papers disagree on cluster_family, mark the node as "mixed" and list
  all reported families in cluster_families_reported.
- Compute in_degree (how many edges point TO this node) and out_degree
  (how many edges go FROM this node).
- A node with in_degree=0 is a ROOT DRIVER.
- A node with out_degree=0 is a TERMINAL OUTCOME.
- Set is_taxonomy=true if the variable is from the existing taxonomy, false if NEW_.

STEP 2 — COLLECT EDGES:
- List every unique causal edge from the causal_chains arrays across all extractions.
- If multiple papers describe the same A→B edge, MERGE them into one edge:
  combine mechanism text, list all supporting papers, upgrade confidence.
- Assign each edge a unique edge_id (e1, e2, e3, ...).
- Carry over: from, to, mechanism, direction, strength, conditions, excerpt,
  from_cluster_family, to_cluster_family, is_cross_stressor, mechanism_domains, season_scope,
  severity_scope, medium_scope.
- Carry over from_var_value_range and to_var_value_range from each paper; when merging
  the same A→B edge, combine ranges like nodes (envelope if comparable, else list by paper).
- Merge `season_scope` across duplicate edges: if papers report the same A→B link for
  different seasons, store every reported value in `seasons_scope_reported` and set
  `season_scope` to the dominant season, or "mixed" if truly season-agnostic.
- Merge `severity_scope` the same way: if papers report the same A→B link for different
  severity levels, store every reported value in `severities_scope_reported` and set
  `severity_scope` to the dominant severity, or "mixed" if truly severity-agnostic.
- Merge `medium_scope` the same way: if papers report the same A→B link for different
  media (groundwater vs soil), store every reported value in `media_scope_reported`
  and set `medium_scope` to the dominant medium, or "mixed" if truly medium-agnostic.
- Add confidence: "high" if 2+ papers support it, "medium" if 1 paper with
  strong/moderate strength, "low" if 1 paper with weak strength.

STEP 3 — BUILD ADJACENCY:
- For every node, list its outgoing neighbors and incoming neighbors.

STEP 4 — ENUMERATE PATHS:
- Starting from every ROOT DRIVER (in_degree=0), do a depth-first traversal
  through outgoing edges to reach every TERMINAL OUTCOME (out_degree=0).
- Record each unique path as an ordered sequence of edge_ids.
- Also record paths that start from mediators if they lead to outcomes not
  reachable from root drivers.
- Classify each path by structure:
  * "linear" — single chain, no branching (A→B→C→D)
  * "fan_out" — one node feeds multiple downstream nodes (A→B, A→C)
  * "fan_in" — multiple nodes converge to one (A→C, B→C)
  * "complex" — combination of fan_out and fan_in
- Also classify each path by stressor transitions:
  * "within_stressor" — all nodes share one cluster_family
  * "cross_stressor" — the path traverses two or more cluster families
  * "mixed" — includes at least one node whose family is "mixed" or "unknown"
- For each path, compute the net_direction by chaining the individual edge directions.
  E.g., increase_causes_decrease + decrease_causes_decrease = increase_causes_decrease.
- Write a narrative: a 1-3 sentence plain-English explanation of the full mechanism
  from root driver to terminal outcome.

STEP 5 — IDENTIFY CONTEXT MODIFIERS:
- Context variables (role=context) do not appear as from/to in edges but MODIFY
  when edges are active. Attach them to paths where they are relevant.

STEP 6 — VALIDATE:
- Every variable in edges must exist in nodes.
- Every edge must be referenced in at least one path.
- No orphan nodes (unless they are context variables).
- No cycles (if you find one, note it in graph_metadata.notes).
- Confirm cross-stressor edges were preserved (count them and report in metadata).

Return this EXACT JSON structure:

{{
  "graph_metadata": {{
    "pattern": "{production_system} → {observational_stressor} → {causal_stressor}",
    "source_papers": [{"paper_id": 0, "paper_title": "string"}],
    "total_nodes": 0,
    "total_edges": 0,
    "total_paths": 0,
    "within_stressor_edges": 0,
    "cross_stressor_edges": 0,
    "root_drivers": ["nodes with in_degree=0"],
    "terminal_outcomes": ["nodes with out_degree=0"],
    "context_variables": ["nodes with role=context"],
    "source_papers_profile": [
      {{"paper_id": 0, "paper_title": "string", "paper_type": "mechanism | case_study | technical | policy | review"}}
    ],
    "notes": "any cycles found, merge decisions, or anomalies"
  }},

  "nodes": [
    {{
      "id": "taxonomy_name (parent) or NEW_name",
      "label": "human-readable short name",
      "role": "driver | mediator | outcome | context",
      "description": "what this variable measures",
      "unit": "mm | % | categorical | etc.",
      "threshold_or_range": "specific value or null",
      "indicator_direction": "high_means_stressed | decreasing_trend_means_stressed | etc.",
      "data_source": "where to get this data",
      "cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "cluster_families_reported": ["list of all families reported across papers"],
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "seasons_reported": ["kharif | rabi | zaid | annual | not_applicable"],
      "severities_reported": ["mild | moderate | severe | not_applicable"],
      "media_reported": ["groundwater | soil | not_applicable"],
      "is_taxonomy": true,
      "in_degree": 0,
      "out_degree": 0
    }}
  ],

  "edges": [
    {{
      "edge_id": "e1",
      "from": "var_A",
      "to": "var_B",
      "mechanism": "1-2 sentences: WHY A causes a change in B",
      "direction": "increase_causes_increase | increase_causes_decrease | decrease_causes_decrease | decrease_causes_increase | categorical_determines",
      "strength": "strong | moderate | weak",
      "conditions": "when/where this link is active, or null",
      "supporting_papers": [{{"paper_id": 0, "paper_title": "string"}}],
      "confidence": "high | medium | low",
      "from_var_value_range": "merged numeric range/threshold for 'from' on this edge, or null",
      "to_var_value_range": "merged numeric range/threshold for 'to' on this edge, or null",
      "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "is_cross_stressor": true,
      "season_scope": "kharif | rabi | zaid | annual | not_applicable | mixed",
      "seasons_scope_reported": ["kharif | rabi | zaid | annual | not_applicable"],
      "severity_scope": "mild | moderate | severe | not_applicable | mixed",
      "severities_scope_reported": ["mild | moderate | severe | not_applicable"],
      "medium_scope": "groundwater | soil | not_applicable | mixed",
      "media_scope_reported": ["groundwater | soil | not_applicable"],
      "excerpt": "key sentence from paper"
    }}
  ],

  "paths": [
    {{
      "path_id": "p1",
      "name": "short descriptive name",
      "narrative": "end-to-end plain-English explanation of the full causal mechanism",
      "path_type": "linear | fan_out | fan_in | complex",
      "stressor_scope": "within_stressor | cross_stressor | mixed",
      "cluster_families_traversed": ["ordered list of cluster families along the path"],
      "root_drivers": ["var_A"],
      "terminal_outcomes": ["var_D"],
      "ordered_edges": ["e1", "e2", "e3"],
      "context_variables": ["variables that moderate any edge in this path"],
      "net_direction": "driver_increase_causes_outcome_decrease",
      "overall_strength": "strong | moderate | weak",
      "length": 3
    }}
  ],

  "adjacency": {{
    "var_A": {{
      "outgoing": ["var_B", "var_C"],
      "incoming": []
    }},
    "var_B": {{
      "outgoing": ["var_D"],
      "incoming": ["var_A"]
    }}
  }}
}}

RULES:
- Include ALL edges from the source extractions. Do not drop any.
- Do not invent edges not supported by the papers.
- Preserve cross-stressor edges. Drop them ONLY if no paper actually supports them.
- If two edges have the same from/to but different mechanisms (from different papers),
  MERGE into one edge with combined mechanism text and both papers in supporting_papers.
- Paths must trace actual edge sequences — do not skip intermediate nodes.
- A good graph from one paper has 8-17 nodes, 10-15 edges, and 5-15 paths.
- Return ONLY the JSON. No markdown, no preamble."""


# ---------------------------------------------------------------------------
# MASTER GRAPH PROMPT (visualisation-ready graph from master consolidated JSON)
# ---------------------------------------------------------------------------

MASTER_GRAPH_PROMPT = """You are given the MASTER consolidated JSON produced by the
master_cross_stressor consolidation step (the file looks like master_consolidated.json:
it already contains source_papers_profile, consolidated_variables,
consolidated_causal_chains, unified_mechanism_blocks, taxonomy_expansion_candidates,
and consolidation_summary — do NOT re-merge or re-extract anything).

Your job is to RESHAPE this consolidated content into a CLEAN, VISUALISATION-READY
KNOWLEDGE GRAPH that can be plotted directly (e.g. with networkx + matplotlib,
Cytoscape, Graphviz, or D3). The output must preserve every consolidated variable
and every consolidated causal edge — no dropping, no invention.

MASTER CONSOLIDATED INPUT:
{master_consolidated_json}

---

STEP-BY-STEP INSTRUCTIONS:

STEP 1 — BUILD NODES (one per consolidated variable):
- For every entry in consolidated_variables, emit one node.
- node.id        = variable_name (PARENT canonical name; never a season/severity/medium suffix).
- node.label     = short human-readable label derived from the variable_name and unit
                   (e.g. "Annual rainfall (mm)" for prec_annual_avg_rain).
- Carry over: role, description, unit, indicator_direction, threshold_or_range,
  per_paper_ranges, cluster_family, cluster_families_reported, mechanism_domains, seasons_reported,
  severities_reported, media_reported, confidence, paper_count, importance_rank.
- Compute in_degree / out_degree from the consolidated_causal_chains array.
- Set is_root_driver=true when in_degree=0; is_terminal_outcome=true when out_degree=0.
- Set is_taxonomy_candidate=true when the variable_name appears in
  taxonomy_expansion_candidates.
- Assign cluster_id = cluster_family. Nodes with cluster_family="mixed" or
  "unknown" get cluster_id="bridge" (these are the cross-stressor bridges).
- Assign visual hints (purely as string labels — do NOT pick exact pixel values):
  * color_hint     = cluster_family value
  * shape_hint     = "ellipse" for driver, "diamond" for mediator, "rectangle" for
                     outcome, "hexagon" for context, "doubleoctagon" for context+mixed
  * size_hint      = "large" if importance_rank in top 10 OR confidence="high",
                     "medium" if confidence="medium", "small" otherwise
  * border_hint    = "dashed" if is_taxonomy_candidate else "solid"

STEP 2 — BUILD EDGES (one per consolidated causal chain):
- For every entry in consolidated_causal_chains, emit one edge.
- edge.id        = "e1", "e2", ... in input order.
- edge.from / to = exactly the from_var / to_var (PARENT names; do not rename).
- Carry over: mechanism, direction, strength, conditions,
  from_var_value_range_merged, to_var_value_range_merged, from_cluster_family,
  to_cluster_family, mechanism_domains, is_cross_stressor, season_scope, seasons_scope_reported,
  severity_scope, severities_scope_reported, medium_scope, media_scope_reported,
  supporting_papers, confidence.
- Compute paper_count_edge = len(supporting_papers).
- Assign visual hints:
  * color_hint     = from_cluster_family if is_cross_stressor=false,
                     "cross_stressor" if is_cross_stressor=true.
  * style_hint     = "solid" if confidence="high",
                     "dashed" if confidence="medium",
                     "dotted" if confidence="low".
  * width_hint     = "thick" if paper_count_edge>=3,
                     "medium" if paper_count_edge==2,
                     "thin" if paper_count_edge==1.
  * arrow_hint     = "normal" by default; "inhibitor" (T-bar) when direction is
                     increase_causes_decrease or decrease_causes_increase.
  * tooltip        = 1-2 sentence string combining mechanism + merged value ranges
                     + supporting paper count, suitable for hover display.

STEP 3 — BUILD ADJACENCY:
- For every node, list outgoing and incoming neighbour ids.

STEP 4 — BUILD CLUSTERS (one per cluster family + a "bridge" cluster):
- One cluster per distinct cluster_family observed in nodes
  (groundwater_stress, drought, rainfed_risk, irrigation_challenges, mixed, unknown).
- Group "mixed" and "unknown" together into a single "bridge" cluster (these are the
  cross-stressor connector variables).
- For each cluster: id, label, member_node_ids, internal_edge_count,
  outgoing_cross_edge_count (edges leaving this cluster), incoming_cross_edge_count.

STEP 5 — ENUMERATE KEY PATHS FOR THE PRESENTATION:
- Reuse unified_mechanism_blocks if present: each block becomes one "named cascade".
  Preserve block name, description, stressor_scope, primary_edges, secondary_edges,
  and context_variables. List the ordered edge ids (looked up from STEP 2) that
  realise each primary chain.
- Additionally, enumerate the top 10 paths through the graph by composite score:
  composite_score = (path_length) + (count_of_high_confidence_edges * 2)
                    + (3 if path is cross_stressor else 0).
- Each path entry: path_id, name, narrative, ordered_edge_ids, ordered_node_ids,
  path_type (linear | fan_out | fan_in | complex), stressor_scope
  (within_stressor | cross_stressor | mixed), cluster_families_traversed,
  net_direction, overall_confidence, length, composite_score.

STEP 6 — TERMINAL-NODE STRESS RULES (for the downstream detection rule):
- For each is_terminal_outcome=true node, emit a stress_rule entry combining
  threshold_or_range and indicator_direction so a downstream engine can compare
  observed district/block values to paper-derived stressed ranges.
- Each rule entry: terminal_variable, indicator_direction, stressed_range_summary
  (one-line plain language), supporting_paths (path_ids ending at this terminal),
  confidence, cluster_families_implicated (union of from_cluster_family across
  the supporting paths).

STEP 7 — VISUALISATION HINTS (graph-level, not per-element):
- Suggest a layout family ("hierarchical_top_down" by default; switch to "force_directed"
  if total_edges/total_nodes > 1.5; switch to "concentric_by_cluster_family" if
  cluster count >= 4 with significant cross-cluster edges).
- Suggest a legend with stressor-family colors, edge-style meaning (confidence),
  edge-width meaning (paper_count), arrow-shape meaning (direction sign), and node-
  border meaning (taxonomy candidate vs existing).

STEP 8 — VALIDATE:
- Every variable in edges must exist in nodes.
- Every named cascade and every enumerated path must reference real edge ids.
- No new nodes/edges invented beyond what the master consolidated JSON contains.
- Counts in graph_metadata MUST match nodes / edges / paths arrays exactly.

Return this EXACT JSON structure:

{{
  "graph_metadata": {{
    "pattern": "string copied from master consolidated JSON",
    "consolidation_mode": "master_cross_stressor",
    "source_paper_count": 0,
    "total_nodes": 0,
    "total_edges": 0,
    "total_paths": 0,
    "within_stressor_edges": 0,
    "cross_stressor_edges": 0,
    "root_drivers": ["node ids with in_degree=0"],
    "terminal_outcomes": ["node ids with out_degree=0"],
    "taxonomy_candidates_in_graph": ["node ids flagged as taxonomy candidates"],
    "cluster_family_counts": {{
      "groundwater_stress": 0,
      "drought": 0,
      "rainfed_risk": 0,
      "irrigation_challenges": 0,
      "mixed": 0,
      "unknown": 0
    }}
  }},

  "nodes": [
    {{
      "id": "variable_name",
      "label": "human-readable short label",
      "role": "driver | mediator | outcome | context",
      "description": "string",
      "unit": "string",
      "indicator_direction": "string",
      "threshold_or_range": "merged envelope or null",
      "per_paper_ranges": [{{"paper_id": 0, "paper_title": "string", "range_or_threshold": "string"}}],
      "stressor_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "cluster_families_reported": ["list"],
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "seasons_reported": ["kharif | rabi | zaid | annual | not_applicable"],
      "severities_reported": ["mild | moderate | severe | not_applicable"],
      "media_reported": ["groundwater | soil | not_applicable"],
      "confidence": "high | medium | low",
      "paper_count": 0,
      "importance_rank": 0,
      "in_degree": 0,
      "out_degree": 0,
      "is_root_driver": false,
      "is_terminal_outcome": false,
      "is_taxonomy_candidate": false,
      "cluster_id": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | bridge",
      "color_hint": "string",
      "shape_hint": "string",
      "size_hint": "small | medium | large",
      "border_hint": "solid | dashed"
    }}
  ],

  "edges": [
    {{
      "edge_id": "e1",
      "from": "node_id",
      "to": "node_id",
      "mechanism": "string",
      "direction": "string",
      "strength": "string",
      "conditions": "string or null",
      "from_var_value_range_merged": "string or null",
      "to_var_value_range_merged": "string or null",
      "from_cluster_family": "string",
      "to_cluster_family": "string",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "is_cross_stressor": true,
      "season_scope": "kharif | rabi | zaid | annual | not_applicable | mixed",
      "seasons_scope_reported": ["list"],
      "severity_scope": "mild | moderate | severe | not_applicable | mixed",
      "severities_scope_reported": ["list"],
      "medium_scope": "groundwater | soil | not_applicable | mixed",
      "media_scope_reported": ["list"],
      "supporting_papers": [{{"paper_id": 0, "paper_title": "string"}}],
      "paper_count_edge": 0,
      "confidence": "high | medium | low",
      "color_hint": "string",
      "style_hint": "solid | dashed | dotted",
      "width_hint": "thin | medium | thick",
      "arrow_hint": "normal | inhibitor",
      "tooltip": "string"
    }}
  ],

  "adjacency": {{
    "node_id": {{"outgoing": ["node_id", ...], "incoming": ["node_id", ...]}}
  }},

  "clusters": [
    {{
      "id": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | bridge",
      "label": "human-readable cluster name",
      "member_node_ids": ["..."],
      "internal_edge_count": 0,
      "outgoing_cross_edge_count": 0,
      "incoming_cross_edge_count": 0
    }}
  ],

  "named_cascades": [
    {{
      "name": "string from unified_mechanism_blocks.name",
      "description": "string",
      "stressor_scope": "within_stressor | cross_stressor | mixed",
      "ordered_edge_ids": ["e1", "e2", "e3"],
      "context_node_ids": ["..."]
    }}
  ],

  "top_paths": [
    {{
      "path_id": "p1",
      "name": "short descriptive name",
      "narrative": "1-3 sentence end-to-end mechanism explanation",
      "ordered_edge_ids": ["e1", "e2"],
      "ordered_node_ids": ["A", "B", "C"],
      "path_type": "linear | fan_out | fan_in | complex",
      "stressor_scope": "within_stressor | cross_stressor | mixed",
      "cluster_families_traversed": ["ordered families along the path"],
      "net_direction": "string",
      "overall_confidence": "high | medium | low",
      "length": 0,
      "composite_score": 0.0
    }}
  ],

  "stress_rules": [
    {{
      "terminal_variable": "node_id",
      "indicator_direction": "string",
      "stressed_range_summary": "plain-language one-line rule with numbers where available",
      "supporting_paths": ["path_id", ...],
      "confidence": "high | medium | low",
      "cluster_families_implicated": ["list"]
    }}
  ],

  "visualisation_hints": {{
    "suggested_layout": "hierarchical_top_down | force_directed | concentric_by_cluster_family",
    "layout_rationale": "1 sentence: WHY this layout was chosen given node/edge density",
    "legend": {{
      "node_color_by": "cluster_family",
      "node_shape_by": "role",
      "node_size_by": "importance_rank or confidence",
      "node_border_by": "taxonomy_candidate flag",
      "edge_color_by": "cluster_family / cross_stressor",
      "edge_style_by": "confidence",
      "edge_width_by": "paper_count_edge",
      "edge_arrow_by": "direction sign"
    }},
    "cluster_family_palette_suggestion": {{
      "groundwater_stress": "blue family",
      "drought": "orange/red family",
      "rainfed_risk": "brown/yellow family",
      "irrigation_challenges": "teal/green family",
      "mixed": "purple family",
      "unknown": "grey family"
    }}
  }}
}}

HARD RULES:
- Use ONLY data already present in the master consolidated JSON. Do not invent
  variables, edges, ranges, or supporting papers.
- Preserve PARENT canonical variable names exactly. Never re-introduce season /
  severity / medium suffixes into ids.
- Cross-stressor edges MUST be retained (this is the whole point of master mode).
- Visualisation hints are SUGGESTIONS for the renderer, not commitments. They are
  expressed as string categories so the downstream Python script can map them to
  concrete colors/widths/shapes.
- Counts in graph_metadata MUST match the arrays exactly.
- Return ONLY the JSON. No markdown, no preamble."""


# ---------------------------------------------------------------------------
# CONSOLIDATION PROMPT (cross-paper merge for one pattern OR master all-stressor)
# ---------------------------------------------------------------------------

CONSOLIDATION_PROMPT = """You are merging variable and causal chain extractions from
{n_papers} research papers.



This consolidation may be either:
- per_stressor: all input extractions focus on ONE causal stressor family
  (groundwater_stress | drought | rainfed_risk | irrigation_challenges), OR
- master_cross_stressor: the input extractions span ALL stressor families and
  cross-stressor causal chains must be retained.

Below are the extractions from each paper:

{all_extractions}

---

YOUR TASK:

0. SOURCE PAPERS PROFILE (do this first):
   - For EACH input extraction, record paper_title, paper_type, and paper_type_rationale
     (copy from the JSON; if rationale missing, infer one line from methodology/summary).
   - Output these in "source_papers_profile". This supports weighting policy vs mechanism
     vs review evidence later.

1. MERGE VARIABLES:
   - Combine duplicate/near-duplicate variables. Use PARENT canonical names only
     (no season, severity, or medium suffixes). If an extraction uses a legacy
     suffixed name (e.g. kharif_cropping_area_trend, mild_weeks_trend,
     groundwater_ec, soil_salinity), normalize it now by mapping the suffix back to
     the parent name plus the appropriate qualifier (season, severity, and/or
     medium).
   - Keep the clearest description and all data sources
   - Add "confidence": "high" if 3+ papers, "medium" if 2, "low" if 1
   - Add "paper_count": how many papers mention this variable
   - MERGE NUMERIC RANGES across papers for the same variable into "threshold_or_range":
     * Same unit and comparable magnitudes: report an ENVELOPE (min lower bound, max upper
       bound) and note "merged across N papers" in plain language inside the string.
     * Different units, regions, or incomparable metrics: keep a semicolon-separated list
       of paper-specific ranges (cite paper title in each fragment if helpful).
   - Add "per_paper_ranges": [{{"paper_title": "...", "range_or_threshold": "..."}}]
     for every paper that stated a number (empty array if none).
   - Carry cluster_family. If papers disagree, set cluster_family="mixed" and list
     all reported families in cluster_families_reported.
   - Merge mechanism_domains as a deduplicated union across papers.
   - MERGE QUALIFIERS:
     * `seasons_reported` = every `season` value reported across papers for the same
       parent variable (subset of kharif / rabi / zaid / annual / not_applicable).
     * `severities_reported` = every `severity` value reported across papers for the
       same parent variable (subset of mild / moderate / severe / not_applicable).
     * `media_reported` = every `medium` value reported across papers for the same
       parent variable (subset of groundwater / soil / not_applicable).
     Preserve per-paper qualifier attribution inside `per_paper_qualifiers` so
     downstream analysis can still split by season, severity, and/or medium.

2. MERGE CAUSAL CHAINS:
   - Same edge from multiple papers -> higher confidence
   - Combine mechanism descriptions (keep the most detailed)
   - Track which papers support each edge
   - For each consolidated edge, MERGE from_var_value_range and to_var_value_range from
     the source causal_chains the same way as variables (envelope if comparable, else list).
   - Carry from_cluster_family, to_cluster_family, and is_cross_stressor.
   - Merge mechanism_domains on edges as deduplicated union.
   - KEEP cross-stressor edges. Do NOT discard them because endpoints belong to different
     stressor families. This is the point of the relaxed pipeline.
   - MERGE QUALIFIERS on edges:
     * Seasons: if papers report the same A->B link for different seasons, store every
       reported season in `seasons_scope_reported` and set `season_scope` to the
       single dominant season, or "mixed" when genuinely season-agnostic.
     * Severities: if papers report the same A->B link for different severity levels,
       store every reported severity in `severities_scope_reported` and set
       `severity_scope` to the single dominant severity, or "mixed" when genuinely
       severity-agnostic.
     * Media: if papers report the same A->B link for different media (groundwater
       vs soil), store every reported medium in `media_scope_reported` and set
       `medium_scope` to the single dominant medium, or "mixed" when genuinely
       medium-agnostic.

3. BUILD UNIFIED MECHANISM BLOCKS:
   - Construct a COMPLETE causal model from drivers -> mediators -> outcomes.
   - Identify the primary mechanism pathway vs. secondary pathways.
   - Note where papers AGREE vs. DISAGREE on mechanisms.
   - For master_cross_stressor consolidation, create at least one block per major
     cross-stressor cascade observed (e.g. rainfall_deficit -> groundwater_decline ->
     irrigation_failure -> rainfed_risk).
   - EVERY edge in primary_edges and secondary_edges MUST include:
     from_var_value_range_merged and to_var_value_range_merged (merged across all papers
     that contributed that edge, using the same merge rules as in step 2; null only if
     no paper gave a numeric range for that endpoint on that link).
   - EVERY edge in primary_edges and secondary_edges MUST also include
     from_cluster_family, to_cluster_family, mechanism_domains, and is_cross_stressor.

4. IDENTIFY GAPS:
   - Which parts of the causal chain have weak evidence (only 1 paper)?
   - Are there missing links that would complete a chain?
   - For cross-stressor chains, flag missing bridge variables (e.g. no paper explicitly
     connects groundwater decline to rainfed crop failure via irrigation dependence).

5. NORMALIZE NEW_ VARIABLE NAMES (DEDUP PASSES):
   - Run explicit dedup passes in order:
     (a) exact canonical match,
     (b) alias-table match,
     (c) near-synonym fallback (suggest merge; do not destructive auto-merge at low confidence).
   - Before merging, scan ALL NEW_ variables across all papers.
   - If two or more papers use different NEW_ names for the same concept
     (e.g. NEW_recharge_rate vs NEW_gw_recharge vs NEW_aquifer_recharge),
     unify them under ONE canonical name.
   - Record every merge in "new_variable_name_merges" with the original names,
     the chosen canonical name, and the reason.
   - Then use ONLY the canonical names in all subsequent output fields.

6. IDENTIFY TAXONOMY EXPANSION CANDIDATES:
   - From all NEW_ variables (after name normalization), identify those that
     should be considered for addition to the universal indicator taxonomy.
   - A variable qualifies if it meets ANY of:
     (a) Appears in 2+ papers for this pattern, OR
     (b) Is rated "candidate_for_taxonomy" in any paper's important_variables
         with evidence_strength "strong", OR
     (c) Fills a critical gap in the causal chain (connects otherwise
         disconnected drivers and outcomes), including cross-stressor bridges.
   - AND it must be:
     * Quantifiable and measurable
     * Obtainable from Indian public data sources (remote sensing, census,
       government databases, weather stations)
     * Not redundant with an existing taxonomy variable
   - For each candidate, propose a clean taxonomy name (without NEW_ prefix),
     explain why it should be added, and rate its priority.

7. COUNT CROSS-STRESSOR EVIDENCE:
   - Compute within_stressor_edge_count and cross_stressor_edge_count across the
     merged edges and report them in "consolidation_summary".
   - List the top 3-5 cross-stressor cascades by confidence.

Return JSON:
{{
  "pattern": " Agriculture -> Water Scarcity -> Groundwater Stress",
  "consolidation_mode": "per_stressor | master_cross_stressor",

  "source_papers_profile": [
    {{
      "paper_id": 0,
      "paper_title": "string",
      "paper_type": "mechanism | case_study | technical | policy | review",
      "paper_type_rationale": "1-2 sentences copied or inferred from extraction"
    }}
  ],

  "consolidated_variables": [
    {{
      "variable_name": "taxonomy (PARENT name) or NEW_ name",
      "description": "best combined description",
      "unit": "string",
      "role": "driver | mediator | outcome | context",
      "data_sources": [{"paper_id": 0, "paper_title": "string", "data_source": "source string"}],
      "threshold_or_range": "MERGED numeric envelope or combined paper-specific ranges; null if no numbers anywhere",
      "per_paper_ranges": [{{"paper_id": 0, "paper_title": "string", "range_or_threshold": "string"}}],
      "indicator_direction": "string",
      "relevance": "direct | proxy | contextual",
      "cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "cluster_families_reported": ["list of all reported families"],
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "seasons_reported": ["kharif | rabi | zaid | annual | not_applicable"],
      "severities_reported": ["mild | moderate | severe | not_applicable"],
      "media_reported": ["groundwater | soil | not_applicable"],
      "per_paper_qualifiers": [{{"paper_id": 0, "paper_title": "string", "season": "kharif | rabi | zaid | annual | not_applicable", "severity": "mild | moderate | severe | not_applicable", "medium": "groundwater | soil | not_applicable"}}],
      "confidence": "high | medium | low",
      "paper_count": 0,
      "importance_rank": 0
    }}
  ],

  "consolidated_causal_chains": [
    {{
      "from_var": "string (PARENT name; no qualifier suffix)",
      "to_var": "string (PARENT name; no qualifier suffix)",
      "mechanism": "best combined mechanism explanation",
      "direction": "string",
      "strength": "strong | moderate | weak",
      "conditions": "string or null",
      "from_var_value_range_merged": "merged across supporting papers, or null",
      "from_var_value_ranges_by_paper": [{{"paper_id": 0, "paper_title": "string", "value_range": "string"}}],
      "to_var_value_range_merged": "merged across supporting papers, or null",
      "to_var_value_ranges_by_paper": [{{"paper_id": 0, "paper_title": "string", "value_range": "string"}}],
      "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
      "is_cross_stressor": true,
      "season_scope": "kharif | rabi | zaid | annual | not_applicable | mixed",
      "seasons_scope_reported": ["kharif | rabi | zaid | annual | not_applicable"],
      "severity_scope": "mild | moderate | severe | not_applicable | mixed",
      "severities_scope_reported": ["mild | moderate | severe | not_applicable"],
      "medium_scope": "groundwater | soil | not_applicable | mixed",
      "media_scope_reported": ["groundwater | soil | not_applicable"],
      "supporting_papers": [{{"paper_id": 0, "paper_title": "string"}}],
      "confidence": "high | medium | low"
    }}
  ],

  "unified_mechanism_blocks": [
    {{
      "name": "string",
      "description": "complete narrative combining all papers",
      "stressor_scope": "within_stressor | cross_stressor | mixed",
      "primary_edges": [
        {{
          "from_var": "string (PARENT name; no qualifier suffix)",
          "to_var": "string (PARENT name; no qualifier suffix)",
          "mechanism": "1 sentence: WHY from_var causes a change in to_var",
          "direction": "increase_causes_increase | increase_causes_decrease | decrease_causes_increase | decrease_causes_decrease | categorical_determines",
          "conditions": "when/where this link is active, or null",
          "from_var_value_range_merged": "merged numeric range for from_var on this edge, or null",
          "to_var_value_range_merged": "merged numeric range for to_var on this edge, or null",
          "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
          "is_cross_stressor": true,
          "season_scope": "kharif | rabi | zaid | annual | not_applicable | mixed",
          "severity_scope": "mild | moderate | severe | not_applicable | mixed",
          "medium_scope": "groundwater | soil | not_applicable | mixed"
        }}
      ],
      "secondary_edges": [
        {{
          "from_var": "string (PARENT name; no qualifier suffix)",
          "to_var": "string (PARENT name; no qualifier suffix)",
          "mechanism": "string",
          "direction": "string",
          "conditions": "string or null",
          "from_var_value_range_merged": "merged numeric range for from_var, or null",
          "to_var_value_range_merged": "merged numeric range for to_var, or null",
          "from_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "to_cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
          "mechanism_domains": ["dynamic_domain_1", "dynamic_domain_2"],
          "is_cross_stressor": true,
          "season_scope": "kharif | rabi | zaid | annual | not_applicable | mixed",
          "severity_scope": "mild | moderate | severe | not_applicable | mixed",
          "medium_scope": "groundwater | soil | not_applicable | mixed"
        }}
      ],
      "context_variables": ["moderating variables"],
      "evidence_strength": "strong | moderate | weak"
    }}
  ],

  "stressor_detection_rules": [
    {{
      "rule": "natural language rule for detecting the stressor; where possible reference consolidated threshold_or_range / merged edge ranges so rules can later be compared to observed district/block values",
      "variables_needed": ["list of variable names"],
      "thresholds": {{"var_name": "threshold_value"}},
      "stressor_family_targeted": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed",
      "activation_score_formula": "threshold_breach + scope_match + evidence_confidence + upstream_path_support",
      "activation_bands": {{
        "active_strong": "score >= 0.75",
        "active_moderate": "0.50 <= score < 0.75",
        "active_weak": "0.30 <= score < 0.50",
        "inactive": "score < 0.30"
      }},
      "required_query_outputs": ["activation_band", "activation_score", "top_trigger_nodes", "scope_used", "explanation_paths"],
      "confidence": "high | medium | low"
    }}
  ],

  "evidence_gaps": [
    "Causal links or variables with weak evidence"
  ],

  "new_variable_name_merges": [
    {{
      "original_names": ["NEW_name_from_paper1", "NEW_name_from_paper2"],
      "canonical_name": "NEW_unified_name",
      "reason": "why these are the same concept"
    }}
  ],

  "taxonomy_expansion_candidates": [
    {{
      "variable_name": "NEW_canonical_name (after normalization)",
      "proposed_taxonomy_name": "clean name without NEW_ prefix, matching taxonomy naming style",
      "description": "what it measures and why it matters for this stressor",
      "unit": "mm | % | ha | index | etc.",
      "role": "driver | mediator | outcome | context",
      "cluster_family": "groundwater_stress | drought | rainfed_risk | irrigation_challenges | mixed | unknown",
      "paper_count": 0,
      "significance_summary": "why this variable should be added to the universal taxonomy — cite cross-paper evidence",
      "data_availability": "specific Indian public data source where this can be obtained",
      "fills_gap": "what gap in the existing taxonomy this variable fills (mention if it bridges stressor families)",
      "priority": "high | medium"
    }}
  ],

  "consolidation_summary": {{
    "within_stressor_edge_count": 0,
    "cross_stressor_edge_count": 0,
    "top_cross_stressor_cascades": [
      {{
        "cascade_name": "short name",
        "from_stressor_family": "string",
        "to_stressor_family": "string",
        "example_path": ["var1", "var2", "var3"],
        "confidence": "high | medium | low"
      }}
    ]
  }},

  "total_unique_variables": 0,
  "total_causal_edges": 0,
  "notes": "Patterns or insights from consolidation, including whether this is a per_stressor or master_cross_stressor batch"
}}

DOWNSTREAM USE (do not implement logic here — structure data only):
- Merged ranges on variables and on unified_mechanism_blocks edges exist so that later,
  when a causal CHAIN is instantiated with observed values, TERMINAL nodes can be checked
  against paper-derived stressed ranges. Preserve numeric detail; do not round away bounds.
- Cross-stressor edges power the master knowledge graph that detects when one stressor
  (e.g. drought) propagates into another (e.g. groundwater stress -> irrigation failure).

TAXONOMY EXPANSION PRIORITY GUIDE:
- "high": variable appears in 4+ papers, OR is a critical mechanism link (connects
  otherwise disconnected drivers and outcomes), OR bridges two stressor families, OR
  has strong statistical evidence from multiple studies.
- "medium": variable appears in 2 papers, OR is important but not critical (the
  causal chain can be told without it, but it adds explanatory power).

Return ONLY the JSON.save it to out_5 folder"""
