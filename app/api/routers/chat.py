from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_vector_db_client, get_embedding_client, get_llm_client
from app.services.chat_service import ChatService

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    collection_name: str = "university_library"

@router.post("/query")
async def ask_question(
    request: ChatRequest,
    vector_db = Depends(get_vector_db_client),
    embedding_client = Depends(get_embedding_client),
    llm_client = Depends(get_llm_client)  
):
    service = ChatService(vector_db, embedding_client, llm_client)
    
    try:
        answer = await service.answer_question(request.message, request.collection_name)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))