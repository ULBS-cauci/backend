import uuid
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.schemas.course_schemas import Course


class CourseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_courses_by_teacher(self, teacher_id: uuid.UUID) -> list[Course]:
        result = await self.db.exec(select(Course).where(Course.held_by == teacher_id))
        return result.all()

    async def get_all_courses(self) -> list[Course]:
        result = await self.db.exec(select(Course))
        return result.all()
