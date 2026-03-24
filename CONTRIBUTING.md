# Contributing to Capability Commons

Capability Commons is an open knowledge platform. Contributions come in many forms — adding knowledge to the corpus, improving the code, reviewing existing objects, documenting field tests, and creating local adaptations.

## Ways to contribute

### 1. Add knowledge to the commons (ingestion projects)

This is the most impactful contribution. You take source material — a reference book, a technical manual, field notes, a practitioner's guide — and run it through the ingestion pipeline to produce structured, citable knowledge objects.

**What you submit:** A complete project directory containing parsed segments, extraction matrix, draft YAML objects, citations, and edges.

**What maintainers review:** The YAML objects (accuracy, clarity, plain-language quality), citation integrity, edge relationships, and safety notices.

See the full ingestion workflow below.

### 2. Review and improve existing objects

Browse published objects and submit improvements:
- Fix factual errors (with citations to evidence)
- Improve plain-language clarity
- Add missing failure modes or safety notices
- Add local adaptations for your climate, region, or budget
- Fill in missing prerequisites or suggested edges

### 3. Field test and report

The most valuable form of review is field testing — actually performing the skill or project described in a knowledge object and reporting what happened:
- Did the instructions work?
- What was unclear or missing?
- What went wrong that the failure modes didn't cover?
- What tools or materials were actually needed?
- How long did it actually take?

Field reports are submitted as `field_report` objects linked to the original.

### 4. Create local adaptations

Many skills and projects assume conditions that don't apply everywhere. If you have expertise in a specific context — cold climate, tropical, arid, urban apartment, off-grid, low-budget — create adapted versions of existing objects.

### 5. Improve the code

Bug fixes, performance improvements, new features, and test coverage are welcome. See the development section below.

---

## Ingestion contribution workflow

The ingestion pipeline is the primary path for adding knowledge to the commons. It converts source documents into structured, citable knowledge objects through an 8-pass process.

### Prerequisites

```bash
# Clone the repo and install with ingestion dependencies
git clone <repo-url>
cd CapabilityCommons
pip install -e '.[ingest]'

# You need an OpenAI-compatible API key for the LLM passes
export OPENAI_API_KEY="sk-..."
```

### Step 1: Fork and create a branch

```bash
git checkout -b contrib/<your-project-name>
```

### Step 2: Initialize a project

```bash
python -m capability_commons.cli.ingest init <project-name> \
  --source path/to/document.pdf \
  --source-id src.<domain>.<short-name>.<year> \
  --source-title "Full Title of Source Document" \
  --source-kind BOOK
```

Source ID convention: `src.<domain>.<short-name>.<year>` — for example, `src.water.who-guidelines.2022` or `src.soil.rodale-encyclopedia.2018`.

### Step 3: Run the pipeline

```bash
# Parse the PDF into segments
python -m capability_commons.cli.ingest parse <project-name>

# Generate extraction matrix (identifies candidate objects)
python -m capability_commons.cli.ingest extract <project-name>

# Review the matrix at ingestion/projects/<project-name>/matrix/extraction_matrix.csv
# Remove low-confidence rows, fix slugs, adjust types as needed

# Draft canonical objects
python -m capability_commons.cli.ingest draft <project-name>

# Link citations to source spans
python -m capability_commons.cli.ingest cite <project-name>

# Deduplicate and canonicalize
python -m capability_commons.cli.ingest canonicalize <project-name>

# Extract edges between objects
python -m capability_commons.cli.ingest edges <project-name>

# Generate learning bundles (for skill_guide, project_blueprint, module types)
python -m capability_commons.cli.ingest bundles <project-name>
```

### Step 4: Review your output

This is the most important step. The LLM drafts are a starting point, not a finished product.

**For each draft YAML file in `ingestion/projects/<project-name>/drafts/`:**

- [ ] **Accuracy:** Does the content accurately reflect the source material? Are there invented claims?
- [ ] **Plain language:** Can a beginner understand this without field-specific jargon?
- [ ] **Completeness:** Are the failure modes, safety notices, and prerequisites realistic?
- [ ] **Citations:** Do the citations point to real passages in the source? Is the support strength rating honest?
- [ ] **Structured data:** Are tools, materials, success criteria, and acceptance criteria sensible?
- [ ] **Edges:** Do the prerequisite and relationship edges make sense? Are any obvious connections missing?
- [ ] **Bundles:** Is the hook compelling? Is the teach-forward kit practical?

Edit the YAML files directly. This is human review — you are the editor, not the LLM.

### Step 5: Validate

```bash
python -m capability_commons.cli.ingest validate <project-name>
```

