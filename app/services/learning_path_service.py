import uuid
import logging
from typing import AsyncIterator, List, Optional

from sqlmodel import select, desc, asc
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("uvicorn.error")

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.llm import LLMInterface
from app.schemas.chat_schemas import StatusEvent, ErrorEvent
from app.schemas.knowledge_schemas import Material
from app.schemas.learning_path_schemas import (
    LearningPath,
    LearningPathModule,
    LearningPathDoneEvent,
)
from app.rag_engine.learning_path_prompt import (
    build_material_block,
    build_synthesis_messages,
    parse_learning_path,
)
from app.core.config import QDRANT_MATERIALS_COLLECTION

# Total character budget for the surveyed material text fed to the synthesis LLM call.
# Mirrors the spirit of ChatService.MAX_TOTAL_ATTACHMENT_CHARS to bound prompt size.
MAX_SURVEY_CHARS = 40_000
# How many chunks to pull across all the course's materials before sampling.
SURVEY_SCROLL_LIMIT = 600


class LearningPathService:
    def __init__(
        self,
        vector_db: VectorDBInterface,
        llm_client: LLMInterface,
        db_session: AsyncSession,
    ):
        self.vector_db = vector_db
        self.llm_client = llm_client
        self.db_session = db_session

    # ------------------------------------------------------------------ generate
    async def generate_stream(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> AsyncIterator[BaseModel]:
        """Survey all of a course's materials and synthesize a persisted learning path.

        Wrapped in SSE so the frontend gets progress; the path itself is a single JSON
        document persisted before the terminal LearningPathDoneEvent is emitted.
        """
        # Map object_storage_key -> Material so we can tag survey blocks and resolve refs.
        materials_stmt = select(Material).where(Material.course_id == course_id)
        materials_result = await self.db_session.exec(materials_stmt)
        materials = list(materials_result.all())
        key_to_material = {
            m.object_storage_key: m for m in materials if m.object_storage_key
        }
        valid_material_ids = {str(m.id) for m in materials}

        if not key_to_material:
            yield ErrorEvent(
                message="This course has no uploaded materials to build a learning path from."
            )
            return

        yield StatusEvent(message="Surveying the course materials...")
        chunks = await self.vector_db.scroll_by_course(
            QDRANT_MATERIALS_COLLECTION, str(course_id), limit=SURVEY_SCROLL_LIMIT
        )
        if not chunks:
            yield ErrorEvent(
                message="The course materials have not finished processing yet. Please try again shortly."
            )
            return

        # Group chunk texts by their source material (object_storage_key).
        grouped: dict[str, List[str]] = {}
        for result in chunks:
            source = result.chunk.metadata.get("source")
            if source in key_to_material:
                grouped.setdefault(source, []).append(result.chunk.text)

        if not grouped:
            yield ErrorEvent(
                message="Could not match the course materials to their content. Please re-upload them."
            )
            return

        # Every material gets a fair share of the budget so a large textbook can't
        # starve smaller lecture notes; strided sampling keeps coverage across each file.
        per_material_budget = max(1500, MAX_SURVEY_CHARS // len(grouped))
        material_blocks: List[str] = []
        for source, texts in grouped.items():
            material = key_to_material[source]
            body = self._sample_within_budget(texts, per_material_budget)
            material_blocks.append(
                build_material_block(material.id, material.file_name, body)
            )

        yield StatusEvent(message="Designing your learning path...")
        raw = await self.llm_client.generate(build_synthesis_messages(material_blocks))
        parsed = parse_learning_path(raw)
        if not parsed or not isinstance(parsed.get("modules"), list):
            logger.warning(f"Learning-path synthesis returned unparseable output: {raw[:500]}")
            yield ErrorEvent(
                message="Failed to generate a learning path. Please try again."
            )
            return

        modules = self._build_modules(parsed["modules"], valid_material_ids)
        if not modules:
            yield ErrorEvent(
                message="The generated learning path was empty. Please try again."
            )
            return

        path = LearningPath(
            user_id=user_id,
            course_id=course_id,
            title=(str(parsed.get("title") or "Learning Path"))[:255],
            modules=[m.model_dump(mode="json") for m in modules],
            progress={m.id: False for m in modules},
        )
        self.db_session.add(path)
        await self.db_session.commit()
        await self.db_session.refresh(path)

        yield LearningPathDoneEvent(learning_path_id=str(path.id))

    @staticmethod
    def _sample_within_budget(texts: List[str], budget: int) -> str:
        """Return material text within `budget` chars, strided for whole-file coverage."""
        if not texts:
            return ""
        total_len = sum(len(t) for t in texts)
        if total_len <= budget:
            return "\n".join(texts)
        avg = max(1, total_len // len(texts))
        fit = max(1, budget // avg)
        step = max(1, len(texts) // fit)
        selected: List[str] = []
        used = 0
        for i in range(0, len(texts), step):
            t = texts[i]
            if used + len(t) > budget:
                break
            selected.append(t)
            used += len(t)
        return "\n".join(selected)

    @staticmethod
    def _build_modules(
        raw_modules: list, valid_material_ids: set[str]
    ) -> List[LearningPathModule]:
        """Validate raw LLM module dicts; drop hallucinated material ids and bad rows."""
        modules: List[LearningPathModule] = []
        for index, raw in enumerate(raw_modules):
            if not isinstance(raw, dict):
                continue
            # Keep only material ids the LLM was actually given (guards hallucination).
            raw["material_ids"] = [
                mid for mid in (raw.get("material_ids") or [])
                if str(mid) in valid_material_ids
            ]
            # Guarantee a stable, unique id even if the model omitted/duplicated one.
            raw["id"] = str(raw.get("id") or f"m{index + 1}")
            try:
                modules.append(LearningPathModule.model_validate(raw))
            except ValidationError:
                logger.warning(f"Skipping invalid learning-path module: {raw}")
        # De-duplicate ids (the model occasionally repeats them).
        seen: set[str] = set()
        deduped: List[LearningPathModule] = []
        for i, m in enumerate(modules):
            if m.id in seen:
                m.id = f"m{i + 1}"
            seen.add(m.id)
            deduped.append(m)
        return deduped

    # ------------------------------------------------------------------ read
    async def list_paths(self, user_id: uuid.UUID) -> List[LearningPath]:
        stmt = (
            select(LearningPath)
            .where(LearningPath.user_id == user_id)
            .order_by(desc(LearningPath.updated_at))
        )
        result = await self.db_session.exec(stmt)
        return list(result.all())

    async def get_path(
        self, path_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[LearningPath]:
        path = await self.db_session.get(LearningPath, path_id)
        if path and path.user_id == user_id:
            return path
        return None

    # ------------------------------------------------------------------ mutate
    async def update_progress(
        self,
        path_id: uuid.UUID,
        user_id: uuid.UUID,
        module_id: str,
        completed: bool,
    ) -> LearningPath:
        path = await self.get_path(path_id, user_id)
        if not path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found"
            )
        if module_id not in path.progress:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown module id for this learning path.",
            )
        # Reassign (not in-place mutate) so SQLAlchemy marks the JSON column dirty.
        path.progress = {**path.progress, module_id: completed}
        self.db_session.add(path)
        await self.db_session.commit()
        await self.db_session.refresh(path)
        return path

    async def delete_path(self, path_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        path = await self.get_path(path_id, user_id)
        if not path:
            return False
        await self.db_session.delete(path)
        await self.db_session.commit()
        return True
