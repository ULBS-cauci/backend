import uuid
from fastapi import APIRouter, Depends
from app.api.dependencies import get_course_service
from app.services.course_service import CourseService
from app.schemas.course_schemas import CoursePublic

router = APIRouter()

HARDCODED_TEACHER_ID = uuid.UUID("123e4567-e89b-12d3-a456-426614174001")


@router.get("/", response_model=list[CoursePublic])
async def get_courses_by_teacher(
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.get_courses_by_teacher(HARDCODED_TEACHER_ID)


@router.get("/all", response_model=list[CoursePublic])
async def get_all_courses(
    course_service: CourseService = Depends(get_course_service),
):
    return await course_service.get_all_courses()
