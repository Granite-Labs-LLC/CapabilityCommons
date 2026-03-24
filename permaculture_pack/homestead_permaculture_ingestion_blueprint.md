# Homestead & Permaculture Ingestion Blueprint for Capability Commons

This document translates the uploaded permaculture and natural farming source materials into a seed-pack and knowledge-graph plan for the current Capability Commons architecture.

## 1. Purpose

Build a first-class public corpus for off-grid, homestead, and permaculture knowledge that can be retrieved through the chat interface using `/v1/search`, `/v1/retrieve/evidence_pack`, and the public graph/object APIs already present in the architecture.

## 2. Source-to-Model Strategy

- **Mollison / Holmgren** contribute the core permaculture definition, design grammar, zone/sector thinking, site design, water, animals, and cultivated ecosystem framing.

- **IDEP / Permatil Reference Book** contributes practical module structure for houses, water, waste, soil, seed saving, gardens, farming, forests, bamboo, pest management, animal systems, aquaculture, and appropriate technology.

- **IDEP / Permatil Facilitator’s Handbook** contributes teach-forward structure: lesson plans, hands-on demonstrations, design projects, pre-course research, post-course follow-up, and workshop logistics.

- **Fukuoka** contributes the natural farming counterweight: no tillage, no fertilizer, no pesticides, no weeding, no pruning, direct seeding, straw mulch, clover/green manure, seed balls, and a strong anti-overprocessing philosophy.

## 3. Canonical Design Thesis

The corpus should treat permaculture not as a loose collection of gardening tips but as a **design system for durable self-reliance**. Every important topic should map:

1. concept → meaning, principles, context

2. skill → observable action, tools, success criteria

3. project → a useful build / design / implementation artifact

4. module → how to teach it

5. teach-forward asset → how to pass it on


Use the architecture’s doctrine directly:

- open by default
- practical before ornamental
- layered for beginners
- locally adaptable
- project-based
- teach-forward

## 4. What to Add to the Existing Capability Domains

Add a new **Homestead / Permaculture corpus ring** using the current domain model but expanding beyond the present 7 seeded domains.


Recommended domain set for seed pack v1:

- `foundations`

- `water`

- `soil`

- `gardens`

- `farming`

- `forests`

- `ecology`

- `animals`

- `aquaculture`

- `household`

- `appropriate_technology`


## 5. Knowledge Object Taxonomy

Use the architecture’s current object types with this preferred distribution:

- `concept_note`: ethics, principles, natural patterns, nutrient cycles, healthy soil, integrated systems

- `skill_guide`: observation walk, contour marking, composting, mulching, seed saving, propagation, pest observation, animal care, water cleaning

- `project_blueprint`: swale build, nursery, fishpond, compost toilet, garden system, animal rotation, windbreak, reforestation

- `reference_sheet`: companion planting charts, bamboo uses, appropriate technology comparisons, seasonal crop calendars

- `learning_path`: beginner off-grid starter path, soil-first path, water-first path, orchard path, rice-and-grain path, animal integration path

- `module`: course units derived from the workshop structure

- `assessment`: observation-based, artifact-based, teach-forward based

- future expansion: `worksheet`, `teach_forward_packet`, `field_report`, `local_adaptation`, `expert_review`, `correction`, `safety_notice`, `community_map`, `resource_directory`

## 6. Edge Taxonomy for This Corpus

Use the current 25 edge types. Recommended usage:


### Learning-path edges

- `prerequisite_for`: soil before compost; contour marking before swales; seed saving before community seed bank

- `next_step_for`: healthy soil → garden design → food preservation

- `builds_on`: intercropping builds on diversity; animal rotation builds on fencing + forage + water

- `contains`: learning paths contain modules; modules contain concept / skill / project nodes


### Content / evidence edges

- `supported_by`: swales supported by erosion-control and water-storage references

- `derived_from`: workshop lesson derived from canonical skill guide

- `summarizes`: reference sheet summarizes a longer module or guide

- `quotes`: only for short fair-use excerpts or public-domain sources

- `validated_by`: attach expert reviews, field reports, or replicated examples


### Localization edges

- `adapted_for`: cold-climate mulch variant; humid-tropics nursery variant; dryland seed-ball variant

- `applies_in`: climate zone, rainfall pattern, slope, grid status, settlement type

- `translated_from`: translated teaching materials

- `forked_from`: region-specific forks of canonical guides


### Constraints / safety edges

- `requires_tool`: A-frame, shovel, pruners, sieve, watering can, grafting knife

- `requires_material`: straw, seed, compost inputs, bamboo, drums, pond liner (if used)

- `has_failure_mode`: pond leakage, water contamination, nitrogen tie-up, overgrazing, seed contamination

- `mitigated_by`: mulch, windbreak, predator habitat, contouring, shade, quarantine, drainage

- `unsafe_without`: clean water handling, manure aging, safe compost toilet placement, pond-bank stability

- `bounded_by`: local law, invasive species risk, rainfall minimums, freeze risk, animal pressure


### Versioning / truth maintenance edges

