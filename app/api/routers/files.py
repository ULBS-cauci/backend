import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import get_course_service, get_current_user, get_file_service
from app.services.course_service import CourseService
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
    course_service: CourseService = Depends(get_course_service),
    current_user: User = Depends(get_current_user),
):
    """Upload a document and enqueue it for background indexing."""
    course = await course_service.get_course_by_id(course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found.",
        )
    try:
        return await file_service.upload_and_index(
            file, course_id=course_id, user_id=current_user.id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
