"""
Health and readiness check endpoints.
"""
from fastapi import APIRouter
from backend.config import settings
from backend.api.schemas.evaluation import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health():
    """Returns application health, readiness, and vector index status."""
    # We will check if vector store file exists
    vector_loaded = settings.VECTOR_INDEX_PATH.exists() and settings.METADATA_PATH.exists()
    chunk_count = 0
    if vector_loaded:
        try:
            import json
            with open(settings.METADATA_PATH, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                chunk_count = len(metadata)
        except Exception:
            vector_loaded = False
            chunk_count = 0

    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        vector_index_loaded=vector_loaded,
        total_indexed_chunks=chunk_count
    )