- `corrected_by`, `contradicted_by`, `deprecated_by`, `supersedes`

These are important because practical homestead advice varies by climate, disease pressure, regulation, and local material availability.

## 7. Facet Schema

The current architecture already supports `domain`, `audience`, `housing_type`, `settlement_type`, `budget_profile`, `climate_zone`, `utility_profile`, `locale`, `language`, and `delivery_mode`.


### Use current facets immediately

- `domain`: water / soil / gardens / animals / etc.

- `audience`: beginner / intermediate / trainer / community organizer

- `housing_type`: apartment / village house / rural house / off-grid cabin / farmstead

- `settlement_type`: urban / peri_urban / rural / remote / village

- `budget_profile`: low / medium / high / scavenged_local_materials

- `climate_zone`: local taxonomy or USDA/Koppen-compatible values

- `utility_profile`: grid / off_grid / intermittent_grid / hand_tool_only / low_water

- `locale`: region / country / watershed / island / language region

- `delivery_mode`: self-study / workshop / field-demo / train-the-trainer


### Encode as entities or structured data in v1, then promote later if needed

- soil_type
- rainfall_profile
- slope_class
- water_access
- water_quality
- season
- crop_type
- livestock_type
- pest_pressure
- wildfire_risk
- flood_risk
- drought_risk
- labor_profile
- property_scale

## 8. Seed Pack Layout

Recommended new pack:

```text
homestead_permaculture_seed_pack_v1/
├── canonical/
│   ├── nodes/
│   │   ├── concept_note/
│   │   ├── skill_guide/
│   │   ├── project_blueprint/
│   │   ├── reference_sheet/
│   │   └── learning_path/
│   ├── facets/
│   │   ├── domains.csv
│   │   ├── audiences.csv
│   │   ├── climate_zones.csv
│   │   ├── settlement_types.csv
│   │   └── budget_profiles.csv
│   └── entities/
│       ├── tools.csv
│       ├── materials.csv
│       ├── crops.csv
│       ├── livestock.csv
│       ├── risks.csv
│       └── locales.csv
├── imports/
│   ├── edges.csv
│   ├── object_facets.csv
│   ├── object_entities.csv
│   ├── evidence_sources.csv
│   └── evidence_spans.csv
├── curriculum/
│   ├── modules/
│   ├── assessments/
│   └── learning_paths/
├── workshop/
│   ├── facilitator_guides/
│   ├── worksheets/
│   └── teach_forward_packets/
└── README.md
```

## 9. Seeding Order

Use a 4-pass seed strategy instead of a single dump:

1. **Pass A — Canonical concepts and skills**
   - 100 candidate nodes in this document
   - attach domain, audience, climate, budget, utility facets

2. **Pass B — Projects and learning paths**
   - swales, pond, nursery, garden, compost toilet, windbreak, animal rotation, seed bank

3. **Pass C — Curriculum and teach-forward**
   - workshop modules, assessments, reference sheets, field demos

4. **Pass D — Evidence and localization**
   - evidence sources, field reports, local adaptations, corrections, safety notices

## 10. Ingestion Workflow

### A. Canonical extraction

- break each PDF into topic chunks
- classify each chunk as concept / skill / project / module / reference
- draft YAML nodes with structured fields
- route to editorial review before publication

### B. Entity extraction

Extract and normalize:
- tools
- materials
- crops
- trees
- legumes
- livestock
- pests / predators
- risks / hazards
- climates / locales

### C. Edge generation

Generate obvious edges automatically:
- section hierarchy → `contains`
- concept dependency → `prerequisite_for`
- tools and materials → `requires_tool`, `requires_material`
- workshop exercise references → `derived_from`
- cited support material → `supported_by`

### D. Human review

Review for:
- climate specificity
- safety boundaries
- legal or code issues
- invasive species risk
- water contamination / sanitation concerns
- whether the node is actually actionable

## 11. Retrieval Behavior to Optimize For

The corpus should be shaped for the existing intent-aware retrieval planner:

- `how_to`: compost heap, swale build, clean water, seed saving

- `learn_path`: beginner homestead starter sequence

- `localize`: cold climate, dryland, humid tropics, off-grid, low-budget

- `debug_failure`: why compost stinks, why seedlings damp-off, why ducks muddy the garden

- `teach_forward`: turn garden, soil, or water topics into mini-lessons

- `what_changed`: corrected advice or improved local variant

- `safety_check`: manure handling, drinking water, compost toilet siting, pond safety

## 12. Review Workflow for Practical Knowledge

For each node, require:

- plain-language summary
- prerequisites
- tools
- materials
- steps
- success criteria
- failure modes
- safety boundary
- adaptation notes
- evidence source(s)


Publish status progression:

`draft → reviewed → verified → published`


Use `field_report`, `local_adaptation`, and `correction` objects as soon as local implementations begin.

## 13. Sample Canonical Node (YAML)

