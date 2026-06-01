import io
import json
import uuid
from pathlib import Path
from typing import List
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
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

MAX_ATTACHMENT_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_ATTACHMENT_MIME_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


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
    return await service.get_conversation_messages_public(conversation_id=conversation_id)


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
    filename = file.filename or "unnamed"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in _ATTACHMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported file type '.{suffix}'. "
                f"Accepted: {', '.join(sorted(_ATTACHMENT_MIME_TYPES))}"
            ),
        )

    # Read up to the size limit + 1 so we can detect oversize uploads without buffering more.
    content = await file.read(MAX_ATTACHMENT_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )
    if len(content) > MAX_ATTACHMENT_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Uploaded file exceeds the {MAX_ATTACHMENT_UPLOAD_BYTES // (1024 * 1024)} MB limit."
            ),
        )

    attachment_id = uuid.uuid4()
    object_key = build_attachment_object_key(current_user.id, attachment_id, filename)

    await object_storage.upload_file(
        MINIO_ATTACHMENTS_BUCKET, object_key, content, _ATTACHMENT_MIME_TYPES[suffix]
    )

    try:
        attachment = Attachment(
            id=attachment_id,
            user_id=current_user.id,
            file_name=filename,
            object_storage_key=object_key,
        )
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
    except Exception:
        await object_storage.delete_file(MINIO_ATTACHMENTS_BUCKET, object_key)
        raise

    return AttachmentPublic.model_validate(attachment)


@router.get("/attachments/{attachment_id}")
async def download_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    object_storage: ObjectStorageInterface = Depends(get_object_storage_client),
    db: AsyncSession = Depends(get_db_session),
):
    attachment = await db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )
    if attachment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this attachment",
        )

    try:
        data = await object_storage.download_file(
            MINIO_ATTACHMENTS_BUCKET, attachment.object_storage_key
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file is missing from storage",
        )

    encoded_name = quote(attachment.file_name)
    headers = {
        "Content-Disposition": f'inline; filename="{encoded_name}"; filename*=UTF-8\'\'{encoded_name}'
    }
    suffix = Path(attachment.file_name).suffix.lstrip(".").lower()
    media_type = _ATTACHMENT_MIME_TYPES.get(suffix, "application/octet-stream")
    return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)


@router.post("/{conversation_id}/regenerate")
async def regenerate(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.get_conversation_for_user(
        conversation_id=conversation_id, user_id=current_user.id
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    async def event_stream():
        try:
            async for chunk in service.regenerate_stream(
                conversation_id=conversation_id, user_id=current_user.id
            ):
                yield f"data: {chunk.model_dump_json()}\n\n"
        except HTTPException as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': exc.detail})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/ask")
async def ask(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
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

    async def event_stream():
        try:
            async for event in service.ask_stream(
                query=payload.content,
                user_id=current_user.id,
                conversation_id=payload.conversation_id,
                attachment_ids=payload.attachment_ids,
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except HTTPException as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': exc.detail})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
