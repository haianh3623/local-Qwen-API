from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging

# Import các module (Giữ nguyên như cũ)
from app.services.llm_service import llm_service
from app.core.task_runner import task_runner
# LƯU Ý: Bạn cần đảm bảo hàm process_upload_files trong common.py 
# đã được sửa để có thể đọc nội dung file từ đường dẫn (path string).
from app.core.common import process_upload_files, validate_submission_content 

logger = logging.getLogger("grading_endpoint")

router = APIRouter()

# 1. Định nghĩa Data Model (Dùng cho JSON Body)
class GradingRequest(BaseModel):
    # --- Meta ---
    callback_url: str
    request_id: Optional[str] = None
    
    # --- Inputs ---
    course_id: Optional[str] = None
    assignment_content: str
    # Thay đổi: Nhận List[str] là danh sách đường dẫn file thay vì UploadFile
    assignment_attachments: Optional[List[str]] = [] 
    
    student_submission_text: Optional[str] = None
    # Thay đổi: Nhận List[str]
    student_submission_files: Optional[List[str]] = []
    
    reference_answer_text: Optional[str] = None
    # Thay đổi: Nhận str (đường dẫn đơn)
    reference_answer_file: Optional[str] = None
    
    grading_criteria: Optional[str] = None
    teacher_instruction: Optional[str] = None
    max_score: float = 10.0

@router.post("/async-batch", status_code=202)
async def grade_submission_async(
    payload: GradingRequest, # Nhận toàn bộ dữ liệu dưới dạng JSON
    background_tasks: BackgroundTasks
):
    # logger.info("Payload: %s", payload)

    # 1. Sinh ID nếu thiếu (Truy cập qua payload.request_id)
    req_id = payload.request_id
    if not req_id:
        req_id = str(uuid.uuid4())

    # 2. Xử lý file 
    # Lưu ý: Hàm này bây giờ sẽ nhận vào List[str] (đường dẫn). 
    # Logic bên trong cần mở file tại đường dẫn đó để đọc nội dung.
    q_files = await process_upload_files(payload.assignment_attachments)
    logger.info(f"Processed {payload.assignment_attachments} question attachment files.")
    
    s_files = await process_upload_files(payload.student_submission_files)
    
    # Xử lý reference_file (vì đây là str đơn, có thể cần đưa vào list để xử lý chung hoặc xử lý riêng)
    r_files_input = [payload.reference_answer_file] if payload.reference_answer_file else []
    r_files = await process_upload_files(r_files_input)

    # 3. Validate
    validate_submission_content(payload.student_submission_text, s_files)

    # 4. Gom dữ liệu
    grading_data = {
        "course_id": payload.course_id,
        "question": payload.assignment_content + q_files,
        "submission": (payload.student_submission_text or "") + s_files,
        "reference": (payload.reference_answer_text or "") + r_files,
        "rubric": payload.grading_criteria,
        "teacher_instruction": payload.teacher_instruction,
        "max_score": payload.max_score
    }
    logger.info(f"📝 [Request Prepared] ID: {req_id}, Preparing to queue grading task.")
    logger.info(f"Grading Data: {grading_data}")

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