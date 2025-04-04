"""
API endpoints for managing file attachments.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid

from app.core.deps import get_db, get_current_user, get_optional_current_user
from app.models.user import User
from app.models.attachment import Attachment
from app.services.file_storage import save_file, validate_file, UPLOAD_DIR

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),  # "document" or "image"
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Upload a file and return attachment information.
    The attachment will be associated with a message when it's sent.
    """
    # Validate the file
    if not validate_file(file, file_type):
        raise HTTPException(status_code=400, detail="Invalid file type or size")
    
    # Save the file
    file_path = await save_file(file, file_type)
    
    # Get file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    
    # Create temporary attachment record (not associated with a message yet)
    attachment = Attachment(
        message_id=None,  # Will be set when the message is created
        file_name=file.filename,
        file_type=file.content_type,
        file_size=file_size,
        file_path=file_path
    )
    
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    
    return {
        "id": str(attachment.id),
        "file_name": attachment.file_name,
        "file_type": attachment.file_type,
        "file_size": attachment.file_size
    }

@router.get("/file/{attachment_id}")
async def serve_file(
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Serve the file for viewing or downloading.
    """
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    file_path = os.path.join(UPLOAD_DIR, attachment.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=attachment.file_name,
        media_type=attachment.file_type
    ) 