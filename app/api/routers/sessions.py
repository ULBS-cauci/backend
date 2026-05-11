import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service, get_current_user
from app.schemas.chat_schemas import MessageCreate, ChatSessionPublic, MessagePublic
from app.schemas.user_schemas import User, UserPublic
from app.services.chat_service import ChatService

router = APIRouter()

@router.get("/", response_model=List[ChatSessionPublic])
async def list_sessions(
    current_user: UserPublic = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    sessions = await service.get_user_sessions(user_id=current_user.id)
    return sessions

@router.get("/{conversation_id}/messages", response_model=List[MessagePublic])
async def list_session_messages(
    conversation_id: uuid.UUID,
    current_user: UserPublic = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    sessions = await service.get_user_sessions(user_id=current_user.id)
    if not any(session.id == conversation_id for session in sessions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this conversation")
    
    messages = await service.get_session_messages(conversation_id=conversation_id)
    return messages

@router.post("/ask")
async def ask(
    payload: MessageCreate,
    current_user: UserPublic = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    async def event_stream():
        async for chunk in service.ask_stream(query=payload.content, user_id=current_user.id, conversation_id=payload.conversation_id):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
