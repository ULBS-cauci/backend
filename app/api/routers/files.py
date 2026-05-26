import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import get_current_user, get_db_session, get_dev_course, get_file_service
from app.schemas.course_schemas import Course
from app.schemas.knowledge_schemas import Material, MaterialPublic
from app.schemas.user_schemas import User
from app.services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=MaterialPublic)
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    current_user: User = Depends(get_current_user),
    course: Course = Depends(get_dev_course),
):
    """Upload a document and enqueue it for background ingestion.

    Returns immediately with ingestion_status=pending. Poll
    GET /api/v1/files/{material_id}/status to track progress.
    """
    try:
        return await file_service.upload_and_index(
            file, course_id=course.id, user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


class IngestionStatusResponse(MaterialPublic):
    """MaterialPublic already carries ingestion_status + ingestion_error."""
    pass


@router.get("/{material_id}/status", response_model=MaterialPublic)
async def get_ingestion_status(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Poll the ingestion status of an uploaded document.

    Returns the full MaterialPublic record including:
    - ingestion_status: pending | running | completed | failed
    - ingestion_error:  set when status=failed, null otherwise

    Typical polling flow:
        POST /files/upload          → { ingestion_status: "pending", id: "<uuid>", ... }
        GET  /files/<uuid>/status   → { ingestion_status: "running",    ... }
        GET  /files/<uuid>/status   → { ingestion_status: "completed",  ... }
    """
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail=f"Material {material_id} not found.")
    return MaterialPublic.model_validate(material)
