"""Intent auto-detection for public ask queries.

Classifies user queries into RetrievalIntent categories using weighted
keyword patterns. Designed to be swappable with an LLM-based classifier
when needed — callers use `classify_intent()` regardless of backend.
"""
from __future__ import annotations

import re

from capability_commons.domain.enums import RetrievalIntent

# Pattern → intent mappings, scored by specificity.
# Each entry: (compiled_regex, intent, weight)
_PATTERNS: list[tuple[re.Pattern[str], RetrievalIntent, float]] = [
    # HOW_TO — procedural/instructional queries
    (re.compile(r"\bhow\s+(do|can|should|would)\s+(i|we|you)\b", re.I), RetrievalIntent.HOW_TO, 1.0),
    (re.compile(r"\bhow\s+to\b", re.I), RetrievalIntent.HOW_TO, 1.0),
    (re.compile(r"\bsteps?\s+(to|for)\b", re.I), RetrievalIntent.HOW_TO, 0.8),
    (re.compile(r"\bguide\s+(to|for|on)\b", re.I), RetrievalIntent.HOW_TO, 0.7),
    (re.compile(r"\binstruct(ions?|me)\b", re.I), RetrievalIntent.HOW_TO, 0.7),
    (re.compile(r"\bwhat\s+tools?\s+(do|should)\b", re.I), RetrievalIntent.HOW_TO, 0.6),
    (re.compile(r"\bbuild(ing)?\s+a\b", re.I), RetrievalIntent.HOW_TO, 0.5),
    (re.compile(r"\binstall(ing|ation)?\b", re.I), RetrievalIntent.HOW_TO, 0.5),

    # WHY — explanatory queries
    (re.compile(r"\bwhy\s+(does|do|is|are|did|would|should|can)\b", re.I), RetrievalIntent.WHY, 1.0),
    (re.compile(r"\bexplain\s+why\b", re.I), RetrievalIntent.WHY, 1.0),
    (re.compile(r"\bwhat\s+causes?\b", re.I), RetrievalIntent.WHY, 0.8),
    (re.compile(r"\breason(s?)\s+(for|behind|why)\b", re.I), RetrievalIntent.WHY, 0.8),

    # COMPARE_OPTIONS — comparative queries
    (re.compile(r"\bvs\.?\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 1.0),
    (re.compile(r"\bcompare\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 1.0),
    (re.compile(r"\bdifference\s+between\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 1.0),
    (re.compile(r"\bwhich\s+is\s+(better|best|cheaper|safer|easier)\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 0.9),
    (re.compile(r"\bpros?\s+and\s+cons?\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 0.9),
    (re.compile(r"\balternatives?\s+to\b", re.I), RetrievalIntent.COMPARE_OPTIONS, 0.7),

    # SAFETY_CHECK — risk/safety queries
    (re.compile(r"\bis\s+(it|this|that)\s+safe\b", re.I), RetrievalIntent.SAFETY_CHECK, 1.0),
    (re.compile(r"\bsafety\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.8),
    (re.compile(r"\bdanger(ous|s)?\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.8),
    (re.compile(r"\brisk(s|y)?\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.6),
    (re.compile(r"\bwarning\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.7),
    (re.compile(r"\btoxic\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.9),
    (re.compile(r"\bharmful\b", re.I), RetrievalIntent.SAFETY_CHECK, 0.8),

    # LEARN_PATH — learning/curriculum queries
    (re.compile(r"\blearn(ing)?\s+(path|plan|order|sequence)\b", re.I), RetrievalIntent.LEARN_PATH, 1.0),
    (re.compile(r"\bwhere\s+(do|should)\s+i\s+start\b", re.I), RetrievalIntent.LEARN_PATH, 1.0),
    (re.compile(r"\bcurriculum\b", re.I), RetrievalIntent.LEARN_PATH, 0.9),
    (re.compile(r"\bprerequisites?\s+(for|to)\b", re.I), RetrievalIntent.LEARN_PATH, 0.8),
    (re.compile(r"\bwhat\s+(should|do)\s+i\s+learn\s+(first|next|before)\b", re.I), RetrievalIntent.LEARN_PATH, 1.0),
    (re.compile(r"\bbeginner('?s?)?\s+guide\b", re.I), RetrievalIntent.LEARN_PATH, 0.7),

    # DEBUG_FAILURE — troubleshooting queries
    (re.compile(r"\bnot\s+working\b", re.I), RetrievalIntent.DEBUG_FAILURE, 1.0),
    (re.compile(r"\bfail(ed|ing|s)?\b", re.I), RetrievalIntent.DEBUG_FAILURE, 0.7),
    (re.compile(r"\bbroken\b", re.I), RetrievalIntent.DEBUG_FAILURE, 0.8),
    (re.compile(r"\btroubleshoot\b", re.I), RetrievalIntent.DEBUG_FAILURE, 1.0),
    (re.compile(r"\bwhat\s+went\s+wrong\b", re.I), RetrievalIntent.DEBUG_FAILURE, 0.9),
    (re.compile(r"\bfix(ing)?\b", re.I), RetrievalIntent.DEBUG_FAILURE, 0.5),

    # LOCALIZE — adaptation queries
    (re.compile(r"\bin\s+(my|this|the)\s+(area|region|country|climate|zone)\b", re.I), RetrievalIntent.LOCALIZE, 0.8),
    (re.compile(r"\badapt(ing|ation)?\s+(for|to)\b", re.I), RetrievalIntent.LOCALIZE, 0.9),
    (re.compile(r"\blocal(ly|ize)?\b", re.I), RetrievalIntent.LOCALIZE, 0.6),

    # TEACH_FORWARD — teaching/sharing queries
    (re.compile(r"\bteach(ing)?\s+(someone|others|my|a)\b", re.I), RetrievalIntent.TEACH_FORWARD, 1.0),
    (re.compile(r"\bexplain\s+(this|it)\s+to\b", re.I), RetrievalIntent.TEACH_FORWARD, 0.9),
    (re.compile(r"\bworkshop\b", re.I), RetrievalIntent.TEACH_FORWARD, 0.7),
    (re.compile(r"\btraining\s+(plan|session|material)\b", re.I), RetrievalIntent.TEACH_FORWARD, 0.8),

    # WHAT_CHANGED — change/update queries
    (re.compile(r"\bwhat('?s)?\s+(changed|new|updated|different)\b", re.I), RetrievalIntent.WHAT_CHANGED, 1.0),
    (re.compile(r"\brecent\s+(changes?|updates?)\b", re.I), RetrievalIntent.WHAT_CHANGED, 0.9),
]

DEFAULT_INTENT = RetrievalIntent.HOW_TO


def classify_intent(query: str) -> RetrievalIntent:
    """Classify a query into a RetrievalIntent.

    Returns the intent with the highest cumulative weighted score.
    Falls back to HOW_TO if no patterns match.
    """
    scores: dict[RetrievalIntent, float] = {}
    for pattern, intent, weight in _PATTERNS:
        if pattern.search(query):
            scores[intent] = scores.get(intent, 0.0) + weight

    if not scores:
        return DEFAULT_INTENT

    return max(scores, key=scores.get)  # type: ignore[arg-type]
