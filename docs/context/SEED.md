Below is a v1 blueprint for a **Capability Commons**: one system that works as a public campaign, a graph knowledge base, and a 12‑week syllabus.

The unit of value is the **reproducible capability**. Every node in the system should do one of three things:

* explain something people need to understand
* train something people need to be able to do
* produce something people can keep, use, and teach forward

A good operating rule is:

> No module is complete until it creates a durable artifact, an observable skill, and a teach-forward action.

## Program operating model

Use one canonical source of truth and publish many outputs from it.

* **Canonical source**: Markdown files with YAML front matter
* **Machine layer**: JSONL for nodes, CSV for edges
* **Public layer**: website, printable PDFs, one-page reference sheets, workshop packets
* **Assessment**: artifact + demonstration + teach-forward, not abstract testing
* **Barrier-lowering rule**: every public module must include plain language, low-cost path, renter/homeowner or urban/rural variants, and offline-printable materials

---

## 1) Exact ontology / schema

### 1.1 Graph model

Use a **property graph + content repo hybrid**.

* The repo stores canonical content files.
* The graph stores relationships, sequencing, and retrieval logic.
* The site renders beginner-friendly pages from the same source files.

Suggested repo layout:

```text
/domains/
/nodes/concepts/
/nodes/skills/
/nodes/projects/
/modules/
/assessments/
/resources/
/exports/nodes.jsonl
/exports/edges.csv
```

### 1.2 Core object types

| Type         | Purpose                                     | Required extension fields                                                                                       |
| ------------ | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `domain`     | top-level capability area                   | `outcome_statement`, `parent_domain?`                                                                           |
| `concept`    | explains a principle or model               | `definition`, `key_questions`, `misconceptions`, `formulas_or_rules`, `units?`                                  |
| `skill`      | observable action a learner can perform     | `performance_statement`, `inputs`, `tools`, `materials`, `success_criteria`, `failure_modes`, `safety_boundary` |
| `project`    | applied task that creates a useful artifact | `goal`, `deliverables`, `acceptance_criteria`, `time_box_hours`, `budget_band`, `team_size`                     |
| `module`     | one teachable unit, usually one week        | `week`, `node_refs`, `learning_objectives`, `lab`, `field_task`, `teach_forward_task`, `assessment_ref`         |
| `assessment` | checks competence                           | `assessment_type`, `rubric`, `passing_threshold`, `evidence_required`                                           |
| `resource`   | source material or reference                | `format`, `origin`, `trust_tier`, `license`, `link_or_file`                                                     |
| `risk`       | danger, constraint, or failure pattern      | `trigger`, `consequence`, `mitigation`, `stop_condition`                                                        |

For v1, keep **tools** and **materials** inside `skill` and `project` fields. Promote them to first-class node types only when they become cross-cutting enough to justify it.

### 1.3 Core node schema

```yaml
NodeCore:
  id: string                         # e.g. power.runtime-calculation
  type: enum[
    domain, concept, skill, project, module,
    assessment, resource, risk
  ]
  title: string
  summary: string                    # 1-3 sentences
  plain_language: string             # jargon-free explanation
  domains: [string]                  # e.g. [power]
  stage: enum[
    foundation, household, productive, community, advanced
  ]
  difficulty: integer                # 1-5
  estimated_hours: number
  cost_band: enum[free, low, medium, high]
  risk_band: enum[low, moderate, high]
  contexts: [string]                 # e.g. renter, homeowner, urban, rural, off_grid, low_budget
  tags: [string]

  requires:
    - mode: enum[all_of, any_of, n_of]
      ids: [node_id]
      n: integer|null

  outputs: [string]                  # artifact names or IDs
  lifecycle_state: enum[draft, reviewed, verified, deprecated]
  evidence_level: enum[compiled, reviewed, field_tested, replicated]
  source_refs: [resource_id]
  version: string
  updated_at: YYYY-MM-DD
```

### 1.4 Type-specific extensions

