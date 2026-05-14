"""Structured answer composer for the public ask endpoint.

Transforms an EvidencePackResponse into a user-facing AskResponse by:
1. Synthesizing a direct answer from evidence summaries
2. Extracting an immediate action item
3. Building implementation steps from evidence ordering
4. Collecting safety information from safety-related nodes
5. Mapping citations from evidence spans
6. Identifying related objects from graph edges / next_steps
"""
from __future__ import annotations

import uuid

from capability_commons.domain.enums import RetrievalIntent
from capability_commons.schemas.ask import (
    AskCitation,
    AskRequest,
    AskResponse,
    ImplementationStep,
    RelatedObject,
    SafetyBlock,
)
from capability_commons.schemas.retrieval import EvidencePackResponse

# Intent categories that should emphasize safety information
SAFETY_EMPHASIS_INTENTS = {
    RetrievalIntent.HOW_TO,
    RetrievalIntent.SAFETY_CHECK,
    RetrievalIntent.DEBUG_FAILURE,
}

# Keywords that indicate safety-relevant content in summaries
_SAFETY_KEYWORDS = {"warning", "danger", "caution", "risk", "hazard", "toxic", "never", "do not", "avoid"}


def _extract_safety_warnings(evidence: EvidencePackResponse) -> list[str]:
    """Extract safety warnings from envelope common_mistakes, evidence
    nodes (safety_notice/correction), and contradictions."""
    warnings: list[str] = []
    envelope = _top_envelope(evidence)
    if envelope:
        warnings.extend(envelope.get("common_mistakes") or [])
    for node in evidence.evidence:
        if node.type in ("safety_notice", "correction"):
            warnings.append(f"{node.title}: {node.summary_short or ''}")
        elif node.summary_short:
            lower = node.summary_short.lower()
            if any(kw in lower for kw in _SAFETY_KEYWORDS):
                warnings.append(node.summary_short)
    for contradiction in evidence.contradictions:
        desc = contradiction.get("description", "")
        if desc:
            warnings.append(f"Conflicting evidence: {desc}")
    return warnings


def _extract_stop_conditions(evidence: EvidencePackResponse) -> list[str]:
    """Pull stop_conditions from the implementation envelope when present;
    otherwise fall back to scanning evidence rationales for 'stop' cues."""
    envelope = _top_envelope(evidence)
    if envelope and envelope.get("stop_conditions"):
        return list(envelope["stop_conditions"])
    stops: list[str] = []
    for node in evidence.evidence:
        if node.rationale and "stop" in node.rationale.lower():
            stops.append(node.rationale)
    return stops


def _extract_when_to_get_help(evidence: EvidencePackResponse) -> list[str]:
    """Surface the envelope's escalation conditions to the user."""
    envelope = _top_envelope(evidence)
    return list(envelope.get("when_to_escalate") or []) if envelope else []


def _envelope_for(node) -> dict | None:
    """Return the implementation envelope dict on an evidence node, if any."""
    sd = getattr(node, "structured_data", None) or {}
    impl = sd.get("implementation") if isinstance(sd, dict) else None
    return impl if isinstance(impl, dict) else None


def _top_envelope(evidence: EvidencePackResponse) -> dict | None:
    """Pick the implementation envelope from the highest-scoring actionable
    evidence node (skill_guide / project_blueprint)."""
    for node in evidence.evidence:
        if node.type in ("skill_guide", "project_blueprint"):
            env = _envelope_for(node)
            if env:
                return env
    return None


def _build_implementation_steps(evidence: EvidencePackResponse) -> list[ImplementationStep]:
    """Build ordered implementation steps.

    Preferred path (PLAN P1-8): use the structured implementation envelope
    on the top actionable evidence node — smallest_viable_version + variants
    + escalations turn into typed steps with materials, time, and source.

    Fallback: derive coarse steps from the evidence ordering by title.
    """
    envelope = _top_envelope(evidence)
    if envelope:
        steps: list[ImplementationStep] = []
        # Step 1 is always the smallest viable thing the user can do now.
        svv = envelope.get("smallest_viable_version")
        top_slug = next(
            (n.slug for n in evidence.evidence
             if n.type in ("skill_guide", "project_blueprint")
             and _envelope_for(n) is envelope),
            None,
        )
        if svv:
            steps.append(ImplementationStep(
                step=1,
                action=svv,
                tools=list(envelope.get("tools") or []),
                materials=list(envelope.get("materials") or []),
                time_estimate=envelope.get("expected_time"),
                source_slug=top_slug,
            ))
        # Then one step per success_check (these are the user's milestones).
        for i, check in enumerate(envelope.get("success_checks") or [], start=2):
            steps.append(ImplementationStep(
                step=i, action=f"Confirm: {check}", source_slug=top_slug,
            ))
        if steps:
            return steps

    # Fallback: title/summary scaffold.
    actionable_types = {"skill_guide", "project_blueprint", "concept_note", "worksheet"}
    steps = []
    step_num = 0
    for node in evidence.evidence:
        if node.type not in actionable_types:
            continue
        step_num += 1
        steps.append(ImplementationStep(
            step=step_num,
            action=node.summary_short or node.title,
            source_slug=node.slug,
        ))
    return steps


