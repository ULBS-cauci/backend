import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.chat_service import ChatService
from app.api.dependencies import get_chat_service
from app.schemas.chat_schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/query")
async def ask_question(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    try:
        answer = await chat_service.answer_question(request.message, request.collection_name)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Internal error in ask_question: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while processing your request. Please try again later."
        )