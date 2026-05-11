import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service
from app.schemas.chat_schemas import AskRequest
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/ask")
async def ask(
    payload: AskRequest,
    service: ChatService = Depends(get_chat_service),
):

    async def event_stream():
        async for chunk in service.ask_stream(payload.query):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield f"data: {json.dumps('[DONE]')}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
