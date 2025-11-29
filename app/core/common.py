import uuid
from typing import Union, List, Optional
from fastapi import UploadFile, HTTPException
from app.services.file_parser import file_parser

def generate_request_id(request_id: Optional[str] = None) -> str:
    if request_id and request_id.strip():
        return request_id
    return str(uuid.uuid4())

async def process_upload_files(file_input: Union[List[UploadFile], List[str], UploadFile, None]) -> str:
    combined_text = ""
    if not file_input:
        return ""

    files_to_process = []
    if isinstance(file_input, list):
        files_to_process = file_input
    else:
        files_to_process = [file_input]

    for item in files_to_process:
        if isinstance(item, UploadFile) and item.filename:
            combined_text += await file_parser.parse_file_to_text(item)
            
    return combined_text

def validate_submission_content(text_content: str, file_content_parsed: str):
    has_text = text_content and text_content.strip()
    has_file = file_content_parsed and file_content_parsed.strip()
    
    if not has_text and not has_file:
        raise HTTPException(400, "Yêu cầu không hợp lệ: Thiếu nội dung.")