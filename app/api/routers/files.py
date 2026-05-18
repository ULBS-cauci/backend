import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.api.dependencies import get_file_service
from app.services.file_service import FileService
from app.schemas.knowledge_schemas import MaterialPublic

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=MaterialPublic)
async def upload_file(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    course_id: uuid.UUID = uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
    user_id: uuid.UUID = uuid.UUID("123e4567-e89b-12d3-a456-426614174001"),
):
    try:
        return await file_service.upload_and_index(
            file, course_id=course_id, user_id=user_id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
