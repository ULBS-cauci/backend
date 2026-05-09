from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import get_db_session, get_file_service
from app.schemas.vector_schemas import DocumentMetadata
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/upload")
async def upload_textbook(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Upload a PDF, vectorize it in Qdrant, and save metadata in Postgres.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        content = await file.read()
        
        collection = await file_service.process_and_index_pdf(content, file.filename)
        
        new_doc = DocumentMetadata(
            filename=file.filename,
            qdrant_collection=collection
        )
        db.add(new_doc)
        await db.commit() 
        await db.refresh(new_doc) 
        
        return {
            "status": "success",
            "message": f"The document {file.filename} has been indexed in {collection}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")