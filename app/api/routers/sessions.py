import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service, get_current_user
from app.schemas.chat_schemas import MessageCreate, ConversationPublic, MessagePublic
from app.schemas.user_schemas import User
from app.services.chat_service import ChatService

router = APIRouter()

@router.get("/", response_model=List[ConversationPublic])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversations = await service.get_user_conversations(user_id=current_user.id)
    return conversations

@router.post("/", response_model=ConversationPublic)
async def create_conversation(
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.create_conversation(user_id=current_user.id)
    return conversation

@router.get("/{conversation_id}/messages", response_model=List[MessagePublic])
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    conversation = await service.get_conversation_for_user(conversation_id=conversation_id, user_id=current_user.id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    
    messages = await service.get_conversation_messages(conversation_id=conversation_id)
    return messages

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
        async for chunk in service.regenerate_stream(
            conversation_id=conversation_id,
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/ask")
async def ask(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    if payload.conversation_id:
        conversation = await service.get_conversation_for_user(conversation_id=payload.conversation_id, user_id=current_user.id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    async def event_stream():
        async for chunk in service.ask_stream(query=payload.content, user_id=current_user.id, conversation_id=payload.conversation_id):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