```yaml
ConceptFields:
  definition: string
  key_questions: [string]
  misconceptions: [string]
  formulas_or_rules: [string]
  units: [string]

SkillFields:
  performance_statement: string
  inputs: [string]
  tools: [string]
  materials: [string]
  steps_summary: [string]
  success_criteria: [string]
  failure_modes: [string]
  safety_boundary: string

ProjectFields:
  goal: string
  deliverables: [string]
  acceptance_criteria: [string]
  time_box_hours: number
  budget_band: enum[free, low, medium, high]
  team_size: integer

ModuleFields:
  week: integer
  node_refs: [node_id]
  learning_objectives: [string]
  seminar_outline: [string]
  lab: string
  field_task: string
  teach_forward_task: string
  deliverable_refs: [string]
  assessment_ref: assessment_id

AssessmentFields:
  assessment_type: enum[quiz, checklist, demo, portfolio_review]
  rubric: [string]
  passing_threshold: string
  evidence_required: [string]

ResourceFields:
  format: enum[text, video, audio, worksheet, checklist, diagram, dataset]
  origin: string
  trust_tier: enum[primary, secondary, field_note]
  license: string
  link_or_file: string

RiskFields:
  trigger: string
  consequence: string
  mitigation: [string]
  stop_condition: string
```

### 1.5 Edge vocabulary

Store edges in CSV with columns:

```text
source,type,target,note,condition
```

Use this minimal edge vocabulary:

| Edge            | Meaning                                 | Example                                                                 |
| --------------- | --------------------------------------- | ----------------------------------------------------------------------- |
| `BELONGS_TO`    | node sits inside a domain               | `water.safe-storage -> water`                                           |
| `REQUIRES`      | source depends on target                | `power.runtime-calculation REQUIRES power.load-audit`                   |
| `ENABLES`       | source unlocks downstream work          | `foundation.systems-mapping ENABLES power.load-audit`                   |
| `MITIGATES`     | source reduces a risk or vulnerability  | `shelter.weatherization-audit MITIGATES shelter heat-loss`              |
| `ASSESSED_BY`   | node is measured by an assessment       | `water.basic-testing ASSESSED_BY assessment.water.01`                   |
| `DOCUMENTED_BY` | node supported by one or more resources | `food.safe-preservation-basics DOCUMENTED_BY resource.food.03`          |
| `TAUGHT_IN`     | node appears in a module                | `power.circuit-basics TAUGHT_IN module.09`                              |
| `NEXT`          | recommended next step for navigation    | `water.household-water-plan NEXT food.pantry-design`                    |
| `VARIANT_OF`    | local or contextual variation           | `power.backup-power-plan.low-budget VARIANT_OF power.backup-power-plan` |

For v1, only `REQUIRES`, `TAUGHT_IN`, and `DOCUMENTED_BY` are mandatory. The others can be derived or added later.

### 1.6 Validation rules

These rules keep the system useful to non-experts.

1. Every node must have a `plain_language` field.
2. Every skill must have at least one `success_criteria` entry and one `failure_modes` entry.
3. Every project must produce at least one concrete artifact.
4. Every module must reference 2–4 core nodes and end with a teach-forward task.
5. Every public module must contain:

   * low-cost option
   * renter/homeowner or urban/rural adaptation
   * printable one-page reference
   * plain-language glossary
6. Nothing reaches `verified` without either expert review or field-tested evidence.
7. No capability is considered complete until a learner can explain it to another person in simple language.

---

## 2) Starter 25-node knowledge graph

This starter graph is intentionally small, practical, and public-facing.

### Foundation

| ID                                          | Type    | Purpose                                                                                  | Requires                                                                                            | Primary artifact                     |
| ------------------------------------------- | ------- | ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `foundation.verify-and-cite`                | skill   | evaluate claims, sources, dates, and evidence                                            | —                                                                                                   | claim-check worksheet                |
| `foundation.measurement-and-units`          | concept | understand units, conversions, estimation, tolerances                                    | —                                                                                                   | units cheat sheet                    |
| `foundation.systems-mapping`                | skill   | map inputs, outputs, dependencies, and failure points                                    | —                                                                                                   | household systems map                |
| `foundation.ai-grounded-research`           | skill   | use AI to summarize, compare, localize, and cite rather than hallucinate                 | `foundation.verify-and-cite`                                                                        | prompt pack + source comparison note |
| `foundation.household-resilience-inventory` | project | create a baseline inventory of needs, dependencies, tools, contacts, and vulnerabilities | `foundation.measurement-and-units`, `foundation.systems-mapping`, `foundation.ai-grounded-research` | household inventory sheet            |

### Water

