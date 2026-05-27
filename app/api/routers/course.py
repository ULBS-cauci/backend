import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_course_service, get_current_user, get_file_service
from app.schemas.course_schemas import CourseCreate, CourseDisplay, CourseUpdate
from app.schemas.knowledge_schemas import MaterialPublic
from app.schemas.user_schemas import User
from app.services.course_service import CourseService
from app.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter()

HARDCODED_TEACHER_ID = uuid.UUID("123e4567-e89b-12d3-a456-426614174001")


@router.get("/", response_model=list[CourseDisplay])
async def get_courses_by_teacher(
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.get_courses_by_teacher(HARDCODED_TEACHER_ID)


@router.get("/all", response_model=list[CourseDisplay])
async def get_all_courses(
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.get_all_courses()


@router.get("/{course_id}/materials", response_model=list[MaterialPublic])
async def get_course_materials(
    course_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
):
    return await file_service.get_materials_by_course(course_id)


@router.post("/{course_id}/materials", response_model=MaterialPublic, status_code=status.HTTP_201_CREATED)
async def upload_course_material(
    course_id: uuid.UUID,
    file: UploadFile = File(...),
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
        logger.error("Error during material upload: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{course_id}/materials/{material_id}/preview")
async def preview_course_material(
    course_id: uuid.UUID,
    material_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
) -> StreamingResponse:
    result = await file_service.get_material_stream(course_id, material_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Material not found")
    filename, stream = result
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/", response_model=CourseDisplay, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_data: CourseCreate,
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.create_course(course_data, HARDCODED_TEACHER_ID)


@router.get("/{course_id}", response_model=CourseDisplay)
async def get_course(
    course_id: uuid.UUID,
    course_service: CourseService = Depends(get_course_service),
):
    result = await course_service.get_course_by_id(course_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return result


@router.patch("/{course_id}", response_model=CourseDisplay)
async def update_course(
    course_id: uuid.UUID,
    course_data: CourseUpdate,
    course_service: CourseService = Depends(get_course_service),
):
    result = await course_service.update_course(course_id, course_data)
    if result is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return result


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    course_service: CourseService = Depends(get_course_service),
):
    if not await course_service.delete_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
