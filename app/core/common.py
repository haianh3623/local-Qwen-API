import uuid
import os
from typing import Union, List, Optional
from fastapi import HTTPException
from app.services.file_parser import file_parser

import logging

logger = logging.getLogger("common_utils")

def generate_request_id(request_id: Optional[str] = None) -> str:
    if request_id and request_id.strip():
        return request_id
    return str(uuid.uuid4())

async def process_upload_files(
    file_input: Union[List[str], str, None]
) -> str:
    combined_text = ""
    if not file_input:
        return ""

    logger.info(f"Processing file input: {file_input}")

    # Chuẩn hóa đầu vào thành list
    files_to_process = file_input if isinstance(file_input, list) else [file_input]

    for file_path in files_to_process:
        try:
            # Bỏ qua nếu không phải chuỗi
            if not isinstance(file_path, str):
                continue

            clean_path = file_path.strip()
            
            # Kiểm tra đường dẫn có tồn tại không
            if clean_path and os.path.exists(clean_path):
                content = await file_parser.parse_local_file(clean_path)
                filename = os.path.basename(clean_path)
                combined_text += f"\n--- File: {filename} ---\n{content}\n"
            else:
                print(f"Warning: File not found at path: {clean_path}")

        except Exception as e:
            print(f"Error processing file path '{file_path}': {e}")
            continue

    return combined_text

def validate_submission_content(text_content: str, file_content_parsed: str):
    has_text = text_content and text_content.strip()
    has_file = file_content_parsed and file_content_parsed.strip()
    
    if not has_text and not has_file:
        raise HTTPException(400, detail="Yêu cầu không hợp lệ: Thiếu nội dung.")