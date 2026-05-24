import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from app.api.dependencies import get_file_service, get_current_user, get_dev_course, get_db_session
from app.services.file_service import FileService
from app.schemas.knowledge_schemas import Material, MaterialPublic
from app.schemas.user_schemas import User
from app.schemas.course_schemas import Course

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=MaterialPublic)
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    current_user: User = Depends(get_current_user),
    course: Course = Depends(get_dev_course),
):
    try:
        return await file_service.upload_and_index(
            file, course_id=course.id, user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{material_id}/status", response_model=MaterialPublic)
async def get_material_status(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    material = await db.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    if material.uploaded_by is not None and material.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return MaterialPublic.model_validate(material)