| ID                           | Type    | Purpose                                                       | Requires                                                                                                              | Primary artifact          |
| ---------------------------- | ------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `water.safe-storage`         | skill   | store potable water in usable quantities and intervals        | `foundation.measurement-and-units`                                                                                    | storage table             |
| `water.treatment-selection`  | concept | understand treatment methods and when each applies            | `foundation.verify-and-cite`, `foundation.ai-grounded-research`                                                       | treatment decision matrix |
| `water.basic-testing`        | skill   | inspect and test source or treated water at a household level | `foundation.verify-and-cite`, `water.treatment-selection`                                                             | water test log            |
| `water.household-water-plan` | project | produce a 72-hour and 2-week household water plan             | `foundation.household-resilience-inventory`, `water.safe-storage`, `water.treatment-selection`, `water.basic-testing` | household water plan      |

### Food

| ID                              | Type    | Purpose                                                                           | Requires                                                                              | Primary artifact          |
| ------------------------------- | ------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------- |
| `food.pantry-design`            | project | design a pantry around calories, diet, shelf life, budget, and storage conditions | `foundation.measurement-and-units`, `foundation.household-resilience-inventory`       | pantry map                |
| `food.pantry-rotation`          | skill   | rotate and replenish food systematically                                          | `food.pantry-design`                                                                  | rotation sheet            |
| `food.safe-preservation-basics` | concept | understand safe boundaries of freezing, drying, fermenting, and canning decisions | `foundation.verify-and-cite`, `foundation.ai-grounded-research`, `food.pantry-design` | preservation safety card  |
| `food.seed-starting`            | skill   | start plants from seed with correct timing, medium, light, and moisture           | `foundation.measurement-and-units`                                                    | seed-start log            |
| `food.beginner-garden-system`   | project | plan a small bed or container garden for reliable output                          | `foundation.systems-mapping`, `food.seed-starting`                                    | garden layout + crop plan |

### Shelter and repair

| ID                                  | Type    | Purpose                                                                        | Requires                                                                                               | Primary artifact             |
| ----------------------------------- | ------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------- |
| `shelter.building-envelope`         | concept | understand heat, air, moisture, insulation, and leakage pathways               | `foundation.measurement-and-units`                                                                     | building-envelope diagram    |
| `shelter.weatherization-audit`      | project | inspect drafts, heat loss, infiltration, and weatherization priorities         | `foundation.systems-mapping`, `foundation.household-resilience-inventory`, `shelter.building-envelope` | weatherization audit         |
| `shelter.moisture-and-mold-control` | skill   | identify moisture sources and interrupt mold conditions                        | `foundation.verify-and-cite`, `shelter.building-envelope`                                              | moisture checklist           |
| `repair.hand-tool-literacy`         | skill   | use measuring, tightening, cutting, and fastening tools safely and confidently | `foundation.measurement-and-units`                                                                     | tool competency checklist    |
| `repair.shutoffs-seals-and-patches` | skill   | locate shutoffs, stop minor leaks, seal gaps, and make temporary repairs       | `shelter.moisture-and-mold-control`, `repair.hand-tool-literacy`                                       | shutoff map + patch kit list |

### Power

| ID                          | Type    | Purpose                                                         | Requires                                                                                          | Primary artifact   |
| --------------------------- | ------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------ |
| `power.circuit-basics`      | concept | understand volts, amps, watts, watt-hours, breakers, and loads  | `foundation.measurement-and-units`                                                                | power formula card |
| `power.load-audit`          | project | inventory critical devices and outage priorities                | `foundation.systems-mapping`, `foundation.household-resilience-inventory`, `power.circuit-basics` | load sheet         |
| `power.runtime-calculation` | skill   | calculate runtime from batteries, generators, or power stations | `foundation.measurement-and-units`, `power.circuit-basics`, `power.load-audit`                    | runtime table      |
| `power.backup-power-plan`   | project | produce low-, mid-, and high-budget backup options              | `foundation.ai-grounded-research`, `power.load-audit`, `power.runtime-calculation`                | backup power plan  |

### Community

| ID                                | Type    | Purpose                                                                    | Requires                                                                                                                                                                                                                     | Primary artifact      |
| --------------------------------- | ------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `community.local-resource-map`    | project | map local tools, skills, food sources, water sources, spaces, and contacts | `foundation.systems-mapping`, `foundation.household-resilience-inventory`                                                                                                                                                    | local resource map    |
| `community.teach-forward-session` | project | teach one completed capability to others in 10–20 minutes                  | `foundation.verify-and-cite` and `n_of(2)` from `water.household-water-plan`, `food.pantry-design`, `food.beginner-garden-system`, `shelter.weatherization-audit`, `power.backup-power-plan`, `community.local-resource-map` | lesson plan + handout |

### Core dependency spine

This is the shortest useful spine through the graph:

