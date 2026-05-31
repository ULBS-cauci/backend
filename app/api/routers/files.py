import io
import logging
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

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


@router.get("/{material_id}/download")
async def download_material(
    material_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
    _current_user: User = Depends(get_current_user),
):
    """Download a course material file with Content-Disposition: attachment."""
    data, file_name, content_type = await file_service.download_material(material_id)
    encoded = quote(file_name)
    headers = {
        "Content-Disposition": (
            f'attachment; filename="{encoded}"; filename*=UTF-8\'\'{encoded}'
        )
    }
    return StreamingResponse(io.BytesIO(data), media_type=content_type, headers=headers)
