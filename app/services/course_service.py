import uuid
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.schemas.course_schemas import Course, CourseCreate, CourseUpdate
from app.schemas.knowledge_schemas import Material


class CourseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_courses_by_teacher(self, teacher_id: uuid.UUID) -> list[Course]:
        result = await self.db.exec(select(Course).where(Course.held_by == teacher_id))
        return result.all()

    async def get_all_courses(self) -> list[Course]:
        result = await self.db.exec(select(Course))
        return result.all()

    async def get_materials_by_course(self, course_id: uuid.UUID) -> list[Material]:
        result = await self.db.exec(select(Material).where(Material.course_id == course_id))
        return result.all()

    async def create_course(
        self, course_data: CourseCreate, teacher_id: uuid.UUID
    ) -> Course:
        course = Course(**course_data.model_dump(), held_by=teacher_id)
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def update_course(self, course_id: uuid.UUID, course_data: CourseUpdate) -> Course | None:
        result = await self.db.exec(select(Course).where(Course.id == course_id))
        course = result.first()
        if not course:
            return None
        for field, value in course_data.model_dump(exclude_unset=True).items():
            setattr(course, field, value)
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def delete_course(self, course_id: uuid.UUID) -> None:
        result = await self.db.exec(select(Course).where(Course.id == course_id))
        course = result.first()
        if course:
            await self.db.delete(course)
            await self.db.commit()
