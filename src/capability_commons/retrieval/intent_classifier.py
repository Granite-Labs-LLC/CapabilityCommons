"""Intent auto-detection for public ask queries.

Kept as the stable import `/v1/public/ask` uses; it delegates to
`retrieval.intent.infer_intent` so the ask route and `RetrievalService`
classify queries identically. Until 2026-09-14 this module had its own,
separate pattern table: the two disagreed on 5 of 27 gold/test queries
(e.g. "Is bleach safe for treating drinking water?" -> how_to here,
safety_check there), which is why eval's intent column kept missing even
after fixes to `infer_intent`. The three phrasings only this table handled
("explain why", "what causes", "dangers of") were merged into `infer_intent`.
"""

from __future__ import annotations

from capability_commons.domain.enums import RetrievalIntent
from capability_commons.retrieval.intent import infer_intent

DEFAULT_INTENT = RetrievalIntent.HOW_TO


def classify_intent(query: str) -> RetrievalIntent:
    """Classify a query into a RetrievalIntent (HOW_TO when nothing matches)."""
    return infer_intent(query)
