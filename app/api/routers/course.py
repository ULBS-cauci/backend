import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_course_service, get_file_service
from app.services.course_service import CourseService
from app.services.file_service import FileService
from app.schemas.course_schemas import CourseCreate, CourseDisplay, CourseUpdate
from app.schemas.knowledge_schemas import MaterialPublic

router = APIRouter()

HARDCODED_TEACHER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


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


@router.get("/{course_id}/materials", response_model=list[MaterialPublic])
async def get_course_materials(
    course_id: uuid.UUID,
    file_service: FileService = Depends(get_file_service),
):
    return await file_service.get_materials_by_course(course_id)


@router.post("/", response_model=CourseDisplay, status_code=status.HTTP_201_CREATED)
async def create_course(
    course_data: CourseCreate,
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.create_course(course_data, HARDCODED_TEACHER_ID)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    course_service: CourseService = Depends(get_course_service),
):
    if not await course_service.delete_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")
