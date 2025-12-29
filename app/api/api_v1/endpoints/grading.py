from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging

# Import các module
from app.services.llm_service import llm_service
from app.core.task_runner import task_runner
from app.core.common import process_upload_files, validate_submission_content 
# Đảm bảo đã import service bảo mật
from app.services.prompt_security_service import prompt_security_service

logger = logging.getLogger("grading_endpoint")

router = APIRouter()

# 1. Định nghĩa Data Model
class GradingRequest(BaseModel):
    # --- Meta ---
    callback_url: str
    request_id: Optional[str] = None
    
    # --- Inputs ---
    course_id: Optional[str] = None
    assignment_content: str
    assignment_attachments: Optional[List[str]] = [] 
    
    student_submission_text: Optional[str] = None
    student_submission_files: Optional[List[str]] = []
    
    reference_answer_text: Optional[str] = None
    reference_answer_file: Optional[str] = None
    
    grading_criteria: Optional[str] = None
    teacher_instruction: Optional[str] = None
    max_score: float = 10.0

@router.post("/async-batch", status_code=202)
async def grade_submission_async(
    payload: GradingRequest, 
    background_tasks: BackgroundTasks
):
    # 1. Sinh ID nếu thiếu
    req_id = payload.request_id or str(uuid.uuid4())
    logger.info(f"🚀 [Received Request] ID: {req_id}")

    # =========================================================================
    # [NEW] BƯỚC BẢO MẬT: KIỂM TRA SUBMISSION TEXT TRƯỚC
    # =========================================================================
    
    raw_sub_text = payload.student_submission_text or ""
    
    # Hàm này sẽ trả về văn bản sạch hoặc thông báo lỗi "ERROR: [SECURITY_VIOLATION]..."
    sanitized_sub_text = prompt_security_service.validate_and_sanitize(raw_sub_text)
    
    # Kiểm tra xem có bị thay thế bằng thông báo lỗi không
    is_text_violation = "ERROR: [SECURITY_VIOLATION]" in sanitized_sub_text
    
    s_files_content = ""

    if is_text_violation:
        logger.warning(f"⚠️ [Security Block] Request {req_id}: Text submission contains prompt injection. Skipping file processing.")
        # NẾU GIAN LẬN:
        # 1. Nội dung bài làm chính là thông báo lỗi
        # 2. Bỏ qua bước đọc file (s_files_content rỗng)
        s_files_content = "" 
    else:
        # NẾU AN TOÀN:
        # Mới tiến hành đọc file (CPU Bound)
        # Lưu ý: Trong process_upload_files cần gọi FileParserService (đã tích hợp bảo mật ở bước trước)
        # để đảm bảo file cũng được kiểm tra.
        logger.info(f"Request {req_id}: Text clean. Processing attachment files...")
        s_files_content = await process_upload_files(payload.student_submission_files)

    # =========================================================================

    # 2. Xử lý các file đề bài và đáp án (Vẫn xử lý bình thường)
    q_files = await process_upload_files(payload.assignment_attachments)
    
    r_files_input = [payload.reference_answer_file] if payload.reference_answer_file else []
    r_files = await process_upload_files(r_files_input)

    # 3. Validate (Kiểm tra xem có nội dung gì để chấm không)
    # Lưu ý: sanitized_sub_text lúc này có thể là nội dung bài làm hoặc thông báo lỗi
    validate_submission_content(sanitized_sub_text, s_files_content)

    # 4. Gom dữ liệu
    grading_data = {
        "course_id": payload.course_id,
        "question": payload.assignment_content + q_files,
        # Kết hợp văn bản đã vệ sinh + nội dung file (nếu có)
        "submission": sanitized_sub_text + s_files_content, 
        "reference": (payload.reference_answer_text or "") + r_files,
        "rubric": payload.grading_criteria,
        "teacher_instruction": payload.teacher_instruction,
        "max_score": payload.max_score
    }

    # 5. Đẩy vào Background Task
    background_tasks.add_task(
        task_runner.run_task_and_callback,
        processing_function=llm_service.grade_submission,
        input_data=grading_data,
        callback_url=payload.callback_url,
        request_id=req_id
    )

    return {
        "status": "queued",
        "message": "Đã tiếp nhận vào hàng đợi.",
        "request_id": req_id
    }