```text
foundation.verify-and-cite
  -> foundation.ai-grounded-research
  -> foundation.household-resilience-inventory
  -> water.household-water-plan
  -> food.pantry-design
  -> shelter.weatherization-audit
  -> power.load-audit
  -> power.backup-power-plan
  -> community.local-resource-map
  -> community.teach-forward-session
```

And the main branch structure looks like:

```text
foundation.measurement-and-units
  -> water.safe-storage
  -> food.seed-starting
  -> shelter.building-envelope
  -> power.circuit-basics
  -> power.runtime-calculation

foundation.systems-mapping
  -> foundation.household-resilience-inventory
  -> food.beginner-garden-system
  -> shelter.weatherization-audit
  -> power.load-audit
  -> community.local-resource-map
```

---

## 3) 12-week syllabus

### Program cadence

A simple public-friendly cadence:

* **Seminar**: 60–75 minutes
* **Lab**: 75–90 minutes
* **Field task**: 45–90 minutes
* **Teach-forward relay**: 5–10 minutes

Pass each week on three criteria:

1. the artifact exists
2. one observable action is demonstrated
3. one concept is explained to another person

### 12-week sequence

| Week | Theme                                             | Graph nodes                                                                                                   | Lab / field task                                                        | Deliverable                              |
| ---- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------- |
| 1    | Truth, tools, and AI as amplifier                 | `foundation.verify-and-cite`, `foundation.ai-grounded-research`                                               | compare three claims using AI plus source checks                        | claim-check worksheet + prompt pack      |
| 2    | Measure, map, inventory                           | `foundation.measurement-and-units`, `foundation.systems-mapping`, `foundation.household-resilience-inventory` | map household systems and baseline needs                                | household resilience inventory           |
| 3    | Water I: store and choose treatment               | `water.safe-storage`, `water.treatment-selection`                                                             | calculate daily water needs and compare treatment paths                 | storage table + treatment matrix         |
| 4    | Water II: test and plan                           | `water.basic-testing`, `water.household-water-plan`                                                           | run a testing demo and build 72-hour / 2-week plan                      | household water plan                     |
| 5    | Food I: pantry, rotation, preservation boundaries | `food.pantry-design`, `food.pantry-rotation`, `food.safe-preservation-basics`                                 | build pantry categories, labels, and do/don’t card                      | pantry map + rotation sheet              |
| 6    | Food II: seed starting and garden planning        | `food.seed-starting`, `food.beginner-garden-system`                                                           | start seeds or design container/bed system                              | seed log or garden layout                |
| 7    | Shelter I: envelope and weatherization            | `shelter.building-envelope`, `shelter.weatherization-audit`                                                   | inspect drafts, insulation, leakage, and rank fixes                     | weatherization audit                     |
| 8    | Repair I: moisture, tools, shutoffs, patching     | `shelter.moisture-and-mold-control`, `repair.hand-tool-literacy`, `repair.shutoffs-seals-and-patches`         | locate shutoffs and practice minor sealing / patching                   | shutoff map + patch kit list             |
| 9    | Power I: electrical literacy                      | `power.circuit-basics`                                                                                        | read device labels, breakers, and power formulas                        | power formula card + circuit notes       |
| 10   | Power II: critical loads and runtime              | `power.load-audit`, `power.runtime-calculation`                                                               | calculate outage priorities and runtimes                                | load sheet + runtime table               |
| 11   | Power III + community layer                       | `power.backup-power-plan`, `community.local-resource-map`                                                     | draft budget-tiered backup plans and local capability map               | backup power plan + local resource map   |
| 12   | Capstone: teach-forward and archive               | `community.teach-forward-session`                                                                             | deliver a 10–20 minute micro-lesson using one artifact from prior weeks | lesson plan + handout + portfolio binder |

### What participants finish with

By week 12, each learner should have a durable portfolio:

* claim-evaluation worksheet
* household resilience inventory
* household water plan
* pantry map and rotation sheet
* preservation safety card
* seed-start log or garden plan
* weatherization audit
* shutoff map and patch kit list
* power formula card
* load sheet and runtime table
* backup power plan
* local resource map
* 10–20 minute teach-forward packet

That portfolio matters more than a certificate. It is proof of usable competence.

---

## 4) Content template for each module

This is the canonical template for the source file that generates all public outputs.

### 4.1 Module front matter

