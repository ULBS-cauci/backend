import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.dependencies import get_db_session, get_file_service
from app.schemas.vector_schemas import DocumentMetadata
from app.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload")
async def upload_textbook(
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Upload a PDF, vectorize it in Qdrant, and save metadata in Postgres.
    """
    try:
        collection = await file_service.upload_and_index(file, db)
        
        return {
            "status": "success",
            "message": f"The document {file.filename} has been indexed in {collection}."
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred while processing the file. Please try again."
        )