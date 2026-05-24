import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import MATERIALS_BUCKET
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.knowledge_schemas import Material, MaterialPublic, IngestionStatus

_SUPPORTED: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
}


def build_object_key(course_id: uuid.UUID, filename: str) -> str:
    return f"{course_id}/{uuid.uuid4()}_{filename}"


class FileService:
    def __init__(
        self,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
        arq_pool: object,
    ) -> None:
        self.object_storage = object_storage
        self.db = db
        self.arq_pool = arq_pool

    async def upload_and_index(
        self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> MaterialPublic:
        filename: str = file.filename or "unnamed_document"
        suffix: str = Path(filename).suffix.lower()

        if suffix not in _SUPPORTED:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Accepted: {', '.join(sorted(_SUPPORTED))}"
            )

        content_type: str = _SUPPORTED[suffix]
        file_type: str = suffix.lstrip(".")  # e.g. "pdf", "docx", "pptx"

        content: bytes = await file.read()
        object_key: str = build_object_key(course_id, filename)

        await self.object_storage.upload_file(
            MATERIALS_BUCKET, object_key, content, content_type
        )

        material = Material(
            course_id=course_id,
            file_name=filename,
            file_type=file_type,
            uploaded_by=user_id,
            object_storage_key=object_key,
            ingestion_status=IngestionStatus.PENDING,
        )
        self.db.add(material)
        await self.db.commit()
        await self.db.refresh(material)

        await self.arq_pool.enqueue_job(
            "process_document_task",
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
        output: list[MaterialPublic] = []
        for material in materials:
            preview_url: str | None = None
            if material.object_storage_key:
                preview_url = await self.object_storage.generate_presigned_url(
                    MATERIALS_BUCKET, material.object_storage_key
                )
            public = MaterialPublic.model_validate(material)
            public.preview_url = preview_url
            output.append(public)
        return output
