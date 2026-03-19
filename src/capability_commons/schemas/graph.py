from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    slug: str
    title: str
    type: str
    domain: str = "foundation"
    stage: str = "foundation"
    difficulty: int = 1
    risk_band: str = "low"
    beginner_safe: bool = True
    plain_language: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
