"""
Service module for file storage operations.
This module handles file uploads, validation, and storage.
"""

import os
import uuid
import base64
from fastapi import UploadFile
from app.core.config import settings

# Define constants for file storage
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB

ALLOWED_DOCUMENT_TYPES = [
    "application/pdf", 
    "application/msword", 
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
]
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_AUDIO_TYPES = ["audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/flac", "audio/ogg", "audio/webm"]

# Map MIME types to extensions for conversion
MIME_TO_EXT = {
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'audio/ogg': 'ogg',
    'audio/webm': 'webm',
    'audio/mp4': 'm4a',
    'audio/x-m4a': 'm4a'
}

def get_extension_from_content_type(content_type: str) -> str:
    """Get file extension from content type"""
    return MIME_TO_EXT.get(content_type, 'bin')

async def save_file(file: UploadFile, file_type: str) -> str:
    """
    Save uploaded file and return the path.
    
    Args:
        file: The uploaded file
        file_type: Either "document", "image", or "audio"
        
    Returns:
        The relative file path for storage in the database
    """
    # Create directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    # Different directories for different file types
    if file_type == "document":
        subdir = "documents"
    elif file_type == "audio":
        subdir = "audio"
    else:  # image
        subdir = "images"
    
    os.makedirs(os.path.join(UPLOAD_DIR, subdir), exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, subdir, unique_filename)
    
    # Write file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Return relative path for database storage
    return os.path.join(subdir, unique_filename)

def validate_file(file: UploadFile, file_type: str) -> bool:
    """
    Validate file size and type.
    
    Args:
        file: The uploaded file
        file_type: Either "document", "image", or "audio"
        
    Returns:
        True if valid, False otherwise
    """
    if file_type == "document":
        if file.content_type not in ALLOWED_DOCUMENT_TYPES:
            return False
        # Check file size (we can't rely on content_length)
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_DOCUMENT_SIZE:
            return False
    elif file_type == "image":
        # More flexible approach: accept any content type that starts with "image/"
        if not file.content_type.startswith("image/"):
            return False
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_IMAGE_SIZE:
            return False
    elif file_type == "audio":
        # Accept specific audio MIME types
        if file.content_type not in ALLOWED_AUDIO_TYPES:
            return False
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_AUDIO_SIZE:
            return False
    
    return True

def detect_file_type(file: UploadFile) -> str:
    """
    Detect the file type based on content type.
    
    Args:
        file: The uploaded file
        
    Returns:
        String identifier for the file type ("document", "image", "audio", or None)
    """
    content_type = file.content_type
    
    if content_type in ALLOWED_DOCUMENT_TYPES or content_type == "application/octet-stream":
        # Check extension for application/octet-stream
        if content_type == "application/octet-stream":
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ['.pdf', '.doc', '.docx', '.txt']:
                return "document"
        else:
            return "document"
    
    if content_type.startswith("image/"):
        return "image"
        
    if content_type in ALLOWED_AUDIO_TYPES:
        return "audio"
    
    return None

def encode_file_to_base64(file_path: str) -> str:
    """
    Encode a file to base64 for inclusion in LLM messages.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Base64 encoded string
    """
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode('utf-8')

async def extract_text_from_document(file_path: str) -> str:
    """
    Extract text from documents - for non-image files to be processed by the LLM.
    This is mainly for binary document formats that need text extraction.
    
    Args:
        file_path: Path to the document
        
    Returns:
        Extracted text
    """
    # For simple implementation, we'll just extract text from PDFs
    # We'll need external libraries for more complex formats
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext == '.pdf':
            # Use PyPDF2 if available
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n\n"
                    return text
            except ImportError:
                return "[PDF text extraction requires PyPDF2 library]"
                
        elif file_ext in ['.docx', '.doc']:
            # Use python-docx if available
            try:
                import docx
                doc = docx.Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                return "[DOCX text extraction requires python-docx library]"
                
        elif file_ext in ['.txt', '.md', '.csv']:
            # For text-based formats
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            return f"[Text extraction not supported for this file type: {file_ext}]"
                
    except Exception as e:
        print(f"Error extracting text: {e}")
        return f"[Error extracting text from document]" 