def _build_citations(evidence: EvidencePackResponse) -> list[AskCitation]:
    """Map evidence citations to AskCitation format."""
    citations: list[AskCitation] = []
    seen_excerpts: set[str] = set()

    for node in evidence.evidence:
        for cite in node.citations:
            excerpt = (cite.text[:300] if hasattr(cite, "text") else cite.excerpt[:300]) if cite else ""
            if not excerpt or excerpt in seen_excerpts:
                continue
            seen_excerpts.add(excerpt)
            citations.append(AskCitation(
                source_title=getattr(cite, "source_title", node.title),
                slug=node.slug,
                excerpt=excerpt,
                support_strength="strong" if float(node.score) > 0.7 else "moderate",
            ))

    return citations


def _build_related_objects(evidence: EvidencePackResponse) -> list[RelatedObject]:
    """Extract related objects from next_steps and lower-scored evidence."""
    related: list[RelatedObject] = []
    seen_slugs: set[str] = set()

    for ns in evidence.next_steps:
        slug = ns.get("slug", "")
        if slug and slug not in seen_slugs:
            seen_slugs.add(slug)
            related.append(RelatedObject(
                slug=slug,
                title=ns.get("title", slug),
                role=ns.get("role", "related"),
            ))

    return related


def _synthesize_answer(evidence: EvidencePackResponse, intent: RetrievalIntent) -> str:
    """Build a direct answer from evidence summaries."""
    if not evidence.evidence:
        return "No relevant information found for your query."

    parts: list[str] = []
    for node in evidence.evidence[:5]:  # Top 5 for the main answer
        if node.summary_short:
            parts.append(f"**{node.title}**: {node.summary_short}")
        elif node.title:
            parts.append(f"**{node.title}**")

    return "\n\n".join(parts) if parts else "No relevant information found for your query."


def _extract_action_now(evidence: EvidencePackResponse, intent: RetrievalIntent) -> str | None:
    """Prefer the envelope's smallest_viable_version; fall back to top summary."""
    envelope = _top_envelope(evidence)
    if envelope and envelope.get("smallest_viable_version"):
        return envelope["smallest_viable_version"]
    if not evidence.evidence:
        return None
    top = evidence.evidence[0]
    return top.summary_short or top.title


def _detect_uncertainties(evidence: EvidencePackResponse) -> list[str]:
    """Identify gaps and qualifications in the answer."""
    uncertainties: list[str] = []

    if not evidence.evidence:
        uncertainties.append("No matching evidence found.")
        return uncertainties

    if float(evidence.sufficiency_score) < 0.5:
        uncertainties.append(
            "The available evidence may not fully address your question. "
            "Consider consulting additional sources."
        )

    if evidence.contradictions:
        uncertainties.append(
            f"There are {len(evidence.contradictions)} conflicting viewpoints in the evidence."
        )

    if len(evidence.evidence) < 3:
        uncertainties.append(
            "Limited evidence available. Verify critical details independently."
        )

    return uncertainties


_INTENT_SHAPE: dict[RetrievalIntent, dict[str, bool]] = {
    # Intents where the implementation plan is the wrong frame to lead with.
    RetrievalIntent.SAFETY_CHECK: {"plan": False, "action_now": False, "comparison": False},
    RetrievalIntent.DEBUG_FAILURE: {"plan": True, "action_now": True, "comparison": False},
    RetrievalIntent.COMPARE_OPTIONS: {"plan": False, "action_now": False, "comparison": True},
    RetrievalIntent.WHY: {"plan": False, "action_now": False, "comparison": False},
    RetrievalIntent.WHAT_CHANGED: {"plan": False, "action_now": False, "comparison": False},
    RetrievalIntent.LEARN_PATH: {"plan": True, "action_now": False, "comparison": False},
    # Defaults for how_to / teach_forward / localize.
}


