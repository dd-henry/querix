import logging
from typing import Dict

from fastapi import APIRouter, Depends

from api.app import APIError
from api.dependencies import (
    get_predefined_query_repository,
    get_semantic_context,
    get_translator,
    require_approved_user,
)
from api.schemas.sync import SchemaSyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.post("/sync", response_model=SchemaSyncResponse)
def synchronize_schema(
    _profile: Dict[str, object] = Depends(require_approved_user),
) -> SchemaSyncResponse:
    get_semantic_context.cache_clear()
    get_translator.cache_clear()
    get_predefined_query_repository.cache_clear()
    try:
        get_semantic_context().get_profile()
        get_translator()
    except Exception as exc:
        logger.exception("Schema synchronization failed.")
        raise APIError(
            503,
            "schema_sync_failed",
            "The database schema could not be synchronized.",
        ) from exc
    return SchemaSyncResponse(status="synchronized")
