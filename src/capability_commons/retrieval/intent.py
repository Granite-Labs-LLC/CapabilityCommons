"""Heuristic intent inference for retrieval queries.

When a `/v1/retrieve/...` or `/v1/ask` caller does not specify an intent
(per updates/PLAN.md retrieval P0-5), we score the query against keyword
patterns for each `RetrievalIntent` and pick the highest-scoring one,
falling back to `HOW_TO` for ordinary "ordinary person" how-do-I queries.
"""
from __future__ import annotations

import re

from capability_commons.domain.enums import RetrievalIntent

# Regex patterns per intent; weights are arbitrary but tuned so the
# narrower intents (safety, debug, what-changed) outrank the generic ones.
_PATTERNS: list[tuple[RetrievalIntent, float, re.Pattern[str]]] = [
    (RetrievalIntent.SAFETY_CHECK, 3.0,
     # "safe" alone is too noisy ("renter-safe", "kid-safe"); require the
     # explicit safety-check vocabulary or a leading "is X safe".
     re.compile(r"\b(safety|hazard|hazardous|dangerous|toxic|unsafe|emergency)\b"
                r"|\b(?:is|are) .* safe\b", re.I)),
    (RetrievalIntent.DEBUG_FAILURE, 3.0,
     re.compile(r"\b(not working|won'?t|broken|fail(?:ing|ed)?|leak|stopped|stuck|"
                r"error|debug|fix|troubleshoot|why is(?: my)? .* (?:not|broken))\b", re.I)),
    (RetrievalIntent.WHAT_CHANGED, 2.5,
     re.compile(r"\b(what(?:'s| is) new|changed|update[ds]?|revis(?:ed|ion)|deprecated)\b", re.I)),
    (RetrievalIntent.COMPARE_OPTIONS, 2.5,
     re.compile(r"\b(compare|vs\.?|versus|which is better|alternatives?|trade-?offs?|pros and cons)\b", re.I)),
    (RetrievalIntent.LOCALIZE, 2.0,
     re.compile(r"\b(renter|apartment|off[- ]grid|urban|rural|low[- ]budget|"
                r"in (?:my )?(?:climate|country|state|city)|humid|arid|cold climate)\b", re.I)),
    (RetrievalIntent.TEACH_FORWARD, 2.0,
     re.compile(r"\b(teach|lesson plan|curriculum|workshop|how to teach|train others)\b", re.I)),
    # Slightly higher than LOCALIZE so "what should I learn before off-grid X"
    # resolves as learn_path (the verb) rather than localize (the modifier).
    (RetrievalIntent.LEARN_PATH, 2.2,
     re.compile(r"\b(learn(?:ing)? path|where (?:do|should) I start|prerequisites?|"
                r"what (?:should|do) I learn (?:first|before|next)|roadmap)\b", re.I)),
    (RetrievalIntent.WHY, 1.5,
     re.compile(r"^\s*why\b|\b(reason|rationale|because|justif(?:y|ication))\b", re.I)),
    (RetrievalIntent.HOW_TO, 1.0,
     re.compile(r"^\s*how\b|\b(how (?:to|do I|can I)|set up|build|make|install|"
                r"start(?:ing)?|begin(?:ner)?)\b", re.I)),
]


def infer_intent(query: str) -> RetrievalIntent:
    """Pick the best-matching `RetrievalIntent` for a free-form query.

    Returns `RetrievalIntent.HOW_TO` if nothing matches — the public-facing
    UI default per the website scaffold spec.
    """
    if not query or not query.strip():
        return RetrievalIntent.HOW_TO

    best: tuple[RetrievalIntent, float] = (RetrievalIntent.HOW_TO, 0.0)
    for intent, weight, pattern in _PATTERNS:
        if pattern.search(query):
            if weight > best[1]:
                best = (intent, weight)
    return best[0]