def _shape_for(intent: RetrievalIntent) -> dict[str, bool]:
    return _INTENT_SHAPE.get(intent, {"plan": True, "action_now": True, "comparison": False})


def _comparison_variants(evidence: EvidencePackResponse) -> list[str]:
    """For compare_options, pull each top actionable node's SVV + first
    variant blurb into a flat list the UI renders as a comparison rail."""
    out: list[str] = []
    for node in evidence.evidence:
        if node.type not in ("skill_guide", "project_blueprint", "concept_note"):
            continue
        env = _envelope_for(node)
        if not env:
            continue
        svv = env.get("smallest_viable_version") or node.summary_short or node.title
        out.append(f"**{node.title}**: {svv}")
        variants = env.get("variants") or []
        if variants:
            v = variants[0]
            label = v.get("label", "") if isinstance(v, dict) else str(v)
            note = v.get("notes") if isinstance(v, dict) else None
            out.append(f"  - variant: {label}{f' — {note}' if note else ''}")
    return out


def _contradiction_strings(evidence: EvidencePackResponse) -> list[str]:
    """Map the typed contradiction records into human-readable strings."""
    out: list[str] = []
    for c in evidence.contradictions or []:
        if not isinstance(c, dict):
            continue
        bits = []
        if c.get("dimension"):
            bits.append(c["dimension"])
        if c.get("severity"):
            bits.append(f"severity={c['severity']}")
        if c.get("status"):
            bits.append(c["status"])
        out.append("Conflicting evidence: " + (", ".join(bits) or "see review queue"))
    return out


def _related_with_next_steps(evidence: EvidencePackResponse) -> list[RelatedObject]:
    """Combine the lower-scored evidence nodes with the graph-expansion
    next_steps the planner produced. Previously next_steps were dropped."""
    related = _build_related_objects(evidence)
    seen = {r.slug for r in related}
    for ns in evidence.next_steps or []:
        slug = ns.get("slug") or ""
        if not slug or slug in seen:
            continue
        related.append(RelatedObject(
            slug=slug,
            title=str(ns.get("title") or slug),
            role=str(ns.get("role") or "next-step"),
        ))
        seen.add(slug)
    return related


def compose_answer(
    evidence: EvidencePackResponse,
    intent: RetrievalIntent,
    request: AskRequest,
) -> AskResponse:
    """Compose a structured AskResponse from retrieval evidence.

    The shape is tuned per resolved intent (ANSWER-1):
      - safety_check / compare_options / why / what_changed: no plan,
        no action_now (the user isn't asking for a how-to).
      - compare_options: variants get pulled into the answer body.
      - debug_failure: stop_conditions and common_mistakes get top
        billing in the safety block via the existing extractors.
      - learn_path: plan stays (it IS the learning sequence) but
        action_now is suppressed.
    """
    shape = _shape_for(intent)
    answer = _synthesize_answer(evidence, intent)
    if shape["comparison"]:
        comparison_lines = _comparison_variants(evidence)
        if comparison_lines:
            answer = answer + "\n\n" + "\n\n".join(comparison_lines)

    action_now = _extract_action_now(evidence, intent) if shape["action_now"] else None
    steps = _build_implementation_steps(evidence) if shape["plan"] else []
    citations = _build_citations(evidence)
    related = _related_with_next_steps(evidence)
    uncertainties = _detect_uncertainties(evidence)
    contradictions = _contradiction_strings(evidence)

    # Safety extraction — emphasized for certain intents
    warnings = _extract_safety_warnings(evidence)
    stops = _extract_stop_conditions(evidence)
    when_to_get_help = _extract_when_to_get_help(evidence)
    if intent in SAFETY_EMPHASIS_INTENTS and not warnings and not when_to_get_help:
        when_to_get_help.append(
            "If you're unsure about any step, consult a qualified professional before proceeding."
        )

    return AskResponse(
        answer=answer,
        action_now=action_now,
        implementation_plan=steps,
        safety=SafetyBlock(
            warnings=warnings,
            stop_conditions=stops,
            when_to_get_help=when_to_get_help,
        ),
        citations=citations,
        related_objects=related,
        uncertainties=uncertainties,
        contradictions=contradictions,
        resolved_intent=intent,
        context_used=request.context,
        conversation_id=request.conversation_id,
        retrieval_run_id=evidence.run_id,
    )
