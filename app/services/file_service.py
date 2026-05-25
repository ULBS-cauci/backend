import logging
import uuid

from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from arq.connections import ArqRedis

from app.core.config import MATERIALS_BUCKET, QDRANT_MATERIALS_COLLECTION
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.knowledge_schemas import Material, MaterialPublic, IngestionStatus

logger = logging.getLogger(__name__)


def build_object_key(course_id: uuid.UUID, filename: str) -> str:
    return f"{course_id}/{uuid.uuid4()}_{filename}"


class FileService:
    def __init__(
        self,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
        arq_pool: ArqRedis,
    ) -> None:
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

        uploaded = False
        material_committed = False
        material: Material | None = None
        try:
            await self.object_storage.upload_file(
                MATERIALS_BUCKET, object_key, content, "application/pdf"
            )
            uploaded = True

            material = Material(
                course_id=course_id,
                file_name=filename,
                file_type="pdf",
                uploaded_by=user_id,
                object_storage_key=object_key,
                ingestion_status=IngestionStatus.PENDING,
                vector_namespace=QDRANT_MATERIALS_COLLECTION,
            )
            self.db.add(material)
            await self.db.commit()
            await self.db.refresh(material)
            material_committed = True

            await self.arq_pool.enqueue_job(
                "process_pdf_task",
                material_id=str(material.id),
                object_storage_key=object_key,
                filename=filename,
            )

            return MaterialPublic.model_validate(material)

        except Exception:
            if material_committed and material is not None:
                try:
                    await self.db.delete(material)
                    await self.db.commit()
                except Exception as db_err:
                    logger.warning(
                        f"Failed to clean up orphaned material record '{material.id}': {db_err}"
                    )
            if uploaded:
                try:
                    await self.object_storage.delete_file(MATERIALS_BUCKET, object_key)
                except Exception as cleanup_err:
                    logger.warning(
                        f"Failed to clean up orphaned object '{object_key}': {cleanup_err}"
                    )
            raise

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
