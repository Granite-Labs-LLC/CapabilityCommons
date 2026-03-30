# Public Ask API Contract

## Endpoint

```
POST /v1/public/ask
```

**Authentication:** None required (public workspace). Authenticated callers resolve their own workspace.

**Rate limit:** Public rate limit (60 req/min by default).

## Request

```json
{
  "query": "How do I store water safely for emergencies?",
  "intent": "how_to",
  "context": {
    "housing_type": "apartment",
    "climate_zone": "temperate",
    "budget_profile": "minimal",
    "experience_level": "beginner",
    "settlement_type": "urban"
  },
  "conversation_id": null,
  "max_results": 8
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Plain-language question |
| `intent` | string\|null | no | One of: `how_to`, `learn_path`, `why`, `compare_options`, `localize`, `debug_failure`, `teach_forward`, `what_changed`, `safety_check`. If null or `"auto"`, auto-detected from query. |
| `context` | object\|null | no | User's situational context for filtering and ranking |
| `context.housing_type` | string | no | e.g., `apartment`, `house`, `mobile_home`, `tent` |
| `context.climate_zone` | string | no | e.g., `tropical`, `arid`, `temperate`, `cold` |
| `context.budget_profile` | string | no | e.g., `free`, `minimal`, `moderate`, `full` |
| `context.experience_level` | string | no | e.g., `beginner`, `intermediate`, `advanced` |
| `context.settlement_type` | string | no | e.g., `urban`, `suburban`, `rural`, `remote` |
| `conversation_id` | uuid\|null | no | Continue a previous conversation |
| `max_results` | int | no | Max evidence nodes (default 8) |

## Response

```json
{
  "answer": "For safe emergency water storage, use food-grade containers...",
  "action_now": "Fill clean food-grade containers with tap water today. Label each with the fill date. Store in a cool, dark place. Replace every 6 months.",
  "implementation_plan": [
    {
      "step": 1,
      "action": "Get food-grade water containers (minimum 1 gallon per person per day)",
      "tools": ["food-grade containers"],
      "materials": ["tap water", "date labels"],
      "time_estimate": "15 minutes",
      "source_slug": "water.storage-basics"
    }
  ],
  "safety": {
    "warnings": ["Never reuse containers that held chemicals or milk"],
    "stop_conditions": ["If water looks cloudy or smells unusual, do not use it"],
    "when_to_get_help": ["If your only water source is untreated surface water, consult local health authorities"]
  },
  "citations": [
    {
      "source_title": "Water Storage Basics",
      "slug": "water.storage-basics",
      "excerpt": "Store at least one gallon per person per day for a minimum of three days.",
      "page_range": "12-14",
      "support_strength": "strong"
    }
  ],
  "related_objects": [
    {
      "slug": "water.purification-methods",
      "title": "Water Purification Methods",
      "role": "next_step"
    }
  ],
  "uncertainties": [
    "Specific container material recommendations may vary by local availability."
  ],
  "resolved_intent": "how_to",
  "conversation_id": "a1b2c3d4-...",
  "retrieval_run_id": "e5f6g7h8-..."
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Plain-language direct answer |
| `action_now` | string | Immediate actionable summary |
| `implementation_plan` | array | Ordered steps with tools/materials/time |
| `safety` | object | Warnings, stop conditions, escalation guidance |
| `citations` | array | Evidence sources with excerpts |
| `related_objects` | array | Related capability objects with roles |
| `uncertainties` | array | Gaps or qualifications in the answer |
| `resolved_intent` | string | The intent used (auto-detected or explicit) |
| `conversation_id` | uuid | For follow-up queries |
| `retrieval_run_id` | uuid | Internal run ID (for diagnostics) |

## Separation of Concerns

| Surface | Endpoint | Audience | Returns |
|---------|----------|----------|---------|
| **Public Ask** | `POST /v1/public/ask` | End users | Structured answer with action plan |
| **Evidence Pack** | `POST /v1/retrieve/evidence_pack` | Operators, evaluators | Raw ranked evidence nodes + run diagnostics |
| **Public Search** | `GET /v1/search` | End users | Search results with UX filters |
| **Public Objects** | `GET /v1/public/objects/{slug}` | End users | Single object with implementation profile |

The evidence pack endpoint is the diagnostic/evaluation surface. The public ask endpoint is the product surface. They share retrieval infrastructure but return different response shapes.
