# Capability Commons — Vision

> Build an open capability commons that maps concepts to skills, skills to projects, projects to local deployment, and every learner to teach-forward transmission.

## What this is

Capability Commons is a public knowledge platform for practical, civilizational literacy. It takes knowledge that is normally trapped inside trades, institutions, guilds, paywalls, jargon, and credential barriers, and converts it into structured, searchable, teachable objects that anyone can use.

The unit of value is the **reproducible capability** — not the article, not the video, not the course. A capability is a node in a knowledge graph that explains something people need to understand, trains something people need to do, or produces something people can keep, use, and teach forward.

## The problem

Most adults cannot maintain the systems their households depend on. Practical knowledge about water, food, shelter, power, repair, health, and coordination exists, but it is scattered across expert communities, behind professional certifications, locked in technical jargon, or buried in dense reference material that assumes a reader already knows what they need to learn.

This is not a content problem. The internet has more information than anyone could consume. It is a **structure problem**. The knowledge exists, but it is not organized for a beginner who needs to act, does not know the vocabulary, and cannot afford to get it wrong.

## The thesis

> AI should be used to convert hidden competence into shared public capacity.

AI is not the product. AI is the compiler. It takes source material — manuals, reference books, field notes, expert knowledge — and helps transform it into structured, plain-language, context-aware capability objects. Human review and field testing decide what becomes canon.

## What the commons contains

### Three interlocking graphs

The system is not a document library. It is three graphs working together:

- **Concept graph** — what things mean and how ideas relate. "What is thermal mass?" "How does soil pH affect nutrient availability?"
- **Skill graph** — what people can do, in what order, with what prerequisites. "What can I do next?" "What must I know first?"
- **Deployment graph** — where, when, and under what constraints something is useful. "Does this work in my apartment?" "What's the low-budget version?"

That combination is what lowers the barrier to entry. Not just explanation, but explanation tied to action and context.

### Capability domains

The corpus is organized by civilizational function, not academic discipline:

| Layer | Domains |
|-------|---------|
| **Foundation** | Epistemics and verification, AI/tool use, measurement, systems thinking, numeracy |
| **Household** | Water, food, shelter, heat/cooling, electricity and backup power, sanitation, health, communications |
| **Productive** | Gardening and soil, food preservation, carpentry and repair, plumbing, electrical work, small engines, electronics, fabrication |
| **Community** | Mutual aid logistics, group decision-making, local mapping, shared infrastructure, emergency coordination, economic cooperation |
| **Advanced** | Architecture, mechanical systems, energy systems design, networking, manufacturing, open-source hardware, governance design |

### Knowledge object model

Every node uses the same structure: a typed knowledge object with a canonical title, plain-language explanation, structured payload, prerequisite logic, context-aware facets, and durable output artifacts.

The core types:

| Type | Purpose |
|------|---------|
| **Concept note** | Explains a principle, model, or mental framework |
| **Skill guide** | Observable action a learner can perform, with tools, steps, and failure modes |
| **Project blueprint** | Applied task that creates a useful artifact, with deliverables and acceptance criteria |
| **Module** | Weekly curriculum unit covering multiple capabilities |
| **Reference sheet** | Specs, formulas, diagrams, checklists |
| **Learning path** | Sequenced progression through a domain |
| **Field report** | Documented real-world application with results |
| **Local adaptation** | Region/climate/budget-specific variant of an existing object |
| **Teach-forward packet** | Materials for passing knowledge to someone else |

### Five-format publishing rule

Every core topic exists in five forms:

1. **Hook** — a compelling 1-2 sentence pitch for why this matters
2. **Primer** — plain-language background explanation
3. **Guide** — step-by-step practical instructions
4. **Reference** — specs, formulas, diagrams, checklists
5. **Teach-forward kit** — how to pass it on (3-minute version, 10-minute outline, discussion prompts)

## Entry model

People start with immediate needs and expand outward through concentric rings:

1. **Stay functional** — verify information, store water, keep lights running, maintain heat
2. **Repair and maintain** — hand tools, patching, sealing, diagnosing common failures
3. **Produce** — gardening, preservation, rainwater, solar basics, local resource mapping
4. **Coordinate** — shared inventories, mutual aid, tool libraries, communication plans
5. **Steward and transmit** — documentation, teaching methods, archives, offline kits

## Barrier-lowering requirements

Every module includes:

- A plain-language version and zero-jargon glossary
- Cheap path / better path / best path
- Renter / homeowner / rural / urban adaptation
- What you can do with minimal tools
- Common mistakes and what not to do
- How to verify your work
- What to learn next

## Governance

- Open license for the core corpus
- Transparent version history with lifecycle states: `DRAFT` > `IN_REVIEW` > `REVIEWED` > `VERIFIED` > `PUBLISHED` > `DEPRECATED`
- Editorial standards and subject-matter review
- Field-testing status labels and evidence provenance
- Regional forks with clear provenance
- No black-box canonical truth claims

## Success metrics

The metric is not attention. It is **replicated competence**:

- Modules completed by real people
- Tasks performed in the physical world
- People who teach another person what they learned
- Local variants documented from different regions and contexts
- Offline kits distributed
- Households that gain a new competence
- Communities that create shared infrastructure

## How it works technically

Capability Commons is built on a Postgres-first architecture with pgvector for retrieval, a FastAPI async API, and a multi-pass ingestion pipeline that converts source documents into fully populated knowledge objects with citations, edges, and learning bundles.

For technical details, see the [README](README.md). For the ingestion pipeline, see [ingestion/README.md](ingestion/README.md). For the full philosophical foundation, see [PHILOSOPHY.md](PHILOSOPHY.md). To contribute knowledge to the commons, see [CONTRIBUTING.md](CONTRIBUTING.md).
