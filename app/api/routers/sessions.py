import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_llm_client
from app.data_access.interfaces.llm import LLMInterface
from app.schemas.chat_schemas import AskRequest
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/ask")
async def ask(
    payload: AskRequest,
    llm: LLMInterface = Depends(get_llm_client),
):
    service = ChatService(llm=llm)

    async def event_stream():
        async for chunk in service.ask_stream(payload.query):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