Fix all errors. Warnings are advisory but should be addressed where possible (especially missing citations and safety notices for high-risk topics).

### Step 6: Submit a pull request

Your PR should contain the entire project directory:

```
ingestion/projects/<project-name>/
├── manifest.yaml
├── sources/
├── segments/
├── matrix/
├── drafts/          ← the main review target
├── edges/
└── output/          ← not required; maintainers run the load pass
```

**PR title:** `contrib: <domain> — <source short name>`

**PR description should include:**
- Source document title and author
- Number of objects produced
- Domains covered
- Any known limitations or areas where review is especially needed
- Whether you field-tested any of the content

### What happens after you submit

1. A maintainer reviews the YAML objects for accuracy, clarity, and adherence to the doctrine
2. Safety-critical content (anything with `risk_band: high` or `risk_band: expert_only`) gets additional review
3. Accepted objects are loaded into the commons via the load pass
4. Your contribution is attributed in the object provenance metadata

---

## Content standards

All contributed knowledge objects must follow these principles:

### Accuracy and citations

Every substantive claim must be traceable to a source. The ingestion pipeline generates citations automatically, but contributors should verify them. If you add content beyond what the source material covers, add new citations or mark it clearly.

Do not invent claims the source does not support. If the source is ambiguous, say so.

### Plain language

Write for someone who has never encountered this topic before. Define terms on first use. Avoid acronyms without expansion. The reading level should be accessible to a motivated adult without specialized education.

### Safety

Any content involving physical risk — electrical work, structural modification, chemical use, food preservation, water treatment — must include:
- A `risk_band` rating (low, moderate, high, expert_only)
- A `safety_boundary` in structured data (what is beyond the scope of this guide)
- Explicit `failure_modes` (what can go wrong and how to recognize it)

Do not publish safety-critical content with `risk_band: high` or above without a safety notice. "When in doubt, hire a professional" is an acceptable boundary statement.

### Local adaptability

Where possible, note the assumptions your content makes about climate, geography, available tools, housing type, and budget. A skill guide that assumes a detached house in a temperate climate should say so. Encourage local adaptation objects from contributors in different contexts.

### Doctrine alignment

Review the [six doctrine rules](PHILOSOPHY.md) before submitting. Key questions:
- Does this terminate in action? (practical before ornamental)
- Can a beginner start here? (layered for beginners)
- Does it acknowledge different conditions? (locally adaptable)
- Could someone teach this forward? (teach-forward)

---

## Code contributions

### Development setup

```bash
git clone <repo-url>
cd CapabilityCommons
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,ingest]'
```

### Running tests

```bash
pytest tests/ -v
```

The integration tests require a running Postgres database. Unit tests (everything except `test_integration.py`) run without external dependencies.

### Code conventions

- Python 3.12+, type hints throughout
- Pydantic v2 for all data models
- SQLAlchemy 2 async ORM
- FastAPI for API routes
- `pytest` with `pytest-asyncio` for async tests

### Pull request checklist

- [ ] All existing tests pass
- [ ] New code has tests
- [ ] No hardcoded credentials or API keys
- [ ] Type hints on all public functions
- [ ] Docstrings on modules and non-trivial functions

---

## Governance

Capability Commons uses a lifecycle-based editorial model:

| State | Meaning |
|-------|---------|
| `DRAFT` | Initial submission, not yet reviewed |
| `IN_REVIEW` | Under editorial or expert review |
| `REVIEWED` | Passed editorial review |
| `VERIFIED` | Field-tested or expert-verified |
| `PUBLISHED` | Available in the public corpus |
| `DEPRECATED` | Superseded or no longer recommended |

Contributors can submit at `DRAFT` state. Maintainers advance objects through the lifecycle based on review quality and field testing.

### Review types

- **Editorial** — clarity, plain language, structure
- **Expert** — domain accuracy, completeness
- **Safety** — risk assessment, failure modes, boundary statements
- **Pedagogy** — learning sequence, prerequisites, difficulty rating

### Provenance

Every edge and object carries provenance metadata indicating how it was created:
- `human_authored` — written directly by a contributor
- `llm_extracted` — generated by the ingestion pipeline
- `human_verified` — reviewed and approved by a human
- `imported` — imported from an external source

This transparency is a core commitment. The commons never claims something was human-reviewed when it wasn't.

---

## License

The core knowledge corpus is open. Code contributions are made under the project's license. By submitting a contribution, you agree that your work may be freely used, adapted, and redistributed as part of the commons.

---

## Questions?

Open an issue on the repository. For questions about the ingestion pipeline specifically, see [ingestion/README.md](ingestion/README.md).
