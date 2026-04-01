from fastapi import APIRouter

from capability_commons.api.routes import ask, edges, entities, evidence, health, ingest, metrics, objects, public, retrieval, reviews, search

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(objects.router, prefix="/v1", tags=["objects"])
api_router.include_router(entities.router, prefix="/v1", tags=["entities"])
api_router.include_router(edges.router, prefix="/v1", tags=["edges"])
api_router.include_router(evidence.router, prefix="/v1", tags=["evidence"])
api_router.include_router(reviews.router, prefix="/v1", tags=["reviews"])
api_router.include_router(search.router, prefix="/v1", tags=["search"])
api_router.include_router(retrieval.router, prefix="/v1", tags=["retrieval"])
api_router.include_router(public.router, prefix="/v1", tags=["public"])
api_router.include_router(ask.router, prefix="/v1", tags=["ask"])
api_router.include_router(metrics.router, prefix="/v1", tags=["metrics"])
api_router.include_router(ingest.router, prefix="/v1", tags=["ingest"])
