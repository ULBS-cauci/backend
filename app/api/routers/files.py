import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.api.dependencies import get_file_service
from app.services.file_service import FileService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/courses/{course_id}/upload")
async def upload_file(
    course_id: uuid.UUID,
    file: UploadFile = File(...),
    file_service: FileService = Depends(get_file_service),
    user_id: uuid.UUID = None  # TODO: Extract from JWT token in security.py
):
    try:
        # TODO: Get user_id from authenticated token instead of parameter
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        collection_name = await file_service.upload_and_index(
            file,
            course_id=course_id,
            user_id=user_id
        )
        
        return {
            "status": "success",
            "message": f"Document {file.filename} uploaded and indexed.",
            "collection": collection_name     
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")