```markdown
---
id: module.01-truth-tools-ai
type: module
week: 1
title: Truth, Tools, and AI as Amplifier
summary: Learn how to verify claims, use AI as a grounded assistant, and avoid outsourcing judgment.
plain_language: This week teaches you how to check whether information is real, current, and useful before you act on it.
domains: [foundation]
stage: foundation
difficulty: 1
estimated_hours: 4
cost_band: free
risk_band: low
contexts: [general, renter, homeowner, urban, rural, low_budget]

node_refs:
  - foundation.verify-and-cite
  - foundation.ai-grounded-research

requires:
  - mode: all_of
    ids: []

learning_objectives:
  - Evaluate a claim using source quality, date, and evidence.
  - Use AI to summarize and compare without treating it as an oracle.
  - Produce a claim-check worksheet.

deliverable_refs:
  - artifact.claim-check-worksheet
  - artifact.prompt-pack

assessment_ref: assessment.module.01
source_refs:
  - resource.foundation.01
  - resource.foundation.02

version: 1.0.0
updated_at: 2026-03-13
---
```

### 4.2 Module body template

Use the same section order every time.

```markdown
# 1. Promise
One sentence describing the transformation.
Example: "By the end of this module, you will be able to verify a practical claim before acting on it."

# 2. Why it matters
2-5 short paragraphs.
Answer:
- what problem this solves
- what failure looks like
- why a beginner should care now

# 3. Plain-language overview
A zero-jargon explanation of the core idea.
This is the section a general audience should be able to read first.

# 4. Graph position
- Node refs covered
- What this module depends on
- What this module unlocks next

# 5. Learning objectives
3-5 objectives using action verbs.
Examples:
- identify
- compare
- calculate
- map
- demonstrate
- teach

# 6. Vocabulary
8-12 key terms with one-line definitions.

# 7. Core concepts
Explain the minimum theory needed to act.
Include:
- diagrams
- formulas or rules of thumb
- common misconceptions
- what not to overcomplicate

# 8. Procedure / lab
Step-by-step lab instructions.
Include:
- setup
- materials/tools
- time estimate
- checkpoints
- stop conditions
- cleanup / documentation

# 9. Field task
A real-world assignment done at home or locally.
The task must create a durable artifact.

# 10. Deliverable
Describe exactly what the learner submits or keeps.
Include a checklist of required elements.

# 11. Common failure modes
List the most likely errors.
For each:
- what it looks like
- why it happens
- how to correct it

# 12. Variants
Always include:
- low-cost path
- renter version
- homeowner version
- urban version
- rural version
- climate or locality notes if relevant

# 13. AI prompt pack
Include 3-5 reusable prompts:
- explain in plain language
- compare options
- localize to my budget / region / housing type
- generate a checklist
- critique my draft plan

# 14. Assessment
State exactly how the module is passed.
Use:
- artifact checklist
- performance demo
- short oral explanation
Avoid abstract testing where possible.

# 15. Teach-forward card
A tiny lesson the learner can pass on.
Include:
- 3-minute version
- 10-minute version
- one handout or diagram
- one discussion question

# 16. References and revision log
Keep:
- sources
- version changes
- field notes
- deprecations or warnings
```

### 4.3 Every module should publish as a six-part bundle

From that canonical file, generate these public-facing assets:

1. **Hook**
   one paragraph, poster, social post, or 60–90 second script

2. **Primer**
   beginner-friendly explanation

3. **Lab guide**
   step-by-step practical activity

4. **Reference sheet**
   formulas, checklists, tables, limits, glossary

5. **Worksheet / artifact template**
   the form people fill out

6. **Teach-forward card**
   how to explain it to someone else

That six-part bundle is how the program becomes a campaign instead of a private curriculum.

### 4.4 Standard assessment pattern

Use the same structure across all modules:

```yaml
assessment_pattern:
  artifact_complete: true
  performance_demo: true
  oral_explanation: true
  teach_forward: true
```

A practical rubric:

* **Incomplete**: artifact missing or unusable
* **Emerging**: artifact exists but learner cannot explain or apply it
* **Functional**: artifact works and learner can demonstrate the task
* **Teach-forward ready**: learner can explain it clearly to someone else

---

## 5) One implementation rule that keeps the whole thing coherent

For every node, ask four questions:

1. What does this help someone **understand**?
2. What does this help someone **do**?
3. What does this help someone **produce**?
4. What does this help someone **teach forward**?

If a node cannot answer at least two of those, it is probably too abstract for the public commons and should be rewritten.

The next useful move is to convert these 25 nodes into seed files and an import sheet for Obsidian, Airtable, or Neo4j so the graph and syllabus exist as a working system on day one.

