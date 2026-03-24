# Capability Commons — Vision and Doctrine

> Build an open capability commons that maps concepts to skills, skills to projects, projects to local deployment, and every learner to teach-forward transmission.

## The problem

Practical knowledge — how to store water safely, size a backup power system, seal a drafty house, grow food, verify a claim before acting on it — is trapped inside trades, institutions, guilds, paywalls, jargon, and credential barriers. Most adults cannot maintain the systems their households depend on.

## The thesis

> AI should be used to convert hidden competence into shared public capacity.

The unit of value is not the article. It is the **reproducible capability**: a node in a knowledge graph that explains something people need to understand, trains something people need to do, or produces something people can keep, use, and teach forward.

## Doctrine

Six rules govern the commons:

1. **Open by default** — the core corpus is freely accessible
2. **Practical before ornamental** — every lesson terminates in action
3. **Layered for beginners** — no topic requires insider language to start
4. **Locally adaptable** — climate, region, budget, and available tools matter
5. **Project-based** — competence comes from making, repairing, measuring, building
6. **Teach-forward** — every learner becomes a transmitter

## Three interlocking graphs

The system is not a pile of documents. It is three graphs working together:

- **Concept graph** — what things mean, how ideas relate (*"what is thermal mass?"*)
- **Skill graph** — what people can do, what they must know first (*"what can I do next?"*)
- **Deployment graph** — where, when, and under what constraints something is useful (*"how does this apply in my actual life?"*)

That combination lowers the barrier to entry. Not just explanation, but explanation tied to action and context.

## Capability domains

The corpus is organized by civilizational functions, not academic disciplines:

| Layer | Domains |
|-------|---------|
| **Foundation** | Epistemics and verification, AI/tool use, measurement, systems thinking |
| **Household** | Water, food, shelter, heat/cooling, power, sanitation, health, communications |
| **Productive** | Gardening, preservation, carpentry, plumbing, electrical, fabrication |
| **Community** | Mutual aid, local mapping, shared infrastructure, emergency coordination |
| **Advanced** | Architecture, energy systems, networking, manufacturing, governance |

## Concentric ring entry model

People start with immediate needs and expand outward:

1. **Stay functional** — verify information, store water, keep lights running, maintain heat
2. **Repair and maintain** — hand tools, patching, sealing, diagnosing common failures
3. **Produce** — gardening, preservation, rainwater, solar basics, local resource mapping
4. **Coordinate** — shared inventories, mutual aid, tool libraries, communication plans
5. **Steward and transmit** — documentation, teaching methods, archives, offline kits

## Knowledge object model

Every node uses the same structure: a typed knowledge object with a title, plain-language explanation, structured payload, prerequisite logic, context-aware facets, and durable output artifacts.

Three core types in the v1 graph:

| Type | Purpose | Key payload fields |
|------|---------|-------------------|
| **Concept** | Explains a principle or model | definition, key questions, misconceptions, formulas |
| **Skill** | Observable action a learner can perform | performance statement, tools, steps, success criteria, failure modes |
| **Project** | Applied task that creates a useful artifact | goal, deliverables, acceptance criteria, time box, budget |

## Five-format publishing rule

Every core topic should exist in five forms:

1. **Hook** — short, compelling entry point (poster, 90-second script)
2. **Primer** — plain-language explanation
3. **Guide** — step-by-step practical instructions
4. **Reference** — specs, formulas, diagrams, checklists
5. **Teach-forward kit** — how to pass it on to someone else

## Assessment model

Competence is measured by action, not abstract testing:

- **Artifact exists** — the learner produced something usable
- **Performance demonstrated** — the learner can do the thing
- **Oral explanation** — the learner can explain it clearly
- **Teach-forward** — the learner can pass it on

Rubric: Incomplete → Emerging → Functional → Teach-forward ready.

## AI's role

AI serves as compiler and tutor, not oracle:

- **Translation** — expert language into plain language
- **Personalization** — adapt paths for context (renter, rural, low-budget)
- **Graph navigation** — what to learn next and why
- **Localization** — adjust for climate, materials, available tools
- **Conversion** — one source into many forms (article → checklist → workshop)

> AI may draft, map, compare, and explain. Human-reviewed evidence decides canon.

## Barrier-lowering requirements

Every module must include:

- Plain-language version and zero-jargon glossary
- Cheap path / better path / best path
- Renter / homeowner / rural / urban adaptation
- What you can do with minimal tools
- Common mistakes and what not to do
- How to verify your work
- What to learn next

## Governance

- Open license for the core corpus
- Transparent version history with `draft → reviewed → verified → deprecated` states
- Editorial standards and subject-matter review
- Field-testing status labels
- Regional forks with clear provenance
- No black-box canonical truth claims

## Success metrics

The metric is not attention. It is **replicated competence**:

- Modules completed
- Real tasks performed
- People who teach another person
- Local variants documented
- Offline kits distributed
- Households with a new competence
- Communities with shared infrastructure

## Current implementation

The v1 starter graph contains 25 nodes across 7 domains, with 50 prerequisite edges and 27 navigation edges. See the [README](../README.md) for technical details, quick start, and project layout.

## Further reading

- [VISION.md](../VISION.md) — comprehensive vision document (project root)
- [PHILOSOPHY.md](../PHILOSOPHY.md) — core intent, goals, and aspirations
- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to contribute knowledge and code
- [ingestion/README.md](../ingestion/README.md) — ingestion pipeline operator guide

The full original design documents are preserved in `docs/context/`:

- `INIT.md` — original vision and doctrine (15 sections)
- `SEED.md` — v1 blueprint with ontology, 25-node graph, 12-week syllabus, and content templates
- `CONTEXT.md` — architectural rationale for choosing Agentic Data Lite over Neo4j-first