```yaml
id: water.construct-swales
type: project_blueprint
domain: water
title: Design and construct productive swales
summary_short: Use contour-based earthworks to slow water, reduce erosion, and support tree crops or mixed planting.
plain_language: A swale is a level ditch-and-berm system that helps rain soak into the ground instead of rushing away.
structured_data:
  goal: Store water in the ground and reduce runoff on sloped land
  deliverables:
    - contour map
    - marked swale line
    - completed swale section
    - planting plan for berm and downslope area
  acceptance_criteria:
    - contour marked accurately
    - overflow planned safely
    - erosion points stabilized
    - species chosen for local rainfall and slope
  time_box_hours: 6
  team_size: 3
  budget_notes: Can be built with hand tools on small sites
facets:
  domain: [water]
  audience: [beginner, intermediate]
  climate_zone: [temperate, tropical, dryland]
  settlement_type: [rural, remote, village]
  utility_profile: [off_grid, low_water]
entities:
  tools: [a_frame, shovel, hoe, rake]
  materials: [stakes, twine, mulch, tree_seedlings]
  risks: [erosion, bank_failure, poor_overflow_design]
```

## 14. Example Edges (CSV)

```csv
src_id,edge_type,dst_id
permaculture.methods-of-design,prerequisite_for,water.mark-contours-a-frame
water.mark-contours-a-frame,prerequisite_for,water.construct-swales
soil.mulch-basics,supported_by,water.construct-swales
forest.start-reforestation,builds_on,water.construct-swales
ipm.healthy-soil-reduces-pests,builds_on,soil.healthy-living-soil
gardens.design-home-garden,requires_material,soil.compost-quick-heap
animals.ducks-needs-products,alternative_to,animals.chickens-needs-products
aquaculture.integrate-with-chickens-pigs-rice-swales,builds_on,water.pond-basics
tech.clay-stoves-and-ovens,next_step_for,tech.solar-cooker-and-drier
```

## 15. Ten Recommended Learning Paths

- Beginner Off-Grid Starter

- Soil First

- Water First

- Kitchen Garden to Pantry

- Seed Sovereignty Starter

- Tree Crops & Reforestation

- Field Cropping & Rice

- Integrated Pest Management

- Homestead Animals Starter

- Pond & Aquaculture Integration

## 16. First 100 Candidate Nodes

See the companion CSV: `homestead_permaculture_first_100_nodes.csv`.


### Recommended first 25 to seed immediately

- `permaculture.definition-permanent-agriculture-culture` — Permaculture as permanent agriculture and permanent culture

- `permaculture.ethics-care-earth-people-future` — Permaculture ethics: care for earth, people, future

- `permaculture.design-principles-overview` — Permaculture design principles overview

- `permaculture.patterns-in-nature` — Patterns in nature as a design guide

- `permaculture.methods-of-design` — Use maps, observation, zones, sectors, and element analysis

- `permaculture.zones-and-sectors` — Zones and sectors for site planning

- `permaculture.observation-walk` — Run a site observation and data collection walk

- `permaculture.element-analysis` — Perform element analysis for site components

- `permaculture.microclimate-reading` — Read microclimates, slope, wind, and water flow

- `permaculture.multiple-functions-redundancy` — Multiple functions per element and redundancy per function

- `permaculture.relative-location` — Relative location and functional placement

- `water.collect-rainwater` — Collect rainwater from roofs and simple catchments

- `water.safe-storage` — Store drinking water safely

- `water.clean-drinking-water` — Clean and filter drinking water

- `water.reduce-mosquito-breeding` — Reduce stagnant water and mosquito breeding

- `water.greywater-basic-treatment` — Build a simple biological filter for wastewater

- `water.swales-introduction` — Swales as water storage and erosion control

- `water.mark-contours-a-frame` — Use an A-frame to mark contour lines

- `water.construct-swales` — Design and construct productive swales

- `water.pond-basics` — Design a pond for storage, habitat, and integrated production

- `soil.healthy-living-soil` — What healthy living soil is

- `soil.soil-testing-simple` — Run simple soil tests in the field

- `soil.soil-ph-and-balance` — Identify and balance soil pH

- `soil.nutrient-cycles` — Nutrient cycles in living soil

- `soil.compost-quick-heap` — Make a quick compost heap

## 17. Implementation Recommendation

Start with **concept_note + skill_guide + project_blueprint + reference_sheet** only. Add `module`, `assessment`, and `learning_path` in the second pass. Hold `field_report`, `local_adaptation`, and `correction` in reserve until the first local cohort or pilot site produces grounded feedback.

## 18. Why This Fits the Current Architecture

This blueprint matches the current system because:

- it uses the existing public retrieval surface
- it uses the existing object / edge / evidence / review model
- it respects the current doctrine of practical, locally adaptable, teach-forward competence
- it extends the current seed-pack pattern instead of fighting it
- it gives the AI tutor richer concept, skill, project, and localization data to retrieve

## 19. Next Build Artifacts

Highest-value follow-on artifacts:

1. YAML generation templates for each object type
2. `edges.csv` starter set for the first 100 nodes
3. `learning_paths.csv` for the ten paths above
4. a trainer-facing module pack derived from the Facilitator’s Handbook structure
5. a small `field_report` submission schema for local implementations
