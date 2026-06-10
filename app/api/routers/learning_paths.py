import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user, get_learning_path_service
from app.schemas.learning_path_schemas import (
    LearningPathGenerateRequest,
    LearningPathProgressUpdate,
    LearningPathPublic,
)
from app.schemas.user_schemas import User
from app.services.learning_path_service import LearningPathService

router = APIRouter()


@router.post("/generate")
async def generate(
    payload: LearningPathGenerateRequest,
    current_user: User = Depends(get_current_user),
    service: LearningPathService = Depends(get_learning_path_service),
):
    async def event_stream():
        try:
            async for event in service.generate_stream(
                user_id=current_user.id, course_id=payload.course_id
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except HTTPException as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': exc.detail})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/", response_model=List[LearningPathPublic])
async def list_paths(
    current_user: User = Depends(get_current_user),
    service: LearningPathService = Depends(get_learning_path_service),
):
    paths = await service.list_paths(user_id=current_user.id)
    return [LearningPathPublic.model_validate(p) for p in paths]


@router.get("/{path_id}", response_model=LearningPathPublic)
async def get_path(
    path_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: LearningPathService = Depends(get_learning_path_service),
):
    path = await service.get_path(path_id, current_user.id)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found"
        )
    return LearningPathPublic.model_validate(path)


@router.patch("/{path_id}/progress", response_model=LearningPathPublic)
async def update_progress(
    path_id: uuid.UUID,
    payload: LearningPathProgressUpdate,
    current_user: User = Depends(get_current_user),
    service: LearningPathService = Depends(get_learning_path_service),
):
    path = await service.update_progress(
        path_id, current_user.id, payload.module_id, payload.completed
    )
    return LearningPathPublic.model_validate(path)


@router.delete("/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_path(
    path_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: LearningPathService = Depends(get_learning_path_service),
):
    deleted = await service.delete_path(path_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found"
        )
