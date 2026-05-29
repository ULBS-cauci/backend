import uuid
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.schemas.course_schemas import Course, CourseCreate, CourseUpdate, CourseDisplay
from app.schemas.knowledge_schemas import Material
from app.schemas.user_schemas import User
from app.core.config import MINIO_MATERIALS_BUCKET


class CourseService:
    def __init__(
        self,
        db: AsyncSession,
        object_storage: ObjectStorageInterface,
        vector_db: VectorDBInterface,
    ):
        self.db = db
        self.object_storage = object_storage
        self.vector_db = vector_db

    async def get_courses_by_teacher(
        self, teacher_id: uuid.UUID
    ) -> list[CourseDisplay]:
        stmt = (
            select(Course, User)
            .outerjoin(User, Course.held_by == User.id)
            .where(Course.held_by == teacher_id)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        output = []
        for course, user in rows:
            display = CourseDisplay.model_validate(course)
            if user:
                display.teacher_name = f"{user.first_name} {user.last_name}"
            output.append(display)
        return output

    async def get_all_courses(self) -> list[CourseDisplay]:
        stmt = select(Course, User).outerjoin(User, Course.held_by == User.id)
        result = await self.db.execute(stmt)
        rows = result.all()
        output = []
        for course, user in rows:
            display = CourseDisplay.model_validate(course)
            if user:
                display.teacher_name = f"{user.first_name} {user.last_name}"
            output.append(display)
        return output

    async def create_course(
        self, course_data: CourseCreate, teacher_id: uuid.UUID
    ) -> Course:
        course = Course(**course_data.model_dump(), held_by=teacher_id)
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def update_course(
        self, course_id: uuid.UUID, course_data: CourseUpdate
    ) -> CourseDisplay | None:
        result = await self.db.execute(select(Course).where(Course.id == course_id))
        course = result.scalar_one_or_none()
        if not course:
            return None
        for field, value in course_data.model_dump(exclude_unset=True).items():
            setattr(course, field, value)
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        stmt = (
            select(Course, User)
            .outerjoin(User, Course.held_by == User.id)
            .where(Course.id == course_id)
        )
        result = await self.db.execute(stmt)
        course, user = result.one()
        display = CourseDisplay.model_validate(course)
        if user:
            display.teacher_name = f"{user.first_name} {user.last_name}"
        return display

    async def delete_course(self, course_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(Material).where(Material.course_id == course_id)
        )
        materials = result.scalars().all()
        for material in materials:
            if material.object_storage_key:
                await self.object_storage.delete_file(
                    MINIO_MATERIALS_BUCKET, material.object_storage_key
                )
            if material.vector_namespace:
                if material.object_storage_key:
                    await self.vector_db.delete_chunks_by_source(
                        material.vector_namespace, material.object_storage_key
                    )
                elif material.file_name:
                    await self.vector_db.delete_chunks_by_source(
                        material.vector_namespace, material.file_name
                    )
            await self.db.delete(material)
        await self.db.flush()
        course = await self.db.get(Course, course_id)
        if not course:
            return False
        await self.db.delete(course)
        await self.db.commit()
        return True
