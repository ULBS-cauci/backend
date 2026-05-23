import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from app.api.dependencies import get_file_service, get_current_user
from app.services.file_service import FileService
from app.schemas.knowledge_schemas import MaterialPublic
from app.schemas.user_schemas import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=MaterialPublic)
async def upload_file(
    file: UploadFile = File(...),
    course_id: uuid.UUID = Query(...),
    file_service: FileService = Depends(get_file_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return await file_service.upload_and_index(
            file, course_id=course_id, user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
