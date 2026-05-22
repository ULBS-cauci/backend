import uuid
from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import MATERIALS_BUCKET
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.knowledge_schemas import Material, MaterialPublic, IngestionStatus


def build_object_key(course_id: uuid.UUID, filename: str) -> str:
    return f"{course_id}/{uuid.uuid4()}_{filename}"


class FileService:
    def __init__(
        self,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
        arq_pool,
    ):
        self.object_storage = object_storage
        self.db = db
        self.arq_pool = arq_pool

    async def upload_and_index(
        self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> MaterialPublic:
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()
        object_key = build_object_key(course_id, filename)

        await self.object_storage.upload_file(
            MATERIALS_BUCKET, object_key, content, "application/pdf"
        )

        material = Material(
            course_id=course_id,
            file_name=filename,
            file_type="pdf",
            uploaded_by=user_id,
            object_storage_key=object_key,
            ingestion_status=IngestionStatus.PENDING,
        )
        self.db.add(material)
        await self.db.commit()
        await self.db.refresh(material)

        await self.arq_pool.enqueue_job(
            "process_pdf_task",
            material_id=str(material.id),
            object_storage_key=object_key,
            filename=filename,
        )

        return MaterialPublic.model_validate(material)

    async def get_materials_by_course(
        self, course_id: uuid.UUID
    ) -> list[MaterialPublic]:
        result = await self.db.exec(
            select(Material).where(Material.course_id == course_id)
        )
        materials = result.all()
        output = []
        for material in materials:
            preview_url = None
            if material.object_storage_key:
                preview_url = await self.object_storage.generate_presigned_url(
                    MATERIALS_BUCKET, material.object_storage_key
                )
            public = MaterialPublic.model_validate(material)
            public.preview_url = preview_url
            output.append(public)
        return output
