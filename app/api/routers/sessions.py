import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import (
    get_chat_service,
    get_current_user,
    get_db_session,
    get_object_storage_client,
)
from app.core.config import MINIO_ATTACHMENTS_BUCKET
from app.core.helpers import build_attachment_object_key
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.chat_schemas import (
    Attachment,
    AttachmentPublic,
    ConversationPublic,
    MessageCreate,
    MessagePublic,
)
from app.schemas.user_schemas import User
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/", response_model=List[ConversationPublic])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return await service.get_user_conversations(user_id=current_user.id)


@router.post("/", response_model=ConversationPublic)
async def create_conversation(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    return await service.create_conversation(user_id=current_user.id)


@router.get("/{conversation_id}/messages", response_model=List[MessagePublic])
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.get_conversation_for_user(
        conversation_id=conversation_id, user_id=current_user.id
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return await service.get_conversation_messages(conversation_id=conversation_id)


@router.post(
    "/attachments/upload",
    response_model=AttachmentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    object_storage: ObjectStorageInterface = Depends(get_object_storage_client),
    db: AsyncSession = Depends(get_db_session),
):
    filename = file.filename or "unnamed.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted for chat attachments.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    attachment_id = uuid.uuid4()
    object_key = build_attachment_object_key(current_user.id, attachment_id, filename)
    await object_storage.upload_file(
        MINIO_ATTACHMENTS_BUCKET, object_key, content, "application/pdf"
    )

    attachment = Attachment(
        id=attachment_id,
        user_id=current_user.id,
        file_name=filename,
        object_storage_key=object_key,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return AttachmentPublic.model_validate(attachment)


@router.post("/ask")
async def ask(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_db_session),
):
    if payload.conversation_id:
        conversation = await service.get_conversation_for_user(
            conversation_id=payload.conversation_id, user_id=current_user.id
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized",
            )

    if payload.attachment_ids:
        stmt = (
            select(Attachment)
            .where(Attachment.id.in_(payload.attachment_ids))
            .where(Attachment.user_id == current_user.id)
            .where(Attachment.message_id == None)  # noqa: E711
        )
        result = await db.exec(stmt)
        found = list(result.all())
        if len(found) != len(payload.attachment_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="One or more attachments not found, not owned by you, or already used.",
            )

    async def event_stream():
        async for chunk in service.ask_stream(
            query=payload.content,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            attachment_ids=payload.attachment_ids,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
