import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_current_user, get_dev_course, get_file_service
from app.schemas.course_schemas import Course
from app.schemas.knowledge_schemas import MaterialPublic
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
    """Upload a document and enqueue it for background indexing."""
    try:
        return await file_service.upload_and_index(
            file, course_id=course.id, user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
